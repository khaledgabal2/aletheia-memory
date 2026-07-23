"""Candidate extraction interfaces and deterministic/governed extractors."""

from __future__ import annotations

import json
import re
from typing import Protocol

from aletheia.llm import LLMInvocation, input_hash, output_hash, provider_for_name as llm_provider_for_name
from aletheia.models import (
    CandidateClaimDraft,
    EvidenceEvent,
    EvidenceSpan,
    ExtractionPolicy,
)

PRIVACY_ORDER = {"public": 0, "personal": 1, "private": 2, "sensitive": 3, "secret": 4}
PROTECTED_LLM_METADATA_KEYS = {
    "extraction_prompt_id",
    "provider",
    "model",
    "temperature",
    "schema_version",
    "llm_output",
}


class Extractor(Protocol):
    name: str
    version: str

    def extract(
        self,
        *,
        namespace: str,
        evidence: list[EvidenceEvent],
        policy: ExtractionPolicy,
    ) -> list[CandidateClaimDraft]:
        ...


class LLMExtractor:
    """Governed structured-output extractor for optional untrusted LLM suggestions."""

    name = "llm"
    version = "m12"

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = 2048,
        allow_sensitive: bool = False,
        allow_secret: bool = False,
    ) -> None:
        self.provider = llm_provider_for_name(provider, model=model)
        self.name = f"llm:{self.provider.name}"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.allow_sensitive = allow_sensitive
        self.allow_secret = allow_secret
        self.last_invocation: LLMInvocation | None = None

    def extract(
        self,
        *,
        namespace: str,
        evidence: list[EvidenceEvent],
        policy: ExtractionPolicy,
    ) -> list[CandidateClaimDraft]:
        blocked = _llm_privacy_warnings(
            evidence,
            provider_external=bool(getattr(self.provider, "external_network_access", False)),
            allow_sensitive=self.allow_sensitive,
            allow_secret=self.allow_secret,
        )
        input_payload = [_event_payload(event) for event in evidence]
        schema = _candidate_schema()
        if blocked:
            self.last_invocation = LLMInvocation(
                task_type="extract_candidates",
                provider=self.provider.name,
                provider_type=getattr(self.provider, "provider_type", "unknown"),
                model=self.provider.model,
                prompt_template_id="m12.extract_candidates",
                prompt_version="1",
                temperature=self.temperature,
                schema_version="candidate_claim_draft.v1",
                input_evidence_ids=[event.id for event in evidence],
                input_hash=input_hash(input_payload),
                status="unsafe",
                warnings=blocked,
                output={},
                metadata={"policy": policy.to_dict()},
            )
            return []
        messages = [
            {
                "role": "system",
                "content": (
                    "Extract candidate memories only. Return strict JSON matching the schema. "
                    "Every candidate must include a supporting evidence_span. Do not create trusted facts."
                ),
            },
            {"role": "user", "content": json.dumps({"namespace": namespace, "evidence": input_payload}, sort_keys=True)},
        ]
        try:
            output = self.provider.complete_json(
                messages=messages,
                schema=schema,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                metadata={"task_type": "extract_candidates", "namespace": namespace, "evidence": input_payload},
            )
            drafts = self._drafts_from_output(output, evidence_by_id={event.id: event for event in evidence})
            drafts, warnings = self._apply_policy(drafts, policy)
            status = "completed"
        except (KeyError, TypeError, ValueError) as exc:
            output = {"error": str(exc)}
            drafts = []
            status = "invalid_schema"
            warnings = [str(exc)]
        invocation = LLMInvocation(
            task_type="extract_candidates",
            provider=self.provider.name,
            provider_type=getattr(self.provider, "provider_type", "unknown"),
            model=self.provider.model,
            prompt_template_id="m12.extract_candidates",
            prompt_version="1",
            temperature=self.temperature,
            schema_version="candidate_claim_draft.v1",
            input_evidence_ids=[event.id for event in evidence],
            input_hash=input_hash(input_payload),
            output_hash=output_hash(output),
            status=status,
            warnings=warnings,
            output=output,
            metadata={"policy": policy.to_dict()},
        )
        self.last_invocation = invocation
        return drafts

    def _apply_policy(
        self,
        drafts: list[CandidateClaimDraft],
        policy: ExtractionPolicy,
    ) -> tuple[list[CandidateClaimDraft], list[str]]:
        kept: list[CandidateClaimDraft] = []
        warnings: list[str] = []
        per_event: dict[str, int] = {}
        for draft in drafts:
            reason = self._policy_rejection_reason(draft, policy)
            if reason:
                warnings.append(f"LLM candidate rejected by extraction policy: {reason}.")
                continue
            evidence_id = draft.evidence_spans[0].evidence_id if draft.evidence_spans else "__missing__"
            count = per_event.get(evidence_id, 0)
            if count >= policy.max_candidates_per_event:
                warnings.append(f"LLM candidate rejected by extraction policy: max_candidates_per_event exceeded for {evidence_id}.")
                continue
            per_event[evidence_id] = count + 1
            kept.append(draft)
        return kept, warnings

    @staticmethod
    def _policy_rejection_reason(draft: CandidateClaimDraft, policy: ExtractionPolicy) -> str | None:
        if draft.memory_type not in policy.allowed_memory_types:
            return f"memory_type {draft.memory_type!r} is not allowed"
        if draft.memory_type == "preference" and not policy.allow_preference_candidates:
            return "preference candidates are disabled"
        if draft.memory_type == "procedure" and not policy.allow_procedure_candidates:
            return "procedure candidates are disabled"
        if draft.memory_type == "project" and not policy.allow_project_candidates:
            return "project candidates are disabled"
        if draft.memory_type == "inference" and not policy.allow_inference_candidates:
            return "inference candidates are disabled"
        if draft.suggested_confidence < policy.min_candidate_confidence:
            return "suggested_confidence is below min_candidate_confidence"
        if policy.require_evidence_spans and not draft.evidence_spans:
            return "evidence spans are required"
        return None

    def _drafts_from_output(self, output: dict, *, evidence_by_id: dict[str, EvidenceEvent]) -> list[CandidateClaimDraft]:
        candidates = output["candidates"]
        if not isinstance(candidates, list):
            raise ValueError("LLM output field 'candidates' must be a list.")
        drafts: list[CandidateClaimDraft] = []
        for item in candidates:
            if not isinstance(item, dict):
                raise ValueError("Each LLM candidate must be an object.")
            for field in ["subject", "predicate", "object", "memory_type", "evidence_span"]:
                if field not in item:
                    raise ValueError(f"LLM candidate missing {field}.")
            span_data = item["evidence_span"]
            evidence_id = span_data["evidence_id"]
            if evidence_id not in evidence_by_id:
                raise ValueError(f"LLM candidate references unknown evidence: {evidence_id}.")
            event = evidence_by_id[evidence_id]
            start_char = int(span_data.get("start_char", 0))
            end_char = int(span_data.get("end_char", len(event.content)))
            span_text = str(span_data.get("text", event.content[start_char:end_char]))
            if start_char < 0 or end_char <= start_char or end_char > len(event.content):
                raise ValueError("LLM candidate evidence_span offsets are invalid.")
            if event.content[start_char:end_char] != span_text:
                raise ValueError("LLM candidate evidence_span text does not match source evidence.")
            suggested_confidence = float(item.get("suggested_confidence", 0.65))
            suggested_importance = float(item.get("suggested_importance", 0.5))
            if not 0.0 <= suggested_confidence <= 1.0:
                raise ValueError("LLM candidate suggested_confidence must be between 0 and 1.")
            if not 0.0 <= suggested_importance <= 1.0:
                raise ValueError("LLM candidate suggested_importance must be between 0 and 1.")
            span = EvidenceSpan(
                evidence_id=evidence_id,
                start_char=start_char,
                end_char=end_char,
                text=span_text,
                role=span_data.get("role", "supporting"),
            )
            model_metadata = {
                key: value
                for key, value in dict(item.get("metadata") or {}).items()
                if key not in PROTECTED_LLM_METADATA_KEYS
            }
            metadata = {
                **model_metadata,
                "candidate_reason": item.get("candidate_reason"),
                "extraction_prompt_id": "m12.extract_candidates",
                "provider": self.provider.name,
                "model": self.provider.model,
                "temperature": self.temperature,
                "schema_version": "candidate_claim_draft.v1",
                "llm_output": True,
            }
            privacy_level = _max_privacy_level(str(item.get("privacy_level") or event.privacy_level), event.privacy_level)
            drafts.append(
                CandidateClaimDraft(
                    subject=str(item["subject"]),
                    predicate=str(item["predicate"]),
                    object=str(item["object"]),
                    memory_type=str(item["memory_type"]),
                    evidence_spans=[span],
                    suggested_confidence=suggested_confidence,
                    suggested_importance=suggested_importance,
                    suggested_half_life_days=item.get("suggested_half_life_days"),
                    suggested_scope=item.get("suggested_scope"),
                    suggested_categories=list(item.get("suggested_categories") or []),
                    suggested_entities=list(item.get("suggested_entities") or []),
                    privacy_level=privacy_level,
                    metadata=metadata,
                )
            )
        return drafts


