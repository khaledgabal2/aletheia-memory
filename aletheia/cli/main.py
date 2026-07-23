"""MVP command line interface for Aletheia."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import urllib.error
import urllib.request
import webbrowser
from datetime import timedelta
from pathlib import Path
from dataclasses import asdict

from aletheia import Memory
from aletheia.core.errors import AletheiaError
from aletheia.core.ids import new_id
from aletheia.core.time import utc_now, utc_now_iso
from aletheia.help import docs_root, find_help_document, iter_help_documents, read_help_document
from aletheia.retrieval.lexical import claim_text
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService, DEFAULT_LOCAL_AGENT_CAPABILITIES
from aletheia.service.errors import ServiceError
from aletheia.service.http import AletheiaDaemon, AletheiaService, openapi_schema
from aletheia.service.mcp import McpToolRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aletheia")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create or migrate a database.")
    init_parser.add_argument("--db", default="./aletheia.db")
    init_parser.add_argument("--protected", action="store_true", help="Enable protected mode after initialization.")

    migrate_parser = subparsers.add_parser("migrate", help="Run database migrations.")
    migrate_parser.add_argument("--db", default="./aletheia.db")
    migrate_subparsers = migrate_parser.add_subparsers(dest="migrate_command")
    migrate_plan = migrate_subparsers.add_parser("plan")
    migrate_plan.add_argument("--db", default=argparse.SUPPRESS)
    migrate_plan.add_argument("--target-version", default=None)
    migrate_apply = migrate_subparsers.add_parser("apply")
    migrate_apply.add_argument("--db", default=argparse.SUPPRESS)
    migrate_apply.add_argument("--target-version", default=None)
    migrate_apply.add_argument("--dry-run", action="store_true")
    migrate_apply.add_argument("--backup-before", action="store_true")
    migrate_apply.add_argument("--backup-output")
    migrate_apply.add_argument("--passphrase")
    migrate_apply.add_argument("--verify-after", action="store_true")
    migrate_verify = migrate_subparsers.add_parser("verify")
    migrate_verify.add_argument("--db", default=argparse.SUPPRESS)
    migrate_verify.add_argument("--namespace")
    migrate_verify.add_argument("--deep", action="store_true")

    remember = subparsers.add_parser("remember", help="Store an explicit memory.")
    _add_db_namespace(remember)
    remember.add_argument("--type", dest="memory_type", required=True)
    remember.add_argument("--subject", required=True)
    remember.add_argument("--predicate", required=True)
    remember.add_argument("--object", required=True)
    remember.add_argument("--confidence", type=float, default=0.75)
    remember.add_argument("--importance", type=float, default=0.5)
    remember.add_argument("--half-life-days", type=float)
    remember.add_argument("--status", default="active")
    remember.add_argument("--source-type", default="manual")
    remember.add_argument("--project")
    remember.add_argument("--session")

    search = subparsers.add_parser("search", help="Search active memory.")
    _add_db_namespace(search)
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--type", dest="memory_type")
    search.add_argument("--status")
    search.add_argument("--subject")
    search.add_argument("--predicate")
    search.add_argument("--project")
    search.add_argument("--session")
    search.add_argument("--min-confidence", type=float)
    search.add_argument("--include-disputed", action="store_true")
    search.add_argument("--include-archived", action="store_true")
    search.add_argument("--mode", choices=["lexical", "semantic", "hybrid"], default="lexical")
    search.add_argument("--semantic", action="store_true")
    search.add_argument("--hybrid", action="store_true")
    search.add_argument("--category", action="append", dest="categories")
    search.add_argument("--semantic-provider")

    context = subparsers.add_parser("context", help="Build an M1 memory context.")
    _add_db_namespace(context)
    context.add_argument("--query", required=True)
    context.add_argument("--project")
    context.add_argument("--session")
    context.add_argument("--budget", type=int, default=1500)
    context.add_argument("--mode", choices=["lexical", "semantic", "hybrid"], default="lexical")
    context.add_argument("--include-candidate-warnings", action="store_true")
    context.add_argument("--no-reflections", action="store_true")
    context.add_argument("--include-inferences", action="store_true")
    context.add_argument("--include-derivation", action="store_true")
    context.add_argument("--policy-version")
    context.add_argument("--record-usage", action="store_true")
    context.add_argument("--explain-policy", action="store_true")
    context.add_argument("--json", action="store_true")

    context_pack = subparsers.add_parser(
        "context-pack", help="Build an agent-ready memory context pack."
    )
    _add_db_namespace(context_pack)
    context_pack.add_argument("query")
    context_pack.add_argument("--token-budget", type=int, default=1500)
    context_pack.add_argument("--project")
    context_pack.add_argument("--session")
    context_pack.add_argument("--mode", choices=["lexical", "semantic", "hybrid"], default="lexical")
    context_pack.add_argument("--include-candidate-warnings", action="store_true")
    context_pack.add_argument("--no-reflections", action="store_true")
    context_pack.add_argument("--include-inferences", action="store_true")
    context_pack.add_argument("--include-derivation", action="store_true")
    context_pack.add_argument("--policy-version")
    context_pack.add_argument("--record-usage", action="store_true")
    context_pack.add_argument("--explain-policy", action="store_true")
    context_pack.add_argument("--json", action="store_true")

    audit = subparsers.add_parser("audit", help="Show provenance for a claim or event.")
    audit.add_argument("target_id")
    audit.add_argument("--db", default="./aletheia.db")
    audit.add_argument("--json", action="store_true")

    feedback = subparsers.add_parser("feedback", help="Record feedback on memory.")
    feedback.add_argument("target_id")
    _add_db_namespace(feedback)
    feedback.add_argument(
        "--signal",
        required=True,
        choices=[
            "confirmed",
            "wrong",
            "stale",
            "useful",
            "not_useful",
            "contradicted",
            "verified",
            "irrelevant",
            "important",
            "unimportant",
        ],
    )
    feedback.add_argument("--target-type", default="claim")
    feedback.add_argument("--source", default="user")
    feedback.add_argument("--evidence")
    feedback.add_argument("--strength", type=float, default=1.0)
    feedback.add_argument("--note")

    ingest = subparsers.add_parser("ingest", help="Ingest raw content as evidence.")
    ingest_subparsers = ingest.add_subparsers(dest="ingest_command", required=True)
    ingest_text = ingest_subparsers.add_parser("text")
    _add_db_namespace(ingest_text)
    ingest_text.add_argument("content")
    ingest_text.add_argument("--source-type", default="text")
    ingest_text.add_argument("--source-uri")
    ingest_text.add_argument("--project")
    ingest_text.add_argument("--session")
    ingest_text.add_argument("--title")
    ingest_text.add_argument("--metadata-json")
    ingest_text.add_argument("--privacy", default="personal")
    ingest_text.add_argument("--trust", default="unknown")
    ingest_file = ingest_subparsers.add_parser("file")
    _add_db_namespace(ingest_file)
    ingest_file.add_argument("path")
    ingest_file.add_argument("--source-type", default="file")
    ingest_file.add_argument("--project")
    ingest_file.add_argument("--session")
    ingest_file.add_argument("--title")
    ingest_file.add_argument("--metadata-json")
    ingest_file.add_argument("--privacy", default="personal")
    ingest_file.add_argument("--trust", default="unknown")

    extract = subparsers.add_parser("extract", help="Run candidate extraction.")
    extract_subparsers = extract.add_subparsers(dest="extract_command", required=True)
    extract_run = extract_subparsers.add_parser("run")
    _add_db_namespace(extract_run)
    extract_run.add_argument("--batch")
    extract_run.add_argument("--evidence", action="append")
    extract_run.add_argument("--extractor", default="rule_based")
    extract_run.add_argument("--max-candidates", type=int)
    extract_dry_run = extract_subparsers.add_parser("dry-run")
    _add_db_namespace(extract_dry_run)
    extract_dry_run.add_argument("--batch")
    extract_dry_run.add_argument("--evidence", action="append")
    extract_dry_run.add_argument("--extractor", default="rule_based")
    extract_dry_run.add_argument("--max-candidates", type=int)
    extract_show = extract_subparsers.add_parser("show")
    extract_show.add_argument("run_id")
    extract_show.add_argument("--db", default="./aletheia.db")

    llm = subparsers.add_parser("llm", help="Run governed LLM memory tasks.")
    llm_subparsers = llm.add_subparsers(dest="llm_command", required=True)
    llm_expand = llm_subparsers.add_parser("expand-query")
    _add_db_namespace(llm_expand)
    llm_expand.add_argument("query")
    llm_expand.add_argument("--provider", default="mock_llm")
    llm_expand.add_argument("--model")
    llm_expand.add_argument("--privacy-level", default="personal")
    llm_summary = llm_subparsers.add_parser("summarize-evidence")
    _add_db_namespace(llm_summary)
    llm_summary.add_argument("--evidence", action="append", required=True)
    llm_summary.add_argument("--provider", default="mock_llm")
    llm_summary.add_argument("--model")
    llm_entities = llm_subparsers.add_parser("suggest-entities")
    _add_db_namespace(llm_entities)
    llm_entities.add_argument("--evidence", action="append", required=True)
    llm_entities.add_argument("--provider", default="mock_llm")
    llm_entities.add_argument("--model")
    llm_categories = llm_subparsers.add_parser("suggest-categories")
    _add_db_namespace(llm_categories)
    llm_categories.add_argument("--evidence", action="append", required=True)
    llm_categories.add_argument("--provider", default="mock_llm")
    llm_categories.add_argument("--model")
    llm_scope = llm_subparsers.add_parser("suggest-scope")
    _add_db_namespace(llm_scope)
    llm_scope.add_argument("candidate_id")
    llm_scope.add_argument("--provider", default="mock_llm")
    llm_scope.add_argument("--model")
    llm_merge = llm_subparsers.add_parser("suggest-duplicate-merge")
    _add_db_namespace(llm_merge)
    llm_merge.add_argument("candidate_id")
    llm_merge.add_argument("--provider", default="mock_llm")
    llm_merge.add_argument("--model")
    llm_reflection = llm_subparsers.add_parser("draft-reflection")
    _add_db_namespace(llm_reflection)
    llm_reflection.add_argument("--claim", action="append", dest="source_claim_ids")
    llm_reflection.add_argument("--evidence", action="append", dest="source_evidence_ids")
    llm_reflection.add_argument("--title", default="LLM Reflection Draft")
    llm_reflection.add_argument("--provider", default="mock_llm")
    llm_reflection.add_argument("--model")
    llm_conflict = llm_subparsers.add_parser("explain-conflict")
    llm_conflict.add_argument("conflict_id")
    llm_conflict.add_argument("--db", default="./aletheia.db")
    llm_conflict.add_argument("--provider", default="mock_llm")
    llm_conflict.add_argument("--model")
    llm_runs = llm_subparsers.add_parser("runs")
    _add_db_namespace(llm_runs)
    llm_runs.add_argument("--task")
    llm_runs.add_argument("--limit", type=int, default=20)
    llm_show = llm_subparsers.add_parser("show")
    llm_show.add_argument("llm_run_id")
    llm_show.add_argument("--db", default="./aletheia.db")

    candidates = subparsers.add_parser("candidates", help="Review candidate memories.")
    candidate_subparsers = candidates.add_subparsers(dest="candidates_command", required=True)
    candidates_list = candidate_subparsers.add_parser("list")
    _add_db_namespace(candidates_list)
    candidates_list.add_argument("--status")
    candidates_list.add_argument("--type", dest="memory_type")
    candidates_list.add_argument("--project")
    candidates_list.add_argument("--run")
    candidates_show = candidate_subparsers.add_parser("show")
    candidates_show.add_argument("candidate_id")
    candidates_show.add_argument("--db", default="./aletheia.db")
    candidates_promote = candidate_subparsers.add_parser("promote")
    candidates_promote.add_argument("candidate_id")
    candidates_promote.add_argument("--db", default="./aletheia.db")
    candidates_promote.add_argument("--reason", required=True)
    candidates_promote.add_argument("--to", default="active")
    candidates_promote.add_argument("--reviewer", default="user")
    candidates_promote.add_argument("--force", action="store_true")
    candidates_reject = candidate_subparsers.add_parser("reject")
    candidates_reject.add_argument("candidate_id")
    candidates_reject.add_argument("--db", default="./aletheia.db")
    candidates_reject.add_argument("--reason", required=True)
    candidates_reject.add_argument("--reviewer", default="user")
    candidates_edit = candidate_subparsers.add_parser("edit")
    candidates_edit.add_argument("candidate_id")
    candidates_edit.add_argument("--db", default="./aletheia.db")
    candidates_edit.add_argument("--reason", required=True)
    candidates_edit.add_argument("--reviewer", default="user")
    candidates_edit.add_argument("--subject")
    candidates_edit.add_argument("--predicate")
    candidates_edit.add_argument("--object")
    candidates_edit.add_argument("--type", dest="memory_type")
    candidates_edit.add_argument("--status")
    candidates_edit.add_argument("--confidence", type=float)
    candidates_edit.add_argument("--importance", type=float)
    candidates_edit.add_argument("--scope-json")

    entities = subparsers.add_parser("entities", help="Inspect and manage entities.")
    entity_subparsers = entities.add_subparsers(dest="entities_command", required=True)
    entities_list = entity_subparsers.add_parser("list")
    _add_db_namespace(entities_list)
    entities_list.add_argument("--type", dest="entity_type")
    entities_show = entity_subparsers.add_parser("show")
    entities_show.add_argument("entity_id")
    entities_show.add_argument("--db", default="./aletheia.db")
    entities_merge = entity_subparsers.add_parser("merge")
    _add_db_namespace(entities_merge)
    entities_merge.add_argument("source_entity_id")
    entities_merge.add_argument("target_entity_id")
    entities_merge.add_argument("--reason", required=True)

    categories = subparsers.add_parser("categories", help="Inspect and label categories.")
    category_subparsers = categories.add_subparsers(dest="categories_command", required=True)
    categories_list = category_subparsers.add_parser("list")
    categories_list.add_argument("--db", default="./aletheia.db")
    categories_list.add_argument("--namespace")
    categories_label = category_subparsers.add_parser("label")
    categories_label.add_argument("target_id")
    categories_label.add_argument("--db", default="./aletheia.db")
    categories_label.add_argument("--type", dest="target_type", required=True)
    categories_label.add_argument("--label", action="append", required=True)
    categories_label.add_argument("--reason", required=True)
    categories_label.add_argument("--confidence", type=float, default=1.0)

    index = subparsers.add_parser("index", help="Create semantic indexes.")
    index_subparsers = index.add_subparsers(dest="index_command", required=True)
    index_semantic = index_subparsers.add_parser("semantic")
    _add_db_namespace(index_semantic)
    index_semantic.add_argument("--target", default="claims")
    index_semantic.add_argument("--id", action="append", dest="target_ids")
    index_semantic.add_argument("--provider")
    index_semantic.add_argument("--model")
    index_semantic.add_argument("--dimension", type=int)
    index_semantic.add_argument("--force", action="store_true")
    index_semantic.add_argument("--no-resume", action="store_true")
    index_semantic.add_argument("--protected-mode-policy")
    index_semantic.add_argument("--vector-store", default="sqlite_local")
    index_status = index_subparsers.add_parser("status")
    _add_db_namespace(index_status)
    index_status.add_argument("--target")
    index_resume = index_subparsers.add_parser("resume")
    _add_db_namespace(index_resume)
    index_resume.add_argument("--target", default="claims")
    index_resume.add_argument("--id", action="append", dest="target_ids")
    index_resume.add_argument("--provider")
    index_resume.add_argument("--model")
    index_resume.add_argument("--dimension", type=int)
    index_resume.add_argument("--protected-mode-policy")
    index_resume.add_argument("--vector-store", default="sqlite_local")
    index_verify = index_subparsers.add_parser("verify")
    _add_db_namespace(index_verify)
    index_verify.add_argument("--target", default="claims")
    index_verify.add_argument("--provider")
    index_verify.add_argument("--model")
    index_verify.add_argument("--dimension", type=int)
    index_mark_stale = index_subparsers.add_parser("mark-stale")
    _add_db_namespace(index_mark_stale)
    index_mark_stale.add_argument("--target", default="claims")
    index_mark_stale.add_argument("--provider")
    index_mark_stale.add_argument("--model")
    index_mark_stale.add_argument("--reason", default="manual")
    index_prune_stale = index_subparsers.add_parser("prune-stale")
    _add_db_namespace(index_prune_stale)
    index_prune_stale.add_argument("--target", default="claims")
    index_prune_stale.add_argument("--provider")
    index_prune_stale.add_argument("--model")

    events = subparsers.add_parser("events", help="Inspect raw evidence events.")
    event_subparsers = events.add_subparsers(dest="events_command", required=True)
    events_list = event_subparsers.add_parser("list")
    _add_db_namespace(events_list)
    events_list.add_argument("--limit", type=int, default=20)
    events_list.add_argument("--json", action="store_true")
    events_show = event_subparsers.add_parser("show")
    events_show.add_argument("event_id")
    events_show.add_argument("--db", default="./aletheia.db")
    events_show.add_argument("--json", action="store_true")

    sessions = subparsers.add_parser("sessions", help="Manage durable sessions.")
    session_subparsers = sessions.add_subparsers(dest="sessions_command", required=True)
    sessions_start = session_subparsers.add_parser("start")
    _add_db_namespace(sessions_start)
    sessions_start.add_argument("--agent")
    sessions_start.add_argument("--project")
    sessions_start.add_argument("--title")
    sessions_start.add_argument("--metadata-json")
    sessions_end = session_subparsers.add_parser("end")
    sessions_end.add_argument("--db", default="./aletheia.db")
    sessions_end.add_argument("--session", required=True)
    sessions_end.add_argument("--summary")
    sessions_end.add_argument("--no-remember-summary", action="store_true")
    sessions_list = session_subparsers.add_parser("list")
    _add_db_namespace(sessions_list)
    sessions_list.add_argument("--project")
    sessions_list.add_argument("--limit", type=int, default=50)
    sessions_show = session_subparsers.add_parser("show")
    sessions_show.add_argument("--db", default="./aletheia.db")
    sessions_show.add_argument("--session", required=True)

    projects = subparsers.add_parser("projects", help="Manage durable projects.")
    project_subparsers = projects.add_subparsers(dest="projects_command", required=True)
    projects_create = project_subparsers.add_parser("create")
    _add_db_namespace(projects_create)
    projects_create.add_argument("--id", required=True)
    projects_create.add_argument("--title", required=True)
    projects_create.add_argument("--description")
    projects_create.add_argument("--status", default="active")
    projects_create.add_argument("--metadata-json")
    projects_list = project_subparsers.add_parser("list")
    _add_db_namespace(projects_list)
    projects_list.add_argument("--status")
    projects_show = project_subparsers.add_parser("show")
    _add_db_namespace(projects_show)
    projects_show.add_argument("--id", required=True)

    claims = subparsers.add_parser("claims", help="Inspect and manage claims.")
    claim_subparsers = claims.add_subparsers(dest="claims_command", required=True)
    claims_list = claim_subparsers.add_parser("list")
    _add_db_namespace(claims_list)
    claims_list.add_argument("--status")
    claims_show = claim_subparsers.add_parser("show")
    claims_show.add_argument("claim_id")
    claims_show.add_argument("--db", default="./aletheia.db")
    claims_promote = claim_subparsers.add_parser("promote")
    claims_promote.add_argument("claim_id")
    claims_promote.add_argument("--to", required=True)
    claims_promote.add_argument("--reason")
    claims_promote.add_argument("--force", action="store_true")
    claims_promote.add_argument("--db", default="./aletheia.db")
    claims_demote = claim_subparsers.add_parser("demote")
    claims_demote.add_argument("claim_id")
    claims_demote.add_argument("--to", required=True)
    claims_demote.add_argument("--reason")
    claims_demote.add_argument("--db", default="./aletheia.db")
    claims_supersede = claim_subparsers.add_parser("supersede")
    claims_supersede.add_argument("old_claim_id")
    claims_supersede.add_argument("new_claim_id")
    claims_supersede.add_argument("--reason", required=True)
    claims_supersede.add_argument("--db", default="./aletheia.db")
    claims_scope = claim_subparsers.add_parser("scope")
    claims_scope.add_argument("claim_id")
    claims_scope.add_argument("--type", dest="scope_type", required=True)
    claims_scope.add_argument("--applies-when")
    claims_scope.add_argument("--valid-from")
    claims_scope.add_argument("--valid-to")
    claims_scope.add_argument("--reason", required=True)
    claims_scope.add_argument("--db", default="./aletheia.db")
    claims_history = claim_subparsers.add_parser("history")
    claims_history.add_argument("claim_id")
    claims_history.add_argument("--db", default="./aletheia.db")
    claims_history.add_argument("--json", action="store_true")

    confidence = subparsers.add_parser("confidence", help="Inspect M2 confidence.")
    confidence_subparsers = confidence.add_subparsers(
        dest="confidence_command", required=True
    )
    confidence_show = confidence_subparsers.add_parser("show")
    confidence_show.add_argument("claim_id")
    confidence_show.add_argument("--db", default="./aletheia.db")
    confidence_show.add_argument("--explain", action="store_true")
    confidence_recompute = confidence_subparsers.add_parser("recompute")
    _add_db_namespace(confidence_recompute)
    confidence_recompute.add_argument("--type", dest="memory_type", action="append")
    confidence_policy = confidence_subparsers.add_parser("policy")
    policy_subparsers = confidence_policy.add_subparsers(
        dest="policy_command", required=True
    )
    policy_list = policy_subparsers.add_parser("list")
    _add_db_namespace(policy_list)
    policy_list.add_argument("--type", dest="memory_type")
    policy_set = policy_subparsers.add_parser("set")
    _add_db_namespace(policy_set)
    policy_set.add_argument("--memory-type")
    policy_set.add_argument("--predicate")
    policy_set.add_argument("--half-life-days", type=float, required=True)
    policy_set.add_argument("--reason", required=True)

    decay = subparsers.add_parser("decay", help="Preview or persist confidence decay.")
    decay_subparsers = decay.add_subparsers(dest="decay_command", required=True)
    decay_preview = decay_subparsers.add_parser("preview")
    _add_db_namespace(decay_preview)
    decay_preview.add_argument("--type", dest="memory_type", action="append")
    decay_run = decay_subparsers.add_parser("run")
    _add_db_namespace(decay_run)
    decay_run.add_argument("--type", dest="memory_type", action="append")

    curate = subparsers.add_parser("curate", help="Run deterministic curation.")
    curate_subparsers = curate.add_subparsers(dest="curate_command", required=True)
    curate_preview = curate_subparsers.add_parser("preview")
    _add_db_namespace(curate_preview)
    curate_preview.add_argument("--type", dest="memory_type", action="append")
    curate_preview.add_argument("--max-decisions", type=int)
    curate_apply = curate_subparsers.add_parser("apply")
    _add_db_namespace(curate_apply)
    curate_apply.add_argument("--type", dest="memory_type", action="append")
    curate_apply.add_argument("--max-decisions", type=int)

    conflicts = subparsers.add_parser("conflicts", help="Inspect and resolve conflicts.")
    conflict_subparsers = conflicts.add_subparsers(
        dest="conflicts_command", required=True
    )
    conflicts_detect = conflict_subparsers.add_parser("detect")
    _add_db_namespace(conflicts_detect)
    conflicts_detect.add_argument("--subject")
    conflicts_detect.add_argument("--predicate")
    conflicts_detect.add_argument("--include-resolved", action="store_true")
    conflicts_list = conflict_subparsers.add_parser("list")
    _add_db_namespace(conflicts_list)
    conflicts_list.add_argument("--status")
    conflicts_show = conflict_subparsers.add_parser("show")
    conflicts_show.add_argument("conflict_id")
    conflicts_show.add_argument("--db", default="./aletheia.db")
    conflicts_resolve = conflict_subparsers.add_parser("resolve")
    conflicts_resolve.add_argument("conflict_id")
    conflicts_resolve.add_argument("--active")
    conflicts_resolve.add_argument("--strategy", default="manual")
    conflicts_resolve.add_argument("--superseded", nargs="*")
    conflicts_resolve.add_argument("--rejected", nargs="*")
    conflicts_resolve.add_argument("--scoped-json")
    conflicts_resolve.add_argument("--note")
    conflicts_resolve.add_argument("--db", default="./aletheia.db")

    infer = subparsers.add_parser("infer", help="Run and review reasoned memory inferences.")
    infer_subparsers = infer.add_subparsers(dest="infer_command", required=True)
    infer_run = infer_subparsers.add_parser("run")
    _add_db_namespace(infer_run)
    infer_run.add_argument("--engines", default="logical,semantic,factual")
    infer_run.add_argument("--project")
    infer_run.add_argument("--session")
    infer_run.add_argument("--claim", action="append", dest="claims")
    infer_run.add_argument("--evidence", action="append", dest="evidence")
    infer_run.add_argument("--rule", action="append", dest="rules")
    infer_run.add_argument("--max", type=int, dest="max_inferences")
    infer_run.add_argument("--apply", action="store_true")
    infer_run.add_argument("--json", action="store_true")
    infer_list = infer_subparsers.add_parser("list")
    _add_db_namespace(infer_list)
    infer_list.add_argument("--status")
    infer_list.add_argument("--type", dest="inference_type")
    infer_list.add_argument("--engine")
    infer_list.add_argument("--project")
    infer_list.add_argument("--source-claim")
    infer_list.add_argument("--json", action="store_true")
    infer_show = infer_subparsers.add_parser("show")
    infer_show.add_argument("inference_id")
    infer_show.add_argument("--db", default="./aletheia.db")
    infer_show.add_argument("--json", action="store_true")
    infer_review = infer_subparsers.add_parser("review")
    infer_review.add_argument("inference_id")
    infer_review.add_argument("--db", default="./aletheia.db")
    infer_review.add_argument("--decision", required=True)
    infer_review.add_argument("--reason", required=True)
    infer_review.add_argument("--reviewer", default="user")
    infer_promote = infer_subparsers.add_parser("promote")
    infer_promote.add_argument("inference_id")
    infer_promote.add_argument("--db", default="./aletheia.db")
    infer_promote.add_argument("--target-type", default="claim")
    infer_promote.add_argument("--to", default="active")
    infer_promote.add_argument("--reason", required=True)
    infer_promote.add_argument("--reviewer", default="user")
    infer_promote.add_argument("--force", action="store_true")
    infer_reject = infer_subparsers.add_parser("reject")
    infer_reject.add_argument("inference_id")
    infer_reject.add_argument("--db", default="./aletheia.db")
    infer_reject.add_argument("--reason", required=True)
    infer_reject.add_argument("--reviewer", default="user")
    infer_explain = infer_subparsers.add_parser("explain")
    infer_explain.add_argument("inference_id")
    infer_explain.add_argument("--db", default="./aletheia.db")
    infer_explain.add_argument("--json", action="store_true")

    rules = subparsers.add_parser("rules", help="Register and run inference rules.")
    rule_subparsers = rules.add_subparsers(dest="rules_command", required=True)
    rules_list = rule_subparsers.add_parser("list")
    _add_db_namespace(rules_list)
    rules_list.add_argument("--enabled", choices=["true", "false"])
    rules_list.add_argument("--json", action="store_true")
    rules_define = rule_subparsers.add_parser("define")
    _add_db_namespace(rules_define)
    rules_define.add_argument("--name", required=True)
    rules_define.add_argument("--type", dest="rule_type", required=True)
    rules_define.add_argument("--description", required=True)
    rules_define.add_argument("--condition-json", default="{}")
    rules_define.add_argument("--conclusion-json", default="{}")
    rules_define.add_argument("--confidence-json", default="{}")
    rules_define.add_argument("--disabled", action="store_true")
    rules_enable = rule_subparsers.add_parser("enable")
    rules_enable.add_argument("rule_id")
    rules_enable.add_argument("--db", default="./aletheia.db")
    rules_disable = rule_subparsers.add_parser("disable")
    rules_disable.add_argument("rule_id")
    rules_disable.add_argument("--db", default="./aletheia.db")
    rules_run = rule_subparsers.add_parser("run")
    _add_db_namespace(rules_run)
    rules_run.add_argument("rule_id")
    rules_run.add_argument("--claim", action="append", dest="claims")
    rules_run.add_argument("--apply", action="store_true")
    rules_run.add_argument("--json", action="store_true")

    reflect = subparsers.add_parser("reflect", help="Build and expand source-backed reflections.")
    reflect_subparsers = reflect.add_subparsers(dest="reflect_command", required=True)
    reflect_build = reflect_subparsers.add_parser("build")
    _add_db_namespace(reflect_build)
    reflect_build.add_argument("--title", required=True)
    reflect_build.add_argument("--text")
    reflect_build.add_argument("--claims")
    reflect_build.add_argument("--evidence")
    reflect_build.add_argument("--reflections")
    reflect_build.add_argument("--level", type=int, default=2)
    reflect_build.add_argument("--project")
    reflect_build.add_argument("--reason", required=True)
    reflect_build.add_argument("--builder", default="manual")
    reflect_build.add_argument("--candidate", action="store_true")
    reflect_build.add_argument("--json", action="store_true")
    reflect_expand = reflect_subparsers.add_parser("expand")
    reflect_expand.add_argument("reflection_id")
    reflect_expand.add_argument("--db", default="./aletheia.db")
    reflect_expand.add_argument("--json", action="store_true")
    reflect_list = reflect_subparsers.add_parser("list")
    _add_db_namespace(reflect_list)
    reflect_list.add_argument("--status")
    reflect_list.add_argument("--project")
    reflect_list.add_argument("--json", action="store_true")

    derivation = subparsers.add_parser("derivation", help="Inspect and invalidate derivation lineage.")
    derivation_subparsers = derivation.add_subparsers(dest="derivation_command", required=True)
    derivation_trace = derivation_subparsers.add_parser("trace")
    derivation_trace.add_argument("target_id")
    derivation_trace.add_argument("--type", dest="target_type", required=True)
    derivation_trace.add_argument("--db", default="./aletheia.db")
    derivation_trace.add_argument("--json", action="store_true")
    derivation_invalidated = derivation_subparsers.add_parser("invalidated")
    _add_db_namespace(derivation_invalidated)
    derivation_invalidated.add_argument("--target")
    derivation_invalidated.add_argument("--type", dest="target_type")
    derivation_invalidated.add_argument("--json", action="store_true")
    derivation_invalidate = derivation_subparsers.add_parser("invalidate")
    _add_db_namespace(derivation_invalidate)
    derivation_invalidate.add_argument("source_id")
    derivation_invalidate.add_argument("--source-type", required=True)
    derivation_invalidate.add_argument("--reason", required=True)
    derivation_invalidate.add_argument("--mode", default="mark_stale")
    derivation_invalidate.add_argument("--json", action="store_true")

    clusters = subparsers.add_parser("clusters", help="Build and inspect semantic clusters.")
    cluster_subparsers = clusters.add_subparsers(dest="clusters_command", required=True)
    clusters_build = cluster_subparsers.add_parser("build")
    _add_db_namespace(clusters_build)
    clusters_build.add_argument("--target", default="claims")
    clusters_build.add_argument("--json", action="store_true")
    clusters_list = cluster_subparsers.add_parser("list")
    _add_db_namespace(clusters_list)
    clusters_list.add_argument("--json", action="store_true")
    clusters_show = cluster_subparsers.add_parser("show")
    clusters_show.add_argument("cluster_id")
    clusters_show.add_argument("--db", default="./aletheia.db")
    clusters_relations = cluster_subparsers.add_parser("relations")
    _add_db_namespace(clusters_relations)
    clusters_relations.add_argument("--source-id")
    clusters_relations.add_argument("--json", action="store_true")

    abstractions = subparsers.add_parser("abstractions", help="Create and inspect lossless abstractions.")
    abstraction_subparsers = abstractions.add_subparsers(dest="abstractions_command", required=True)
    abstractions_create = abstraction_subparsers.add_parser("create")
    _add_db_namespace(abstractions_create)
    abstractions_create.add_argument("--sources", required=True)
    abstractions_create.add_argument("--source-type", required=True)
    abstractions_create.add_argument("--text", required=True)
    abstractions_create.add_argument("--level", type=int, required=True)
    abstractions_create.add_argument("--policy", default="lossless_via_backlinks")
    abstractions_create.add_argument("--reason", required=True)
    abstractions_create.add_argument("--json", action="store_true")
    abstractions_list = abstraction_subparsers.add_parser("list")
    _add_db_namespace(abstractions_list)
    abstractions_list.add_argument("--status")
    abstractions_list.add_argument("--json", action="store_true")
    abstractions_show = abstraction_subparsers.add_parser("show")
    abstractions_show.add_argument("abstraction_id")
    abstractions_show.add_argument("--db", default="./aletheia.db")
    abstractions_show.add_argument("--json", action="store_true")

    usage = subparsers.add_parser("usage", help="Inspect M5 usage events.")
    usage_subparsers = usage.add_subparsers(dest="usage_command", required=True)
    usage_list = usage_subparsers.add_parser("list")
    _add_db_namespace(usage_list)
    usage_list.add_argument("--target")
    usage_list.add_argument("--type", dest="target_type")
    usage_list.add_argument("--context")
    usage_list.add_argument("--json", action="store_true")
    usage_show = usage_subparsers.add_parser("show")
    usage_show.add_argument("usage_id")
    usage_show.add_argument("--db", default="./aletheia.db")

    outcome = subparsers.add_parser("outcome", help="Record and inspect task outcomes.")
    outcome_subparsers = outcome.add_subparsers(dest="outcome_command", required=True)
    outcome_record = outcome_subparsers.add_parser("record")
    _add_db_namespace(outcome_record)
    outcome_record.add_argument("--task", required=True)
    outcome_record.add_argument("--outcome", required=True)
    outcome_record.add_argument("--context")
    outcome_record.add_argument("--session")
    outcome_record.add_argument("--project")
    outcome_record.add_argument("--user-feedback")
    outcome_record.add_argument("--score", type=float)
    outcome_record.add_argument("--note")
    outcome_list = outcome_subparsers.add_parser("list")
    _add_db_namespace(outcome_list)
    outcome_list.add_argument("--project")

    eval_cmd = subparsers.add_parser("eval", help="Create and run local evaluation sets.")
    eval_subparsers = eval_cmd.add_subparsers(dest="eval_command", required=True)
    eval_create = eval_subparsers.add_parser("create")
    _add_db_namespace(eval_create)
    eval_create.add_argument("--name", required=True)
    eval_create.add_argument("--description")
    eval_create.add_argument("--project")
    eval_add = eval_subparsers.add_parser("add-case")
    eval_add.add_argument("--db", default="./aletheia.db")
    eval_add.add_argument("--set", dest="eval_set_id", required=True)
    eval_add.add_argument("--query", required=True)
    eval_add.add_argument("--expected", action="append")
    eval_add.add_argument("--expected-reflection", action="append")
    eval_add.add_argument("--forbidden", action="append")
    eval_add.add_argument("--project")
    eval_add.add_argument("--session")
    eval_add.add_argument("--tag", action="append", dest="tags")
    eval_add.add_argument("--note")
    eval_run = eval_subparsers.add_parser("run")
    _add_db_namespace(eval_run)
    eval_run.add_argument("--set", dest="eval_set_id", required=True)
    eval_run.add_argument("--mode", choices=["lexical", "semantic", "hybrid"], default="hybrid")
    eval_run.add_argument("--limit", type=int, default=10)
    eval_report = eval_subparsers.add_parser("report")
    eval_report.add_argument("run_id")
    eval_report.add_argument("--db", default="./aletheia.db")
    eval_list = eval_subparsers.add_parser("list")
    _add_db_namespace(eval_list)

    optimize = subparsers.add_parser("optimize", help="Run governed optimization.")
    optimize_subparsers = optimize.add_subparsers(dest="optimize_command", required=True)
    optimize_retrieval = optimize_subparsers.add_parser("retrieval")
    _add_db_namespace(optimize_retrieval)
    optimize_retrieval.add_argument("--eval-set")
    optimize_retrieval.add_argument("--objective", default="balanced")
    optimize_retrieval.add_argument("--dry-run", action="store_true")
    optimize_retrieval.add_argument("--apply-proposal", action="store_true")
    optimize_retrieval.add_argument("--max-trials", type=int, default=50)

    learn = subparsers.add_parser("learn", help="Run governed learning cycles.")
    learn_subparsers = learn.add_subparsers(dest="learn_command", required=True)
    learn_run = learn_subparsers.add_parser("run")
    _add_db_namespace(learn_run)
    learn_run.add_argument("--project")
    learn_run.add_argument("--target", action="append", dest="targets")
    learn_run.add_argument("--targets", dest="targets_csv")
    learn_run.add_argument("--eval-set")
    learn_run.add_argument("--dry-run", action="store_true")
    learn_run.add_argument("--create-proposals", action="store_true")
    learn_run.add_argument("--apply-proposals", action="store_true")
    learn_list = learn_subparsers.add_parser("list")
    _add_db_namespace(learn_list)

    policies = subparsers.add_parser("policies", help="Inspect and apply learned policies.")
    policy_subparsers = policies.add_subparsers(dest="policies_command", required=True)
    policies_list = policy_subparsers.add_parser("list")
    _add_db_namespace(policies_list)
    policies_proposals = policy_subparsers.add_parser("proposals")
    _add_db_namespace(policies_proposals)
    policies_proposals.add_argument("--status")
    policies_proposals.add_argument("--type", dest="policy_type")
    policies_show = policy_subparsers.add_parser("show")
    policies_show.add_argument("proposal_id")
    policies_show.add_argument("--db", default="./aletheia.db")
    policies_approve = policy_subparsers.add_parser("approve")
    policies_approve.add_argument("proposal_id")
    policies_approve.add_argument("--db", default="./aletheia.db")
    policies_approve.add_argument("--reason", required=True)
    policies_reject = policy_subparsers.add_parser("reject")
    policies_reject.add_argument("proposal_id")
    policies_reject.add_argument("--db", default="./aletheia.db")
    policies_reject.add_argument("--reason", required=True)
    policies_apply = policy_subparsers.add_parser("apply")
    policies_apply.add_argument("proposal_id")
    policies_apply.add_argument("--db", default="./aletheia.db")
    policies_apply.add_argument("--reason", required=True)
    policies_apply.add_argument("--force", action="store_true")
    policies_versions = policy_subparsers.add_parser("versions")
    policies_versions.add_argument("--db", default="./aletheia.db")
    policies_versions.add_argument("--policy", default="rpol_default")

    procedures = subparsers.add_parser("procedures", help="Review and version procedure updates.")
    proc_subparsers = procedures.add_subparsers(dest="procedures_command", required=True)
    proc_propose = proc_subparsers.add_parser("propose")
    _add_db_namespace(proc_propose)
    proc_propose.add_argument("--claim")
    proc_propose.add_argument("--title", required=True)
    proc_propose.add_argument("--text", required=True)
    proc_propose.add_argument("--reason", required=True)
    proc_propose.add_argument("--source", action="append", dest="sources")
    proc_propose.add_argument("--source-type")
    proc_propose.add_argument("--eval-run")
    proc_approve = proc_subparsers.add_parser("approve")
    proc_approve.add_argument("proposal_id")
    proc_approve.add_argument("--db", default="./aletheia.db")
    proc_approve.add_argument("--reason", required=True)
    proc_reject = proc_subparsers.add_parser("reject")
    proc_reject.add_argument("proposal_id")
    proc_reject.add_argument("--db", default="./aletheia.db")
    proc_reject.add_argument("--reason", required=True)
    proc_apply = proc_subparsers.add_parser("apply")
    proc_apply.add_argument("proposal_id")
    proc_apply.add_argument("--db", default="./aletheia.db")
    proc_apply.add_argument("--reason", required=True)
    proc_list = proc_subparsers.add_parser("list")
    _add_db_namespace(proc_list)
    proc_list.add_argument("--status")
    proc_versions = proc_subparsers.add_parser("versions")
    _add_db_namespace(proc_versions)
    proc_versions.add_argument("--claim")
    proc_versions.add_argument("--title")

    jobs = subparsers.add_parser("jobs", help="Manage local M5 jobs.")
    jobs_subparsers = jobs.add_subparsers(dest="jobs_command", required=True)
    jobs_enqueue = jobs_subparsers.add_parser("enqueue")
    _add_db_namespace(jobs_enqueue)
    jobs_enqueue.add_argument("--type", dest="job_type", required=True)
    jobs_enqueue.add_argument("--payload-json", default="{}")
    jobs_enqueue.add_argument("--priority", type=float, default=0.5)
    jobs_run = jobs_subparsers.add_parser("run")
    _add_db_namespace(jobs_run)
    jobs_run.add_argument("--type", dest="job_type")
    jobs_run.add_argument("--max", type=int, default=10)
    jobs_list = jobs_subparsers.add_parser("list")
    _add_db_namespace(jobs_list)
    jobs_list.add_argument("--type", dest="job_type")
    jobs_list.add_argument("--status")
    jobs_show = jobs_subparsers.add_parser("show")
    jobs_show.add_argument("job_id")
    jobs_show.add_argument("--db", default="./aletheia.db")

    health = subparsers.add_parser("health", help="Generate memory health reports.")
    health_subparsers = health.add_subparsers(dest="health_command", required=True)
    health_report = health_subparsers.add_parser("report")
    _add_db_namespace(health_report)
    health_report.add_argument("--project")
    health_report.add_argument("--no-recommendations", action="store_true")

    rollback = subparsers.add_parser("rollback", help="Rollback learned behavior.")
    rollback_subparsers = rollback.add_subparsers(dest="rollback_command", required=True)
    rollback_policy = rollback_subparsers.add_parser("policy")
    _add_db_namespace(rollback_policy)
    rollback_policy.add_argument("--policy", required=True)
    rollback_policy.add_argument("--to-version", required=True)
    rollback_policy.add_argument("--reason", required=True)
    rollback_procedure = rollback_subparsers.add_parser("procedure")
    _add_db_namespace(rollback_procedure)
    rollback_procedure.add_argument("--claim")
    rollback_procedure.add_argument("--procedure", dest="claim")
    rollback_procedure.add_argument("--to-version", required=True)
    rollback_procedure.add_argument("--reason", required=True)

    serve = subparsers.add_parser("serve", help="Run the local HTTP daemon.")
    serve.add_argument("--db")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--config")
    serve.add_argument("--auto-migrate", action="store_true")
    serve.add_argument("--no-auth", action="store_true")
    serve.add_argument("--allow-remote", action="store_true")
    serve.add_argument("--with-worker", action="store_true")
    serve.add_argument("--with-console", action="store_true")
    serve.add_argument("--no-console", action="store_true")
    serve.add_argument("--log-level", default="info")

    mcp = subparsers.add_parser("mcp", help="Run MCP-style memory tools over stdio.")
    mcp.add_argument("--db")
    mcp.add_argument("--namespace")
    mcp.add_argument("--mode", choices=["read_only", "read_write_candidate", "read_write_active", "admin"])
    mcp.add_argument("--project")
    mcp.add_argument("--token")
    mcp.add_argument("--config")
    mcp.add_argument("--list-tools", action="store_true")

    auth = subparsers.add_parser("auth", help="Manage API tokens.")
    auth_subparsers = auth.add_subparsers(dest="auth_command", required=True)
    auth_create = auth_subparsers.add_parser("create-token")
    auth_create.add_argument("--db", default="./aletheia.db")
    auth_create.add_argument("--client", required=True)
    auth_create.add_argument("--namespace", action="append", dest="namespaces", required=True)
    auth_create.add_argument("--capabilities")
    auth_create.add_argument("--privacy-ceiling", default="personal")
    auth_create.add_argument("--expires-at")
    auth_list = auth_subparsers.add_parser("list-tokens")
    auth_list.add_argument("--db", default="./aletheia.db")
    auth_list.add_argument("--include-inactive", action="store_true")
    auth_revoke = auth_subparsers.add_parser("revoke-token")
    auth_revoke.add_argument("token_id")
    auth_revoke.add_argument("--db", default="./aletheia.db")
    auth_revoke.add_argument("--reason")

    clients = subparsers.add_parser("clients", help="Manage API clients and agents.")
    clients_subparsers = clients.add_subparsers(dest="clients_command", required=True)
    clients_create = clients_subparsers.add_parser("create")
    clients_create.add_argument("--db", default="./aletheia.db")
    clients_create.add_argument("--name", required=True)
    clients_create.add_argument("--type", dest="client_type", default="agent")
    clients_list = clients_subparsers.add_parser("list")
    clients_list.add_argument("--db", default="./aletheia.db")
    clients_list.add_argument("--include-disabled", action="store_true")
    clients_disable = clients_subparsers.add_parser("disable")
    clients_disable.add_argument("client_id")
    clients_disable.add_argument("--db", default="./aletheia.db")

    api = subparsers.add_parser("api", help="Inspect API schema and service behavior.")
    api_subparsers = api.add_subparsers(dest="api_command", required=True)
    api_openapi = api_subparsers.add_parser("openapi")
    api_openapi.add_argument("--db", default="./aletheia.db")
    api_openapi.add_argument("--output")
    api_routes = api_subparsers.add_parser("routes")
    api_routes.add_argument("--db", default="./aletheia.db")
    api_ping = api_subparsers.add_parser("ping")
    api_ping.add_argument("--url", default="http://127.0.0.1:8765")
    api_ping.add_argument("--db", default="./aletheia.db")

    worker = subparsers.add_parser("worker", help="Run M5 local jobs through the service layer.")
    worker_subparsers = worker.add_subparsers(dest="worker_command", required=True)
    worker_run = worker_subparsers.add_parser("run")
    worker_run.add_argument("--db", default="./aletheia.db")
    worker_run.add_argument("--namespace")
    worker_run.add_argument("--type", dest="job_type")
    worker_run.add_argument("--max-jobs", type=int, default=10)
    worker_watch = worker_subparsers.add_parser("watch")
    worker_watch.add_argument("--db", default="./aletheia.db")
    worker_watch.add_argument("--namespace")
    worker_watch.add_argument("--max-jobs", type=int, default=10)

    service = subparsers.add_parser("service", help="Inspect service logs and status.")
    service_subparsers = service.add_subparsers(dest="service_command", required=True)
    service_status = service_subparsers.add_parser("status")
    service_status.add_argument("--db", default="./aletheia.db")
    service_requests = service_subparsers.add_parser("requests")
    service_requests.add_argument("--db", default="./aletheia.db")
    service_requests.add_argument("--limit", type=int, default=50)
    service_mcp = service_subparsers.add_parser("mcp-log")
    service_mcp.add_argument("--db", default="./aletheia.db")
    service_mcp.add_argument("--limit", type=int, default=50)

    _add_m7_parsers(subparsers)
    _add_m8_parsers(subparsers)
    _add_m9_parsers(subparsers)
    _add_m10_parsers(subparsers)
    return parser


def _add_m10_parsers(subparsers: argparse._SubParsersAction) -> None:
    federation = subparsers.add_parser("federation", help="Manage M10 federation identity and status.")
    federation_sub = federation.add_subparsers(dest="federation_command", required=True)
    federation_init = federation_sub.add_parser("init")
    federation_init.add_argument("--db", default="./aletheia.db")
    federation_init.add_argument("--display-name", required=True)
    federation_init.add_argument("--key-algorithm", default="default")
    federation_init.add_argument("--unprotected", action="store_true")
    federation_status = federation_sub.add_parser("status")
    federation_status.add_argument("--db", default="./aletheia.db")
    federation_export = federation_sub.add_parser("export-identity")
    federation_export.add_argument("--db", default="./aletheia.db")
    federation_export.add_argument("--output")
    federation_rotate = federation_sub.add_parser("rotate-key")
    federation_rotate.add_argument("--db", default="./aletheia.db")
    federation_rotate.add_argument("--reason", required=True)
    federation_rotate.add_argument("--actor", default="user")

    peers = subparsers.add_parser("peers", help="Add, trust, revoke, and inspect federation peers.")
    peers_sub = peers.add_subparsers(dest="peers_command", required=True)
    peers_add = peers_sub.add_parser("add")
    peers_add.add_argument("--db", default="./aletheia.db")
    peers_add.add_argument("--identity", dest="peer_identity_file", required=True)
    peers_add.add_argument("--display-name")
    peers_add.add_argument("--trust-status", default="unknown")
    peers_add.add_argument("--reason", required=True)
    peers_list = peers_sub.add_parser("list")
    peers_list.add_argument("--db", default="./aletheia.db")
    peers_list.add_argument("--include-revoked", action="store_true")
    peers_show = peers_sub.add_parser("show")
    peers_show.add_argument("peer_id")
    peers_show.add_argument("--db", default="./aletheia.db")
    peers_trust = peers_sub.add_parser("trust")
    peers_trust.add_argument("peer_id")
    peers_trust.add_argument("--db", default="./aletheia.db")
    peers_trust.add_argument("--status", dest="trust_status", required=True)
    peers_trust.add_argument("--domain", dest="trust_domain_id")
    peers_trust.add_argument("--reason", required=True)
    peers_trust.add_argument("--actor", default="user")
    peers_revoke = peers_sub.add_parser("revoke")
    peers_revoke.add_argument("peer_id")
    peers_revoke.add_argument("--db", default="./aletheia.db")
    peers_revoke.add_argument("--reason", required=True)
    peers_revoke.add_argument("--actor", default="user")
    peers_revoke.add_argument("--keep-shares", action="store_true")
    peers_domains = peers_sub.add_parser("trust-domains")
    peers_domains.add_argument("--db", default="./aletheia.db")

    shares = subparsers.add_parser("shares", help="Create, export, import, and revoke share grants.")
    shares_sub = shares.add_subparsers(dest="shares_command", required=True)
    shares_create = shares_sub.add_parser("create")
    _add_db_namespace(shares_create)
    shares_create.add_argument("--name", required=True)
    shares_create.add_argument("--peer", action="append", dest="peers")
    shares_create.add_argument("--peers", dest="peers_csv")
    shares_create.add_argument("--permission", action="append", dest="permissions")
    shares_create.add_argument("--permissions", dest="permissions_csv")
    shares_create.add_argument("--type", dest="grant_type", default="read_write_candidate")
    shares_create.add_argument("--privacy-ceiling", default="personal")
    shares_create.add_argument("--memory-types")
    shares_create.add_argument("--statuses")
    shares_create.add_argument("--project")
    shares_create.add_argument("--reason", required=True)
    shares_create.add_argument("--allow-secret", action="store_true")
    shares_create.add_argument("--no-evidence", action="store_true")
    shares_create.add_argument("--no-reflections", action="store_true")
    shares_create.add_argument("--include-inferences", action="store_true")
    shares_create.add_argument("--include-audit", action="store_true")
    shares_create.add_argument("--expires-at")
    shares_list = shares_sub.add_parser("list")
    shares_list.add_argument("--db", default="./aletheia.db")
    shares_list.add_argument("--namespace")
    shares_list.add_argument("--status")
    shares_show = shares_sub.add_parser("show")
    shares_show.add_argument("share_id")
    shares_show.add_argument("--db", default="./aletheia.db")
    shares_recipients = shares_sub.add_parser("recipients")
    shares_recipients.add_argument("share_id")
    shares_recipients.add_argument("--db", default="./aletheia.db")
    shares_export = shares_sub.add_parser("export")
    shares_export.add_argument("share_id")
    shares_export.add_argument("--db", default="./aletheia.db")
    shares_export.add_argument("--output", required=True)
    shares_export.add_argument("--no-encrypt", action="store_true")
    shares_export.add_argument("--redacted", action="store_true")
    shares_import = shares_sub.add_parser("import")
    shares_import.add_argument("--db", default="./aletheia.db")
    shares_import.add_argument("--input", required=True)
    shares_import.add_argument("--trust-policy", default="candidate_only")
    shares_import.add_argument("--dry-run", action="store_true")
    shares_revoke = shares_sub.add_parser("revoke")
    shares_revoke.add_argument("share_id")
    shares_revoke.add_argument("--db", default="./aletheia.db")
    shares_revoke.add_argument("--reason", required=True)
    shares_revoke.add_argument("--actor", default="user")

    sync = subparsers.add_parser("sync", help="Run M10 file-bundle sync and inspect sync state.")
    sync_sub = sync.add_subparsers(dest="sync_command", required=True)
    sync_run = sync_sub.add_parser("run")
    sync_run.add_argument("collection_id")
    sync_run.add_argument("--db", default="./aletheia.db")
    sync_run.add_argument("--peer")
    sync_run.add_argument("--direction", default="bidirectional")
    sync_run.add_argument("--transport", default="file_bundle")
    sync_run.add_argument("--input")
    sync_run.add_argument("--output")
    sync_run.add_argument("--dry-run", action="store_true")
    sync_export = sync_sub.add_parser("export")
    sync_export.add_argument("share_id")
    sync_export.add_argument("--db", default="./aletheia.db")
    sync_export.add_argument("--output", required=True)
    sync_import = sync_sub.add_parser("import")
    sync_import.add_argument("--db", default="./aletheia.db")
    sync_import.add_argument("--input", required=True)
    sync_import.add_argument("--trust-policy", default="candidate_only")
    sync_import.add_argument("--dry-run", action="store_true")
    sync_runs = sync_sub.add_parser("runs")
    sync_runs.add_argument("--db", default="./aletheia.db")
    sync_runs.add_argument("--limit", type=int, default=50)
    sync_collections = sync_sub.add_parser("collections")
    sync_collections.add_argument("--db", default="./aletheia.db")
    sync_collections.add_argument("--status")
    sync_conflicts = sync_sub.add_parser("conflicts")
    sync_conflicts.add_argument("--db", default="./aletheia.db")
    sync_conflicts.add_argument("--namespace")
    sync_conflicts.add_argument("--status")
    sync_resolve = sync_sub.add_parser("resolve")
    sync_resolve.add_argument("conflict_id")
    sync_resolve.add_argument("--db", default="./aletheia.db")
    sync_resolve.add_argument("--strategy", required=True)
    sync_resolve.add_argument("--reason", required=True)
    sync_resolve.add_argument("--actor", default="user")
    sync_cursors = sync_sub.add_parser("cursors")
    sync_cursors.add_argument("--db", default="./aletheia.db")
    sync_sources = sync_sub.add_parser("remote-sources")
    sync_sources.add_argument("--db", default="./aletheia.db")
    sync_sources.add_argument("--local-object-id")
    sync_policies = sync_sub.add_parser("trust-policies")
    sync_policies.add_argument("--db", default="./aletheia.db")

    workspaces = subparsers.add_parser("workspaces", help="Manage M10 workspaces and agent groups.")
    workspaces_sub = workspaces.add_subparsers(dest="workspaces_command", required=True)
    workspaces_create = workspaces_sub.add_parser("create")
    _add_db_namespace(workspaces_create)
    workspaces_create.add_argument("--name", required=True)
    workspaces_create.add_argument("--description")
    workspaces_list = workspaces_sub.add_parser("list")
    _add_db_namespace(workspaces_list)
    workspaces_show = workspaces_sub.add_parser("show")
    workspaces_show.add_argument("workspace_id")
    workspaces_show.add_argument("--db", default="./aletheia.db")
    workspaces_members = workspaces_sub.add_parser("members")
    workspaces_members.add_argument("workspace_id")
    workspaces_members.add_argument("--db", default="./aletheia.db")
    workspaces_add = workspaces_sub.add_parser("add-member")
    workspaces_add.add_argument("workspace_id")
    workspaces_add.add_argument("--db", default="./aletheia.db")
    workspaces_add.add_argument("--member-type", required=True)
    workspaces_add.add_argument("--member-id", required=True)
    workspaces_add.add_argument("--role", required=True)
    workspaces_remove = workspaces_sub.add_parser("remove-member")
    workspaces_remove.add_argument("workspace_id")
    workspaces_remove.add_argument("--db", default="./aletheia.db")
    workspaces_remove.add_argument("--member-id", required=True)
    groups_create = workspaces_sub.add_parser("create-agent-group")
    _add_db_namespace(groups_create)
    groups_create.add_argument("--name", required=True)
    groups_create.add_argument("--description")
    groups_create.add_argument("--capabilities")
    groups_list = workspaces_sub.add_parser("agent-groups")
    _add_db_namespace(groups_list)
    groups_add = workspaces_sub.add_parser("add-agent")
    groups_add.add_argument("group_id")
    groups_add.add_argument("--db", default="./aletheia.db")
    groups_add.add_argument("--agent-id", required=True)
    groups_add.add_argument("--role", default="agent")
    groups_members = workspaces_sub.add_parser("agent-members")
    groups_members.add_argument("group_id")
    groups_members.add_argument("--db", default="./aletheia.db")

    grants = subparsers.add_parser("grants", help="Inspect share grants and consent records.")
    grants_sub = grants.add_subparsers(dest="grants_command", required=True)
    grants_list = grants_sub.add_parser("list")
    grants_list.add_argument("--db", default="./aletheia.db")
    grants_list.add_argument("--namespace")
    grants_list.add_argument("--status")
    grants_show = grants_sub.add_parser("show")
    grants_show.add_argument("share_id")
    grants_show.add_argument("--db", default="./aletheia.db")
    grants_consent = grants_sub.add_parser("consent")
    grants_consent.add_argument("--db", default="./aletheia.db")

    revocations = subparsers.add_parser("revocations", help="Inspect and propagate M10 revocations.")
    revocations_sub = revocations.add_subparsers(dest="revocations_command", required=True)
    revocations_list = revocations_sub.add_parser("list")
    revocations_list.add_argument("--db", default="./aletheia.db")
    revocations_propagate = revocations_sub.add_parser("propagate")
    revocations_propagate.add_argument("--db", default="./aletheia.db")
    revocations_propagate.add_argument("--peer")

    federation_conformance = subparsers.add_parser("federation-conformance", help="Run M10 federation conformance checks.")
    federation_conformance_sub = federation_conformance.add_subparsers(dest="federation_conformance_command", required=True)
    federation_conformance_run = federation_conformance_sub.add_parser("run")
    federation_conformance_run.add_argument("--db", default="./aletheia.db")


def _add_m9_parsers(subparsers: argparse._SubParsersAction) -> None:
    doctor = subparsers.add_parser("doctor", help="Run M9 platform diagnostics.")
    doctor.add_argument("--db", default="./aletheia.db")
    doctor.add_argument("--service-url")
    doctor.add_argument("--service", dest="service_url")

    compatibility = subparsers.add_parser("compatibility", help="Inspect v1 compatibility.")
    compatibility_sub = compatibility.add_subparsers(dest="compatibility_command", required=True)
    compatibility_report = compatibility_sub.add_parser("report")
    compatibility_report.add_argument("--db", default="./aletheia.db")
    compatibility_report.add_argument("--no-plugins", action="store_true")
    compatibility_report.add_argument("--no-sdks", action="store_true")
    compatibility_report.add_argument("--no-runtime", action="store_true")
    compatibility_matrix = compatibility_sub.add_parser("matrix")
    compatibility_matrix.add_argument("--db", default="./aletheia.db")
    compatibility_matrix.add_argument("--type", dest="component_type")
    compatibility_status = compatibility_sub.add_parser("status")
    compatibility_status.add_argument("--db", default="./aletheia.db")
    compatibility_status.add_argument("--type", dest="component_type", required=True)
    compatibility_status.add_argument("--name", dest="component_name", required=True)
    compatibility_status.add_argument("--version", dest="component_version", required=True)
    compatibility_sdks = compatibility_sub.add_parser("sdks")
    compatibility_sdks.add_argument("--db", default="./aletheia.db")
    compatibility_plugins = compatibility_sub.add_parser("plugins")
    compatibility_plugins.add_argument("--db", default="./aletheia.db")
    compatibility_plugins.add_argument("--enabled-only", action="store_true")

    plugins = subparsers.add_parser("plugins", help="Manage governed v1 plugins.")
    plugins_sub = plugins.add_subparsers(dest="plugins_command", required=True)
    plugins_discover = plugins_sub.add_parser("discover")
    plugins_discover.add_argument("path")
    plugins_discover.add_argument("--db", default="./aletheia.db")
    plugins_install = plugins_sub.add_parser("install")
    plugins_install.add_argument("path")
    plugins_install.add_argument("--db", default="./aletheia.db")
    plugins_install.add_argument("--trust-level", default="local")
    plugins_install.add_argument("--approve-permissions", action="store_true")
    plugins_enable = plugins_sub.add_parser("enable")
    plugins_enable.add_argument("plugin_id")
    plugins_enable.add_argument("--db", default="./aletheia.db")
    plugins_enable.add_argument("--reason", required=True)
    plugins_enable.add_argument("--permission", action="append", dest="permissions")
    plugins_enable.add_argument("--permissions", dest="permissions_csv")
    plugins_disable = plugins_sub.add_parser("disable")
    plugins_disable.add_argument("plugin_id")
    plugins_disable.add_argument("--db", default="./aletheia.db")
    plugins_disable.add_argument("--reason", required=True)
    plugins_list = plugins_sub.add_parser("list")
    plugins_list.add_argument("--db", default="./aletheia.db")
    plugins_list.add_argument("--enabled-only", action="store_true")
    plugins_show = plugins_sub.add_parser("show")
    plugins_show.add_argument("plugin_id")
    plugins_show.add_argument("--db", default="./aletheia.db")
    plugins_logs = plugins_sub.add_parser("logs")
    plugins_logs.add_argument("plugin_id", nargs="?")
    plugins_logs.add_argument("--db", default="./aletheia.db")
    plugins_logs.add_argument("--plugin")
    plugins_logs.add_argument("--limit", type=int, default=50)
    plugins_run = plugins_sub.add_parser("run")
    plugins_run.add_argument("plugin_id")
    plugins_run.add_argument("--db", default="./aletheia.db")
    plugins_run.add_argument("--namespace", default="user/default")
    plugins_run.add_argument("--operation", required=True)
    plugins_run.add_argument("--payload-json", default="{}")

    conformance = subparsers.add_parser("conformance", help="Run v1 conformance suites.")
    conformance_sub = conformance.add_subparsers(dest="conformance_command", required=True)
    conformance_list = conformance_sub.add_parser("list")
    conformance_list.add_argument("--db", default="./aletheia.db")
    conformance_run = conformance_sub.add_parser("run")
    conformance_run.add_argument("--db", default="./aletheia.db")
    conformance_run.add_argument("--suite")
    conformance_run.add_argument("--target")
    conformance_run.add_argument("--target-type")
    conformance_run.add_argument("--plugin")
    conformance_run.add_argument("--url")
    conformance_run.add_argument("--fail-fast", action="store_true")
    conformance_report = conformance_sub.add_parser("report")
    conformance_report.add_argument("run_id", nargs="?")
    conformance_report.add_argument("--db", default="./aletheia.db")
    conformance_report.add_argument("--run")
    conformance_report.add_argument("--limit", type=int, default=20)

    adapters = subparsers.add_parser("adapters", help="Scaffold and certify agent adapters.")
    adapters_sub = adapters.add_subparsers(dest="adapters_command", required=True)
    adapters_scaffold = adapters_sub.add_parser("scaffold")
    adapters_scaffold.add_argument("--db", default="./aletheia.db")
    adapters_scaffold.add_argument("--type", dest="adapter_type", choices=["generic-http", "mcp-client", "python-sdk"], default="generic-http")
    adapters_scaffold.add_argument("--name", required=True)
    adapters_scaffold.add_argument("--output", required=True)
    adapters_test = adapters_sub.add_parser("test")
    adapters_test.add_argument("path", nargs="?")
    adapters_test.add_argument("--path", dest="path_option")
    adapters_test.add_argument("--db", default="./aletheia.db")
    adapters_certify = adapters_sub.add_parser("certify")
    adapters_certify.add_argument("path", nargs="?")
    adapters_certify.add_argument("--path", dest="path_option")
    adapters_certify.add_argument("--db", default="./aletheia.db")
    adapters_certify.add_argument("--type", dest="adapter_type", default="generic-http")
    adapters_list = adapters_sub.add_parser("list")
    adapters_list.add_argument("--db", default="./aletheia.db")

    docs = subparsers.add_parser("docs", help="Build and validate v1 documentation.")
    docs_sub = docs.add_subparsers(dest="docs_command", required=True)
    docs_build = docs_sub.add_parser("build")
    docs_build.add_argument("--db", default="./aletheia.db")
    docs_build.add_argument("--output", required=True)
    docs_build.add_argument("--no-api-reference", action="store_true")
    docs_build.add_argument("--no-cli-reference", action="store_true")
    docs_build.add_argument("--no-validate-examples", action="store_true")
    docs_status = docs_sub.add_parser("status")
    docs_status.add_argument("--db", default="./aletheia.db")
    docs_test = docs_sub.add_parser("test-examples")
    docs_test.add_argument("--db", default="./aletheia.db")
    docs_open = docs_sub.add_parser("open")
    docs_open.add_argument("--db", default="./aletheia.db")
    docs_list = docs_sub.add_parser("list")
    docs_list.add_argument("--json", action="store_true")
    docs_path = docs_sub.add_parser("path")
    docs_path.add_argument("document", nargs="?")
    docs_show = docs_sub.add_parser("show")
    docs_show.add_argument("document", nargs="?", default="index")

    examples = subparsers.add_parser("examples", help="Manage example projects.")
    examples_sub = examples.add_subparsers(dest="examples_command", required=True)
    examples_list = examples_sub.add_parser("list")
    examples_list.add_argument("--db", default="./aletheia.db")
    examples_create = examples_sub.add_parser("create")
    examples_create.add_argument("--db", default="./aletheia.db")
    examples_create.add_argument("--type", dest="example_type", choices=["generic-http", "mcp-client", "python-sdk"], default="generic-http")
    examples_create.add_argument("--name", required=True)
    examples_create.add_argument("--output", required=True)
    examples_test = examples_sub.add_parser("test")
    examples_test.add_argument("--db", default="./aletheia.db")

    contracts = subparsers.add_parser("contracts", help="Inspect v1 public contracts.")
    contracts_sub = contracts.add_subparsers(dest="contracts_command", required=True)
    contracts_list = contracts_sub.add_parser("list")
    contracts_list.add_argument("--db", default="./aletheia.db")
    contracts_list.add_argument("--type", dest="contract_type")
    contracts_list.add_argument("--stability")
    contracts_show = contracts_sub.add_parser("show")
    contracts_show.add_argument("contract")
    contracts_show.add_argument("--db", default="./aletheia.db")
    contracts_register = contracts_sub.add_parser("register")
    contracts_register.add_argument("--db", default="./aletheia.db")
    contracts_register.add_argument("--type", dest="contract_type", required=True)
    contracts_register.add_argument("--name", required=True)
    contracts_register.add_argument("--version", required=True)
    contracts_register.add_argument("--stability", default="stable")
    contracts_register.add_argument("--schema-ref")
    contracts_register.add_argument("--documentation-ref")
    contracts_register.add_argument("--metadata-json")

    deprecations = subparsers.add_parser("deprecations", help="Inspect deprecation policy.")
    deprecations_sub = deprecations.add_subparsers(dest="deprecations_command", required=True)
    deprecations_list = deprecations_sub.add_parser("list")
    deprecations_list.add_argument("--db", default="./aletheia.db")
    deprecations_list.add_argument("--target-type")
    deprecations_check = deprecations_sub.add_parser("check")
    deprecations_check.add_argument("--db", default="./aletheia.db")

    v1_gate = subparsers.add_parser("v1-gate", help="Run the v1 release gate.")
    v1_gate_sub = v1_gate.add_subparsers(dest="v1_gate_command", required=True)
    v1_gate_run = v1_gate_sub.add_parser("run")
    v1_gate_run.add_argument("--db", default="./aletheia.db")
    v1_gate_run.add_argument("--no-conformance", action="store_true")
    v1_gate_run.add_argument("--no-docs", action="store_true")
    v1_gate_run.add_argument("--external-telemetry-enabled", action="store_true")
    v1_gate_report = v1_gate_sub.add_parser("report")
    v1_gate_report.add_argument("run_id", nargs="?")
    v1_gate_report.add_argument("--db", default="./aletheia.db")
    v1_gate_report.add_argument("--run")
    v1_gate_report.add_argument("--limit", type=int, default=20)


def _add_m8_parsers(subparsers: argparse._SubParsersAction) -> None:
    backup = subparsers.add_parser("backup", help="Create, verify, and inspect M8 backup archives.")
    backup_sub = backup.add_subparsers(dest="backup_command", required=True)
    backup_create = backup_sub.add_parser("create")
    _add_db_namespace(backup_create)
    backup_create.add_argument("--output", required=True)
    backup_create.add_argument("--type", dest="backup_type", choices=["physical", "logical", "hybrid"], default="physical")
    backup_create.add_argument("--encrypt", action="store_true")
    backup_create.add_argument("--passphrase")
    backup_create.add_argument("--key-id")
    backup_create.add_argument("--privacy-mode", default="full")
    backup_create.add_argument("--no-verify", action="store_true")
    backup_verify = backup_sub.add_parser("verify")
    backup_verify.add_argument("path")
    backup_verify.add_argument("--db", default="./aletheia.db")
    backup_verify.add_argument("--passphrase")
    backup_verify.add_argument("--key-id")
    backup_verify.add_argument("--shallow", action="store_true")
    backup_list = backup_sub.add_parser("list")
    backup_list.add_argument("--db", default="./aletheia.db")
    backup_list.add_argument("--limit", type=int, default=20)
    backup_show = backup_sub.add_parser("show")
    backup_show.add_argument("backup_id")
    backup_show.add_argument("--db", default="./aletheia.db")

    restore = subparsers.add_parser("restore", help="Verify and restore M8 backups.")
    restore_sub = restore.add_subparsers(dest="restore_command", required=True)
    restore_verify = restore_sub.add_parser("verify")
    restore_verify.add_argument("backup_path")
    restore_verify.add_argument("--db", default="./aletheia.db")
    restore_verify.add_argument("--passphrase")
    restore_dry = restore_sub.add_parser("dry-run")
    restore_dry.add_argument("backup_path")
    restore_dry.add_argument("--db", default="./aletheia.db")
    restore_dry.add_argument("--target-db", required=True)
    restore_dry.add_argument("--namespace")
    restore_dry.add_argument("--passphrase")
    restore_apply = restore_sub.add_parser("apply")
    restore_apply.add_argument("backup_path")
    restore_apply.add_argument("--db", default="./aletheia.db")
    restore_apply.add_argument("--target-db", required=True)
    restore_apply.add_argument("--mode", choices=["new_database", "overwrite_existing", "in_place"], default="new_database")
    restore_apply.add_argument("--namespace")
    restore_apply.add_argument("--passphrase")
    restore_apply.add_argument("--confirm")
    restore_namespace = restore_sub.add_parser("namespace")
    restore_namespace.add_argument("backup_path")
    restore_namespace.add_argument("--db", default="./aletheia.db")
    restore_namespace.add_argument("--namespace", required=True)
    restore_namespace.add_argument("--passphrase")
    restore_namespace.add_argument("--apply", action="store_true")

    encrypt = subparsers.add_parser("encrypt", help="Inspect and enable protected mode.")
    encrypt_sub = encrypt.add_subparsers(dest="encrypt_command", required=True)
    encrypt_status = encrypt_sub.add_parser("status")
    encrypt_status.add_argument("--db", default="./aletheia.db")
    encrypt_enable = encrypt_sub.add_parser("enable")
    encrypt_enable.add_argument("--db", default="./aletheia.db")
    encrypt_enable.add_argument("--protected", action="store_true")
    encrypt_enable.add_argument("--actor", default="cli")

    keys = subparsers.add_parser("keys", help="Manage M8 encryption key records.")
    keys_sub = keys.add_subparsers(dest="keys_command", required=True)
    keys_list = keys_sub.add_parser("list")
    keys_list.add_argument("--db", default="./aletheia.db")
    keys_list.add_argument("--include-inactive", action="store_true")
    keys_create = keys_sub.add_parser("create")
    keys_create.add_argument("--db", default="./aletheia.db")
    keys_create.add_argument("--provider", default="passphrase")
    keys_create.add_argument("--label", required=True)
    keys_rotate = keys_sub.add_parser("rotate")
    keys_rotate.add_argument("old_key_id")
    keys_rotate.add_argument("--db", default="./aletheia.db")
    keys_rotate.add_argument("--label", required=True)
    keys_rotate.add_argument("--target", default="content")
    keys_rotate.add_argument("--apply", action="store_true")
    keys_rotate.add_argument("--force", action="store_true")

    redact = subparsers.add_parser("redact", help="Preview or apply redaction.")
    redact_sub = redact.add_subparsers(dest="redact_command", required=True)
    redact_evidence = redact_sub.add_parser("evidence")
    redact_evidence.add_argument("target_id")
    redact_evidence.add_argument("--db", default="./aletheia.db")
    redact_evidence.add_argument("--reason", required=True)
    redact_evidence.add_argument("--replacement", default="[REDACTED]")
    redact_evidence.add_argument("--actor", default="cli")
    redact_evidence.add_argument("--apply", action="store_true")

    forget = subparsers.add_parser("forget", help="Preview or apply tombstone/delete requests.")
    forget_sub = forget.add_subparsers(dest="forget_command", required=True)
    for name in ("preview", "apply"):
        forget_parser = forget_sub.add_parser(name)
        forget_parser.add_argument("--db", default="./aletheia.db")
        forget_parser.add_argument("--namespace")
        forget_parser.add_argument("--claim")
        forget_parser.add_argument("--evidence")
        forget_parser.add_argument("--selector-json")
        forget_parser.add_argument("--mode", default="tombstone")
        forget_parser.add_argument("--reason", required=True)
        forget_parser.add_argument("--actor", default="cli")
        forget_parser.add_argument("--confirm")

    retention = subparsers.add_parser("retention", help="Manage and run retention policies.")
    retention_sub = retention.add_subparsers(dest="retention_command", required=True)
    retention_policy = retention_sub.add_parser("policy")
    retention_policy_sub = retention_policy.add_subparsers(dest="retention_policy_command", required=True)
    retention_policy_create = retention_policy_sub.add_parser("create")
    _add_db_namespace(retention_policy_create)
    retention_policy_create.add_argument("--memory-type")
    retention_policy_create.add_argument("--privacy-level")
    retention_policy_create.add_argument("--source-type")
    retention_policy_create.add_argument("--action", default="queue_review")
    retention_policy_create.add_argument("--after-days", type=int, default=365)
    retention_policy_create.add_argument("--reason", required=True)
    retention_policy_list = retention_policy_sub.add_parser("list")
    _add_db_namespace(retention_policy_list)
    retention_run = retention_sub.add_parser("run")
    _add_db_namespace(retention_run)
    retention_apply = retention_sub.add_parser("apply")
    _add_db_namespace(retention_apply)

    integrity = subparsers.add_parser("integrity", help="Run and repair integrity checks.")
    integrity_sub = integrity.add_subparsers(dest="integrity_command", required=True)
    integrity_check = integrity_sub.add_parser("check")
    _add_db_namespace(integrity_check)
    integrity_check.add_argument("--scope", default="standard")
    integrity_check.add_argument("--deep", action="store_true")
    integrity_repair = integrity_sub.add_parser("repair")
    integrity_repair.add_argument("finding_id")
    integrity_repair.add_argument("--db", default="./aletheia.db")
    integrity_repair.add_argument("--apply", action="store_true")

    compact = subparsers.add_parser("compact", help="Preview or run database compaction.")
    compact_sub = compact.add_subparsers(dest="compact_command", required=True)
    for name in ("preview", "run"):
        compact_parser = compact_sub.add_parser(name)
        compact_parser.add_argument("--db", default="./aletheia.db")
        compact_parser.add_argument("--backup-before", action="store_true")
        compact_parser.add_argument("--passphrase")

    export = subparsers.add_parser("export", help="Export namespace archives.")
    export_sub = export.add_subparsers(dest="export_command", required=True)
    export_namespace = export_sub.add_parser("namespace")
    _add_db_namespace(export_namespace)
    export_namespace.add_argument("--output", required=True)
    export_namespace.add_argument("--format", choices=["alet", "jsonl"], default="alet")
    export_namespace.add_argument("--encrypt", action="store_true")
    export_namespace.add_argument("--privacy-mode", default="redacted")
    export_namespace.add_argument("--passphrase")

    import_cmd = subparsers.add_parser("import", help="Import namespace archives.")
    import_sub = import_cmd.add_subparsers(dest="import_command", required=True)
    for name in ("dry-run", "apply"):
        import_parser = import_sub.add_parser(name)
        import_parser.add_argument("input_path")
        import_parser.add_argument("--db", default="./aletheia.db")
        import_parser.add_argument("--namespace")
        import_parser.add_argument("--passphrase")

    support = subparsers.add_parser("support", help="Create redacted support bundles.")
    support_sub = support.add_subparsers(dest="support_command", required=True)
    support_bundle = support_sub.add_parser("bundle")
    support_bundle.add_argument("--db", default="./aletheia.db")
    support_bundle.add_argument("--output", required=True)
    support_bundle.add_argument("--encrypt", action="store_true")
    support_bundle.add_argument("--include-raw-content", action="store_true")
    support_bundle.add_argument("--passphrase")

    benchmark = subparsers.add_parser("benchmark", help="Run and compare benchmark profiles.")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run = benchmark_sub.add_parser("run")
    benchmark_run.add_argument("--db", default="./aletheia.db")
    benchmark_run.add_argument("--profile", choices=["tiny", "small", "medium", "large"], default="tiny")
    benchmark_compare = benchmark_sub.add_parser("compare")
    benchmark_compare.add_argument("--db", default="./aletheia.db")
    benchmark_compare.add_argument("--limit", type=int, default=2)

    release = subparsers.add_parser("release", help="Check and write release manifests.")
    release_sub = release.add_subparsers(dest="release_command", required=True)
    release_check = release_sub.add_parser("check")
    release_check.add_argument("--db", default="./aletheia.db")
    release_manifest = release_sub.add_parser("manifest")
    release_manifest.add_argument("--db", default="./aletheia.db")
    release_manifest.add_argument("--output")

    readiness = subparsers.add_parser("readiness", help="Run production readiness checks.")
    readiness_sub = readiness.add_subparsers(dest="readiness_command", required=True)
    readiness_check = readiness_sub.add_parser("check")
    _add_db_namespace(readiness_check)
    readiness_check.add_argument("--profile", default="local_production")


def _add_m7_parsers(subparsers: argparse._SubParsersAction) -> None:
    console = subparsers.add_parser("console", help="Run and administer the M7 operational console.")
    console_subparsers = console.add_subparsers(dest="console_command", required=True)
    console_serve = console_subparsers.add_parser("serve", help="Run the HTTP daemon with /console enabled.")
    console_serve.add_argument("--db")
    console_serve.add_argument("--host")
    console_serve.add_argument("--port", type=int)
    console_serve.add_argument("--config")
    console_serve.add_argument("--auto-migrate", action="store_true")
    console_serve.add_argument("--no-auth", action="store_true")
    console_serve.add_argument("--allow-remote", action="store_true")
    console_serve.add_argument("--with-worker", action="store_true")
    console_serve.add_argument("--open-browser", action="store_true")
    console_token = console_subparsers.add_parser("login-token", help="Create a one-time console login token.")
    console_token.add_argument("--db", default="./aletheia.db")
    console_token.add_argument("--namespace", action="append", dest="namespaces")
    console_token.add_argument("--capabilities")
    console_token.add_argument("--privacy-ceiling", default="personal")
    console_token.add_argument("--expires-minutes", type=int, default=30)
    console_token.add_argument("--actor", default="cli")
    console_sessions = console_subparsers.add_parser("sessions", help="List console sessions.")
    console_sessions.add_argument("--db", default="./aletheia.db")
    console_sessions.add_argument("--include-revoked", action="store_true")
    console_revoke = console_subparsers.add_parser("revoke-session", help="Revoke a console session.")
    console_revoke.add_argument("session_id")
    console_revoke.add_argument("--db", default="./aletheia.db")

    reviews = subparsers.add_parser("reviews", help="Inspect and resolve M7 review tasks.")
    review_subparsers = reviews.add_subparsers(dest="reviews_command", required=True)
    reviews_list = review_subparsers.add_parser("list")
    _add_db_namespace(reviews_list)
    reviews_list.add_argument("--status")
    reviews_list.add_argument("--type", dest="task_type")
    reviews_list.add_argument("--severity")
    reviews_list.add_argument("--limit", type=int, default=50)
    reviews_show = review_subparsers.add_parser("show")
    reviews_show.add_argument("task_id")
    reviews_show.add_argument("--db", default="./aletheia.db")
    reviews_generate = review_subparsers.add_parser("generate")
    _add_db_namespace(reviews_generate)
    reviews_resolve = review_subparsers.add_parser("resolve")
    reviews_resolve.add_argument("task_id")
    reviews_resolve.add_argument("--db", default="./aletheia.db")
    reviews_resolve.add_argument("--reason", required=True)
    reviews_resolve.add_argument("--resolution", default="resolved")
    reviews_resolve.add_argument("--actor", default="cli")
    reviews_dismiss = review_subparsers.add_parser("dismiss")
    reviews_dismiss.add_argument("task_id")
    reviews_dismiss.add_argument("--db", default="./aletheia.db")
    reviews_dismiss.add_argument("--reason", required=True)
    reviews_dismiss.add_argument("--actor", default="cli")
    reviews_defer = review_subparsers.add_parser("defer")
    reviews_defer.add_argument("task_id")
    reviews_defer.add_argument("--db", default="./aletheia.db")
    reviews_defer.add_argument("--reason", required=True)
    reviews_defer.add_argument("--actor", default="cli")

    metrics = subparsers.add_parser("metrics", help="Capture and inspect M7 metric snapshots.")
    metric_subparsers = metrics.add_subparsers(dest="metrics_command", required=True)
    metrics_snapshot = metric_subparsers.add_parser("snapshot")
    _add_db_namespace(metrics_snapshot)
    metrics_snapshot.add_argument("--project")
    metrics_snapshot.add_argument("--source", default="cli")
    metrics_latest = metric_subparsers.add_parser("latest")
    _add_db_namespace(metrics_latest)
    metrics_list = metric_subparsers.add_parser("list")
    _add_db_namespace(metrics_list)
    metrics_list.add_argument("--limit", type=int, default=20)

    traces = subparsers.add_parser("traces", help="Run and inspect retrieval/context traces.")
    trace_subparsers = traces.add_subparsers(dest="traces_command", required=True)
    traces_retrieval = trace_subparsers.add_parser("retrieval")
    _add_db_namespace(traces_retrieval)
    traces_retrieval.add_argument("--query", required=True)
    traces_retrieval.add_argument("--mode", default="hybrid")
    traces_retrieval.add_argument("--project")
    traces_retrieval.add_argument("--session")
    traces_retrieval.add_argument("--limit", type=int, default=10)
    traces_context = trace_subparsers.add_parser("context")
    _add_db_namespace(traces_context)
    traces_context.add_argument("--query", required=True)
    traces_context.add_argument("--mode", default="hybrid")
    traces_context.add_argument("--project")
    traces_context.add_argument("--session")
    traces_context.add_argument("--budget", type=int, default=2000)
    traces_list = trace_subparsers.add_parser("list")
    _add_db_namespace(traces_list)
    traces_list.add_argument("--type", dest="trace_type")
    traces_list.add_argument("--limit", type=int, default=20)
    traces_show = trace_subparsers.add_parser("show")
    traces_show.add_argument("trace_id")
    traces_show.add_argument("--db", default="./aletheia.db")
    traces_items = trace_subparsers.add_parser("items")
    traces_items.add_argument("trace_id")
    traces_items.add_argument("--db", default="./aletheia.db")

    notifications = subparsers.add_parser("notifications", help="Inspect and manage M7 notifications.")
    notification_subparsers = notifications.add_subparsers(dest="notifications_command", required=True)
    notifications_list = notification_subparsers.add_parser("list")
    _add_db_namespace(notifications_list)
    notifications_list.add_argument("--status")
    notifications_list.add_argument("--limit", type=int, default=50)
    notifications_create = notification_subparsers.add_parser("create")
    _add_db_namespace(notifications_create)
    notifications_create.add_argument("--type", dest="event_type", required=True)
    notifications_create.add_argument("--severity", default="info")
    notifications_create.add_argument("--title", required=True)
    notifications_create.add_argument("--message", required=True)
    notifications_create.add_argument("--target-type")
    notifications_create.add_argument("--target-id")
    notifications_create.add_argument("--metadata-json")
    notifications_dismiss = notification_subparsers.add_parser("dismiss")
    notifications_dismiss.add_argument("notification_id")
    notifications_dismiss.add_argument("--db", default="./aletheia.db")
    notifications_snooze = notification_subparsers.add_parser("snooze")
    notifications_snooze.add_argument("notification_id")
    notifications_snooze.add_argument("--until", required=True)
    notifications_snooze.add_argument("--db", default="./aletheia.db")

    reports = subparsers.add_parser("reports", help="Export M7 operational reports.")
    report_subparsers = reports.add_subparsers(dest="reports_command", required=True)
    reports_export = report_subparsers.add_parser("export")
    reports_export.add_argument("--db", default="./aletheia.db")
    reports_export.add_argument("--namespace")
    reports_export.add_argument("--type", dest="report_type", default="memory_health")
    reports_export.add_argument("--format", choices=["markdown", "json"], default="markdown")
    reports_export.add_argument("--output")
    reports_export.add_argument("--filters-json")
    reports_list = report_subparsers.add_parser("list")
    reports_list.add_argument("--db", default="./aletheia.db")
    reports_list.add_argument("--namespace")
    reports_list.add_argument("--type", dest="report_type")
    reports_list.add_argument("--limit", type=int, default=20)
    reports_show = report_subparsers.add_parser("show")
    reports_show.add_argument("report_id")
    reports_show.add_argument("--db", default="./aletheia.db")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (AletheiaError, ServiceError) as exc:
        parser.exit(1, f"aletheia: error: {exc}\n")


def _run(args: argparse.Namespace) -> int:
    if args.command == "init":
        memory = Memory.open(args.db)
        try:
            if args.protected:
                memory.enable_protected_mode(protected=True, actor="cli")
            print(json.dumps(memory.health(), indent=2))
        finally:
            memory.close()
        return 0
    if args.command == "migrate" and not getattr(args, "migrate_command", None):
        memory = Memory.open(args.db)
        try:
            print(json.dumps(memory.health(), indent=2))
        finally:
            memory.close()
        return 0
    if args.command == "serve":
        return _run_serve(args)
    if args.command == "console" and args.console_command == "serve":
        return _run_console_serve(args)
    if args.command == "mcp":
        return _run_mcp(args)
    if args.command == "docs" and args.docs_command in {"list", "path", "show"}:
        return _run_installed_docs(args)

    memory = Memory.open(args.db, namespace=getattr(args, "namespace", "user/default"))
    try:
        if args.command == "migrate":
            return _run_migrate(memory, args)
        if args.command == "remember":
            claim = memory.remember(
                namespace=args.namespace,
                memory_type=args.memory_type,
                subject=args.subject,
                predicate=args.predicate,
                object=args.object,
                source_type=args.source_type,
                confidence=args.confidence,
                status=args.status,
                importance=args.importance,
                half_life_days=args.half_life_days,
                project_id=args.project,
                session_id=args.session,
            )
            print(_format_claim(claim))
            return 0
        if args.command == "search":
            mode = args.mode
            if args.semantic:
                mode = "semantic"
            if args.hybrid:
                mode = "hybrid"
            filters = {}
            if args.memory_type:
                filters["memory_type"] = args.memory_type
            if args.status:
                filters["statuses"] = [args.status]
            results = memory.retrieve(
                namespace=args.namespace,
                query=args.query,
                mode=mode,
                limit=args.limit,
                memory_types=[args.memory_type] if args.memory_type else None,
                statuses=[args.status] if args.status else None,
                subject=args.subject,
                predicate=args.predicate,
                project_id=args.project,
                session_id=args.session,
                min_confidence=args.min_confidence,
                categories=args.categories,
                semantic_provider=args.semantic_provider,
                include_disputed=args.include_disputed,
                include_archived=args.include_archived,
            )
            if not results:
                print("No memories found.")
            for result in results:
                print(
                    f"[{result.claim_id}] {result.text}\n"
                    f"type: {result.memory_type}\n"
                    f"status: {result.status}\n"
                    f"confidence: {result.confidence_effective:.2f}\n"
                    f"score: {result.score:.3f} ({result.retrieval_mode})\n"
                    f"lexical: {result.lexical_score:.3f} semantic: {result.semantic_score:.3f}\n"
                    f"evidence: {', '.join(result.evidence_ids) or '-'}\n"
                )
            return 0
        if args.command == "context":
            pack = memory.context_pack(
                namespace=args.namespace,
                query=args.query,
                session_id=args.session,
                project_id=args.project,
                token_budget=args.budget,
                retrieval_mode=args.mode,
                include_candidate_warnings=args.include_candidate_warnings,
                include_reflections=not args.no_reflections,
                include_inferences=args.include_inferences,
                include_derivation_metadata=args.include_derivation,
                policy_version_id=args.policy_version,
                record_usage=args.record_usage,
                explain_policy=args.explain_policy,
            )
            if args.json:
                print(json.dumps(pack.to_dict(), indent=2))
            else:
                print(pack.to_markdown())
            return 0
        if args.command == "context-pack":
            pack = memory.context_pack(
                namespace=args.namespace,
                query=args.query,
                session_id=args.session,
                project_id=args.project,
                token_budget=args.token_budget,
                retrieval_mode=args.mode,
                include_candidate_warnings=args.include_candidate_warnings,
                include_reflections=not args.no_reflections,
                include_inferences=args.include_inferences,
                include_derivation_metadata=args.include_derivation,
                policy_version_id=args.policy_version,
                record_usage=args.record_usage,
                explain_policy=args.explain_policy,
            )
            if args.json:
                print(json.dumps(pack.to_dict(), indent=2))
            else:
                print(pack.to_markdown())
            return 0
        if args.command == "audit":
            audit = memory.audit(args.target_id)
            if args.json:
                print(json.dumps(audit, indent=2))
            else:
                print(_format_audit(audit))
            return 0
        if args.command == "feedback":
            memory.feedback(
                namespace=args.namespace,
                target_id=args.target_id,
                target_type=args.target_type,
                signal=args.signal,
                source=args.source,
                evidence_id=args.evidence,
                strength=args.strength,
                note=args.note,
            )
            if args.target_type == "claim":
                print(_format_claim(memory.read_claim(args.target_id)))
            else:
                print(
                    f"Recorded feedback for {args.target_type} {args.target_id}: "
                    f"{args.signal}"
                )
            return 0
        if args.command == "events":
            return _run_events(memory, args)
        if args.command == "ingest":
            return _run_ingest(memory, args)
        if args.command == "extract":
            return _run_extract(memory, args)
        if args.command == "llm":
            return _run_llm(memory, args)
        if args.command == "candidates":
            return _run_candidates(memory, args)
        if args.command == "entities":
            return _run_entities(memory, args)
        if args.command == "categories":
            return _run_categories(memory, args)
        if args.command == "index":
            return _run_index(memory, args)
        if args.command == "sessions":
            return _run_sessions(memory, args)
        if args.command == "projects":
            return _run_projects(memory, args)
        if args.command == "claims":
            return _run_claims(memory, args)
        if args.command == "confidence":
            return _run_confidence(memory, args)
        if args.command == "decay":
            return _run_decay(memory, args)
        if args.command == "curate":
            return _run_curate(memory, args)
        if args.command == "conflicts":
            return _run_conflicts(memory, args)
        if args.command == "infer":
            return _run_infer(memory, args)
        if args.command == "rules":
            return _run_rules(memory, args)
        if args.command == "reflect":
            return _run_reflect(memory, args)
        if args.command == "derivation":
            return _run_derivation(memory, args)
        if args.command == "clusters":
            return _run_clusters(memory, args)
        if args.command == "abstractions":
            return _run_abstractions(memory, args)
        if args.command == "usage":
            return _run_usage(memory, args)
        if args.command == "outcome":
            return _run_outcome(memory, args)
        if args.command == "eval":
            return _run_eval(memory, args)
        if args.command == "optimize":
            return _run_optimize(memory, args)
        if args.command == "learn":
            return _run_learn(memory, args)
        if args.command == "policies":
            return _run_policies(memory, args)
        if args.command == "procedures":
            return _run_procedures(memory, args)
        if args.command == "jobs":
            return _run_jobs(memory, args)
        if args.command == "health":
            return _run_health(memory, args)
        if args.command == "rollback":
            return _run_rollback(memory, args)
        if args.command == "auth":
            return _run_auth(memory, args)
        if args.command == "clients":
            return _run_clients(memory, args)
        if args.command == "api":
            return _run_api(memory, args)
        if args.command == "worker":
            return _run_worker(memory, args)
        if args.command == "service":
            return _run_service(memory, args)
        if args.command == "console":
            return _run_console(memory, args)
        if args.command == "reviews":
            return _run_reviews(memory, args)
        if args.command == "metrics":
            return _run_metrics(memory, args)
        if args.command == "traces":
            return _run_traces(memory, args)
        if args.command == "notifications":
            return _run_notifications(memory, args)
        if args.command == "reports":
            return _run_reports(memory, args)
        if args.command in {
            "backup",
            "restore",
            "encrypt",
            "keys",
            "redact",
            "forget",
            "retention",
            "integrity",
            "compact",
            "export",
            "import",
            "support",
            "benchmark",
            "release",
            "readiness",
        }:
            return _run_m8(memory, args)
        if args.command in {
            "doctor",
            "compatibility",
            "plugins",
            "conformance",
            "adapters",
            "docs",
            "examples",
            "contracts",
            "deprecations",
            "v1-gate",
        }:
            return _run_m9(memory, args)
        if args.command in {
            "federation",
            "peers",
            "shares",
            "sync",
            "workspaces",
            "grants",
            "revocations",
            "federation-conformance",
        }:
            return _run_m10(memory, args)
    finally:
        memory.close()
    return 0


def _run_installed_docs(args: argparse.Namespace) -> int:
    if args.docs_command == "list":
        documents = iter_help_documents()
        if args.json:
            _print_json([document.to_dict() for document in documents])
            return 0
        print(f"Documentation root: {docs_root()}")
        current_category = None
        for document in documents:
            if document.category != current_category:
                current_category = document.category
                print(f"\n{current_category}:")
            print(f"  {document.slug}: {document.title} ({document.filename})")
            print(f"    {document.summary}")
        return 0
    if args.docs_command == "path":
        if args.document:
            try:
                print(find_help_document(args.document).path)
            except KeyError as exc:
                raise AletheiaError(str(exc)) from exc
        else:
            print(docs_root())
        return 0
    if args.docs_command == "show":
        try:
            print(read_help_document(args.document))
        except KeyError as exc:
            raise AletheiaError(str(exc)) from exc
        return 0
    return 0


def _run_m10(memory: Memory, args: argparse.Namespace) -> int:
    if args.command == "federation":
        if args.federation_command == "init":
            _print_json(asdict(memory.create_federation_identity(
                display_name=args.display_name,
                key_algorithm=args.key_algorithm,
                protected=not args.unprotected,
            )))
            return 0
        if args.federation_command == "status":
            _print_json(memory.federation_status())
            return 0
        if args.federation_command == "export-identity":
            _print_json(memory.export_federation_identity(output_path=args.output))
            return 0
        if args.federation_command == "rotate-key":
            _print_json(asdict(memory.rotate_federation_key(reason=args.reason, actor=args.actor)))
            return 0

    if args.command == "peers":
        if args.peers_command == "add":
            _print_json(asdict(memory.add_peer(
                peer_identity_file=args.peer_identity_file,
                display_name=args.display_name,
                trust_status=args.trust_status,
                reason=args.reason,
            )))
            return 0
        if args.peers_command == "list":
            _print_json([asdict(peer) for peer in memory.list_peers(include_revoked=args.include_revoked)])
            return 0
        if args.peers_command == "show":
            _print_json(asdict(memory.get_peer(args.peer_id)))
            return 0
        if args.peers_command == "trust":
            _print_json(asdict(memory.trust_peer(args.peer_id, trust_status=args.trust_status, trust_domain_id=args.trust_domain_id, reason=args.reason, actor=args.actor)))
            return 0
        if args.peers_command == "revoke":
            _print_json(asdict(memory.revoke_peer(args.peer_id, reason=args.reason, actor=args.actor, revoke_shares=not args.keep_shares)))
            return 0
        if args.peers_command == "trust-domains":
            _print_json([asdict(domain) for domain in memory.list_trust_domains()])
            return 0

    if args.command == "shares":
        if args.shares_command == "create":
            peers = [*(args.peers or []), *_split_csv(args.peers_csv)]
            permissions = [*(args.permissions or []), *_split_csv(args.permissions_csv)]
            _print_json(asdict(memory.create_share_grant(
                name=args.name,
                namespace=args.namespace,
                recipient_peer_ids=peers,
                grant_type=args.grant_type,
                permissions=permissions,
                privacy_ceiling=args.privacy_ceiling,
                memory_types=_split_csv(args.memory_types) or None,
                statuses=_split_csv(args.statuses) or None,
                project_id=args.project,
                include_evidence=not args.no_evidence,
                include_reflections=not args.no_reflections,
                include_inferences=args.include_inferences,
                include_audit=args.include_audit,
                expires_at=args.expires_at,
                reason=args.reason,
                allow_secret=args.allow_secret,
            )))
            return 0
        if args.shares_command == "list":
            _print_json([asdict(share) for share in memory.list_share_grants(namespace=args.namespace, status=args.status)])
            return 0
        if args.shares_command == "show":
            _print_json(asdict(memory.get_share_grant(args.share_id)))
            return 0
        if args.shares_command == "recipients":
            _print_json([asdict(recipient) for recipient in memory.list_share_recipients(args.share_id)])
            return 0
        if args.shares_command == "export":
            _print_json(asdict(memory.export_share_bundle(share_id=args.share_id, output_path=args.output, encrypt=not args.no_encrypt, redacted=args.redacted)))
            return 0
        if args.shares_command == "import":
            _print_json(asdict(memory.import_share_bundle(input_path=args.input, trust_policy=args.trust_policy, dry_run=args.dry_run)))
            return 0
        if args.shares_command == "revoke":
            _print_json(asdict(memory.revoke_share_grant(args.share_id, reason=args.reason, actor=args.actor)))
            return 0

    if args.command == "sync":
        if args.sync_command == "run":
            _print_json(asdict(memory.sync(
                collection_id=args.collection_id,
                peer_id=args.peer,
                direction=args.direction,
                transport=args.transport,
                input_path=args.input,
                output_path=args.output,
                dry_run=args.dry_run,
            )))
            return 0
        if args.sync_command == "export":
            _print_json(asdict(memory.export_share_bundle(share_id=args.share_id, output_path=args.output, encrypt=True)))
            return 0
        if args.sync_command == "import":
            _print_json(asdict(memory.import_share_bundle(input_path=args.input, trust_policy=args.trust_policy, dry_run=args.dry_run)))
            return 0
        if args.sync_command == "runs":
            _print_json([asdict(run) for run in memory.list_sync_runs(limit=args.limit)])
            return 0
        if args.sync_command == "collections":
            _print_json([asdict(collection) for collection in memory.list_sync_collections(status=args.status)])
            return 0
        if args.sync_command == "conflicts":
            _print_json([asdict(conflict) for conflict in memory.list_sync_conflicts(namespace=args.namespace, status=args.status)])
            return 0
        if args.sync_command == "resolve":
            _print_json(asdict(memory.resolve_sync_conflict(args.conflict_id, strategy=args.strategy, reason=args.reason, actor=args.actor)))
            return 0
        if args.sync_command == "cursors":
            _print_json([asdict(cursor) for cursor in memory.list_replication_cursors()])
            return 0
        if args.sync_command == "remote-sources":
            _print_json([asdict(source) for source in memory.list_remote_sources(local_object_id=args.local_object_id)])
            return 0
        if args.sync_command == "trust-policies":
            _print_json([asdict(policy) for policy in memory.list_import_trust_policies()])
            return 0

    if args.command == "workspaces":
        if args.workspaces_command == "create":
            _print_json(asdict(memory.create_workspace(namespace=args.namespace, name=args.name, description=args.description)))
            return 0
        if args.workspaces_command == "list":
            _print_json([asdict(workspace) for workspace in memory.list_workspaces(namespace=args.namespace)])
            return 0
        if args.workspaces_command == "show":
            _print_json(asdict(memory.get_workspace(args.workspace_id)))
            return 0
        if args.workspaces_command == "members":
            _print_json([asdict(member) for member in memory.list_workspace_members(args.workspace_id)])
            return 0
        if args.workspaces_command == "add-member":
            _print_json(asdict(memory.add_workspace_member(args.workspace_id, member_type=args.member_type, member_id=args.member_id, role=args.role)))
            return 0
        if args.workspaces_command == "remove-member":
            _print_json(memory.remove_workspace_member(args.workspace_id, member_id=args.member_id))
            return 0
        if args.workspaces_command == "create-agent-group":
            _print_json(asdict(memory.create_agent_group(namespace=args.namespace, name=args.name, description=args.description, default_capabilities=_split_csv(args.capabilities) or None)))
            return 0
        if args.workspaces_command == "agent-groups":
            _print_json([asdict(group) for group in memory.list_agent_groups(namespace=args.namespace)])
            return 0
        if args.workspaces_command == "add-agent":
            _print_json(asdict(memory.add_agent_group_member(args.group_id, agent_id=args.agent_id, role=args.role)))
            return 0
        if args.workspaces_command == "agent-members":
            _print_json([asdict(member) for member in memory.list_agent_group_members(args.group_id)])
            return 0

    if args.command == "grants":
        if args.grants_command == "list":
            _print_json([asdict(share) for share in memory.list_share_grants(namespace=args.namespace, status=args.status)])
            return 0
        if args.grants_command == "show":
            _print_json(asdict(memory.get_share_grant(args.share_id)))
            return 0
        if args.grants_command == "consent":
            _print_json([asdict(record) for record in memory.list_consent_records()])
            return 0

    if args.command == "revocations":
        if args.revocations_command == "list":
            _print_json([asdict(record) for record in memory.list_revocations()])
            return 0
        if args.revocations_command == "propagate":
            _print_json(memory.propagate_revocations(peer_id=args.peer))
            return 0

    if args.command == "federation-conformance":
        if args.federation_conformance_command == "run":
            _print_json(memory.federation_conformance())
            return 0
    return 0


def _run_m9(memory: Memory, args: argparse.Namespace) -> int:
    if args.command == "doctor":
        _print_json(asdict(memory.doctor_run(service_url=args.service_url)))
        return 0

    if args.command == "compatibility":
        if args.compatibility_command == "report":
            _print_json(memory.compatibility_report(
                include_plugins=not args.no_plugins,
                include_sdks=not args.no_sdks,
                include_runtime=not args.no_runtime,
            ))
            return 0
        if args.compatibility_command == "matrix":
            _print_json([asdict(item) for item in memory.list_compatibility_matrix(component_type=args.component_type)])
            return 0
        if args.compatibility_command == "status":
            _print_json(memory.compatibility_status(
                component_type=args.component_type,
                component_name=args.component_name,
                component_version=args.component_version,
            ))
            return 0
        if args.compatibility_command == "sdks":
            _print_json([asdict(item) for item in memory.list_sdk_releases()])
            return 0
        if args.compatibility_command == "plugins":
            _print_json(memory.list_plugins(include_disabled=not args.enabled_only))
            return 0

    if args.command == "plugins":
        if args.plugins_command == "discover":
            _print_json(memory.discover_plugins(args.path))
            return 0
        if args.plugins_command == "install":
            _print_json(asdict(memory.install_plugin(
                plugin_path=args.path,
                trust_level=args.trust_level,
                approve_permissions=args.approve_permissions,
            )))
            return 0
        if args.plugins_command == "enable":
            permissions = list(args.permissions or []) + _split_csv(args.permissions_csv)
            _print_json(asdict(memory.enable_plugin(args.plugin_id, reason=args.reason, approved_permissions=permissions, actor="cli")))
            return 0
        if args.plugins_command == "disable":
            _print_json(asdict(memory.disable_plugin(args.plugin_id, reason=args.reason, actor="cli")))
            return 0
        if args.plugins_command == "list":
            _print_json(memory.list_plugins(include_disabled=not args.enabled_only))
            return 0
        if args.plugins_command == "show":
            installation = memory.get_plugin_installation(args.plugin_id)
            manifest = memory.get_plugin_manifest(installation.plugin_manifest_id)
            _print_json({"installation": asdict(installation), "manifest": asdict(manifest)})
            return 0
        if args.plugins_command == "logs":
            plugin_id = args.plugin_id or args.plugin
            _print_json([asdict(item) for item in memory.list_plugin_logs(plugin_id=plugin_id, limit=args.limit)])
            return 0
        if args.plugins_command == "run":
            _print_json(memory.run_plugin_operation(
                plugin_id=args.plugin_id,
                operation=args.operation,
                namespace=args.namespace,
                payload=json.loads(args.payload_json),
            ))
            return 0

    if args.command == "conformance":
        if args.conformance_command == "list":
            _print_json([
                {**asdict(suite), "cases": [asdict(case) for case in memory.list_conformance_cases(suite.id)]}
                for suite in memory.list_conformance_suites()
            ])
            return 0
        if args.conformance_command == "run":
            suite = args.suite
            target = args.target
            target_type = args.target_type
            if args.plugin:
                suite = suite or "plugin"
                target = target or args.plugin
                target_type = target_type or "plugin"
            if args.url:
                suite = suite or "http-api"
                target = target or args.url
                target_type = target_type or "http_api"
            if not suite:
                raise AletheiaError("conformance run requires --suite, --plugin, or --url.")
            _print_json(asdict(memory.run_conformance(
                suite=suite,
                target=target,
                target_type=target_type,
                fail_fast=args.fail_fast,
                metadata={"source": "cli"},
            )))
            return 0
        if args.conformance_command == "report":
            run_id = args.run_id or args.run
            if run_id:
                _print_json({
                    "run": asdict(memory.get_conformance_run(run_id)),
                    "results": [asdict(item) for item in memory.list_conformance_results(run_id)],
                })
            else:
                _print_json([asdict(item) for item in memory.list_conformance_runs(limit=args.limit)])
            return 0

    if args.command == "adapters":
        if args.adapters_command == "scaffold":
            _print_json(memory.scaffold_adapter(adapter_type=args.adapter_type, name=args.name, output_path=args.output))
            return 0
        if args.adapters_command == "test":
            path = args.path or args.path_option
            if not path:
                raise AletheiaError("adapters test requires a path.")
            run = memory.run_conformance(suite="agent-adapter", target=path, target_type="agent_adapter")
            _print_json({"run": asdict(run), "results": [asdict(item) for item in memory.list_conformance_results(run.id)]})
            return 0
        if args.adapters_command == "certify":
            path = args.path or args.path_option
            if not path:
                raise AletheiaError("adapters certify requires a path.")
            _print_json(asdict(memory.certify_adapter(path=path, adapter_type=args.adapter_type)))
            return 0
        if args.adapters_command == "list":
            _print_json([asdict(item) for item in memory.list_adapter_certifications()])
            return 0

    if args.command == "docs":
        if args.docs_command == "build":
            _print_json(asdict(memory.build_docs(
                output_dir=args.output,
                include_api_reference=not args.no_api_reference,
                include_cli_reference=not args.no_cli_reference,
                validate_examples=not args.no_validate_examples,
            )))
            return 0
        if args.docs_command == "status":
            _print_json(memory.docs_status())
            return 0
        if args.docs_command == "test-examples":
            _print_json(memory.test_doc_examples())
            return 0
        if args.docs_command == "open":
            status = memory.docs_status()
            latest = status.get("latest") or {}
            _print_json({"status": status.get("status"), "path": latest.get("output_path")})
            return 0

    if args.command == "examples":
        if args.examples_command == "list":
            _print_json([asdict(item) for item in memory.list_examples()])
            return 0
        if args.examples_command == "create":
            _print_json(memory.scaffold_adapter(adapter_type=args.example_type, name=args.name, output_path=args.output))
            return 0
        if args.examples_command == "test":
            _print_json(memory.test_doc_examples())
            return 0

    if args.command == "contracts":
        if args.contracts_command == "list":
            _print_json([asdict(item) for item in memory.list_public_contracts(contract_type=args.contract_type, stability=args.stability)])
            return 0
        if args.contracts_command == "show":
            _print_json(asdict(memory.get_public_contract(args.contract)))
            return 0
        if args.contracts_command == "register":
            _print_json(asdict(memory.register_public_contract(
                contract_type=args.contract_type,
                name=args.name,
                version=args.version,
                stability=args.stability,
                schema_ref=args.schema_ref,
                documentation_ref=args.documentation_ref,
                metadata=_json_arg(args.metadata_json),
            )))
            return 0

    if args.command == "deprecations":
        if args.deprecations_command == "list":
            _print_json([asdict(item) for item in memory.list_deprecations(target_type=args.target_type)])
            return 0
        if args.deprecations_command == "check":
            _print_json(memory.check_deprecations())
            return 0

    if args.command == "v1-gate":
        if args.v1_gate_command == "run":
            _print_json(asdict(memory.v1_gate_run(
                auto_run_conformance=not args.no_conformance,
                require_docs=not args.no_docs,
                external_telemetry_enabled=args.external_telemetry_enabled,
                metadata={"source": "cli"},
            )))
            return 0
        if args.v1_gate_command == "report":
            run_id = args.run_id or args.run
            if run_id:
                _print_json(asdict(memory.get_v1_gate_run(run_id)))
            else:
                _print_json([asdict(item) for item in memory.list_v1_gate_runs(limit=args.limit)])
            return 0

    return 0


def _run_migrate(memory: Memory, args: argparse.Namespace) -> int:
    target_kwargs = {"target_version": args.target_version} if getattr(args, "target_version", None) else {}
    if args.migrate_command == "plan":
        _print_json(asdict(memory.migration_plan(**target_kwargs)))
        return 0
    if args.migrate_command == "apply":
        run = memory.migration_apply(
            **target_kwargs,
            dry_run=args.dry_run,
            backup_before=args.backup_before,
            backup_output=args.backup_output,
            passphrase=args.passphrase,
            verify_after=args.verify_after,
        )
        _print_json(asdict(run))
        return 0
    if args.migrate_command == "verify":
        _print_json(asdict(memory.integrity_check(namespace=args.namespace, scope="migration_verify", deep=args.deep)))
        return 0
    return 0


def _run_m8(memory: Memory, args: argparse.Namespace) -> int:
    if args.command == "backup":
        if args.backup_command == "create":
            _print_json(asdict(memory.create_backup(
                output_path=args.output,
                backup_type=args.backup_type,
                namespace=args.namespace,
                encrypt=args.encrypt,
                privacy_mode=args.privacy_mode,
                passphrase=args.passphrase,
                key_id=args.key_id,
                verify_after=not args.no_verify,
                created_by="cli",
            )))
            return 0
        if args.backup_command == "verify":
            _print_json(asdict(memory.verify_backup(
                backup_path=args.path,
                passphrase=args.passphrase,
                key_id=args.key_id,
                deep=not args.shallow,
            )))
            return 0
        if args.backup_command == "list":
            _print_json([asdict(item) for item in memory.list_backups(limit=args.limit)])
            return 0
        if args.backup_command == "show":
            _print_json(asdict(memory.get_backup(args.backup_id)))
            return 0

    if args.command == "restore":
        if args.restore_command == "verify":
            _print_json(asdict(memory.verify_backup(backup_path=args.backup_path, passphrase=args.passphrase)))
            return 0
        if args.restore_command == "dry-run":
            _print_json(asdict(memory.restore_backup(
                backup_path=args.backup_path,
                target_db_path=args.target_db,
                namespace=args.namespace,
                passphrase=args.passphrase,
                dry_run=True,
            )))
            return 0
        if args.restore_command == "apply":
            if args.confirm != "restore backup":
                raise AletheiaError("Restore apply requires --confirm 'restore backup'.")
            _print_json(asdict(memory.restore_backup(
                backup_path=args.backup_path,
                target_db_path=args.target_db,
                mode=args.mode,
                namespace=args.namespace,
                passphrase=args.passphrase,
                dry_run=False,
            )))
            return 0
        if args.restore_command == "namespace":
            _print_json(asdict(memory.import_archive(
                input_path=args.backup_path,
                namespace=args.namespace,
                passphrase=args.passphrase,
                dry_run=not args.apply,
            )))
            return 0

    if args.command == "encrypt":
        if args.encrypt_command == "status":
            _print_json(asdict(memory.protected_mode_status()))
            return 0
        if args.encrypt_command == "enable":
            _print_json(asdict(memory.enable_protected_mode(protected=True, actor=args.actor)))
            return 0

    if args.command == "keys":
        if args.keys_command == "list":
            _print_json([asdict(item) for item in memory.list_keys(include_inactive=args.include_inactive)])
            return 0
        if args.keys_command == "create":
            _print_json(asdict(memory.create_key(provider=args.provider, label=args.label)))
            return 0
        if args.keys_command == "rotate":
            _print_json(asdict(memory.rotate_key(
                old_key_id=args.old_key_id,
                new_key_label=args.label,
                target=args.target,
                dry_run=not args.apply,
                force=args.force,
            )))
            return 0

    if args.command == "redact":
        if args.redact_command == "evidence":
            _print_json(asdict(memory.redact(
                target_id=args.target_id,
                target_type="evidence",
                reason=args.reason,
                replacement_text=args.replacement,
                actor=args.actor,
                dry_run=not args.apply,
            )))
            return 0

    if args.command == "forget":
        selector = _forget_selector_from_args(args)
        _print_json(asdict(memory.forget(
            selector=selector,
            mode=args.mode,
            reason=args.reason,
            actor=args.actor,
            dry_run=args.forget_command == "preview",
            confirmation=args.confirm,
        )))
        return 0

    if args.command == "retention":
        if args.retention_command == "policy" and args.retention_policy_command == "create":
            _print_json(asdict(memory.create_retention_policy(
                namespace=args.namespace,
                memory_type=args.memory_type,
                privacy_level=args.privacy_level,
                source_type=args.source_type,
                action=args.action,
                after_days=args.after_days,
                reason=args.reason,
            )))
            return 0
        if args.retention_command == "policy" and args.retention_policy_command == "list":
            _print_json([asdict(policy) for policy in memory.list_retention_policies(namespace=args.namespace)])
            return 0
        if args.retention_command == "run":
            _print_json(asdict(memory.run_retention(namespace=args.namespace, dry_run=True)))
            return 0
        if args.retention_command == "apply":
            _print_json(asdict(memory.run_retention(namespace=args.namespace, dry_run=False)))
            return 0

    if args.command == "integrity":
        if args.integrity_command == "check":
            _print_json(asdict(memory.integrity_check(namespace=args.namespace, scope=args.scope, deep=args.deep)))
            return 0
        if args.integrity_command == "repair":
            _print_json(asdict(memory.repair_integrity(finding_id=args.finding_id, dry_run=not args.apply)))
            return 0

    if args.command == "compact":
        _print_json(asdict(memory.compact_database(
            dry_run=args.compact_command == "preview",
            backup_before=args.backup_before,
            passphrase=args.passphrase,
        )))
        return 0

    if args.command == "export":
        if args.export_command == "namespace":
            _print_json(asdict(memory.export_archive(
                output_path=args.output,
                namespace=args.namespace,
                format=args.format,
                encrypt=args.encrypt,
                privacy_mode=args.privacy_mode,
                passphrase=args.passphrase,
            )))
            return 0

    if args.command == "import":
        _print_json(asdict(memory.import_archive(
            input_path=args.input_path,
            namespace=args.namespace,
            passphrase=args.passphrase,
            dry_run=args.import_command == "dry-run",
        )))
        return 0

    if args.command == "support":
        if args.support_command == "bundle":
            _print_json(asdict(memory.support_bundle(
                output_path=args.output,
                encrypt=args.encrypt,
                include_raw_content=args.include_raw_content,
                passphrase=args.passphrase,
            )))
            return 0

    if args.command == "benchmark":
        if args.benchmark_command == "run":
            run = memory.benchmark_run(profile=args.profile)
            _print_json({
                "run": asdict(run),
                "results": [asdict(item) for item in memory.list_benchmark_results(run.id)],
            })
            return 0
        if args.benchmark_command == "compare":
            runs = memory.list_benchmarks(limit=args.limit)
            _print_json({
                "runs": [asdict(run) for run in runs],
                "latest_results": [asdict(item) for item in memory.list_benchmark_results(runs[0].id)] if runs else [],
                "status": "insufficient_baseline" if len(runs) < 2 else "comparison_ready",
            })
            return 0

    if args.command == "release":
        if args.release_command == "check":
            _print_json(asdict(memory.release_manifest()))
            return 0
        if args.release_command == "manifest":
            _print_json(asdict(memory.release_manifest(output_path=args.output)))
            return 0

    if args.command == "readiness":
        if args.readiness_command == "check":
            _print_json(asdict(memory.readiness_check(namespace=args.namespace, profile=args.profile)))
            return 0
    return 0


def _forget_selector_from_args(args: argparse.Namespace) -> dict:
    if args.selector_json:
        return json.loads(args.selector_json)
    if args.evidence:
        return {"target_type": "evidence", "target_id": args.evidence}
    if args.claim:
        return {"target_type": "claim", "target_id": args.claim}
    selector = {}
    if args.namespace:
        selector["namespace"] = args.namespace
    return selector


def _run_ingest(memory: Memory, args: argparse.Namespace) -> int:
    if args.ingest_command == "text":
        batch = memory.ingest(
            namespace=args.namespace,
            source_type=args.source_type,
            source_uri=args.source_uri,
            content=args.content,
            project_id=args.project,
            session_id=args.session,
            title=args.title,
            metadata=_json_arg(args.metadata_json),
            privacy_level=args.privacy,
            trust_level=args.trust,
        )
        print(_format_batch(batch))
        return 0
    if args.ingest_command == "file":
        path = Path(args.path)
        content = path.read_text(encoding="utf-8")
        batch = memory.ingest(
            namespace=args.namespace,
            source_type=args.source_type,
            source_uri=str(path),
            content=content,
            project_id=args.project,
            session_id=args.session,
            title=args.title or path.name,
            metadata=_json_arg(args.metadata_json),
            privacy_level=args.privacy,
            trust_level=args.trust,
        )
        print(_format_batch(batch))
        return 0
    return 0


def _run_extract(memory: Memory, args: argparse.Namespace) -> int:
    if args.extract_command in {"run", "dry-run"}:
        run = memory.extract_candidates(
            namespace=args.namespace,
            batch_id=args.batch,
            evidence_ids=args.evidence,
            extractor=args.extractor,
            dry_run=args.extract_command == "dry-run",
            max_candidates=args.max_candidates,
        )
        print(_format_extraction_run(run))
        return 0
    if args.extract_command == "show":
        print(json.dumps(asdict(memory.read_extraction_run(args.run_id)), indent=2))
        return 0
    return 0


def _run_llm(memory: Memory, args: argparse.Namespace) -> int:
    if args.llm_command == "expand-query":
        _print_json(
            memory.expand_query(
                namespace=args.namespace,
                query=args.query,
                provider=args.provider,
                model=args.model,
                privacy_level=args.privacy_level,
            )
        )
        return 0
    if args.llm_command == "summarize-evidence":
        _print_json(memory.summarize_evidence(namespace=args.namespace, evidence_ids=args.evidence, provider=args.provider, model=args.model))
        return 0
    if args.llm_command == "suggest-entities":
        _print_json(memory.suggest_entities(namespace=args.namespace, evidence_ids=args.evidence, provider=args.provider, model=args.model))
        return 0
    if args.llm_command == "suggest-categories":
        _print_json(memory.suggest_categories(namespace=args.namespace, evidence_ids=args.evidence, provider=args.provider, model=args.model))
        return 0
    if args.llm_command == "suggest-scope":
        _print_json(memory.suggest_scope_with_llm(namespace=args.namespace, candidate_id=args.candidate_id, provider=args.provider, model=args.model))
        return 0
    if args.llm_command == "suggest-duplicate-merge":
        _print_json(memory.suggest_duplicate_merge_with_llm(namespace=args.namespace, candidate_id=args.candidate_id, provider=args.provider, model=args.model))
        return 0
    if args.llm_command == "draft-reflection":
        reflection = memory.draft_reflection_with_llm(
            namespace=args.namespace,
            source_claim_ids=args.source_claim_ids,
            source_evidence_ids=args.source_evidence_ids,
            title=args.title,
            provider=args.provider,
            model=args.model,
        )
        _print_json(asdict(reflection))
        return 0
    if args.llm_command == "explain-conflict":
        _print_json(memory.explain_conflict_with_llm(args.conflict_id, provider=args.provider, model=args.model))
        return 0
    if args.llm_command == "runs":
        _print_json(memory.list_llm_runs(namespace=args.namespace, task_type=args.task, limit=args.limit))
        return 0
    if args.llm_command == "show":
        _print_json(memory.read_llm_run(args.llm_run_id))
        return 0
    return 0


def _run_candidates(memory: Memory, args: argparse.Namespace) -> int:
    if args.candidates_command == "list":
        candidates = memory.list_candidates(
            args.namespace,
            status=args.status,
            memory_type=args.memory_type,
            project_id=args.project,
            extraction_run_id=args.run,
        )
        if not candidates:
            print("No candidates found.")
        for candidate in candidates:
            print(_format_candidate(candidate))
        return 0
    if args.candidates_command == "show":
        print(json.dumps(asdict(memory.read_candidate(args.candidate_id)), indent=2))
        return 0
    if args.candidates_command == "promote":
        claim = memory.promote_candidate(
            args.candidate_id,
            reason=args.reason,
            target_status=args.to,
            reviewer=args.reviewer,
            force=args.force,
        )
        print(_format_claim(claim))
        return 0
    if args.candidates_command == "reject":
        decision = memory.reject_candidate(
            args.candidate_id,
            reason=args.reason,
            reviewer=args.reviewer,
        )
        print(json.dumps(asdict(decision), indent=2))
        return 0
    if args.candidates_command == "edit":
        edits = {}
        for attr, key in [
            ("subject", "subject"),
            ("predicate", "predicate"),
            ("object", "object"),
            ("memory_type", "memory_type"),
            ("status", "candidate_status"),
            ("confidence", "suggested_confidence"),
            ("importance", "suggested_importance"),
        ]:
            value = getattr(args, attr)
            if value is not None:
                edits[key] = value
        if args.scope_json:
            edits["suggested_scope"] = json.loads(args.scope_json)
        decision = memory.review_candidate(
            args.candidate_id,
            decision="edit",
            reason=args.reason,
            reviewer=args.reviewer,
            edits=edits,
        )
        print(json.dumps(asdict(decision), indent=2))
        print(_format_candidate(memory.read_candidate(args.candidate_id)))
        return 0
    return 0


def _run_entities(memory: Memory, args: argparse.Namespace) -> int:
    if args.entities_command == "list":
        entities = memory.list_entities(
            namespace=args.namespace,
            entity_type=args.entity_type,
        )
        if not entities:
            print("No entities found.")
        for entity in entities:
            print(_format_entity(entity))
        return 0
    if args.entities_command == "show":
        print(json.dumps(asdict(memory.get_entity(args.entity_id)), indent=2))
        return 0
    if args.entities_command == "merge":
        entity = memory.merge_entities(
            args.namespace,
            source_entity_id=args.source_entity_id,
            target_entity_id=args.target_entity_id,
            reason=args.reason,
        )
        print(_format_entity(entity))
        return 0
    return 0


def _run_categories(memory: Memory, args: argparse.Namespace) -> int:
    if args.categories_command == "list":
        categories = memory.list_categories(namespace=args.namespace)
        print(json.dumps(categories, indent=2))
        return 0
    if args.categories_command == "label":
        labels = memory.label_memory(
            args.target_id,
            target_type=args.target_type,
            labels=args.label,
            reason=args.reason,
            confidence=args.confidence,
        )
        print(json.dumps([asdict(label) for label in labels], indent=2))
        return 0
    return 0


def _run_index(memory: Memory, args: argparse.Namespace) -> int:
    if args.index_command == "semantic":
        run = memory.index_semantic(
            args.namespace,
            target_type=args.target,
            target_ids=args.target_ids,
            provider=args.provider,
            model=args.model,
            dimension=args.dimension,
            force=args.force,
            resume=not args.no_resume,
            protected_mode_policy=args.protected_mode_policy,
            vector_store=args.vector_store,
        )
        print(json.dumps(asdict(run), indent=2))
        return 0
    if args.index_command == "status":
        print(json.dumps(memory.semantic_index_status(args.namespace, target_type=args.target), indent=2))
        return 0
    if args.index_command == "resume":
        run = memory.index_semantic(
            args.namespace,
            target_type=args.target,
            target_ids=args.target_ids,
            provider=args.provider,
            model=args.model,
            dimension=args.dimension,
            force=False,
            resume=True,
            protected_mode_policy=args.protected_mode_policy,
            vector_store=args.vector_store,
        )
        print(json.dumps(asdict(run), indent=2))
        return 0
    if args.index_command == "verify":
        run = memory.verify_semantic_index(
            args.namespace,
            target_type=args.target,
            provider=args.provider,
            model=args.model,
            dimension=args.dimension,
        )
        print(json.dumps(asdict(run), indent=2))
        return 0
    if args.index_command == "mark-stale":
        run = memory.mark_stale_semantic_index(
            args.namespace,
            target_type=args.target,
            provider=args.provider,
            model=args.model,
            reason=args.reason,
        )
        print(json.dumps(asdict(run), indent=2))
        return 0
    if args.index_command == "prune-stale":
        run = memory.prune_stale_semantic_index(
            args.namespace,
            target_type=args.target,
            provider=args.provider,
            model=args.model,
        )
        print(json.dumps(asdict(run), indent=2))
        return 0
    return 0


def _run_claims(memory: Memory, args: argparse.Namespace) -> int:
    if args.claims_command == "list":
        claims = memory.list_claims(
            namespace=args.namespace,
            status=args.status,
        )
        if not claims:
            print("No claims found.")
        for claim in claims:
            print(_format_claim(claim))
        return 0
    if args.claims_command == "show":
        print(json.dumps(asdict(memory.read_claim(args.claim_id)), indent=2))
        return 0
    if args.claims_command == "promote":
        decision = memory.promote_claim(
            args.claim_id,
            args.to,
            reason=args.reason,
            force=args.force,
        )
        print(_format_curation_decision(decision))
        print(_format_claim(memory.read_claim(args.claim_id)))
        return 0
    if args.claims_command == "demote":
        decision = memory.demote_claim(args.claim_id, args.to, reason=args.reason)
        print(_format_curation_decision(decision))
        print(_format_claim(memory.read_claim(args.claim_id)))
        return 0
    if args.claims_command == "supersede":
        relationship = memory.supersede_claim(
            args.old_claim_id,
            args.new_claim_id,
            reason=args.reason,
        )
        print(json.dumps(asdict(relationship), indent=2))
        return 0
    if args.claims_command == "scope":
        scope = memory.scope_claim(
            args.claim_id,
            scope_type=args.scope_type,
            applies_when=args.applies_when,
            valid_from=args.valid_from,
            valid_to=args.valid_to,
            reason=args.reason,
        )
        print(json.dumps(asdict(scope), indent=2))
        return 0
    if args.claims_command == "history":
        history = memory.claim_history(args.claim_id)
        if args.json:
            print(json.dumps(history, indent=2))
        elif not history:
            print("No claim status history found.")
        else:
            for row in history:
                print(
                    f"{row['created_at']} {row['old_status'] or '-'} -> "
                    f"{row['new_status']} :: {row['reason']}"
                )
        return 0
    return 0


def _run_confidence(memory: Memory, args: argparse.Namespace) -> int:
    if args.confidence_command == "show":
        snapshot = memory.compute_confidence(args.claim_id, explain=args.explain)
        print(_format_confidence_snapshot(snapshot, include_explanation=args.explain))
        return 0
    if args.confidence_command == "recompute":
        snapshots = memory.recompute_confidence(
            namespace=args.namespace,
            memory_types=args.memory_type,
            persist=True,
        )
        print(f"Recomputed confidence for {len(snapshots)} claim(s).")
        for snapshot in snapshots:
            print(_format_confidence_snapshot(snapshot))
        return 0
    if args.confidence_command == "policy":
        if args.policy_command == "list":
            policies = memory.list_half_life_policies(
                namespace=args.namespace,
                memory_type=args.memory_type,
            )
            if not policies:
                print("No half-life policies found.")
            for policy in policies:
                print(_format_policy(policy))
            return 0
        if args.policy_command == "set":
            policy = memory.set_half_life_policy(
                namespace=args.namespace,
                memory_type=args.memory_type,
                predicate=args.predicate,
                half_life_days=args.half_life_days,
                reason=args.reason,
            )
            print(_format_policy(policy))
            return 0
    return 0


def _run_decay(memory: Memory, args: argparse.Namespace) -> int:
    persist = args.decay_command == "run"
    snapshots = memory.recompute_confidence(
        namespace=args.namespace,
        memory_types=args.memory_type,
        persist=persist,
    )
    mode = "Persisted" if persist else "Previewed"
    print(f"{mode} decay for {len(snapshots)} claim(s).")
    for snapshot in snapshots:
        print(_format_confidence_snapshot(snapshot))
    return 0


def _run_curate(memory: Memory, args: argparse.Namespace) -> int:
    dry_run = args.curate_command == "preview"
    decisions = memory.curate(
        namespace=args.namespace,
        dry_run=dry_run,
        memory_types=args.memory_type,
        max_decisions=args.max_decisions,
    )
    if not decisions:
        print("No curation decisions.")
    for decision in decisions:
        print(_format_curation_decision(decision))
    return 0


def _run_conflicts(memory: Memory, args: argparse.Namespace) -> int:
    if args.conflicts_command == "detect":
        families = memory.detect_conflicts(
            namespace=args.namespace,
            subject=args.subject,
            predicate=args.predicate,
            include_resolved=args.include_resolved,
        )
        if not families:
            print("No conflicts found.")
        for family in families:
            print(_format_conflict_family(family))
        return 0
    if args.conflicts_command == "list":
        conflicts = memory.list_conflicts(
            namespace=args.namespace,
            status=args.status,
        )
        if not conflicts:
            print("No conflicts found.")
        for conflict in conflicts:
            print(_format_conflict(conflict))
        return 0
    if args.conflicts_command == "show":
        print(json.dumps(asdict(memory.read_conflict(args.conflict_id)), indent=2))
        return 0
    if args.conflicts_command == "resolve":
        resolution = memory.resolve_conflict(
            conflict_id=args.conflict_id,
            active_claim_id=args.active,
            strategy=args.strategy,
            superseded_claim_ids=args.superseded,
            rejected_claim_ids=args.rejected,
            scoped_claims=json.loads(args.scoped_json) if args.scoped_json else None,
            note=args.note,
        )
        print(json.dumps(asdict(resolution), indent=2))
        print(_format_conflict(memory.read_conflict(args.conflict_id)))
        return 0
    return 0


def _run_events(memory: Memory, args: argparse.Namespace) -> int:
    if args.events_command == "list":
        events = memory.list_events(
            namespace=args.namespace,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps([asdict(event) for event in events], indent=2))
        elif not events:
            print("No events found.")
        else:
            for event in events:
                print(_format_event(event))
        return 0
    if args.events_command == "show":
        event = memory.read_event(args.event_id)
        if args.json:
            print(json.dumps(asdict(event), indent=2))
        else:
            print(_format_event(event, include_content=True))
        return 0
    return 0


def _run_sessions(memory: Memory, args: argparse.Namespace) -> int:
    if args.sessions_command == "start":
        session = memory.start_session(
            namespace=args.namespace,
            agent_id=args.agent,
            project_id=args.project,
            title=args.title,
            metadata=_json_arg(args.metadata_json),
        )
        print(json.dumps(asdict(session), indent=2))
        return 0
    if args.sessions_command == "end":
        session = memory.end_session(
            args.session,
            summary=args.summary,
            remember_summary=not args.no_remember_summary,
        )
        print(json.dumps(asdict(session), indent=2))
        return 0
    if args.sessions_command == "list":
        sessions = memory.list_sessions(
            namespace=args.namespace,
            project_id=args.project,
            limit=args.limit,
        )
        print(json.dumps([asdict(session) for session in sessions], indent=2))
        return 0
    if args.sessions_command == "show":
        print(json.dumps(asdict(memory.get_session(args.session)), indent=2))
        return 0
    return 0


def _run_projects(memory: Memory, args: argparse.Namespace) -> int:
    if args.projects_command == "create":
        project = memory.create_project(
            namespace=args.namespace,
            project_id=args.id,
            title=args.title,
            description=args.description,
            status=args.status,
            metadata=_json_arg(args.metadata_json),
        )
        print(json.dumps(asdict(project), indent=2))
        return 0
    if args.projects_command == "list":
        projects = memory.list_projects(
            namespace=args.namespace,
            status=args.status,
        )
        print(json.dumps([asdict(project) for project in projects], indent=2))
        return 0
    if args.projects_command == "show":
        print(
            json.dumps(
                asdict(memory.get_project(namespace=args.namespace, project_id=args.id)),
                indent=2,
            )
        )
        return 0
    return 0


def _run_infer(memory: Memory, args: argparse.Namespace) -> int:
    if args.infer_command == "run":
        run = memory.run_inference(
            args.namespace,
            engines=_split_csv(args.engines),
            project_id=args.project,
            session_id=args.session,
            target_claim_ids=args.claims,
            target_evidence_ids=args.evidence,
            rule_ids=args.rules,
            dry_run=not args.apply,
            max_inferences=args.max_inferences,
        )
        if args.json:
            print(json.dumps(asdict(run), indent=2))
        else:
            print(
                f"[{run.id}] inference run\n"
                f"engines: {', '.join(run.engines)}\n"
                f"dry_run: {str(run.dry_run).lower()}\n"
                f"inferences: {run.inference_count}\n"
                f"persisted: {run.persisted_count}\n"
            )
        return 0
    if args.infer_command == "list":
        inferences = memory.list_inferences(
            args.namespace,
            status=args.status,
            inference_type=args.inference_type,
            engine=args.engine,
            project_id=args.project,
            source_claim_id=args.source_claim,
        )
        if args.json:
            print(json.dumps([asdict(inference) for inference in inferences], indent=2))
        elif not inferences:
            print("No inferences found.")
        else:
            for inference in inferences:
                print(_format_inference(inference))
        return 0
    if args.infer_command == "show":
        inference = memory.read_inference(args.inference_id)
        if args.json:
            print(json.dumps(asdict(inference), indent=2))
        else:
            print(_format_inference(inference))
        return 0
    if args.infer_command == "review":
        decision = memory.review_inference(
            args.inference_id,
            decision=args.decision,
            reason=args.reason,
            reviewer=args.reviewer,
        )
        print(json.dumps(asdict(decision), indent=2))
        return 0
    if args.infer_command == "promote":
        promoted = memory.promote_inference(
            args.inference_id,
            target_type=args.target_type,
            target_status=args.to,
            reason=args.reason,
            reviewer=args.reviewer,
            force=args.force,
        )
        print(json.dumps(asdict(promoted), indent=2))
        return 0
    if args.infer_command == "reject":
        decision = memory.reject_inference(
            args.inference_id,
            reason=args.reason,
            reviewer=args.reviewer,
        )
        print(json.dumps(asdict(decision), indent=2))
        return 0
    if args.infer_command == "explain":
        explanation = memory.explain_inference(args.inference_id)
        if args.json:
            print(json.dumps(asdict(explanation), indent=2))
        else:
            print(explanation.explanation)
            if explanation.promotion_failures:
                print("promotion_failures: " + "; ".join(explanation.promotion_failures))
        return 0
    return 0


def _run_rules(memory: Memory, args: argparse.Namespace) -> int:
    if args.rules_command == "list":
        enabled = None
        if args.enabled is not None:
            enabled = args.enabled == "true"
        rules = memory.list_rules(namespace=args.namespace, enabled=enabled)
        if args.json:
            print(json.dumps([asdict(rule) for rule in rules], indent=2))
        elif not rules:
            print("No rules found.")
        else:
            for rule in rules:
                print(_format_rule(rule))
        return 0
    if args.rules_command == "define":
        rule = memory.define_rule(
            args.namespace,
            name=args.name,
            rule_type=args.rule_type,
            description=args.description,
            condition=json.loads(args.condition_json),
            conclusion=json.loads(args.conclusion_json),
            confidence_policy=json.loads(args.confidence_json),
            enabled=not args.disabled,
        )
        print(json.dumps(asdict(rule), indent=2))
        return 0
    if args.rules_command == "enable":
        rule = memory.set_rule_enabled(args.rule_id, enabled=True)
        print(json.dumps(asdict(rule), indent=2))
        return 0
    if args.rules_command == "disable":
        rule = memory.set_rule_enabled(args.rule_id, enabled=False)
        print(json.dumps(asdict(rule), indent=2))
        return 0
    if args.rules_command == "run":
        result = memory.run_rule(
            args.rule_id,
            namespace=args.namespace,
            target_claim_ids=args.claims,
            dry_run=not args.apply,
        )
        if args.json:
            print(json.dumps(asdict(result), indent=2))
        else:
            print(
                f"[{result.id}] rule execution\n"
                f"rule: {result.rule_id}\n"
                f"matched: {result.matched_count}\n"
                f"inferences: {result.inference_count}\n"
                f"dry_run: {str(result.dry_run).lower()}\n"
            )
        return 0
    return 0


def _run_reflect(memory: Memory, args: argparse.Namespace) -> int:
    if args.reflect_command == "build":
        reflection = memory.build_reflection(
            args.namespace,
            source_claim_ids=_split_csv(args.claims),
            source_evidence_ids=_split_csv(args.evidence),
            source_reflection_ids=_split_csv(args.reflections),
            title=args.title,
            text=args.text,
            abstraction_level=args.level,
            project_id=args.project,
            reason=args.reason,
            builder=args.builder,
            require_review=args.candidate,
        )
        if args.json:
            print(json.dumps(asdict(reflection), indent=2))
        else:
            print(_format_reflection(reflection))
        return 0
    if args.reflect_command == "expand":
        expansion = memory.expand_reflection(args.reflection_id)
        if args.json:
            print(json.dumps(asdict(expansion), indent=2))
        else:
            print(f"Reflection:\n{expansion.reflection_text}\n")
            if expansion.source_claims:
                print("Source claims:")
                for claim in expansion.source_claims:
                    print(f"- {claim.id}: {claim_text(claim.subject, claim.predicate, claim.object)}")
            if expansion.source_evidence:
                print("Evidence:")
                for event in expansion.source_evidence:
                    print(f"- {event.id}: {event.source_type}")
        return 0
    if args.reflect_command == "list":
        reflections = memory.list_reflections(
            namespace=args.namespace,
            status=args.status,
            project_id=args.project,
        )
        if args.json:
            print(json.dumps([asdict(reflection) for reflection in reflections], indent=2))
        elif not reflections:
            print("No reflections found.")
        else:
            for reflection in reflections:
                print(_format_reflection(reflection))
        return 0
    return 0


def _run_derivation(memory: Memory, args: argparse.Namespace) -> int:
    if args.derivation_command == "trace":
        trace = memory.trace_derivation(args.target_id, target_type=args.target_type)
        if args.json:
            print(json.dumps(asdict(trace), indent=2))
        else:
            print(_format_derivation_trace(trace))
        return 0
    if args.derivation_command == "invalidated":
        events = memory.list_invalidations(
            namespace=args.namespace,
            target_id=args.target,
            target_type=args.target_type,
        )
        if args.json:
            print(json.dumps([asdict(event) for event in events], indent=2))
        elif not events:
            print("No invalidation events found.")
        else:
            for event in events:
                print(_format_invalidation(event))
        return 0
    if args.derivation_command == "invalidate":
        events = memory.invalidate_derived(
            namespace=args.namespace,
            source_id=args.source_id,
            source_type=args.source_type,
            reason=args.reason,
            mode=args.mode,
        )
        if args.json:
            print(json.dumps([asdict(event) for event in events], indent=2))
        else:
            print(f"Invalidated {len(events)} derived record(s).")
            for event in events:
                print(_format_invalidation(event))
        return 0
    return 0


def _run_clusters(memory: Memory, args: argparse.Namespace) -> int:
    if args.clusters_command == "build":
        clusters = memory.build_semantic_clusters(args.namespace, target=args.target)
        if args.json:
            print(json.dumps([asdict(cluster) for cluster in clusters], indent=2))
        else:
            print(f"Built {len(clusters)} semantic cluster(s).")
            for cluster in clusters:
                print(_format_cluster(cluster))
        return 0
    if args.clusters_command == "list":
        clusters = memory.list_semantic_clusters(namespace=args.namespace)
        if args.json:
            print(json.dumps([asdict(cluster) for cluster in clusters], indent=2))
        elif not clusters:
            print("No semantic clusters found.")
        else:
            for cluster in clusters:
                print(_format_cluster(cluster))
        return 0
    if args.clusters_command == "show":
        print(json.dumps(asdict(memory.get_semantic_cluster(args.cluster_id)), indent=2))
        return 0
    if args.clusters_command == "relations":
        relations = memory.list_semantic_relations(
            namespace=args.namespace,
            source_id=args.source_id,
        )
        if args.json:
            print(json.dumps([asdict(relation) for relation in relations], indent=2))
        elif not relations:
            print("No semantic relations found.")
        else:
            for relation in relations:
                print(_format_semantic_relation(relation))
        return 0
    return 0


def _run_abstractions(memory: Memory, args: argparse.Namespace) -> int:
    if args.abstractions_command == "create":
        abstraction = memory.create_abstraction(
            args.namespace,
            source_ids=_split_csv(args.sources),
            source_type=args.source_type,
            abstraction_text=args.text,
            abstraction_level=args.level,
            information_loss_policy=args.policy,
            reason=args.reason,
        )
        if args.json:
            print(json.dumps(asdict(abstraction), indent=2))
        else:
            print(_format_abstraction(abstraction))
        return 0
    if args.abstractions_command == "list":
        abstractions = memory.list_abstractions(
            namespace=args.namespace,
            status=args.status,
        )
        if args.json:
            print(json.dumps([asdict(abstraction) for abstraction in abstractions], indent=2))
        elif not abstractions:
            print("No abstractions found.")
        else:
            for abstraction in abstractions:
                print(_format_abstraction(abstraction))
        return 0
    if args.abstractions_command == "show":
        abstraction = memory.get_abstraction(args.abstraction_id)
        if args.json:
            print(json.dumps(asdict(abstraction), indent=2))
        else:
            print(_format_abstraction(abstraction))
        return 0
    return 0


def _run_usage(memory: Memory, args: argparse.Namespace) -> int:
    if args.usage_command == "list":
        events = memory.list_usage(
            namespace=args.namespace,
            target_id=args.target,
            target_type=args.target_type,
            context_pack_id=args.context,
        )
        print(json.dumps([asdict(event) for event in events], indent=2))
        return 0
    if args.usage_command == "show":
        print(json.dumps(asdict(memory.read_usage(args.usage_id)), indent=2))
        return 0
    return 0


def _run_outcome(memory: Memory, args: argparse.Namespace) -> int:
    if args.outcome_command == "record":
        outcome = memory.record_outcome(
            args.namespace,
            task_id=args.task,
            outcome=args.outcome,
            used_context_pack_id=args.context,
            session_id=args.session,
            project_id=args.project,
            user_feedback=args.user_feedback,
            score=args.score,
            note=args.note,
        )
        print(json.dumps(asdict(outcome), indent=2))
        return 0
    if args.outcome_command == "list":
        outcomes = memory.list_outcomes(namespace=args.namespace, project_id=args.project)
        print(json.dumps([asdict(outcome) for outcome in outcomes], indent=2))
        return 0
    return 0


def _run_eval(memory: Memory, args: argparse.Namespace) -> int:
    if args.eval_command == "create":
        eval_set = memory.create_eval_set(
            args.namespace,
            name=args.name,
            description=args.description,
            project_id=args.project,
        )
        print(json.dumps(asdict(eval_set), indent=2))
        return 0
    if args.eval_command == "add-case":
        case = memory.add_eval_case(
            args.eval_set_id,
            query=args.query,
            expected_claim_ids=args.expected,
            expected_reflection_ids=args.expected_reflection,
            forbidden_claim_ids=args.forbidden,
            project_id=args.project,
            session_id=args.session,
            tags=args.tags,
            note=args.note,
        )
        print(json.dumps(asdict(case), indent=2))
        return 0
    if args.eval_command == "run":
        run = memory.run_evaluation(
            args.namespace,
            eval_set_id=args.eval_set_id,
            retrieval_mode=args.mode,
            limit=args.limit,
        )
        print(json.dumps(asdict(run), indent=2))
        return 0
    if args.eval_command == "report":
        print(json.dumps(asdict(memory.read_evaluation_run(args.run_id)), indent=2))
        return 0
    if args.eval_command == "list":
        print(json.dumps([asdict(item) for item in memory.list_eval_sets(namespace=args.namespace)], indent=2))
        return 0
    return 0


def _run_optimize(memory: Memory, args: argparse.Namespace) -> int:
    if args.optimize_command == "retrieval":
        run = memory.optimize_retrieval(
            args.namespace,
            eval_set_id=args.eval_set,
            objective=args.objective,
            dry_run=not args.apply_proposal,
            max_trials=args.max_trials,
        )
        print(json.dumps(asdict(run), indent=2))
        return 0
    return 0


def _run_learn(memory: Memory, args: argparse.Namespace) -> int:
    if args.learn_command == "run":
        targets = list(args.targets or [])
        if args.targets_csv:
            targets.extend(_split_csv(args.targets_csv))
        create_proposals = args.apply_proposals or args.create_proposals
        run = memory.run_learning(
            args.namespace,
            project_id=args.project,
            learning_targets=targets or None,
            eval_set_id=args.eval_set,
            dry_run=not create_proposals,
        )
        print(json.dumps(asdict(run), indent=2))
        return 0
    if args.learn_command == "list":
        print(json.dumps([asdict(run) for run in memory.list_learning_runs(namespace=args.namespace)], indent=2))
        return 0
    return 0


def _run_policies(memory: Memory, args: argparse.Namespace) -> int:
    if args.policies_command == "list":
        print(json.dumps([asdict(policy) for policy in memory.list_ranking_policies(namespace=args.namespace)], indent=2))
        return 0
    if args.policies_command == "proposals":
        proposals = memory.list_policy_proposals(
            namespace=args.namespace,
            status=args.status,
            policy_type=args.policy_type,
        )
        print(json.dumps([asdict(proposal) for proposal in proposals], indent=2))
        return 0
    if args.policies_command == "show":
        print(json.dumps(asdict(memory.get_policy_proposal(args.proposal_id)), indent=2))
        return 0
    if args.policies_command == "approve":
        proposal = memory.review_policy_proposal(
            args.proposal_id,
            decision="approve",
            reason=args.reason,
        )
        print(json.dumps(asdict(proposal), indent=2))
        return 0
    if args.policies_command == "reject":
        proposal = memory.review_policy_proposal(
            args.proposal_id,
            decision="reject",
            reason=args.reason,
        )
        print(json.dumps(asdict(proposal), indent=2))
        return 0
    if args.policies_command == "apply":
        application = memory.apply_policy_proposal(
            args.proposal_id,
            reason=args.reason,
            require_evaluation_pass=not args.force,
        )
        print(json.dumps(asdict(application), indent=2))
        return 0
    if args.policies_command == "versions":
        versions = memory.list_ranking_policy_versions(args.policy)
        print(json.dumps([asdict(version) for version in versions], indent=2))
        return 0
    return 0


def _run_procedures(memory: Memory, args: argparse.Namespace) -> int:
    if args.procedures_command == "propose":
        proposal = memory.propose_procedure_update(
            args.namespace,
            procedure_claim_id=args.claim,
            title=args.title,
            proposed_text=args.text,
            reason=args.reason,
            source_ids=args.sources,
            source_type=args.source_type,
            evaluation_run_id=args.eval_run,
        )
        print(json.dumps(asdict(proposal), indent=2))
        return 0
    if args.procedures_command == "approve":
        proposal = memory.review_procedure_update(
            args.proposal_id,
            decision="approve",
            reason=args.reason,
        )
        print(json.dumps(asdict(proposal), indent=2))
        return 0
    if args.procedures_command == "reject":
        proposal = memory.review_procedure_update(
            args.proposal_id,
            decision="reject",
            reason=args.reason,
        )
        print(json.dumps(asdict(proposal), indent=2))
        return 0
    if args.procedures_command == "apply":
        version = memory.apply_procedure_update(args.proposal_id, reason=args.reason)
        print(json.dumps(asdict(version), indent=2))
        return 0
    if args.procedures_command == "list":
        proposals = memory.list_procedure_update_proposals(
            namespace=args.namespace,
            status=args.status,
        )
        print(json.dumps([asdict(proposal) for proposal in proposals], indent=2))
        return 0
    if args.procedures_command == "versions":
        versions = memory.list_procedure_versions(
            namespace=args.namespace,
            procedure_claim_id=args.claim,
            title=args.title,
        )
        print(json.dumps([asdict(version) for version in versions], indent=2))
        return 0
    return 0


def _run_jobs(memory: Memory, args: argparse.Namespace) -> int:
    if args.jobs_command == "enqueue":
        job = memory.enqueue_job(
            args.namespace,
            job_type=args.job_type,
            payload=json.loads(args.payload_json),
            priority=args.priority,
        )
        print(json.dumps(asdict(job), indent=2))
        return 0
    if args.jobs_command == "run":
        jobs = memory.run_jobs(
            namespace=args.namespace,
            job_type=args.job_type,
            max_jobs=args.max,
        )
        print(json.dumps([asdict(job) for job in jobs], indent=2))
        return 0
    if args.jobs_command == "list":
        jobs = memory.list_jobs(
            namespace=args.namespace,
            job_type=args.job_type,
            status=args.status,
        )
        print(json.dumps([asdict(job) for job in jobs], indent=2))
        return 0
    if args.jobs_command == "show":
        print(json.dumps(asdict(memory.get_job(args.job_id)), indent=2))
        return 0
    return 0


def _run_health(memory: Memory, args: argparse.Namespace) -> int:
    if args.health_command == "report":
        report = memory.health_report(
            args.namespace,
            project_id=args.project,
            include_recommendations=not args.no_recommendations,
        )
        print(json.dumps(asdict(report), indent=2))
        return 0
    return 0


def _run_rollback(memory: Memory, args: argparse.Namespace) -> int:
    if args.rollback_command == "policy":
        record = memory.rollback_policy(
            args.namespace,
            policy_id=args.policy,
            target_version_id=args.to_version,
            reason=args.reason,
        )
        print(json.dumps(asdict(record), indent=2))
        return 0
    if args.rollback_command == "procedure":
        record = memory.rollback_procedure(
            args.namespace,
            procedure_claim_id=args.claim,
            target_version_id=args.to_version,
            reason=args.reason,
        )
        print(json.dumps(asdict(record), indent=2))
        return 0
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    config = ServiceConfig.load(
        args.config,
        overrides={
            "db_path": args.db,
            "host": args.host,
            "port": args.port,
            "auto_migrate": True if args.auto_migrate else None,
            "auth_required": False if args.no_auth else None,
            "allow_remote": True if args.allow_remote else None,
            "worker_enabled": True if args.with_worker else None,
            "console_enabled": True if args.with_console else (False if args.no_console else None),
        },
    )
    if args.no_auth:
        print("WARNING: authentication disabled; use only for local development.")
    daemon = AletheiaDaemon(config)
    host, port = daemon.start()
    if config.auth_required and not daemon.service.auth.list_tokens():
        print("No API tokens found. Create one with: aletheia auth create-token --db <db> --client local-agent --namespace user/default", flush=True)
    print(f"Aletheia service running at http://{host}:{port}/v1", flush=True)
    print(f"OpenAPI: http://{host}:{port}/v1/openapi.json", flush=True)
    if config.console_enabled:
        print(f"Console: http://{host}:{port}/console", flush=True)
    daemon.serve_forever()
    return 0


def _run_console_serve(args: argparse.Namespace) -> int:
    args.with_console = True
    args.no_console = False
    result_url = None
    config = ServiceConfig.load(
        args.config,
        overrides={
            "db_path": args.db,
            "host": args.host,
            "port": args.port,
            "auto_migrate": True if args.auto_migrate else None,
            "auth_required": False if args.no_auth else None,
            "allow_remote": True if args.allow_remote else None,
            "worker_enabled": True if args.with_worker else None,
            "console_enabled": True,
        },
    )
    if args.no_auth:
        print("WARNING: authentication disabled; use only for local development.")
    daemon = AletheiaDaemon(config)
    host, port = daemon.start()
    result_url = f"http://{host}:{port}/console"
    if config.auth_required and not daemon.service.auth.list_tokens():
        print("No API tokens found. Create one with: aletheia auth create-token --db <db> --client local-agent --namespace user/default", flush=True)
    print(f"Aletheia service running at http://{host}:{port}/v1", flush=True)
    print(f"Console: {result_url}", flush=True)
    if args.open_browser:
        webbrowser.open(result_url)
    daemon.serve_forever()
    return 0


def _run_mcp(args: argparse.Namespace) -> int:
    token = args.token or os.environ.get("ALETHEIA_API_TOKEN")
    config = ServiceConfig.load(
        args.config,
        overrides={
            "db_path": args.db,
            "auto_migrate": True,
            "auth_required": bool(token),
            "mcp_default_namespace": args.namespace,
            "mcp_default_mode": args.mode,
        },
    )
    namespace = args.namespace or config.mcp_default_namespace
    mode = args.mode or config.mcp_default_mode
    service = AletheiaService(Memory.open(config.db_path), config)
    try:
        registry = McpToolRegistry(service, token=token, namespace=namespace, mode=mode)
        if args.list_tools:
            print(json.dumps(registry.list_tools(), indent=2))
            return 0
        registry.serve_stdio()
        return 0
    finally:
        service.close()


def _run_auth(memory: Memory, args: argparse.Namespace) -> int:
    auth = AuthService(memory)
    if args.auth_command == "create-token":
        client_id = _resolve_client_id(auth, args.client)
        capabilities = _split_csv(args.capabilities) if args.capabilities else DEFAULT_LOCAL_AGENT_CAPABILITIES
        token, raw = auth.create_token(
            client_id=client_id,
            namespace_grants=args.namespaces,
            capabilities=capabilities,
            privacy_ceiling=args.privacy_ceiling,
            expires_at=args.expires_at,
        )
        data = asdict(token)
        data["raw_token"] = raw
        print(json.dumps(data, indent=2))
        return 0
    if args.auth_command == "list-tokens":
        print(json.dumps([asdict(token) for token in auth.list_tokens(include_inactive=args.include_inactive)], indent=2))
        return 0
    if args.auth_command == "revoke-token":
        print(json.dumps(asdict(auth.revoke_token(args.token_id, reason=args.reason)), indent=2))
        return 0
    return 0


def _run_clients(memory: Memory, args: argparse.Namespace) -> int:
    auth = AuthService(memory)
    if args.clients_command == "create":
        print(json.dumps(asdict(auth.create_client(name=args.name, client_type=args.client_type)), indent=2))
        return 0
    if args.clients_command == "list":
        print(json.dumps([asdict(client) for client in auth.list_clients(include_disabled=args.include_disabled)], indent=2))
        return 0
    if args.clients_command == "disable":
        print(json.dumps(asdict(auth.disable_client(args.client_id)), indent=2))
        return 0
    return 0


def _run_api(memory: Memory, args: argparse.Namespace) -> int:
    if args.api_command == "openapi":
        schema = openapi_schema()
        if args.output:
            Path(args.output).write_text(json.dumps(schema, indent=2) + "\n")
            print(args.output)
        else:
            print(json.dumps(schema, indent=2))
        return 0
    if args.api_command == "routes":
        paths = openapi_schema()["paths"]
        rows = []
        for path, methods in sorted(paths.items()):
            for method, meta in methods.items():
                rows.append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "required_capability": meta.get("x-required-capability"),
                    }
                )
        print(json.dumps(rows, indent=2))
        return 0
    if args.api_command == "ping":
        url = args.url.rstrip("/") + "/v1/health"
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - local CLI.
            print(response.read().decode("utf-8"))
        return 0
    return 0


def _run_worker(memory: Memory, args: argparse.Namespace) -> int:
    if args.worker_command in {"run", "watch"}:
        jobs = memory.run_jobs(
            namespace=args.namespace,
            job_type=getattr(args, "job_type", None),
            max_jobs=args.max_jobs,
        )
        print(json.dumps([asdict(job) for job in jobs], indent=2))
        return 0
    return 0


def _run_service(memory: Memory, args: argparse.Namespace) -> int:
    config = ServiceConfig(db_path=memory.store.path, auto_migrate=True)
    service = AletheiaService(memory, config)
    if args.service_command == "status":
        print(json.dumps(asdict(service.service_health()), indent=2))
        return 0
    if args.service_command == "requests":
        print(json.dumps(service.service_requests(limit=args.limit), indent=2))
        return 0
    if args.service_command == "mcp-log":
        print(json.dumps(service.mcp_invocations(limit=args.limit), indent=2))
        return 0
    return 0


def _run_console(memory: Memory, args: argparse.Namespace) -> int:
    if args.console_command == "login-token":
        raw = "alc_" + secrets.token_urlsafe(24)
        now = utc_now()
        expires_at = now + timedelta(minutes=args.expires_minutes)
        namespaces = args.namespaces or ["user/default"]
        capabilities = _split_csv(args.capabilities) if args.capabilities else [
            "memory:read",
            "memory:review",
            "memory:admin",
            "memory:jobs",
            "memory:policy",
        ]
        metadata = {
            "expires_at": expires_at.isoformat(),
            "namespace_grants": namespaces,
            "capabilities": capabilities,
            "privacy_ceiling": args.privacy_ceiling,
            "created_by": "aletheia console login-token",
        }
        with memory.store.transaction():
            memory.store.connection.execute(
                """
                INSERT INTO console_action_confirmations (
                    id, namespace, action_type, target_id, target_type,
                    confirmation_text, reason, actor, created_at, metadata_json
                )
                VALUES (?, ?, 'console_login_token', NULL, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("conf"),
                    namespaces[0] if len(namespaces) == 1 else None,
                    _hash_secret(raw),
                    "Console login token issued.",
                    args.actor,
                    now.isoformat(),
                    json.dumps(metadata, sort_keys=True),
                ),
            )
        print(json.dumps({"login_token": raw, "expires_at": expires_at.isoformat(), "namespace_grants": namespaces, "capabilities": capabilities}, indent=2))
        return 0
    if args.console_command == "sessions":
        clauses = [] if args.include_revoked else ["revoked_at IS NULL"]
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        rows = memory.store.connection.execute(
            f"SELECT * FROM console_sessions {where} ORDER BY created_at DESC"
        ).fetchall()
        print(json.dumps([_row_dict(row, redact_keys={"session_token_hash", "csrf_token_hash"}) for row in rows], indent=2))
        return 0
    if args.console_command == "revoke-session":
        with memory.store.transaction():
            memory.store.connection.execute(
                "UPDATE console_sessions SET revoked_at = ? WHERE id = ?",
                (utc_now_iso(), args.session_id),
            )
        print(json.dumps({"revoked": args.session_id}, indent=2))
        return 0
    return 0


