"""Compatibility shim — moved to ``webui.features.workspaces.manifest``."""
import sys
import webui.features.workspaces.manifest as _target
sys.modules[__name__] = _target