class RuleBasedExtractor:
    """Small local extractor for preferences, project statements, and facts."""

    name = "rule_based"
    version = "0.4.0"

    def extract(
        self,
        *,
        namespace: str,
        evidence: list[EvidenceEvent],
        policy: ExtractionPolicy,
    ) -> list[CandidateClaimDraft]:
        drafts: list[CandidateClaimDraft] = []
        seen: set[tuple[str, str, str]] = set()
        for event in evidence:
            event_count = 0
            for start, end, raw_sentence in _sentence_spans(event.content):
                if event_count >= policy.max_candidates_per_event:
                    break
                sentence = _strip_role(raw_sentence)
                span = EvidenceSpan(
                    evidence_id=event.id,
                    start_char=start,
                    end_char=end,
                    text=raw_sentence,
                    role="supporting",
                )
                for draft in self._drafts_for_sentence(sentence, span, event.privacy_level):
                    if draft.memory_type not in policy.allowed_memory_types:
                        continue
                    if draft.memory_type == "preference" and not policy.allow_preference_candidates:
                        continue
                    if draft.memory_type == "procedure" and not policy.allow_procedure_candidates:
                        continue
                    if draft.memory_type == "project" and not policy.allow_project_candidates:
                        continue
                    if draft.memory_type == "inference" and not policy.allow_inference_candidates:
                        continue
                    if draft.suggested_confidence < policy.min_candidate_confidence:
                        continue
                    key = (
                        draft.subject.lower(),
                        draft.predicate.lower(),
                        draft.object.lower(),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    drafts.append(draft)
                    event_count += 1
                    if event_count >= policy.max_candidates_per_event:
                        break
        return drafts

    def _drafts_for_sentence(
        self,
        sentence: str,
        span: EvidenceSpan,
        privacy_level: str,
    ) -> list[CandidateClaimDraft]:
        normalized = " ".join(sentence.strip().split())
        if not normalized:
            return []
        lower = normalized.lower()
        risk_metadata = _risk_metadata(normalized)
        drafts: list[CandidateClaimDraft] = []

        preference = _preference_from_sentence(normalized)
        if preference:
            scope_text, object_text = preference
            drafts.append(
                CandidateClaimDraft(
                    subject="user",
                    predicate="prefers_response_style",
                    object=object_text,
                    memory_type="preference",
                    evidence_spans=[span],
                    suggested_confidence=0.78,
                    suggested_importance=0.62,
                    suggested_scope={"type": "contextual", "applies_when": _scope_key(scope_text)},
                    suggested_categories=[
                        "preference",
                        "preference.communication_style",
                        "communication_style",
                    ],
                    suggested_entities=["user"],
                    privacy_level=privacy_level,
                    metadata=risk_metadata,
                )
            )

        if "should focus on" in lower:
            subject = "project:aletheia" if "aletheia" in lower else "project:m3"
            match = re.search(r"\b(?:aletheia\s+)?(m\d+)\s+should\s+focus\s+on\s+(.+)", normalized, re.I)
            if match:
                milestone = match.group(1).upper()
                focus = _clean_object(match.group(2))
                drafts.append(
                    CandidateClaimDraft(
                        subject=subject,
                        predicate=f"{milestone.lower()}_focuses_on",
                        object=focus,
                        memory_type="project",
                        evidence_spans=[span],
                        suggested_confidence=0.76,
                        suggested_importance=0.66,
                        suggested_scope={"type": "project", "applies_when": "aletheia"},
                        suggested_categories=["project", "project.milestone", "decision"],
                        suggested_entities=["Aletheia", milestone],
                        privacy_level=privacy_level,
                        metadata=risk_metadata,
                    )
                )

        if "should introduce" in lower:
            match = re.search(r"\b(?:aletheia\s+)?(m\d+)\s+should\s+introduce\s+(.+)", normalized, re.I)
            if match:
                milestone = match.group(1).upper()
                drafts.append(
                    CandidateClaimDraft(
                        subject="project:aletheia",
                        predicate=f"{milestone.lower()}_should_introduce",
                        object=_clean_object(match.group(2)),
                        memory_type="decision",
                        evidence_spans=[span],
                        suggested_confidence=0.70,
                        suggested_importance=0.55,
                        suggested_scope={"type": "project", "applies_when": "aletheia"},
                        suggested_categories=["decision", "project"],
                        suggested_entities=["Aletheia", milestone],
                        privacy_level=privacy_level,
                        metadata=risk_metadata,
                    )
                )

        if lower.startswith("remember that "):
            fact = _clean_object(normalized[len("remember that "):])
            drafts.append(
                CandidateClaimDraft(
                    subject="user",
                    predicate="asserted",
                    object=fact,
                    memory_type="fact",
                    evidence_spans=[span],
                    suggested_confidence=0.66,
                    suggested_importance=0.45,
                    suggested_categories=["domain_knowledge"],
                    suggested_entities=_entities_from_text(fact),
                    privacy_level=privacy_level,
                    metadata=risk_metadata,
                )
            )

        if not drafts and re.search(r"\buser\s+prefers\b", lower):
            object_text = _clean_object(
                re.sub(r"^.*?\buser\s+prefers\s+", "", normalized, flags=re.I)
            )
            drafts.append(
                CandidateClaimDraft(
                    subject="user",
                    predicate="prefers",
                    object=object_text,
                    memory_type="preference",
                    evidence_spans=[span],
                    suggested_confidence=0.68,
                    suggested_importance=0.50,
                    suggested_categories=["preference"],
                    suggested_entities=["user"],
                    privacy_level=privacy_level,
                    metadata=risk_metadata,
                )
            )

        return drafts


class MockExtractor:
    """Network-free extractor with LLM-like structured output for tests."""

    name = "mock"
    version = "0.4.0"

    def extract(
        self,
        *,
        namespace: str,
        evidence: list[EvidenceEvent],
        policy: ExtractionPolicy,
    ) -> list[CandidateClaimDraft]:
        drafts: list[CandidateClaimDraft] = []
        for event in evidence:
            spans = list(_sentence_spans(event.content))
            if not spans:
                continue
            start, end, sentence = spans[0]
            text = _strip_role(sentence)
            drafts.append(
                CandidateClaimDraft(
                    subject="mock_extractor",
                    predicate="suggests_memory",
                    object=_clean_object(text),
                    memory_type="fact",
                    evidence_spans=[
                        EvidenceSpan(
                            evidence_id=event.id,
                            start_char=start,
                            end_char=end,
                            text=sentence,
                            role="supporting",
                        )
                    ],
                    suggested_confidence=max(policy.min_candidate_confidence, 0.72),
                    suggested_importance=0.40,
                    suggested_categories=["domain_knowledge"],
                    suggested_entities=_entities_from_text(text),
                    privacy_level=event.privacy_level,
                    metadata={"extractor": "mock"},
                )
            )
        return drafts[: policy.max_candidates_per_event * max(1, len(evidence))]


def extractor_for_name(name: str) -> Extractor:
    if name == "rule_based":
        return RuleBasedExtractor()
    if name == "mock":
        return MockExtractor()
    if name in {"llm", "mock_llm"}:
        return LLMExtractor(provider="mock_llm")
    if name in {"openai_compatible", "local_http", "ollama_style", "local_model"}:
        provider = "local_http" if name == "local_model" else name
        return LLMExtractor(provider=provider)
    raise ValueError(f"Unknown extractor: {name}")


def _event_payload(event: EvidenceEvent) -> dict:
    return {
        "id": event.id,
        "namespace": event.namespace,
        "content": event.content,
        "privacy_level": event.privacy_level,
        "source_type": event.source_type,
    }


def _max_privacy_level(candidate_level: str, evidence_level: str) -> str:
    if candidate_level not in PRIVACY_ORDER:
        return evidence_level
    if evidence_level not in PRIVACY_ORDER:
        return candidate_level
    return candidate_level if PRIVACY_ORDER[candidate_level] >= PRIVACY_ORDER[evidence_level] else evidence_level


def _llm_privacy_warnings(
    evidence: list[EvidenceEvent],
    *,
    provider_external: bool,
    allow_sensitive: bool,
    allow_secret: bool,
) -> list[str]:
    warnings: list[str] = []
    for event in evidence:
        if event.privacy_level == "secret" and not allow_secret:
            warnings.append(f"Evidence {event.id} is secret and blocked for LLM extraction.")
        if event.privacy_level in {"private", "sensitive"} and provider_external and not allow_sensitive:
            warnings.append(f"Evidence {event.id} is {event.privacy_level} and blocked for external LLM extraction.")
    return warnings


def _candidate_schema() -> dict:
    return {
        "type": "object",
        "required": ["candidates"],
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["subject", "predicate", "object", "memory_type", "evidence_span"],
                },
            }
        },
    }