def _run_reviews(memory: Memory, args: argparse.Namespace) -> int:
    if args.reviews_command == "list":
        _print_json([
            asdict(task)
            for task in memory.list_review_tasks(
                namespace=args.namespace,
                status=args.status,
                task_type=args.task_type,
                severity=args.severity,
                limit=args.limit,
            )
        ])
        return 0
    if args.reviews_command == "show":
        task = memory.get_review_task(args.task_id)
        _print_json(
            {
                "task": asdict(task),
                "events": [asdict(event) for event in memory.list_review_task_events(args.task_id)],
            }
        )
        return 0
    if args.reviews_command == "generate":
        _print_json([asdict(task) for task in memory.generate_review_tasks(args.namespace)])
        return 0
    if args.reviews_command == "resolve":
        _print_json(asdict(memory.resolve_review_task(args.task_id, resolution=args.resolution, reason=args.reason, actor=args.actor)))
        return 0
    if args.reviews_command == "dismiss":
        _print_json(asdict(memory.dismiss_review_task(args.task_id, reason=args.reason, actor=args.actor)))
        return 0
    if args.reviews_command == "defer":
        _print_json(asdict(memory.defer_review_task(args.task_id, reason=args.reason, actor=args.actor)))
        return 0
    return 0


def _run_metrics(memory: Memory, args: argparse.Namespace) -> int:
    if args.metrics_command == "snapshot":
        _print_json(asdict(memory.metrics_snapshot(namespace=args.namespace, project_id=args.project, source=args.source)))
        return 0
    if args.metrics_command == "latest":
        snapshot = memory.latest_metric_snapshot(namespace=args.namespace) or memory.metrics_snapshot(namespace=args.namespace, source="cli_latest")
        _print_json(asdict(snapshot))
        return 0
    if args.metrics_command == "list":
        _print_json([asdict(snapshot) for snapshot in memory.list_metric_snapshots(namespace=args.namespace, limit=args.limit)])
        return 0
    return 0


