# Model-free first-run tutorial draft

Phase 1 draft for the 1.4.0 onboarding workstream. The APIs below already exist;
the final presentation, safe starter generation, diagnostics and human timing
will be verified in G4. No new helper is needed by this prototype.

Start with Python 3.11 or newer and install the published package:

```sh
python -m pip install aletheia-memory
```

Save the following as `memory_demo.py` in a disposable directory, then run
`python memory_demo.py`. It uses a new demo database and does not overwrite an
existing one. No account, model, embedding index or external service is needed
after installation.

```python
from pathlib import Path
from aletheia import Memory

path = Path("aletheia-demo.db")
if path.exists():
    raise SystemExit("Demo database already exists. Choose a new demo directory to keep it unchanged.")

namespace = "user/demo"
memory = Memory.open(str(path), namespace=namespace)
claim_id = None
try:
    batch = memory.ingest(
        namespace,
        source_type="manual",
        content="User prefers careful architecture notes.",
        trust_level="user_asserted",
    )
    run = memory.extract_candidates(namespace, batch_id=batch.id, extractor="rule_based")
    candidates = memory.list_candidates(namespace, extraction_run_id=run.id)
    if len(candidates) != 1:
        raise SystemExit("Expected one candidate from the bounded sample; inspect the extraction result.")
    candidate = candidates[0]
    print("Pending candidate:", candidate.subject, candidate.predicate, candidate.object)
    print("Source:", memory.read_event(batch.evidence_ids[0]).content)
    print("Trusted results before approval:", len(memory.retrieve(namespace, "architecture", mode="lexical")))

    if input("Inspect the candidate and source. Type approve to promote it: ").strip() == "approve":
        claim = memory.promote_candidate(candidate.id, reason="I inspected and approved the demo candidate.")
        claim_id = claim.id
        print(memory.context_pack(namespace, "architecture", retrieval_mode="lexical", record_usage=False).to_markdown())
        print("Provenance:", memory.explain_claim(claim.id).evidence[0]["content"])
    else:
        print("Nothing promoted. The candidate remains pending review.")
finally:
    memory.close()

if claim_id:
    reopened = Memory.open(str(path), namespace=namespace)
    try:
        hits = reopened.retrieve(namespace, "architecture", mode="lexical")
        assert hits and hits[0].claim_id == claim_id
        print("Reopened successfully: the reviewed claim and its evidence persist.")
    finally:
        reopened.close()
```

Before approval, the trusted result count is zero. If you approve, the context
contains the reviewed preference, its explanation identifies the sample source,
and the final message confirms persistence. Declining approval leaves a pending
candidate, not a trusted fact. You may keep the database for inspection; remove
only this disposable demo directory when you no longer need it.

The lexical query matches the literal word `architecture` in the sample. This
does not promise arbitrary paraphrase understanding. Rule-based extraction here
is a bounded deterministic example, not an LLM. Embedded Python is trusted local
code; use a separately scoped token and candidate-first SDK calls when connecting
an agent over HTTP.

The five-minute target is not yet a measured human result. G4 must time the
actual developer journey, separate installation/network time, test both approval
and refusal, and verify the final packaged example outside the source checkout.
