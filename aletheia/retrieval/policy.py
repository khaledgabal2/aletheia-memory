"""Validated, executable policy configuration shared by all retrieval modes."""
import math

from aletheia.core.errors import ValidationError


DEFAULT_WEIGHTS = {
    "lexical_score": .25, "semantic_score": .25, "effective_confidence": .15,
    "retrieval_salience": .10, "memory_type_priority": .08, "project_relevance": .07,
    "status_priority": .05, "recency_score": .05, "unresolved_conflict_penalty": .20,
    "duplicate_penalty": .10, "conflict_penalty": .05, "staleness_penalty": 0.0,
}
DEFAULT_FILTERS = {
    "exclude_rejected": True, "exclude_superseded": True, "exclude_archived": True,
    "exclude_disputed_by_default": True, "require_provenance": True,
}
DEFAULT_THRESHOLDS = {
    "forbidden_memory_leak_rate": 0.0, "rejected_memory_leak_rate": 0.0,
    "superseded_memory_leak_rate": 0.0, "disputed_memory_leak_rate": .02,
    "provenance_preservation_rate": .99,
}
DEFAULT_CONTEXT = {
    "token_budget": 1500, "include_reflections": True, "include_inferences": False,
    "include_derivation_metadata": False, "preserve_governance": True,
    "filters": {"exclude_invalid": True}, "thresholds": {"provenance_preservation_rate": .99},
}


def _mapping(value, label):
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object.")
    return value


def _number(value, label):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValidationError(f"{label} must be a finite nonnegative number.")
    return float(value)


def thresholds(values, base=None):
    result = {**DEFAULT_THRESHOLDS, **(base or {})}
    for key, value in _mapping(values, "thresholds").items():
        if key not in DEFAULT_THRESHOLDS:
            raise ValidationError(f"Unsupported policy threshold: {key}")
        value = _number(value, key)
        floor = DEFAULT_THRESHOLDS[key]
        if value > 1 or (value < floor if key == "provenance_preservation_rate" else value > floor):
            raise ValidationError(f"Policy threshold cannot weaken the governance floor: {key}")
        result[key] = value
    return result


def ranking_config(config, base=None):
    config = _mapping(config, "ranking policy")
    # Preserve the supported shorthand consisting solely of score weights.
    if config and set(config).issubset(DEFAULT_WEIGHTS):
        config = {"weights": config}
    unknown = set(config) - {"weights", "filters", "thresholds", "objective", "evaluation_summary"}
    if unknown:
        raise ValidationError("Unsupported ranking policy fields: " + ", ".join(sorted(unknown)))
    base = base or {}
    weights = {**DEFAULT_WEIGHTS, **base.get("weights", {})}
    for key, value in _mapping(config.get("weights", {}), "weights").items():
        if key not in DEFAULT_WEIGHTS:
            raise ValidationError(f"Unsupported ranking weight: {key}")
        weights[key] = _number(value, key)
    if not math.isfinite(sum(weights.values())):
        raise ValidationError("Combined ranking weights must remain finite.")
    filters = {**DEFAULT_FILTERS, **base.get("filters", {})}
    for key, value in _mapping(config.get("filters", {}), "filters").items():
        if key not in DEFAULT_FILTERS or not isinstance(value, bool):
            raise ValidationError(f"Unsupported ranking filter: {key}")
        if key != "require_provenance" and value is not True:
            raise ValidationError(f"Ranking policy cannot disable default governance exclusions: {key}")
        filters[key] = value
    return {"weights": weights, "filters": filters,
            "thresholds": thresholds(config.get("thresholds", {}), base.get("thresholds"))}


def context_config(config, base=None):
    config = _mapping(config, "context policy")
    unknown = set(config) - set(DEFAULT_CONTEXT) - {"objective", "evaluation_summary"}
    if unknown:
        raise ValidationError("Unsupported context policy fields: " + ", ".join(sorted(unknown)))
    result = {**DEFAULT_CONTEXT, **(base or {}), **config}
    budget = result["token_budget"]
    if isinstance(budget, bool) or not isinstance(budget, int) or not 1 <= budget <= 12000:
        raise ValidationError("Policy token_budget must be an integer from 1 to 12000.")
    for key in ("include_reflections", "include_inferences", "include_derivation_metadata", "preserve_governance"):
        if not isinstance(result[key], bool):
            raise ValidationError(f"{key} must be a boolean.")
    if not result["preserve_governance"] or result["filters"] != {"exclude_invalid": True}:
        raise ValidationError("Context policy cannot disable governance or validity checks.")
    result["thresholds"] = thresholds(result["thresholds"])
    return result


def weighted_score(weights, features):
    return sum(weights.get(key, 0.0) * value * (-1 if key.endswith("_penalty") else 1)
               for key, value in features.items())
