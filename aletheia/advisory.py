"""Typed contracts for review-only LLM tasks, without a runtime schema dependency."""
from __future__ import annotations

import math

from aletheia.core.errors import ValidationError


def contract(task: str, *, evidence_ids=()) -> tuple[dict, str]:
    text = {"type": "string", "minLength": 1}
    texts = {"type": "array", "items": text}
    sources = {"type": "array", "items": {"type": "string", "enum": list(evidence_ids)}}
    def obj(properties, required):
        return {"type": "object", "properties": properties, "required": required}
    definitions = {
        "expand_query": (obj({"original_query": text, "expanded_terms": {**texts, "minItems": 1}},
                             ["original_query", "expanded_terms"]),
                         "Return original_query and expanded_terms (an array of useful search phrases). Expand for retrieval only; introduce no facts."),
        "suggest_entities": (obj({"entities": {"type": "array", "items": obj({
            "name": text, "entity_type": text, "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "source_evidence_ids": sources}, ["name", "entity_type", "confidence", "source_evidence_ids"])}}, ["entities"]),
            "Identify named entities explicitly present in the evidence. Return entities with name, entity_type, confidence and source_evidence_ids. Return an empty array if none exist."),
        "suggest_categories": (obj({"categories": texts}, ["categories"]),
                               "Suggest categories describing the evidence. Return categories as an array of strings."),
        "suggest_scope": (obj({"suggested_scope": obj({"type": text, "applies_when": text}, ["type", "applies_when"])}, ["suggested_scope"]),
                          "Suggest where the candidate applies. Return suggested_scope with type and applies_when. Advice only; do not apply it."),
        "suggest_duplicate_merge": (obj({"merge_suggestion": text, "rationale": text}, ["merge_suggestion", "rationale"]),
                                    "Compare candidate with merge_candidates. Return merge_suggestion and rationale. If none exist, say no_merge_target_found. Do not merge anything."),
        "summarize_evidence": (obj({"summary": text, "source_evidence_ids": sources}, ["summary", "source_evidence_ids"]),
                               "Summarize the evidence content, not its metadata. Return summary and exact source_evidence_ids. Preserve names, negation, dates and qualifications."),
        "draft_reflection": (obj({"reflection_text": text, "source_evidence_ids": sources}, ["reflection_text", "source_evidence_ids"]),
                             "Draft a reflection synthesizing the evidence content. Return meaningful reflection_text and exact source_evidence_ids. Do not return a placeholder or infer unsupported facts."),
        "explain_conflict": (obj({"explanation": text, "resolves_conflict": {"type": "boolean", "const": False}}, ["explanation", "resolves_conflict"]),
                             "Explain how the supplied claims disagree. Return explanation and resolves_conflict=false. Do not choose a winner or resolve the conflict."),
    }
    return definitions[task]


def validate(value, schema, path="output"):
    """Validate the subset used by the contracts above, including nested fields."""
    expected = schema.get("type")
    finite_number = type(value) is int or type(value) is float and math.isfinite(value)
    matches = {"object": isinstance(value, dict), "array": isinstance(value, list),
               "string": isinstance(value, str), "boolean": type(value) is bool,
               "number": finite_number}
    if expected and not matches[expected]:
        raise ValidationError(f"Invalid LLM task output: {path} must be {expected}.")
    if "const" in schema and value != schema["const"] or "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"Invalid LLM task output: {path} has an unsupported value.")
    if expected == "object":
        for key in schema.get("required", []):
            if key not in value:
                raise ValidationError(f"Invalid LLM task output: missing {path}.{key}.")
        for key, child in schema.get("properties", {}).items():
            if key in value:
                validate(value[key], child, path + "." + key)
    elif expected == "array":
        if len(value) < schema.get("minItems", 0):
            raise ValidationError(f"Invalid LLM task output: {path} is empty.")
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")
    elif expected == "string" and schema.get("minLength", 0) and not value.strip():
        raise ValidationError(f"Invalid LLM task output: {path} is blank.")
    elif expected == "number" and not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf):
        raise ValidationError(f"Invalid LLM task output: {path} is out of range.")