def _run_traces(memory: Memory, args: argparse.Namespace) -> int:
    if args.traces_command == "retrieval":
        _print_json(asdict(memory.trace_retrieval(
            args.namespace,
            query=args.query,
            retrieval_mode=args.mode,
            project_id=args.project,
            session_id=args.session,
            limit=args.limit,
        )))
        return 0
    if args.traces_command == "context":
        _print_json(asdict(memory.trace_context_pack(
            args.namespace,
            query=args.query,
            retrieval_mode=args.mode,
            project_id=args.project,
            session_id=args.session,
            token_budget=args.budget,
        )))
        return 0
    if args.traces_command == "list":
        _print_json([asdict(trace) for trace in memory.list_traces(namespace=args.namespace, trace_type=args.trace_type, limit=args.limit)])
        return 0
    if args.traces_command == "show":
        _print_json(
            {
                "trace": asdict(memory.get_trace(args.trace_id)),
                "events": [asdict(event) for event in memory.list_trace_events(args.trace_id)],
                "items": [asdict(item) for item in memory.list_trace_items(args.trace_id)],
            }
        )
        return 0
    if args.traces_command == "items":
        _print_json([asdict(item) for item in memory.list_trace_items(args.trace_id)])
        return 0
    return 0


def _run_notifications(memory: Memory, args: argparse.Namespace) -> int:
    if args.notifications_command == "list":
        _print_json([asdict(item) for item in memory.list_notifications(namespace=args.namespace, status=args.status, limit=args.limit)])
        return 0
    if args.notifications_command == "create":
        _print_json(asdict(memory.create_notification(
            args.namespace,
            notification_type=args.event_type,
            title=args.title,
            message=args.message,
            severity=args.severity,
            target_type=args.target_type,
            target_id=args.target_id,
            metadata=_json_arg(args.metadata_json),
        )))
        return 0
    if args.notifications_command == "dismiss":
        _print_json(asdict(memory.dismiss_notification(args.notification_id)))
        return 0
    if args.notifications_command == "snooze":
        _print_json(asdict(memory.snooze_notification(args.notification_id, until=args.until)))
        return 0
    return 0


