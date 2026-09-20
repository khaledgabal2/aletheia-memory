# Plugin Developer Guide

Plugins are local extensions described by `aletheia-plugin.toml`. A plugin must declare its type, version, entrypoint, compatibility range, API contract version, capabilities, and permissions.

Minimal manifest:

```toml
[plugin]
name = "example-extractor"
display_name = "Example Extractor"
version = "1.0.0"
plugin_type = "extractor"
entrypoint = "example_plugin:Plugin"
description = "Extracts candidate memories."

[compatibility]
aletheia_min_version = "1.0.0"
api_contract_version = "v1"

[permissions]
permissions_required = ["write_candidate"]
external_network_access = false
reads_memory_content = false
writes_memory = true
stores_data = false
```

Install and enable:

```bash
aletheia plugins install ./example-plugin --db ./aletheia.db
aletheia plugins enable example-extractor --db ./aletheia.db --permission write_candidate --reason "Local test plugin"
```

Plugins cannot bypass candidate-first governance. Attempts to write active claims directly are blocked and logged.

## HTTP LLM providers

Use `plugin_type = "llm_provider"` for a Python provider implementing
`complete_json`. The entrypoint remains an operator-installed manifest field;
HTTP requests select `plugin:<installation ID>` or `plugin:<registered name>`.
Requests cannot specify a module/factory entrypoint or use the ambient plugin
entrypoint environment variable.

Enable the installation with every declared permission. Source tasks additionally
require `read_claim_text` and `read_evidence_text`; providers declaring external
network access require `use_network`. The caller must also have every capability
in `capabilities_required`. Enablement and grants are checked on each request,
before constructing the provider. The manifest's network disclosure policy
applies in addition to the provider's runtime policy.

Native Python plugins execute as trusted local code after operator approval;
the permission registry is not a Python sandbox. See
[HTTP access boundaries](service_access_boundaries.md) for a provider manifest
example and input privacy rules.
