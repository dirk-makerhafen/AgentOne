# Tools

Tools are LLM-callable functions declared in `scripts.md` manifests. They follow the same format as tasks and commands.

## Quick reference

```yaml
tools:
  - name: read
    file: filesystem.py
    function: read
    bound: True
    requires_approval: false
```

## Full documentation

See [docs/manifest-format.md](manifest-format.md) for the complete manifest format reference, including tools, tasks, commands, chains, groups, maps, and scripts.