def _run_reports(memory: Memory, args: argparse.Namespace) -> int:
    if args.reports_command == "export":
        _print_json(asdict(memory.export_report(
            namespace=args.namespace,
            report_type=args.report_type,
            format=args.format,
            output_path=args.output,
            filters=_json_arg(args.filters_json),
        )))
        return 0
    if args.reports_command == "list":
        _print_json([asdict(report) for report in memory.list_reports(namespace=args.namespace, report_type=args.report_type, limit=args.limit)])
        return 0
    if args.reports_command == "show":
        _print_json(asdict(memory.get_report(args.report_id)))
        return 0
    return 0


def _resolve_client_id(auth: AuthService, value: str) -> str:
    for client in auth.list_clients(include_disabled=True):
        if client.id == value or client.name == value:
            return client.id
    return auth.create_client(name=value, client_type="agent").id


def _print_json(value) -> None:
    print(json.dumps(value, indent=2))


def _hash_secret(value: str) -> str:
    return AuthService.hash_secret(value)


def _row_dict(row, *, redact_keys: set[str] | None = None) -> dict:
    data = dict(row)
    redact_keys = redact_keys or set()
    if "metadata_json" in data and data["metadata_json"]:
        metadata = json.loads(data["metadata_json"])
        for key in redact_keys:
            if key in metadata:
                metadata[key] = "<redacted>"
        data["metadata"] = metadata
        data.pop("metadata_json", None)
    return data


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _json_arg(value: str | None) -> dict:
    if not value:
        return {}
    return json.loads(value)


