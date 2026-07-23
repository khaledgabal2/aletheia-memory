# Examples

List installed help:

```bash
aletheia docs list
aletheia docs show index
```

Create a local adapter example:

```bash
aletheia examples create --db ./aletheia.db --type python-sdk --name python-sdk-agent --output ./examples/python-sdk-agent
aletheia examples test --db ./aletheia.db
```

Build generated docs with examples validated:

```bash
aletheia docs build --db ./aletheia.db --output ./site
aletheia docs status --db ./aletheia.db
```

List generated examples:

```bash
aletheia examples list --db ./aletheia.db
```
