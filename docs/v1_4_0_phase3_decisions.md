# Phase 3: zero-model onboarding decisions

Phase 3 builds on `3817e9a` without merging the earlier PRs. The release plan and
D1–D8 remain authoritative. All implementation and review stay in the isolated
worktree and private dependent PR sequence until the maintainer approves release.

1. Keep the existing public Memory APIs. The prototype already carries returned
   handles between steps; there is no evidence justifying a new scoped helper.
   `remember()` remains a trusted active write, never the recommended agent path.
2. Make a single embedded Python example the primary tutorial. Use only existing
   public APIs and standard-library file creation, so the example also works on
   published 1.3.1. Display evidence and a pending candidate, require explicit
   approval, retrieve lexical context/provenance, close and reopen the database.
3. Add `init --new` as an exclusive-create option. Existing `init` still creates
   or migrates. A file or symlink at the requested destination is never replaced.
4. Add `doctor --read-only` before the CLI opens Memory normally. It never creates
   or migrates a database or writes diagnostic/domain records. SQLite read locks
   and WAL sidecars are normal SQLite behavior, not repair or domain writes.
   Local diagnostics use read-only/query-only SQLite; service checks require an
   explicit URL and use bounded, nonredirecting loopback requests. Configuration
   and environment values, tokens, paths and memory contents are not dumped.
5. Add `embedded` and `http-agent` to `examples create`, without opening a tracking
   database. Bundle their actual source files in the package. Generation requires
   a new output directory. Existing adapter scaffolds also refuse an existing
   output directory rather than overwriting files; this intentional safety change
   is documented. No force/overwrite mode is added.
6. The HTTP starter runs an explicitly invoked operator demo, a disposable local
   service and a separate agent process. The operator provisions short-lived
   scoped tokens for this new demo database only. The agent receives only its own
   token through its process environment; operator approval and credentials stay
   separate. No credentials are generated into source/config files or printed.
   It uses legacy candidate-first writes; stronger G3 review guarantees are not
   advertised early.
7. Provider diagnostics inspect configuration/index metadata without loading
   plugins or contacting models by default. Missing optional providers do not
   fail zero-model setup. The explicit endpoint probe submits no model input
   and never creates an index or promotes memory. Provider recipes and
   a distributable TypeScript starter remain Phase 5.
8. Test the exact installed templates and documentation. Record installation and
   automated execution separately. A five-minute human walkthrough remains a
   human-validation target; automated timing must not be presented as user research.

No schema changes, migration-policy changes, token permission changes, new agent
active-write path, provider default, Desktop dependency or release publication
is introduced by these decisions. Diagnostics do not authorize a resource;
Memory continues to decide access on every service operation.