def _add_db_namespace(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default="./aletheia.db")
    parser.add_argument("--namespace", default="user/default")


def _format_claim(claim) -> str:
    return (
        f"[{claim.id}] {claim_text(claim.subject, claim.predicate, claim.object)}\n"
        f"type: {claim.memory_type}\n"
        f"status: {claim.status}\n"
        f"confidence: {claim.confidence_effective:.2f}\n"
        f"evidence: {', '.join(claim.evidence_ids) or '-'}\n"
    )


def _format_batch(batch) -> str:
    return (
        f"[{batch.id}] ingestion batch\n"
        f"namespace: {batch.namespace}\n"
        f"source_type: {batch.source_type}\n"
        f"title: {batch.title or '-'}\n"
        f"project: {batch.project_id or '-'}\n"
        f"session: {batch.session_id or '-'}\n"
        f"evidence: {', '.join(batch.evidence_ids) or '-'}\n"
    )


def _format_extraction_run(run) -> str:
    warnings = "\n".join(f"- {warning}" for warning in run.warnings)
    if warnings:
        warnings = "\nwarnings:\n" + warnings
    return (
        f"[{run.id}] extraction run\n"
        f"namespace: {run.namespace}\n"
        f"extractor: {run.extractor_name}@{run.extractor_version}\n"
        f"batch: {run.batch_id or '-'}\n"
        f"evidence: {', '.join(run.evidence_ids) or '-'}\n"
        f"candidates: {run.candidate_count}\n"
        f"stored: {run.stored_candidate_count}\n"
        f"dry_run: {str(run.dry_run).lower()}"
        f"{warnings}\n"
    )


