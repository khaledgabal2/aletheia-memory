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
