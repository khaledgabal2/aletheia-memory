"""Thin generic agent adapters for the Aletheia service."""

from __future__ import annotations

from abc import ABC, abstractmethod

from aletheia.client import AletheiaClient


class AgentMemoryAdapter(ABC):
    @abstractmethod
    def before_agent_call(
        self,
        *,
        namespace: str,
        query: str,
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def after_agent_call(
        self,
        *,
        namespace: str,
        task_id: str,
        outcome: str | None = None,
        notes: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def remember_candidate(
        self,
        *,
        namespace: str,
        subject: str,
        predicate: str,
        object: str,
        memory_type: str,
        evidence_text: str,
    ) -> str:
        raise NotImplementedError


class HttpAgentMemoryAdapter(AgentMemoryAdapter):
    def __init__(self, client: AletheiaClient):
        self.client = client
        self.last_context_pack_id: str | None = None

    def before_agent_call(
        self,
        *,
        namespace: str,
        query: str,
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        pack = self.client.context_pack(
            namespace=namespace,
            query=query,
            project_id=project_id,
            session_id=session_id,
            retrieval_mode="hybrid",
            record_usage=True,
        )
        self.last_context_pack_id = pack["context_pack_id"]
        return pack["markdown"]

    def after_agent_call(
        self,
        *,
        namespace: str,
        task_id: str,
        outcome: str | None = None,
        notes: str | None = None,
    ) -> None:
        self.client.record_outcome(
            namespace=namespace,
            task_id=task_id,
            outcome=outcome or "unknown",
            used_context_pack_id=self.last_context_pack_id,
            note=notes,
        )

    def remember_candidate(
        self,
        *,
        namespace: str,
        subject: str,
        predicate: str,
        object: str,
        memory_type: str,
        evidence_text: str,
    ) -> str:
        result = self.client.remember(
            namespace=namespace,
            write_mode="candidate",
            memory_type=memory_type,
            subject=subject,
            predicate=predicate,
            object=object,
            evidence_text=evidence_text,
        )
        return result["candidate"]["id"]