def _format_candidate(candidate) -> str:
    spans = ", ".join(
        f"{span.evidence_id}:{span.start_char}-{span.end_char}"
        for span in candidate.evidence_spans
    )
    return (
        f"[{candidate.id}] {claim_text(candidate.subject, candidate.predicate, candidate.object)}\n"
        f"type: {candidate.memory_type}\n"
        f"status: {candidate.candidate_status}\n"
        f"suggested_confidence: {candidate.suggested_confidence:.2f}\n"
        f"duplicate_risk: {candidate.duplicate_risk:.2f}\n"
        f"contradiction_risk: {candidate.contradiction_risk:.2f}\n"
        f"categories: {', '.join(candidate.suggested_categories) or '-'}\n"
        f"entities: {', '.join(candidate.suggested_entities) or '-'}\n"
        f"spans: {spans or '-'}\n"
    )


def _format_inference(inference) -> str:
    return (
        f"[{inference.id}] {inference.text}\n"
        f"type: {inference.inference_type}\n"
        f"engine: {inference.engine}\n"
        f"status: {inference.status}\n"
        f"strength: {inference.inference_strength}\n"
        f"confidence: {inference.suggested_truth_confidence:.2f}\n"
        f"sources: {', '.join(inference.source_claim_ids + inference.source_evidence_ids) or '-'}\n"
    )


