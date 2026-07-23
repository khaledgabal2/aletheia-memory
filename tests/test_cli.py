from __future__ import annotations

import re

from aletheia.cli.main import main


def test_cli_installed_docs_are_discoverable(capsys):
    assert main(["docs", "list"]) == 0
    list_output = capsys.readouterr().out
    assert "Documentation root:" in list_output
    assert "index: Documentation Index" in list_output
    assert "encryption-layer: Encryption Layer" in list_output
    assert "memory-lifecycle: Memory Lifecycle" in list_output

    assert main(["docs", "path", "core-concepts"]) == 0
    path_output = capsys.readouterr().out
    assert path_output.strip().endswith("docs/core_concepts.md")

    assert main(["docs", "show", "index"]) == 0
    show_output = capsys.readouterr().out
    assert "# Aletheia Documentation Index" in show_output


def test_cli_migrate_subcommands_preserve_parent_db(tmp_path, capsys):
    db = tmp_path / "custom.db"

    assert main(["migrate", "--db", str(db), "apply", "--dry-run"]) == 0
    assert db.exists()
    assert '"status": "completed"' in capsys.readouterr().out

    second_db = tmp_path / "leaf.db"
    assert main(["migrate", "plan", "--db", str(second_db)]) == 0
    assert second_db.exists()
    assert '"to_version": "1.3.0"' in capsys.readouterr().out


def test_cli_init_remember_search_and_conflicts(tmp_path, capsys):
    db = str(tmp_path / "aletheia.db")

    assert main(["init", "--db", db]) == 0
    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "practical and direct",
            "--confidence",
            "0.95",
            "--importance",
            "0.80",
        ]
    ) == 0
    assert main(
        [
            "search",
            "--db",
            db,
            "--namespace",
            "user/default",
            "response style",
        ]
    ) == 0
    assert "practical and direct" in capsys.readouterr().out

    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "long and highly detailed",
        ]
    ) == 0
    assert main(
        [
            "conflicts",
            "list",
            "--db",
            db,
            "--namespace",
            "user/default",
        ]
    ) == 0
    assert "unresolved" in capsys.readouterr().out


def test_cli_claims_audit_context_pack_and_conflict_resolution(tmp_path, capsys):
    db = str(tmp_path / "aletheia.db")

    assert main(["init", "--db", db]) == 0
    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "practical and direct",
            "--confidence",
            "0.95",
            "--importance",
            "0.80",
        ]
    ) == 0
    first_output = capsys.readouterr().out
    first_claim_id = re.search(r"\[(clm_[^\]]+)\]", first_output).group(1)

    assert main(
        [
            "claims",
            "promote",
            first_claim_id,
            "--to",
            "core",
            "--reason",
            "Stable high-importance preference.",
            "--db",
            db,
        ]
    ) == 0
    assert "status: core" in capsys.readouterr().out

    assert main(
        [
            "audit",
            first_claim_id,
            "--db",
            db,
        ]
    ) == 0
    audit_output = capsys.readouterr().out
    assert "Target: claim" in audit_output
    assert "Evidence:" in audit_output
    assert "Audit Trail:" in audit_output

    assert main(
        [
            "context-pack",
            "--db",
            db,
            "--namespace",
            "user/default",
            "response style",
        ]
    ) == 0
    context_output = capsys.readouterr().out
    assert "## Memory Context" in context_output
    assert "### Core Memory" in context_output

    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "long and highly detailed",
        ]
    ) == 0
    second_output = capsys.readouterr().out
    second_claim_id = re.search(r"\[(clm_[^\]]+)\]", second_output).group(1)

    assert main(
        [
            "conflicts",
            "list",
            "--db",
            db,
            "--namespace",
            "user/default",
        ]
    ) == 0
    conflicts_output = capsys.readouterr().out
    conflict_id = re.search(r"\[(conf_[^\]]+)\]", conflicts_output).group(1)

    assert main(
        [
            "conflicts",
            "resolve",
            conflict_id,
            "--active",
            second_claim_id,
            "--db",
            db,
            "--note",
            "Prefer the newer explicit statement.",
        ]
    ) == 0
    resolved_output = capsys.readouterr().out
    assert "status: resolved" in resolved_output

    assert main(
        [
            "claims",
            "show",
            first_claim_id,
            "--db",
            db,
        ]
    ) == 0
    assert '"status": "superseded"' in capsys.readouterr().out


