"""A deterministic evidence → review → memory example; no model required."""
import os
from pathlib import Path
from aletheia import Memory

path = Path("aletheia-demo.db")
for suffix in ("-wal", "-shm", "-journal"):
    companion = Path(str(path) + suffix)
    if companion.exists() or companion.is_symlink():
        raise SystemExit("Database companion file already exists. Preserve it and choose a new directory.")
try:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
except FileExistsError:
    raise SystemExit("Demo database already exists. Choose a new directory; nothing was overwritten.")

namespace = "user/demo"
memory = Memory.open(str(path), namespace=namespace)
claim_id = None
try:
    batch = memory.ingest(namespace, source_type="manual",
                          content="User prefers careful architecture notes.", trust_level="user_asserted")
    run = memory.extract_candidates(namespace, batch_id=batch.id, extractor="rule_based")
    candidates = memory.list_candidates(namespace, extraction_run_id=run.id)
    if len(candidates) != 1:
        raise SystemExit("Expected one candidate from this bounded example; inspect the extraction result.")
    candidate = candidates[0]
    print("Pending candidate:", candidate.subject, candidate.predicate, candidate.object)
    print("Source:", memory.read_event(batch.evidence_ids[0]).content)
    print("Trusted results before approval:", len(memory.retrieve(namespace, "architecture", mode="lexical")))
    try:
        approve = input("Inspect the candidate and source. Type approve to promote it: ").strip() == "approve"
    except EOFError:
        approve = False
    if approve:
        claim = memory.promote_candidate(candidate.id, reason="I inspected and approved the demo candidate.")
        claim_id = claim.id
        print(memory.context_pack(namespace, "architecture", retrieval_mode="lexical", record_usage=False).to_markdown())
        print("Provenance:", memory.explain_claim(claim.id).evidence[0]["content"])
    else:
        print("Nothing promoted. The candidate remains pending review.")
finally:
    memory.close()

if claim_id:
    reopened = Memory.open(str(path), namespace=namespace, auto_migrate=False)
    try:
        hits = reopened.retrieve(namespace, "architecture", mode="lexical")
        assert hits and hits[0].claim_id == claim_id
        print("Reopened successfully: the reviewed claim and its evidence persist.")
    finally:
        reopened.close()