def _format_rule(rule) -> str:
    scope = rule.namespace or "*"
    enabled = "enabled" if rule.enabled else "disabled"
    return (
        f"[{rule.id}] {rule.name}\n"
        f"scope: {scope}\n"
        f"type: {rule.rule_type}\n"
        f"status: {enabled}\n"
        f"description: {rule.description}\n"
    )


def _format_reflection(reflection) -> str:
    return (
        f"[{reflection.id}] {reflection.title}\n"
        f"status: {reflection.status}\n"
        f"level: {reflection.abstraction_level}\n"
        f"confidence: {reflection.confidence_effective:.2f}\n"
        f"text: {reflection.text}\n"
        f"sources: {', '.join(reflection.source_claim_ids + reflection.source_evidence_ids + reflection.source_reflection_ids) or '-'}\n"
    )


def _format_derivation_trace(trace) -> str:
    lines = [f"{trace.target_type} {trace.target_id}"]
    for edge in trace.edges:
        lines.append(
            f"  <- {edge.source_type} {edge.source_id} "
            f"({edge.relationship}, confidence {edge.confidence:.2f})"
        )
    if trace.root_evidence_ids:
        lines.append("root_evidence: " + ", ".join(trace.root_evidence_ids))
    if trace.invalidation_risks:
        lines.append("risks:")
        lines.extend(f"- {risk}" for risk in trace.invalidation_risks)
    return "\n".join(lines) + "\n"


