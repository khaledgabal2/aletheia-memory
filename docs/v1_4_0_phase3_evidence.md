# 1.4.0 Phase 3 verification

Prepared 2026-08-30 on `codex/v1.4-onboarding`, based on Phase 2 commit
`3817e9a683d2a83154483ef9834ba131c50f8f23`. The
[release plan](v1_4_0_contract_hardening_and_developer_experience_plan.md) and
[Phase 3 decisions](v1_4_0_phase3_decisions.md) remain authoritative.
This is implementation evidence, not merge, advisory-publication or release approval.

## G4 implementation and automated verification

The installed-package journey is implemented and passes local automated checks.
Human validation of the approximately five-minute target remains open; neither
script timing nor an automated approval input demonstrates that a new developer
understood the trust boundary. Carry that validation into the final release gate.

| Check | Observed result |
| --- | --- |
| Supported Python matrix | All 210 tests pass on Python 3.11.15, 3.12.11 and 3.13.13 on macOS. Includes 27 onboarding cases. |
| Primary tutorial | README, installed quickstart and embedded starter contain the same runnable Python source. Synthetic evidence produces a pending candidate; explicit approval produces lexical context, provenance and a successful close/reopen check. |
| Public-package compatibility | The actual published 1.3.1 package executes the primary quickstart for approval, refusal and empty input with socket connections blocked. New CLI flags and the HTTP starter are clearly marked as unreleased development features. |
| No-model installation | Fresh wheel and sdist environments contain only Memory and its core cryptography dependencies. No provider SDK, model download, account, Desktop or Relay is required. |
| Installed-artifact execution | Both wheel and sdist pass 11 recorded checks outside the checkout. Imports resolve to installed site-packages; docs/templates come from package resources. Six documentation/embedded approval/refusal/empty-input runs block socket connections. Two HTTP runs use a disposable loopback service and separate agent process. |
| Explicit review and credentials | Before approval there is no trusted result. The HTTP agent receives only read/context/candidate-write capabilities; operator review is separate. Tokens expire after 30 minutes, are revoked on normal cleanup and are not printed or written to source/configuration. |
| Safe initialization/generation | `init --new` and both demos refuse existing databases, final symlinks and orphaned WAL/SHM/journal files. Generators refuse existing project directories. Legacy adapter scaffolds now refuse overwrites too; this intentional safety change is documented. |
| Read-only local diagnostics | Missing paths, permissions, locked/invalid databases, old/new/incomplete schemas, configuration errors, empty namespaces, pending review and lexical mismatch have tested explanations. No missing database is created, no migration/repair is applied and domain tables remain unchanged. |
| Scoped service diagnostics | Actual-service checks cover missing/invalid credentials, absent capability, namespace denial and resource privacy denial without admin access or printing resource content. Legacy/incompatible/profile-missing/unavailable services and redirects are distinguished. |
| Optional providers | Configuration and stored semantic-index state are inspected without model calls or plugin loading. Stale/model-dimension mismatches warn without rebuilding. Explicit local GET probes report unavailability/redirect errors without forwarding credentials or failing core lexical setup. |
| Source distribution | The full 210-test suite also passes from the extracted sdist. Templates and docs are included; Node dependencies, generated output and Python caches are excluded. |
| Existing contract gates | Baseline/discovery/read TypeScript consumers regenerate, compile and execute successfully. All five Node lifecycle tests and both SDK compatibility directions pass. No new profile or API/storage schema is introduced. |
| Repository boundary | Generic release-boundary and whitespace checks pass. The original checkout stays on `codex/v1.4-plan` with no tracked-file changes; unrelated untracked editor configuration was left untouched. No public main push, merge or publication occurs. |

### Timing, measured separately

On the local Python 3.13.13 environment:

| Measurement | Wheel | Source distribution |
| --- | ---: | ---: |
| Create fresh virtual environment | 0.009 s | 0.008 s |
| Install artifact and cached dependencies, explicitly offline | 0.048 s | 0.279 s |
| Complete automated installed-artifact gate | 3.124 s | 3.243 s |

These are local warm-cache automation measurements, not general installation
benchmarks. Cold network installation and human completion time were not measured.
The automation supplies the documented review decision; interactive examples
still require the developer to inspect and approve.

## Reproduce

```sh
python -m pytest
uv build
python -m venv /tmp/memory-wheel
/tmp/memory-wheel/bin/python -m pip install dist/*.whl
python scripts/v1_4_onboarding_check.py --python /tmp/memory-wheel/bin/python
python -m venv /tmp/memory-sdist
/tmp/memory-sdist/bin/python -m pip install dist/*.tar.gz
python scripts/v1_4_onboarding_check.py --python /tmp/memory-sdist/bin/python
```

Use fresh environment paths. The installed-artifact runner uses isolated Python
imports, temporary directories and synthetic inputs, and checks that development
or model dependencies are absent. For the generated-client and compatibility
gates, see [the contract tooling guide](../contracts/typescript/README.md).

The release-gates workflow now runs both installed-artifact checks. GitHub
temporary private security forks do not run Actions/integrations; local macOS
results do not imply Linux CI results. No new real-browser test was needed for
this CLI/documentation slice; Phase 2 browser evidence remains historical.

## Limits and review boundary

- SQLite read-only connections may participate in normal WAL/SHM coordination.
  The guarantee covers no domain/diagnostic writes, migrations or repairs, not
  immutable forensic access to all filesystem sidecars.
- Local database inspection is trusted operator access. Service diagnostics
  respect the token's view and cannot infer whether invisible memory is empty,
  pending or hidden by authorization. No admin or privacy bypass is introduced.
- An explicit provider GET tests endpoint reachability only. It sends no model
  input and does not establish successful inference, dimensions or output quality.
- The HTTP demo uses existing candidate-first writes. Revision preconditions and
  atomic review replay remain Phase 4/G3 work. TypeScript and real local-provider
  starters remain Phase 5/G5 work.
- No scoped helper was added: the existing APIs and returned handles suffice.
  `Memory.remember()` retains its trusted active-write semantics.

Phase 3 remains a dependent private draft PR because its history includes the
unpublished Phase 2 remediation. Review stays under draft advisory
[GHSA-v96m-pj74-648h](https://github.com/khaledgabal2/aletheia-memory/security/advisories/GHSA-v96m-pj74-648h)
and its private temporary fork. The maintainer will review/merge after the work
is complete. Package version remains 1.3.1 and schema version remains 1.3.0 until
the authorized release process. Nothing here authorizes an advisory publication,
CVE request, repository-setting change, merge or package publication.
