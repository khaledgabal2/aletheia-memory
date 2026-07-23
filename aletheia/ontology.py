"""M3 ontology/category registry facade."""

from __future__ import annotations


class OntologyRegistry:
    """Read-only facade for category registry labels stored in Memory."""

    def __init__(self, memory):
        self.memory = memory

    def list_labels(self, *, namespace: str | None = None) -> list[str]:
        return [row["label"] for row in self.memory.list_categories(namespace=namespace)]