def _sentence_spans(content: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", content):
        raw = match.group(0)
        if not raw.strip():
            continue
        start = match.start()
        end = match.end()
        while start < end and content[start].isspace():
            start += 1
        while end > start and content[end - 1].isspace():
            end -= 1
        spans.append((start, end, content[start:end]))
    return spans


def _strip_role(sentence: str) -> str:
    return re.sub(r"^\s*(user|assistant|system|agent)\s*:\s*", "", sentence, flags=re.I).strip()


def _preference_from_sentence(sentence: str) -> tuple[str, str] | None:
    patterns = [
        r"^for\s+(.+?),\s*keep\s+it\s+(.+)$",
        r"^for\s+(.+?),\s*i\s+want\s+(.+)$",
        r"^for\s+(.+?),\s*provide\s+(.+)$",
        r"^i\s+prefer\s+(.+?)\s+for\s+(.+)$",
        r"^i\s+want\s+(.+?)\s+for\s+(.+)$",
    ]
    for pattern in patterns[:3]:
        match = re.search(pattern, sentence, re.I)
        if match:
            scope = _clean_scope(match.group(1))
            value = _clean_object(match.group(2))
            return scope, f"{value} for {scope}"
    for pattern in patterns[3:]:
        match = re.search(pattern, sentence, re.I)
        if match:
            value = _clean_object(match.group(1))
            scope = _clean_scope(match.group(2))
            return scope, f"{value} for {scope}"
    return None


def _clean_scope(value: str) -> str:
    return _clean_object(value).replace("quick progress", "progress")


def _clean_object(value: str) -> str:
    return value.strip(" \t\r\n.:;!?\"'")


def _scope_key(value: str) -> str:
    lowered = value.lower()
    if "progress" in lowered and "update" in lowered:
        return "progress_update"
    if "architecture" in lowered and "contract" in lowered:
        return "architecture_contract"
    if "design" in lowered and "contract" in lowered:
        return "architecture_contract"
    return re.sub(r"[^a-z0-9]+", "_", lowered).strip("_") or "contextual"


def _entities_from_text(text: str) -> list[str]:
    entities: list[str] = []
    if re.search(r"\baletheia\b", text, re.I):
        entities.append("Aletheia")
    for match in re.finditer(r"\bM\d+\b", text):
        entities.append(match.group(0).upper())
    return sorted(set(entities))


def _risk_metadata(text: str) -> dict:
    lower = text.lower()
    patterns = [
        "ignore previous instructions",
        "ignore all previous instructions",
        "store this as core memory",
        "promote this to core",
        "delete all other memories",
        "permanent memory",
    ]
    if any(pattern in lower for pattern in patterns):
        return {
            "risk": "prompt_injection",
            "risk_severity": "high",
            "requires_explicit_review": True,
        }
    return {}
