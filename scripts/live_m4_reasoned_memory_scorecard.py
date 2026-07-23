"""Live M4 scorecard: Reasoned Memory and Lossless Abstraction."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import Memory
from aletheia.core.errors import ValidationError


NAMESPACE = "user/default"


@dataclass
class CaseResult:
    category: str
    case: str
    interface: str
    passed: bool
    details: str


class M4Runner:
    def __init__(self, db_path: Path, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.results: list[CaseResult] = []
        self.ids: dict[str, str] = {}

    def run(self) -> list[CaseResult]:
        cases: list[tuple[str, str, str, Callable[[], str]]] = [
            ("Migration", "Initialize schema 1.3.0 with M4 tables and default rules", "CLI/API", self.case_init_schema),
            ("Migration", "Migration is idempotent and creates no automatic reasoning records", "API", self.case_migration_idempotence),
            ("Setup", "Create project and source memories with contextual scope", "CLI/API", self.case_project_and_seed_memory),
            ("Inference", "Inference runs execute in dry-run mode without persistence", "CLI/API", self.case_inference_dry_run),
            ("Inference", "Logical, semantic, factual, and reflection inference persist candidates deterministically", "API", self.case_inference_apply),
            ("Inference", "Semantic inference creates relations and clusters, not facts", "API", self.case_semantic_relations_not_facts),
            ("Inference", "Factual inference creates pending candidates with source lineage", "API", self.case_factual_candidates_lineage),
            ("Inference", "Inference candidates can be reviewed and explained", "API", self.case_review_and_explain),
            ("Inference", "Validated inference promotes through integrity gates", "API", self.case_promote_validated_inference),
            ("Inference", "Speculative inference cannot promote by default", "API", self.case_speculative_promotion_blocked),
            ("Rules", "Rules can be registered, enabled, disabled, run, logged, and repeated safely", "API", self.case_rule_registry),
            ("Reflection", "Reflections build from claims and evidence with backlinks", "API", self.case_build_reflection),
            ("Reflection", "Reflections expand back to source claims and evidence", "CLI/API", self.case_expand_reflection),
            ("Reflection", "Abstractions preserve source links with lossless policy", "CLI/API", self.case_abstraction),
            ("Derivation", "Derived records expose derivation traces to root evidence", "CLI/API", self.case_derivation_trace),
            ("Context", "Context packs include active reflections with labels", "API", self.case_context_active_reflection),
            ("Context", "Pending inference candidates are excluded by default", "API", self.case_context_excludes_pending_inference),
            ("Context", "Validated inferences can be included only when explicitly requested", "API", self.case_context_optional_inference),
            ("Context", "Structured context can include derivation metadata", "API", self.case_context_derivation_metadata),
            ("Invalidation", "Source supersession marks derived reflections stale and queues refresh", "API", self.case_invalidation_propagates),
            ("Invalidation", "Stale derived memories are excluded from normal context with warnings", "API", self.case_stale_context_excluded),
            ("CLI", "M4 infer, rules, reflect, derivation, clusters, and abstractions commands work", "CLI", self.case_cli_groups),
            ("Compatibility", "Existing M3 search/context commands still work after M4", "CLI/API", self.case_existing_m3_commands),
        ]
        for category, case, interface, fn in cases:
            try:
                self.results.append(CaseResult(category, case, interface, True, fn()))
            except Exception as exc:  # noqa: BLE001 - live scorecard should continue.
                self.results.append(CaseResult(category, case, interface, False, str(exc)))
        return self.results

    def case_init_schema(self) -> str:
        health = json.loads(self.cli("init", "--db", str(self.db_path)).stdout)
        assert health["schema_version"] == "1.3.0"
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            names = {
                row["name"]
                for row in memory.store.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
                ).fetchall()
            }
            required = {
                "inference_runs",
                "inference_candidates",
                "inference_decisions",
                "inference_rules",
                "rule_execution_log",
                "derivation_edges",
                "derived_claim_links",
                "reflections",
                "reflection_sources",
                "abstraction_records",
                "abstraction_sources",
                "semantic_clusters",
                "semantic_cluster_members",
                "semantic_relations",
                "invalidation_events",
                "refresh_queue",
                "inference_explanations",
            }
            assert required.issubset(names)
            default_rules = {rule.id for rule in memory.list_rules(namespace=NAMESPACE)}
            assert {
                "rule_m4_superseded_not_current",
                "rule_m4_semantic_relation",
                "rule_m4_project_focus_factual",
                "rule_m4_source_invalidation_propagates",
            }.issubset(default_rules)
            assert memory.list_inferences(NAMESPACE) == []
            assert memory.list_reflections(namespace=NAMESPACE) == []
            return f"schema_version=1.3.0, m4_tables={len(required)}, default_rules={len(default_rules)}"
        finally:
            memory.close()

    def case_migration_idempotence(self) -> str:
        first = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            before_rules = len(first.list_rules(namespace=NAMESPACE))
            before_runs = len(first.store.connection.execute("SELECT id FROM inference_runs").fetchall())
        finally:
            first.close()
        second = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            after_rules = len(second.list_rules(namespace=NAMESPACE))
            after_runs = len(second.store.connection.execute("SELECT id FROM inference_runs").fetchall())
            assert second.health()["schema_version"] == "1.3.0"
            assert before_rules == after_rules
            assert before_runs == after_runs == 0
            assert second.list_reflections(namespace=NAMESPACE) == []
            return f"rules={after_rules}, inference_runs={after_runs}"
        finally:
            second.close()

    def case_project_and_seed_memory(self) -> str:
        project = json.loads(
            self.cli(
                "projects",
                "create",
                "--db",
                str(self.db_path),
                "--namespace",
                NAMESPACE,
                "--id",
                "aletheia",
                "--title",
                "Aletheia Memory Library",
            ).stdout
        )
        assert project["id"] == "aletheia"
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            milestone = memory.remember(
                namespace=NAMESPACE,
                memory_type="project",
                subject="project:aletheia",
                predicate="current_milestone",
                object="M4",
                confidence=0.92,
                project_id="aletheia",
            )
            name = memory.remember(
                namespace=NAMESPACE,
                memory_type="project",
                subject="M4",
                predicate="name",
                object="Reasoned Memory",
                confidence=0.91,
                project_id="aletheia",
            )
            progress = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user.progress",
                predicate="prefers_response_style",
                object="concise progress updates",
                confidence=0.90,
            )
            architecture = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user.architecture",
                predicate="prefers_response_style",
                object="comprehensive architecture explanations",
                confidence=0.88,
            )
            memory.scope_claim(
                progress.id,
                scope_type="contextual",
                applies_when="progress_update",
                reason="Concise preference applies to progress updates.",
            )
            memory.scope_claim(
                architecture.id,
                scope_type="contextual",
                applies_when="architecture_or_design_request",
                reason="Comprehensive preference applies to architecture/design requests.",
            )
            self.ids.update(
                {
                    "milestone": milestone.id,
                    "milestone_name": name.id,
                    "progress": progress.id,
                    "architecture": architecture.id,
                }
            )
            return f"claims={', '.join(self.ids[key] for key in ['milestone', 'milestone_name', 'progress', 'architecture'])}"
        finally:
            memory.close()

    def case_inference_dry_run(self) -> str:
        run = json.loads(
            self.cli(
                "infer",
                "run",
                "--db",
                str(self.db_path),
                "--namespace",
                NAMESPACE,
                "--project",
                "aletheia",
                "--engines",
                "logical,semantic,factual,reflection",
                "--json",
            ).stdout
        )
        assert run["dry_run"] is True
        assert run["inference_count"] >= 3
        assert run["persisted_count"] == 0
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            assert memory.list_inferences(NAMESPACE) == []
            return f"dry_run={run['id']}, candidates={run['inference_count']}"
        finally:
            memory.close()

    def case_inference_apply(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            first = memory.run_inference(
                NAMESPACE,
                engines=["logical"],
                target_claim_ids=[self.ids["milestone"]],
                dry_run=True,
            )
            second = memory.run_inference(
                NAMESPACE,
                engines=["logical"],
                target_claim_ids=[self.ids["milestone"]],
                dry_run=True,
            )
            assert first.inference_count == second.inference_count
            run = memory.run_inference(
                NAMESPACE,
                engines=["logical", "semantic", "factual", "reflection"],
                project_id="aletheia",
                dry_run=False,
            )
            inferences = memory.list_inferences(NAMESPACE)
            assert run.persisted_count == run.inference_count
            assert {item.engine for item in inferences} >= {"logical", "factual"}
            self.ids["factual_inference"] = next(item.id for item in inferences if item.engine == "factual")
            self.ids["reflection_inference"] = next(item.id for item in inferences if item.engine == "reflection")
            self.ids["logical_inference"] = next(item.id for item in inferences if item.engine == "logical")
            return f"run={run.id}, persisted={run.persisted_count}, deterministic_logical={first.inference_count}"
        finally:
            memory.close()

    def case_semantic_relations_not_facts(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            relations = memory.list_semantic_relations(namespace=NAMESPACE)
            clusters = memory.list_semantic_clusters(namespace=NAMESPACE)
            assert relations
            assert clusters
            assert relations[0].metadata["truth_effect"] == "none"
            assert not any(claim.memory_type == "inference" for claim in memory.list_claims(namespace=NAMESPACE))
            return f"relations={len(relations)}, clusters={len(clusters)}, truth_effect=none"
        finally:
            memory.close()

    def case_factual_candidates_lineage(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            inference = memory.read_inference(self.ids["factual_inference"])
            assert inference.status == "pending_review"
            assert inference.source_claim_ids == sorted([self.ids["milestone"], self.ids["milestone_name"]])
            assert inference.source_evidence_ids
            assert inference.suggested_truth_confidence <= inference.derivation_confidence
            return f"inference={inference.id}, sources={len(inference.source_claim_ids)}"
        finally:
            memory.close()

    def case_review_and_explain(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            decision = memory.review_inference(
                self.ids["factual_inference"],
                decision="validate",
                reason="Inference is directly supported by active project claims.",
            )
            reject_target = next(
                inference
                for inference in memory.list_inferences(NAMESPACE, engine="logical")
                if inference.id != self.ids["logical_inference"]
            )
            rejection = memory.reject_inference(
                reject_target.id,
                reason="Exercise rejection lifecycle in live M4.",
            )
            explanation = memory.explain_inference(self.ids["factual_inference"])
            assert decision.decision == "validate"
            assert rejection.decision == "reject"
            assert memory.read_inference(reject_target.id).status == "rejected"
            assert explanation.sources
            assert explanation.rule["id"] == "rule_m4_project_focus_factual"
            assert explanation.confidence["inference_strength"] == "entailed"
            explanation_rows = memory.store.connection.execute(
                "SELECT id FROM inference_explanations WHERE inference_id = ?",
                (self.ids["factual_inference"],),
            ).fetchall()
            assert explanation_rows
            return f"validated={decision.inference_id}, rejected={reject_target.id}, can_promote={explanation.can_promote}"
        finally:
            memory.close()

    def case_promote_validated_inference(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim = memory.promote_inference(
                self.ids["factual_inference"],
                reason="Promote validated M4 focus inference.",
            )
            self.ids["promoted_inference_claim"] = claim.id
            trace = memory.trace_derivation(claim.id, target_type="claim")
            assert claim.memory_type == "inference"
            assert any(edge.source_id == self.ids["factual_inference"] for edge in trace.edges)
            assert trace.root_evidence_ids
            return f"inference={self.ids['factual_inference']} -> claim={claim.id}"
        finally:
            memory.close()

    def case_speculative_promotion_blocked(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            memory.review_inference(
                self.ids["reflection_inference"],
                decision="mark_speculative",
                reason="Reflection candidate needs human review.",
            )
            try:
                memory.promote_inference(
                    self.ids["reflection_inference"],
                    target_type="reflection",
                    reason="Should fail without force.",
                )
            except ValidationError:
                return f"blocked={self.ids['reflection_inference']}"
            raise AssertionError("Speculative inference promoted unexpectedly.")
        finally:
            memory.close()

    def case_rule_registry(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            rule = memory.define_rule(
                NAMESPACE,
                name="m4_live_current_claim_rule",
                rule_type="logical",
                description="Live test rule for deterministic currentness inference.",
                condition={"status": "active"},
                conclusion={"predicate": "is_current"},
            )
            assert memory.set_rule_enabled(rule.id, enabled=False).enabled is False
            assert memory.set_rule_enabled(rule.id, enabled=True).enabled is True
            first = memory.run_rule(rule.id, namespace=NAMESPACE, target_claim_ids=[self.ids["architecture"]], dry_run=False)
            second = memory.run_rule(rule.id, namespace=NAMESPACE, target_claim_ids=[self.ids["architecture"]], dry_run=False)
            logs = memory.store.connection.execute(
                "SELECT rule_id FROM rule_execution_log WHERE rule_id = ?",
                (rule.id,),
            ).fetchall()
            assert first.inference_count == second.inference_count
            assert logs
            return f"rule={rule.id}, repeated_count={first.inference_count}"
        finally:
            memory.close()

    def case_build_reflection(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            reflection = memory.build_reflection(
                NAMESPACE,
                source_claim_ids=[self.ids["progress"], self.ids["architecture"]],
                title="Context-sensitive response depth",
                text="User prefers concise progress updates and comprehensive architecture/design explanations.",
                abstraction_level=2,
                project_id="aletheia",
                reason="Combines two scoped response-style preferences.",
                require_review=False,
            )
            self.ids["reflection"] = reflection.id
            assert reflection.status == "active"
            assert reflection.source_claim_ids == sorted([self.ids["progress"], self.ids["architecture"]])
            assert reflection.source_evidence_ids
            assert reflection.abstraction_level == 2
            return f"reflection={reflection.id}, sources={len(reflection.source_claim_ids)}"
        finally:
            memory.close()

    def case_expand_reflection(self) -> str:
        expanded = json.loads(
            self.cli(
                "reflect",
                "expand",
                self.ids["reflection"],
                "--db",
                str(self.db_path),
                "--json",
            ).stdout
        )
        assert {claim["id"] for claim in expanded["source_claims"]} == {
            self.ids["progress"],
            self.ids["architecture"],
        }
        assert expanded["source_evidence"]
        assert expanded["derivation_edges"]
        return f"reflection={self.ids['reflection']}, evidence={len(expanded['source_evidence'])}"

    def case_abstraction(self) -> str:
        abstraction = json.loads(
            self.cli(
                "abstractions",
                "create",
                "--db",
                str(self.db_path),
                "--namespace",
                NAMESPACE,
                "--sources",
                self.ids["reflection"],
                "--source-type",
                "reflection",
                "--text",
                "Response depth is context-sensitive.",
                "--level",
                "3",
                "--reason",
                "Live M4 abstraction.",
                "--json",
            ).stdout
        )
        self.ids["abstraction"] = abstraction["id"]
        assert abstraction["information_loss_policy"] == "lossless_via_backlinks"
        assert abstraction["source_ids"] == [self.ids["reflection"]]
        return f"abstraction={abstraction['id']}, policy={abstraction['information_loss_policy']}"

    def case_derivation_trace(self) -> str:
        trace = json.loads(
            self.cli(
                "derivation",
                "trace",
                self.ids["reflection"],
                "--db",
                str(self.db_path),
                "--type",
                "reflection",
                "--json",
            ).stdout
        )
        assert trace["root_evidence_ids"]
        assert any(edge["source_id"] == self.ids["progress"] for edge in trace["edges"])
        return f"nodes={len(trace['nodes'])}, evidence={len(trace['root_evidence_ids'])}"

    def case_context_active_reflection(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            pack = memory.context_pack(
                namespace=NAMESPACE,
                project_id="aletheia",
                query="Write the M4 contract.",
                retrieval_mode="hybrid",
            )
            assert any(item.reflection_id == self.ids["reflection"] for item in pack.reflection_memory)
            item = next(item for item in pack.reflection_memory if item.reflection_id == self.ids["reflection"])
            assert item.source_kind == "reflection"
            assert item.is_reflected is True
            return f"reflection_memory={len(pack.reflection_memory)}, source_kind={item.source_kind}"
        finally:
            memory.close()

    def case_context_excludes_pending_inference(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            pending = memory.read_inference(self.ids["logical_inference"])
            pack = memory.context_pack(
                namespace=NAMESPACE,
                query=pending.text,
                include_inferences=False,
            )
            assert pending.text not in pack.to_markdown()
            assert all(item.inference_id != pending.id for item in pack.items())
            return f"pending_excluded={pending.id}"
        finally:
            memory.close()

    def case_context_optional_inference(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            memory.review_inference(
                self.ids["logical_inference"],
                decision="validate",
                reason="Validated for optional context inclusion.",
            )
            pack = memory.context_pack(
                namespace=NAMESPACE,
                query="current claim",
                include_inferences=True,
            )
            assert any(item.inference_id == self.ids["logical_inference"] for item in pack.items())
            item = next(item for item in pack.items() if item.inference_id == self.ids["logical_inference"])
            assert item.source_kind == "inference"
            return f"optional_inference={item.inference_id}, label={item.source_kind}"
        finally:
            memory.close()

    def case_context_derivation_metadata(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            pack = memory.context_pack(
                namespace=NAMESPACE,
                project_id="aletheia",
                query="architecture design",
                include_derivation_metadata=True,
            )
            item = next(item for item in pack.reflection_memory if item.reflection_id == self.ids["reflection"])
            assert item.derivation
            assert item.derivation["root_evidence_ids"]
            return f"reflection_derivation_edges={len(item.derivation['edges'])}"
        finally:
            memory.close()

    def case_invalidation_propagates(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            replacement = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user.progress",
                predicate="prefers_response_style",
                object="concise progress updates but detailed milestone contracts",
                confidence=0.93,
            )
            memory.supersede_claim(
                self.ids["progress"],
                replacement.id,
                reason="Newer preference refines prior progress-update memory.",
            )
            reflection = memory.get_reflection(self.ids["reflection"])
            invalidations = memory.list_invalidations(
                namespace=NAMESPACE,
                target_id=self.ids["reflection"],
                target_type="reflection",
            )
            queued = memory.store.connection.execute(
                "SELECT id FROM refresh_queue WHERE target_id = ?",
                (self.ids["reflection"],),
            ).fetchall()
            assert reflection.status == "stale"
            assert invalidations
            assert queued
            self.ids["replacement_progress"] = replacement.id
            return f"reflection={reflection.status}, invalidations={len(invalidations)}, refresh={len(queued)}"
        finally:
            memory.close()

    def case_stale_context_excluded(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            pack = memory.context_pack(
                namespace=NAMESPACE,
                project_id="aletheia",
                query="response depth",
            )
            assert all(item.reflection_id != self.ids["reflection"] for item in pack.reflection_memory)
            assert any(warning.warning_type == "reflection_stale" for warning in pack.warnings)
            return f"reflection_memory={len(pack.reflection_memory)}, warnings={len(pack.warnings)}"
        finally:
            memory.close()

    def case_cli_groups(self) -> str:
        infer = json.loads(
            self.cli("infer", "list", "--db", str(self.db_path), "--namespace", NAMESPACE, "--json").stdout
        )
        rules = json.loads(
            self.cli("rules", "list", "--db", str(self.db_path), "--namespace", NAMESPACE, "--json").stdout
        )
        reflections = json.loads(
            self.cli("reflect", "list", "--db", str(self.db_path), "--namespace", NAMESPACE, "--json").stdout
        )
        invalidated = json.loads(
            self.cli("derivation", "invalidated", "--db", str(self.db_path), "--namespace", NAMESPACE, "--json").stdout
        )
        clusters = json.loads(
            self.cli("clusters", "list", "--db", str(self.db_path), "--namespace", NAMESPACE, "--json").stdout
        )
        abstractions = json.loads(
            self.cli("abstractions", "list", "--db", str(self.db_path), "--namespace", NAMESPACE, "--json").stdout
        )
        assert infer
        assert any(rule["id"] == "rule_m4_semantic_relation" for rule in rules)
        assert reflections
        assert invalidated
        assert clusters
        assert abstractions
        return "infer/rules/reflect/derivation/clusters/abstractions ok"

    def case_existing_m3_commands(self) -> str:
        search = self.cli(
            "search",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--mode",
            "hybrid",
            "Reasoned Memory",
        ).stdout
        context = self.cli(
            "context",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--project",
            "aletheia",
            "--query",
            "Write the M4 contract.",
            "--mode",
            "hybrid",
        ).stdout
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            assert self.ids["promoted_inference_claim"] in search
            assert memory.retrieve(namespace=NAMESPACE, query="Reasoned Memory", mode="hybrid")
            assert "## Memory Context" in context
            return "search/context/retrieve remain compatible"
        finally:
            memory.close()

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, "-m", "aletheia.cli.main", *args]
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if self.verbose or result.returncode != 0:
            print("$", " ".join(command))
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        result.check_returncode()
        return result


def print_scorecard(results: list[CaseResult]) -> None:
    passed = sum(1 for result in results if result.passed)
    print("M4 Live Scorecard: Reasoned Memory and Lossless Abstraction")
    print(f"Passed {passed}/{len(results)} cases")
    print()
    current_category = None
    for result in results:
        if result.category != current_category:
            current_category = result.category
            print(f"[{current_category}]")
        mark = "PASS" if result.passed else "FAIL"
        print(f"  {mark} | {result.case} ({result.interface})")
        print(f"       {result.details}")
    print()
    print(json.dumps([result.__dict__ for result in results], indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db")
    parser.add_argument("--keep-db", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db)
        runner = M4Runner(db_path, verbose=args.verbose)
        results = runner.run()
        print_scorecard(results)
        return 0 if all(result.passed for result in results) else 1

    with tempfile.TemporaryDirectory(prefix="aletheia_m4_live_") as tmp:
        db_path = Path(tmp) / "aletheia.db"
        runner = M4Runner(db_path, verbose=args.verbose)
        results = runner.run()
        print_scorecard(results)
        if args.keep_db:
            print(f"Database retained until temp cleanup: {db_path}")
        return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
