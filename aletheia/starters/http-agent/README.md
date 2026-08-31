# A scoped HTTP agent and a separate operator

Use the unpublished 1.4.0rc1 build of Memory and Python 3.11+. This starter needs
current-principal discovery, `memory-read-v1`, `agent-onboarding-v1` and
`memory-review-v1`; it does not work with a 1.3.1 service.

From this new project directory, run:

```sh
python operator_demo.py
```

This explicit operator action creates `aletheia-http-demo.db`, provisions
30-minute demo credentials and starts an authenticated service on an ephemeral
loopback port. A separate `agent.py` process captures a candidate and can retrieve
context, but receives no review, admin or active-write capability. The operator
displays the candidate and source; only typing `approve` promotes it. Approval
produces context/provenance and verifies persistence after the service stops.
Other answers leave the candidate pending. Tokens are revoked during cleanup.

Tokens exist only in the operator's memory and the agent process environment;
they are not printed or written into source/config files. The agent subprocess
does not inherit operator or provider credentials. Like other process environment
secrets, its token is visible to sufficiently privileged local processes.

No model or external network is used. Loopback HTTP is required. The service is
stopped automatically, while the database remains for inspection. Repeated runs
refuse to overwrite it; generate a fresh project to repeat the demonstration.

For a separately operated service, run `python agent.py capture my-operation-key` or
`python agent.py read` with `ALETHEIA_URL`, `ALETHEIA_AGENT_TOKEN` and
`ALETHEIA_NAMESPACE` supplied through your secure environment. Use a trusted
service URL and a scoped token. Never give this process operator credentials.
Do not put tokens in shell history, URLs or committed files.

The demo performs each candidate write once. It does not automatically replay
uncertain writes or decisions. If interrupted, retain the same key and complete
payload, and inspect pending candidates with the operator before continuing.
Review uses the inspected revision and an explicit operator key. A stale review
fails rather than carrying the previous approval onto new state.

On the installed release candidate:

```sh
aletheia doctor --read-only --db ./aletheia-http-demo.db --namespace user/demo --query architecture
```

Local SQLite inspection is trusted operator access. Agent diagnostics against
an already running service can use `doctor --read-only --service-url` with
`--token-env ALETHEIA_AGENT_TOKEN`; they do not need admin access.