def _format_invalidation(event) -> str:
    return (
        f"[{event.id}] {event.affected_type} {event.affected_id}\n"
        f"source: {event.source_type} {event.source_id}\n"
        f"action: {event.action}\n"
        f"reason: {event.reason}\n"
    )


def _format_cluster(cluster) -> str:
    return (
        f"[{cluster.id}] {cluster.label or '-'}\n"
        f"type: {cluster.cluster_type}\n"
        f"confidence: {cluster.confidence:.2f}\n"
        f"members: {', '.join(cluster.member_ids) or '-'}\n"
    )


def _format_semantic_relation(relation) -> str:
    return (
        f"[{relation.id}] {relation.relation_type}\n"
        f"source: {relation.source_type} {relation.source_id}\n"
        f"target: {relation.target_type} {relation.target_id}\n"
        f"confidence: {relation.confidence:.2f}\n"
    )


def _format_abstraction(abstraction) -> str:
    return (
        f"[{abstraction.id}] level {abstraction.abstraction_level}\n"
        f"status: {abstraction.status}\n"
        f"policy: {abstraction.information_loss_policy}\n"
        f"text: {abstraction.abstraction_text}\n"
        f"sources: {', '.join(abstraction.source_ids) or '-'}\n"
    )


def _format_entity(entity) -> str:
    return (
        f"[{entity.id}] {entity.canonical_name}\n"
        f"type: {entity.entity_type}\n"
        f"namespace: {entity.namespace}\n"
        f"aliases: {', '.join(entity.aliases) or '-'}\n"
    )


def _format_conflict(conflict) -> str:
    return (
        f"[{conflict.id}] {conflict.subject}.{conflict.predicate}\n"
        f"status: {conflict.status}\n"
        f"active_claim: {conflict.active_claim_id or '-'}\n"
        f"claims: {', '.join(conflict.claim_ids) or '-'}\n"
    )


def _format_conflict_family(family) -> str:
    return (
        f"[{family.id}] {family.subject}.{family.predicate}\n"
        f"type: {family.conflict_type}\n"
        f"status: {family.status}\n"
        f"strategy: {family.resolution_strategy or '-'}\n"
        f"active_claim: {family.active_claim_id or '-'}\n"
        f"claims: {', '.join(family.claim_ids) or '-'}\n"
    )


def _format_confidence_snapshot(snapshot, include_explanation: bool = False) -> str:
    lines = [
        f"[{snapshot.claim_id}]",
        f"truth_confidence: {snapshot.truth_confidence:.3f}",
        f"retrieval_salience: {snapshot.retrieval_salience:.3f}",
        f"base_confidence: {snapshot.base_confidence:.3f}",
        f"effective_confidence: {snapshot.effective_confidence:.3f}",
        f"decay_factor: {snapshot.decay_factor:.3f}",
        f"source_reliability_factor: {snapshot.source_reliability_factor:.3f}",
        f"feedback_factor: {snapshot.feedback_factor:.3f}",
        f"contradiction_factor: {snapshot.contradiction_factor:.3f}",
        f"verification_factor: {snapshot.verification_factor:.3f}",
        f"half_life_days: {snapshot.half_life_days:.1f}",
        f"age_days: {snapshot.age_days:.2f}",
        f"computed_at: {snapshot.computed_at}",
    ]
    if include_explanation and snapshot.explanation:
        lines.append(f"explanation: {snapshot.explanation}")
    return "\n".join(lines) + "\n"


def _format_policy(policy) -> str:
    return (
        f"[{policy.id}]\n"
        f"namespace: {policy.namespace or '*'}\n"
        f"memory_type: {policy.memory_type or '*'}\n"
        f"predicate: {policy.predicate or '*'}\n"
        f"half_life_days: {policy.half_life_days:.1f}\n"
        f"reason: {policy.reason}\n"
    )


def _format_curation_decision(decision) -> str:
    before = (
        f"{decision.confidence_before:.3f}"
        if decision.confidence_before is not None
        else "-"
    )
    after = (
        f"{decision.confidence_after:.3f}"
        if decision.confidence_after is not None
        else "-"
    )
    return (
        f"[{decision.id}] {decision.decision_type}\n"
        f"claim: {decision.claim_id or '-'}\n"
        f"target_status: {decision.target_status or '-'}\n"
        f"applied: {str(decision.applied).lower()}\n"
        f"dry_run: {str(decision.dry_run).lower()}\n"
        f"confidence_before: {before}\n"
        f"confidence_after: {after}\n"
        f"reason: {decision.reason}\n"
    )


def _format_event(event, include_content: bool = False) -> str:
    content = event.content.replace("\n", " ")
    if not include_content and len(content) > 100:
        content = content[:97] + "..."
    lines = [
        f"[{event.id}] {event.source_type}",
        f"namespace: {event.namespace}",
        f"created_at: {event.created_at}",
        f"trust: {event.trust_level}",
        f"privacy: {event.privacy_level}",
        f"hash: {event.content_hash}",
        f"content: {content}",
    ]
    return "\n".join(lines) + "\n"


def _format_audit(audit: dict) -> str:
    lines = [
        f"Target: {audit['target_type']} {audit['target_id']}",
    ]
    if audit["target_type"] == "claim":
        claim = audit["claim"]
        lines.extend(
            [
                "Claim:",
                f"  {claim_text(claim['subject'], claim['predicate'], claim['object'])}",
                f"  type: {claim['memory_type']}",
                f"  status: {claim['status']}",
                f"  confidence: {claim['confidence_effective']:.2f}",
            ]
        )
        lines.append("Evidence:")
        for event in audit["evidence"]:
            content = event["content"].replace("\n", " ")
            if len(content) > 100:
                content = content[:97] + "..."
            lines.append(
                f"  [{event['id']}] {event['source_type']} "
                f"{event['created_at']} :: {content}"
            )
        if audit["conflicts"]:
            lines.append("Conflicts:")
            for conflict in audit["conflicts"]:
                lines.append(f"  [{conflict['id']}] {conflict['status']}")
    else:
        event = audit["evidence"]
        lines.extend(
            [
                "Evidence:",
                f"  source_type: {event['source_type']}",
                f"  created_at: {event['created_at']}",
                f"  content_hash: {event['content_hash']}",
                f"  content: {event['content']}",
            ]
        )
    lines.append("Audit Trail:")
    if not audit["audit"]:
        lines.append("  No audit entries found.")
    for entry in audit["audit"]:
        lines.append(f"  {entry['created_at']} {entry['action']} {entry['details']}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
