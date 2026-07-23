"""Governed LLM provider primitives for M12."""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMProvider(Protocol):
    name: str
    provider_type: str
    model: str
    provider_version: str
    external_network_access: bool
    stores_data: str
    supports_no_log_mode: str

    def complete_json(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class LLMInvocation:
    task_type: str
    provider: str
    provider_type: str
    model: str
    prompt_template_id: str
    prompt_version: str
    temperature: float
    schema_version: str
    input_evidence_ids: list[str] = field(default_factory=list)
    input_hash: str = ""
    output_hash: str = ""
    status: str = "completed"
    warnings: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class MockLLMProvider:
    """Deterministic provider used by tests, demos, and CI."""

    name = "mock_llm"
    provider_type = "mock_llm"
    model = "mock-llm-memory-v1"
    provider_version = "m12"
    external_network_access = False
    stores_data = "false"
    supports_no_log_mode = "true"

    def complete_json(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or {}
        task_type = metadata.get("task_type", "extract_candidates")
        if task_type == "extract_candidates":
            return {"candidates": [_candidate_from_event(event) for event in metadata.get("evidence", [])]}
        if task_type == "expand_query":
            query = metadata.get("query", "")
            terms = _keywords(query)
            return {
                "original_query": query,
                "expanded_terms": sorted(set(terms + [_synonym(term) for term in terms])),
                "entities": [term for term in terms if term[:1].isupper()],
                "categories": ["project"] if "m" in query.lower() or "project" in query.lower() else [],
                "likely_memory_types": ["project", "preference", "fact"],
                "excluded_assumptions": ["No new facts were inferred from query expansion."],
            }
        if task_type in {"summarize_evidence", "draft_reflection"}:
            evidence = metadata.get("evidence", [])
            text = " ".join(event.get("content", "") for event in evidence).strip()
            summary = _first_sentence(text) or "No source text available."
            return {
                "title": metadata.get("title") or "LLM Draft",
                "summary": summary,
                "reflection_text": summary,
                "source_evidence_ids": [event.get("id") for event in evidence if event.get("id")],
                "source_claim_ids": metadata.get("source_claim_ids", []),
                "review_state": "pending_review",
            }
        if task_type == "suggest_entities":
            evidence = metadata.get("evidence", [])
            text = " ".join(event.get("content", "") for event in evidence)
            entities = _entities_from_text(text)
            return {
                "entities": [
                    {
                        "name": entity,
                        "entity_type": "project" if entity.lower().startswith("m") else "concept",
                        "confidence": 0.70,
                        "source_evidence_ids": [event.get("id") for event in evidence if event.get("id")],
                    }
                    for entity in entities
                ],
                "review_state": "pending_review",
            }
        if task_type == "suggest_categories":
            evidence = metadata.get("evidence", [])
            text = " ".join(event.get("content", "") for event in evidence).lower()
            categories = ["project" if "project" in text or "m12" in text else "domain_knowledge"]
            if "prefer" in text:
                categories.append("preference")
            if "policy" in text or "privacy" in text:
                categories.append("governance")
            return {
                "categories": sorted(set(categories)),
                "review_state": "pending_review",
                "source_evidence_ids": [event.get("id") for event in evidence if event.get("id")],
            }
        if task_type == "suggest_scope":
            candidate = metadata.get("candidate", {})
            memory_type = str(candidate.get("memory_type") or "fact")
            scope_type = "project" if memory_type in {"project", "decision", "procedure"} else "user"
            return {
                "candidate_id": candidate.get("id"),
                "suggested_scope": {"type": scope_type, "requires_review": True},
                "confidence": 0.68,
                "review_state": "pending_review",
            }
        if task_type == "suggest_duplicate_merge":
            candidate = metadata.get("candidate", {})
            candidates = metadata.get("merge_candidates", [])
            target = candidates[0] if candidates else {}
            return {
                "candidate_id": candidate.get("id"),
                "target_id": target.get("id"),
                "merge_suggestion": "review_possible_duplicate" if target else "no_merge_target_found",
                "confidence": 0.62 if target else 0.0,
                "review_state": "pending_review",
                "rationale": "LLM merge output is advisory and must be reviewed.",
            }
        if task_type == "explain_conflict":
            return {
                "conflict_id": metadata.get("conflict_id"),
                "explanation": "The linked claims disagree and require explicit human resolution.",
                "suggested_next_steps": ["Review supporting evidence.", "Resolve with scope or supersession."],
                "resolves_conflict": False,
            }
        return {"suggestions": [], "review_state": "pending_review"}


class HTTPLLMProvider:
    """Configurable local/OpenAI-compatible JSON LLM provider."""

    provider_version = "m12"

    def __init__(
        self,
        *,
        name: str,
        provider_type: str,
        endpoint: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        external_network_access: bool = True,
        stores_data: str = "unknown",
        supports_no_log_mode: str = "unknown",
    ) -> None:
        if not endpoint:
            raise ValueError(f"{name} LLM provider requires an endpoint.")
        if not model:
            raise ValueError(f"{name} LLM provider requires a model.")
        self.name = name
        self.provider_type = provider_type
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.external_network_access = external_network_access
        self.stores_data = stores_data
        self.supports_no_log_mode = supports_no_log_mode

    def complete_json(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._payload(messages=messages, schema=schema, temperature=temperature, max_tokens=max_tokens)
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ValueError(f"LLM provider {self.name!r} failed: {exc}") from exc
        return self._extract_json(body)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(self, *, messages: list[dict[str, str]], schema: dict[str, Any], temperature: float, max_tokens: int | None) -> dict[str, Any]:
        if self.provider_type == "ollama_style":
            return {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"temperature": temperature},
            }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    def _extract_json(self, body: dict[str, Any]) -> dict[str, Any]:
        if isinstance(body.get("message"), dict) and isinstance(body["message"].get("content"), str):
            return _loads_json(body["message"]["content"])
        choices = body.get("choices")
        if choices and isinstance(choices, list):
            content = choices[0].get("message", {}).get("content")
            if isinstance(content, str):
                return _loads_json(content)
        if isinstance(body.get("output"), dict):
            return body["output"]
        if isinstance(body, dict):
            return body
        raise ValueError(f"LLM provider {self.name!r} returned an unsupported payload.")


class PluginLLMProvider:
    """Local plugin-backed LLM provider loaded from a Python entrypoint."""

    provider_type = "plugin"
    provider_version = "m12"

    def __init__(self, *, entrypoint: str, model: str | None = None) -> None:
        if not entrypoint:
            raise ValueError("plugin LLM provider requires ALETHEIA_LLM_PLUGIN_ENTRYPOINT or plugin:module:Provider.")
        self.entrypoint = entrypoint
        self.provider = _load_plugin_provider(entrypoint)
        self.name = str(getattr(self.provider, "name", "plugin_llm"))
        self.model = model or str(getattr(self.provider, "model", os.environ.get("ALETHEIA_LLM_PLUGIN_MODEL", "plugin-llm")))
        self.external_network_access = bool(
            getattr(self.provider, "external_network_access", _env_bool("ALETHEIA_LLM_PLUGIN_EXTERNAL", False))
        )
        self.stores_data = str(getattr(self.provider, "stores_data", os.environ.get("ALETHEIA_LLM_PLUGIN_STORES_DATA", "unknown")))
        self.supports_no_log_mode = str(
            getattr(self.provider, "supports_no_log_mode", os.environ.get("ALETHEIA_LLM_PLUGIN_NO_LOG", "unknown"))
        )

    def complete_json(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output = self.provider.complete_json(
            messages=messages,
            schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata,
        )
        if not isinstance(output, dict):
            raise ValueError(f"Plugin LLM provider {self.name!r} returned JSON that is not an object.")
        return output


def provider_for_name(name: str | None, *, model: str | None = None) -> LLMProvider:
    if name in {None, "mock", "mock_llm", "llm"}:
        return MockLLMProvider()
    if name == "plugin" or (isinstance(name, str) and name.startswith("plugin:")):
        entrypoint = name.split("plugin:", 1)[1] if isinstance(name, str) and name.startswith("plugin:") else ""
        entrypoint = entrypoint or os.environ.get("ALETHEIA_LLM_PLUGIN_ENTRYPOINT", "")
        return PluginLLMProvider(entrypoint=entrypoint, model=model)
    if name in {"local_http", "ollama_style", "openai_compatible"}:
        prefix = "ALETHEIA_LLM"
        env_prefix = f"{prefix}_{name.upper()}"
        endpoint = (
            os.environ.get(f"{env_prefix}_ENDPOINT")
            or os.environ.get(f"{prefix}_ENDPOINT")
            or ("http://localhost:11434/api/chat" if name == "ollama_style" else "")
        )
        resolved_model = model or os.environ.get(f"{env_prefix}_MODEL") or os.environ.get(f"{prefix}_MODEL") or ""
        return HTTPLLMProvider(
            name=name,
            provider_type=name,
            endpoint=endpoint,
            model=resolved_model,
            api_key=os.environ.get(f"{env_prefix}_API_KEY") or os.environ.get(f"{prefix}_API_KEY"),
            timeout=float(os.environ.get(f"{env_prefix}_TIMEOUT") or os.environ.get(f"{prefix}_TIMEOUT") or "60"),
            external_network_access=(os.environ.get(f"{env_prefix}_EXTERNAL", "true").lower() == "true"),
            stores_data=os.environ.get(f"{env_prefix}_STORES_DATA") or os.environ.get(f"{prefix}_STORES_DATA") or "unknown",
            supports_no_log_mode=os.environ.get(f"{env_prefix}_NO_LOG") or os.environ.get(f"{prefix}_NO_LOG") or "unknown",
        )
    raise ValueError(f"Unknown LLM provider: {name}")


def input_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def output_hash(value: Any) -> str:
    return input_hash(value)


def _candidate_from_event(event: dict[str, Any]) -> dict[str, Any]:
    content = event.get("content", "")
    sentence = _first_sentence(content)
    span_text = sentence or content
    end = max(1, len(span_text))
    lower = span_text.lower()
    if "prefers" in lower:
        subject = "user"
        predicate = "prefers"
        obj = _clean(re.sub(r"^.*?\bprefers\s+", "", span_text, flags=re.I))
        memory_type = "preference"
        categories = ["preference"]
    elif "should" in lower:
        subject = "project:aletheia" if "aletheia" in lower else "project"
        predicate = "suggests"
        obj = _clean(span_text)
        memory_type = "project"
        categories = ["project"]
    else:
        subject = "source"
        predicate = "states"
        obj = _clean(span_text)
        memory_type = "fact"
        categories = ["domain_knowledge"]
    return {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "memory_type": memory_type,
        "evidence_span": {
            "evidence_id": event.get("id"),
            "start_char": 0,
            "end_char": end,
            "text": span_text,
            "role": "supporting",
        },
        "suggested_confidence": 0.72,
        "suggested_importance": 0.45,
        "suggested_scope": {"type": "review_required"},
        "privacy_level": event.get("privacy_level", "personal"),
        "candidate_reason": "Structured mock LLM extraction from source evidence.",
        "suggested_categories": categories,
        "suggested_entities": [],
    }


def _first_sentence(text: str) -> str:
    match = re.search(r"[^.!?\n]+(?:[.!?]+|$)", text.strip())
    return match.group(0).strip() if match else text.strip()


def _keywords(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]+", text) if len(token) > 2][:12]


def _entities_from_text(text: str) -> list[str]:
    entities = {token for token in re.findall(r"\b(?:[A-Z][A-Za-z0-9_-]*|M\d+)\b", text) if len(token) > 1}
    if re.search(r"\baletheia\b", text, re.I):
        entities.add("Aletheia")
    return sorted(entities)[:20]


def _synonym(term: str) -> str:
    mapping = {
        "recall": "retrieval",
        "retrieve": "recall",
        "memory": "context",
        "semantic": "meaning",
        "privacy": "protected",
        "conflict": "contradiction",
    }
    return mapping.get(term.lower(), term.lower())


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" .;:")


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_plugin_provider(entrypoint: str):
    module_name, _, attr_name = entrypoint.partition(":")
    if not module_name:
        raise ValueError("Plugin LLM provider entrypoint must include a module name.")
    module = importlib.import_module(module_name)
    obj = getattr(module, attr_name) if attr_name else getattr(module, "provider", None) or getattr(module, "Plugin", None)
    if obj is None:
        raise ValueError(f"Plugin LLM provider entrypoint not found: {entrypoint}")
    if inspect.isclass(obj):
        provider = obj()
    elif callable(obj) and not hasattr(obj, "complete_json"):
        provider = obj()
    else:
        provider = obj
    if not hasattr(provider, "complete_json"):
        raise ValueError(f"Plugin LLM provider {entrypoint!r} does not expose complete_json.")
    return provider


def _loads_json(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM provider returned non-JSON content.") from exc
    if not isinstance(value, dict):
        raise ValueError("LLM provider returned JSON that is not an object.")
    return value
