# Security Policy

Aletheia is local-first software that can store sensitive user, project, and
agent memory. Please report vulnerabilities responsibly.

## Reporting A Vulnerability

Do not open public issues with exploit details, private data, credentials, or
working attack payloads.

Preferred reporting path:

1. Use GitHub private vulnerability reporting for this repository when it is
   enabled.
2. If private reporting is not available, open a minimal public issue asking
   maintainers to establish a private disclosure channel. Do not include
   sensitive technical detail in that issue.

Please include:

- Affected version or commit.
- The vulnerable surface, such as CLI, HTTP API, MCP, SDK, plugins,
  federation, backup/restore, or docs packaging.
- Reproduction steps using synthetic data only.
- Expected impact and any known mitigations.

## Deployment Guidance

- Bind the HTTP service to loopback unless you have configured authentication,
  scoped tokens, namespace grants, and an external TLS boundary.
- Configure `ALETHEIA_PROTECTED_KEY` or `ALETHEIA_KEY_<key_id>` before writing
  secret-tier evidence in protected mode.
- Use encrypted backups for protected deployments and redacted logical exports
  for support or sharing.
- Keep local SQLite databases, support bundles, logs, tokens, and environment
  files out of public repositories.

See [docs/security_privacy_guide.md](docs/security_privacy_guide.md) for the
full security and privacy model.
