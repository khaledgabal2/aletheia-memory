"""Stable v1 plugin protocol contracts for Aletheia."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class PluginContext(Protocol):
    """Minimal kernel context exposed to governed plugins."""

    namespace: str

    def context_pack(self, namespace: str, query: str, **kwargs: Any) -> Any: ...

    def remember_candidate(self, **payload: Any) -> Any: ...


@runtime_checkable
class AletheiaPlugin(Protocol):
    name: str
    version: str

    def setup(self, context: PluginContext) -> None: ...


@runtime_checkable
class ExtractorPlugin(AletheiaPlugin, Protocol):
    def extract(self, *, namespace: str, evidence: list[Any], policy: Any) -> list[Any]: ...


@runtime_checkable
class EmbeddingProviderPlugin(AletheiaPlugin, Protocol):
    model: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class VectorIndexPlugin(AletheiaPlugin, Protocol):
    def upsert(self, *, namespace: str, items: list[dict[str, Any]]) -> None: ...

    def query(self, *, namespace: str, text: str, limit: int = 10) -> list[dict[str, Any]]: ...


@runtime_checkable
class ImporterPlugin(AletheiaPlugin, Protocol):
    def import_data(self, *, namespace: str, source: str, options: dict[str, Any] | None = None) -> dict[str, Any]: ...


@runtime_checkable
class ExporterPlugin(AletheiaPlugin, Protocol):
    def export_data(self, *, namespace: str, destination: str, options: dict[str, Any] | None = None) -> dict[str, Any]: ...


@runtime_checkable
class InferenceEnginePlugin(AletheiaPlugin, Protocol):
    def infer(self, *, namespace: str, inputs: list[dict[str, Any]], rules: list[Any] | None = None) -> list[Any]: ...


@runtime_checkable
class KeyProviderPlugin(AletheiaPlugin, Protocol):
    def resolve_key(self, *, key_id: str, purpose: str) -> bytes: ...


@runtime_checkable
class ReportGeneratorPlugin(AletheiaPlugin, Protocol):
    def render_report(self, *, namespace: str, report_type: str, payload: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class AgentAdapterPlugin(AletheiaPlugin, Protocol):
    def run_once(self, *, namespace: str, query: str) -> dict[str, Any]: ...


__all__ = [
    "AgentAdapterPlugin",
    "AletheiaPlugin",
    "EmbeddingProviderPlugin",
    "ExporterPlugin",
    "ExtractorPlugin",
    "ImporterPlugin",
    "InferenceEnginePlugin",
    "KeyProviderPlugin",
    "PluginContext",
    "ReportGeneratorPlugin",
    "VectorIndexPlugin",
]
