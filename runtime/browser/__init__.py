"""Camoufox-backed browser capability.

Layout
------
``config``    user-tunable browser settings (``~/.agentone/config.yaml``)
``paths``     filesystem locations (profiles, token, state, audit log)
``scope``     session → browser-scope resolution (root session, ownership)
``launcher``  Camoufox launch options + stable-profile launch
``snapshot``  text-first DOM snapshots with stable element refs
``registry``  bindings (one browser process each) and page ownership
``daemon``    long-lived process: driver thread + local authenticated HTTP API
``client``    tool-side client: token auth, lazy daemon start, action dispatch

Why a daemon and not Celery workers: the Celery pool runs five prefork
workers, so module-level browser state would be split across (and dropped
with) worker processes.  The daemon owns every browser process, survives
worker restarts, and is supervised by ``manage.py server run``.

Profiles live under ``~/.agentone/browser/`` — deliberately *not* under
``~/.agentone/runtime/``, which is garbage-collected versioned task state.
"""

from __future__ import annotations
