# Your first reviewed memory

Use Python 3.11+ and install the published package in a fresh environment:

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install aletheia-memory
```

Create a new directory for the demo. Save the following as `memory_demo.py` there,
then run `python memory_demo.py`. This Python example uses public APIs already
available in 1.3.1; no model, account, embedding index or service is needed.
After installation it runs without network access.

```python
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
```

Read the candidate and source before typing `approve`. Before approval, the
trusted-result count is **0**. After approval, context contains the preference,
provenance names its source text, and the final line confirms persistence after
reopening. Any other answer, including end-of-input, leaves a pending candidate.

The steps mean: **evidence** is the original note; a **candidate** is an unapproved
interpretation; **review** is your explicit decision; a **claim** is trusted memory;
**context** selects useful claims; **provenance** explains their sources. The word
`architecture` matches the sample literally. This is deterministic rule-based
extraction and lexical retrieval, not arbitrary natural-language understanding.

The script refuses to overwrite an existing database or symlink. Use a fresh
folder to rerun. Keep the demo database for inspection; remove only that disposable
folder when finished. Embedded Python is trusted local code. `Memory.remember()`
still creates an active claim and is not the recommended untrusted-agent write path.

## Generate this example on 1.4.0 or later

The packaged generator and read-only diagnostics require Memory 1.4.0 or later.
The Python example above also remains usable with 1.3.1.

```sh
aletheia examples create --type embedded --output ./memory-demo
cd memory-demo
python memory_demo.py
aletheia doctor --read-only --db ./aletheia-demo.db --namespace user/demo --query architecture
```

Generation writes only a new project directory; it does not create a tracking
or demo database. Diagnostics do not migrate, repair, provision credentials or
record diagnostic/domain data. Missing optional providers are not a failed setup.

Next, connect a [scoped HTTP agent](examples.md), then read the optional semantic
and LLM sections of the [integration guide](integration_guide.md). Advanced
operations and security remain separate from first success.

Five minutes is a target for the human walkthrough. Automated installation and
execution timings are reported separately in Phase 3 evidence; they are not a
measured human completion time.
