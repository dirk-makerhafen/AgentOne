"""Deterministic provider/model catalog generation.

This package turns three curated upstream JSON sources into the canonical
JSON dataset under ``.agentone/providers/`` and ``.agentone/models/``:

* ``awesome-free-llm-apis`` — free-tier providers with base URLs and models
* ``freellmapi-catalog``    — signed monthly catalog of free platform/models
* ``opencode-models-api``   — detailed model metadata (capabilities, costs,
  release/update dates, reasoning options)

Raw downloads are cached in ``~/.agentone/var/cache/provider-catalog/`` so
rebuilds are fast and reproducible; use ``--offline`` to rebuild from cache.
"""
