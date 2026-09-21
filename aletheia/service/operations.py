"""Authorization for legacy object operations and operator-selected providers."""
from __future__ import annotations

from aletheia.core.errors import NotFoundError
from aletheia.service.errors import forbidden, not_found, validation_error
from aletheia.service.reads import ReadAccess
from aletheia.service.replay import record_target, record_provider


class OperationAccess(ReadAccess):
    def llm_run_allowed(self, run):
        if not self.namespace(run["namespace"]):
            return False
        metadata = run.get("metadata") or {}
        if not self.auth.privacy_allows(self.context, metadata.get("privacy_level", "personal")):
            return False
        return all(self.allowed("evidence", value) for value in run.get("input_evidence_ids", []))

    def scope(self, capability, namespace, project_id=None):
        self.auth.require_capability(self.context, capability)
        if namespace is not None and (not isinstance(namespace, str) or not namespace.strip()):
            raise validation_error("namespace must be a nonempty string.")
        if namespace:
            self.auth.require_namespace(self.context, namespace=namespace, project_id=project_id)
        elif "*" not in self.context.namespace_grants:
            raise validation_error("An explicit authorized namespace is required.")
        return namespace

    def target(self, kind, target_id, *, namespace=None):
        kind = {"candidate": "candidate_claim", "event": "evidence", "evidence_event": "evidence"}.get(kind, kind)
        readers = {
            "claim": self.memory.read_claim, "candidate_claim": self.memory.read_candidate,
            "evidence": self.memory.read_event, "session": self.memory.get_session,
            "conflict": self.memory.read_conflict, "conflict_family": self.memory.read_conflict_family,
            "inference": self.memory.read_inference, "reflection": self.memory.get_reflection,
            "evaluation_set": self.memory.get_eval_set, "policy_proposal": self.memory.get_policy_proposal,
            "job": self.memory.get_job, "ingestion_batch": self.memory.read_ingestion_batch,
        }
        if kind not in readers or not isinstance(target_id, str) or not target_id:
            raise validation_error("A supported target type and target ID are required.")
        item = readers[kind](target_id)
        if namespace is not None and item.namespace != namespace:
            raise forbidden("Target does not belong to the requested namespace.")
        if kind in {"claim", "candidate_claim", "evidence", "conflict", "conflict_family", "inference", "reflection"}:
            if not self.allowed(kind, target_id):
                raise forbidden("Target is unavailable under the current access policy.")
        else:
            self.auth.require_namespace(self.context, namespace=item.namespace, project_id=getattr(item, "project_id", None))
            record_target(kind, item)
        return item

    def evidence_sources(self, namespace, evidence_ids):
        if not isinstance(evidence_ids, list):
            raise validation_error("evidence_ids must be a list.")
        for evidence_id in evidence_ids:
            self.target("evidence", evidence_id, namespace=namespace)

    def provider(self, requested, *, source_task=False, privacy_level="personal"):
        record_provider(requested, source_task, privacy_level)
        # HTTP accepts built-in IDs and installed provider IDs, never Python
        # entrypoints or an ambient plugin-entrypoint environment fallback.
        builtins = {"mock", "mock_llm", "llm", "local_http", "ollama_style", "openai_compatible"}
        source_privacy = [self.memory.read_event(value).privacy_level for (kind, value), allowed in self.checked.items()
                          if kind == "evidence" and allowed]
        if source_task and "secret" in source_privacy:
            raise forbidden("Secret evidence is unavailable to LLM tasks.")
        if isinstance(requested, str) and requested in builtins:
            return requested
        if not isinstance(requested, str) or not requested.startswith("plugin:"):
            raise validation_error("Select a built-in provider ID or plugin:<installation ID>.")
        plugin_id = requested.removeprefix("plugin:")
        if not plugin_id or ":" in plugin_id:
            raise validation_error("Python entrypoints are not accepted as HTTP provider IDs.")
        try:
            installation = self.memory.get_plugin_installation(plugin_id)
        except NotFoundError:
            raise not_found("Approved LLM provider not found.") from None
        manifest = self.memory.get_plugin_manifest(installation.plugin_manifest_id)
        if installation.status != "enabled" or manifest.plugin_type != "llm_provider":
            raise forbidden("LLM provider must be an enabled operator-approved LLM plugin.")
        approved = {row[0] for row in self.db.execute(
            "SELECT permission FROM plugin_capability_grants WHERE plugin_installation_id = ?", (installation.id,))}
        required = set(manifest.permissions_required)
        if source_task:
            required.update({"read_claim_text", "read_evidence_text"})
        if manifest.external_network_access:
            required.add("use_network")
        if not required <= approved:
            raise forbidden("LLM provider lacks approved permissions for this task.")
        for capability in manifest.capabilities_required:
            self.auth.require_capability(self.context, capability)
        if manifest.external_network_access and any(level in {"private", "sensitive", "secret"}
                                                    for level in (source_privacy if source_task else [privacy_level])):
            raise forbidden("Private input is unavailable to an external LLM plugin.")
        return "plugin:" + manifest.entrypoint
