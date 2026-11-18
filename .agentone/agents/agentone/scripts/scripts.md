---
tools:
  - name: admin_tool
    file: admin_tool.py
    function: admin_tool
    bound: True
---
Agent-local framework administration. Only `admin_tool` is exposed to the
model; its `action="help"` responses are the runtime reference for scopes,
actions and keyword arguments. Agents and skills are inspected from the live
DB but created/edited as filesystem manifests by `coding`, followed by
`admin_tool(scope="system", action="reload")`.