def test_cli_events_feedback_and_search_filters(tmp_path, capsys):
    db = str(tmp_path / "aletheia.db")

    assert main(["init", "--db", db]) == 0
    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "Aletheia concise",
            "--confidence",
            "0.60",
        ]
    ) == 0
    preference_output = capsys.readouterr().out
    preference_claim_id = re.search(r"\[(clm_[^\]]+)\]", preference_output).group(1)
    preference_event_id = re.search(r"(evt_[A-Za-z0-9]+)", preference_output).group(1)

    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "project",
            "--subject",
            "project",
            "--predicate",
            "has_name",
            "--object",
            "Aletheia polishing",
        ]
    ) == 0
    capsys.readouterr()

    assert main(
        [
            "events",
            "list",
            "--db",
            db,
            "--namespace",
            "user/default",
        ]
    ) == 0
    assert preference_event_id in capsys.readouterr().out

    assert main(
        [
            "events",
            "show",
            preference_event_id,
            "--db",
            db,
            "--json",
        ]
    ) == 0
    event = capsys.readouterr().out
    assert f'"id": "{preference_event_id}"' in event
    assert '"source_type": "manual"' in event

    assert main(
        [
            "feedback",
            preference_claim_id,
            "--db",
            db,
            "--namespace",
            "user/default",
            "--signal",
            "confirmed",
            "--note",
            "Confirmed through CLI test.",
        ]
    ) == 0
    confirmed_output = capsys.readouterr().out
    confidence = float(re.search(r"confidence: ([0-9.]+)", confirmed_output).group(1))
    assert confidence > 0.60

    assert main(
        [
            "search",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "project",
            "Aletheia",
        ]
    ) == 0
    project_search = capsys.readouterr().out
    assert "type: project" in project_search
    assert "type: preference" not in project_search

    assert main(
        [
            "feedback",
            preference_claim_id,
            "--db",
            db,
            "--namespace",
            "user/default",
            "--signal",
            "wrong",
        ]
    ) == 0
    assert "status: rejected" in capsys.readouterr().out

    assert main(
        [
            "search",
            "--db",
            db,
            "--namespace",
            "user/default",
            "concise",
        ]
    ) == 0
    assert "No memories found." in capsys.readouterr().out

    assert main(
        [
            "search",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--status",
            "rejected",
            "concise",
        ]
    ) == 0
    rejected_search = capsys.readouterr().out
    assert "No memories found." in rejected_search

    assert main(
        [
            "claims",
            "show",
            preference_claim_id,
            "--db",
            db,
        ]
    ) == 0
    assert '"status": "rejected"' in capsys.readouterr().out


def test_cli_m3_ingest_extract_candidates_entities_categories_index(tmp_path, capsys):
    db = str(tmp_path / "aletheia.db")

    assert main(["init", "--db", db]) == 0
    assert main(
        [
            "ingest",
            "text",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--project",
            "aletheia",
            "--title",
            "M3 notes",
            "For architecture contracts, I want comprehensive detail. "
            "Aletheia M3 should focus on intelligent ingestion and semantic recall.",
        ]
    ) == 0
    ingest_output = capsys.readouterr().out
    batch_id = re.search(r"\[(ing_[^\]]+)\]", ingest_output).group(1)

    assert main(
        [
            "extract",
            "run",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--batch",
            batch_id,
        ]
    ) == 0
    assert "candidates: 2" in capsys.readouterr().out

    assert main(
        [
            "candidates",
            "list",
            "--db",
            db,
            "--namespace",
            "user/default",
        ]
    ) == 0
    candidates_output = capsys.readouterr().out
    assert "pending_review" in candidates_output
    candidate_blocks = candidates_output.strip().split("\n\n")
    candidate_id = next(
        re.search(r"\[(cand_[^\]]+)\]", block).group(1)
        for block in candidate_blocks
        if "architecture contracts" in block
    )

    assert main(
        [
            "candidates",
            "promote",
            candidate_id,
            "--db",
            db,
            "--reason",
            "Direct user preference.",
        ]
    ) == 0
    assert "status: active" in capsys.readouterr().out

    assert main(
        [
            "entities",
            "list",
            "--db",
            db,
            "--namespace",
            "user/default",
        ]
    ) == 0
    assert "Aletheia Memory Library" in capsys.readouterr().out

    assert main(["categories", "list", "--db", db]) == 0
    assert "preference" in capsys.readouterr().out

    assert main(
        [
            "index",
            "semantic",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--target",
            "claims",
        ]
    ) == 0
    assert '"indexed_count": 1' in capsys.readouterr().out

    assert main(
        [
            "search",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--mode",
            "hybrid",
            "How detailed should design contracts be?",
        ]
    ) == 0
    search_output = capsys.readouterr().out
    assert "comprehensive detail" in search_output
    assert "(hybrid)" in search_output
