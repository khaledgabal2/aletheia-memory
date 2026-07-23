"""M3 candidate review service wrapper."""

from __future__ import annotations

from aletheia.models import CandidateClaim, Claim, ExtractionDecision


class CandidateReviewService:
    """Thin service facade over Memory's governed candidate lifecycle."""

    def __init__(self, memory):
        self.memory = memory

    def list(
        self,
        namespace: str,
        *,
        status: str | None = None,
        memory_type: str | None = None,
        project_id: str | None = None,
        extraction_run_id: str | None = None,
        limit: int = 50,
    ) -> list[CandidateClaim]:
        return self.memory.list_candidates(
            namespace,
            status=status,
            memory_type=memory_type,
            project_id=project_id,
            extraction_run_id=extraction_run_id,
            limit=limit,
        )

    def review(
        self,
        candidate_id: str,
        *,
        decision: str,
        reason: str,
        reviewer: str = "user",
        edits: dict | None = None,
    ) -> ExtractionDecision:
        return self.memory.review_candidate(
            candidate_id,
            decision=decision,
            reason=reason,
            reviewer=reviewer,
            edits=edits,
        )

    def promote(
        self,
        candidate_id: str,
        *,
        reason: str,
        target_status: str = "active",
        reviewer: str = "user",
        edits: dict | None = None,
        force: bool = False,
    ) -> Claim:
        return self.memory.promote_candidate(
            candidate_id,
            reason=reason,
            target_status=target_status,
            reviewer=reviewer,
            edits=edits,
            force=force,
        )

    def reject(
        self,
        candidate_id: str,
        *,
        reason: str,
        reviewer: str = "user",
    ) -> ExtractionDecision:
        return self.memory.reject_candidate(
            candidate_id,
            reason=reason,
            reviewer=reviewer,
        )
