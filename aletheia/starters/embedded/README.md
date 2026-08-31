# Your first reviewed memory

Use Python 3.11+ with `aletheia-memory` installed. From this new project directory:

```sh
python memory_demo.py
```

The script creates `aletheia-demo.db`, displays a pending candidate and its
evidence, and shows zero trusted matches. Read them before typing `approve`.
Any other answer (including end-of-input) leaves the candidate pending. Approval
produces lexical context, source provenance and a successful close/reopen check.

There is no model, account, provider or network call after installation. The word
`architecture` matches the sample literally; arbitrary paraphrases are not
promised. Rule-based extraction is a bounded example. Embedded Python is trusted
local code, not an authorization sandbox. `Memory.remember()` remains a separate
trusted active-write API.

Rerunning refuses to overwrite the database, including a symlink at its path.
Generate another project directory to repeat the demo. Keep the old directory
for inspection, or remove only that disposable directory when finished.

On the 1.4.0rc1 build, inspect without migrating or recording a doctor run:

```sh
aletheia doctor --read-only --db ./aletheia-demo.db --namespace user/demo --query architecture
```

The five-minute goal is a target for a human walkthrough, not a measured promise.
