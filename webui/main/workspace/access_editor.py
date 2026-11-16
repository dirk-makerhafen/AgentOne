"""Compatibility shim — moved to ``webui.features.workspaces.access``."""
import sys
import webui.features.workspaces.access as _target
sys.modules[__name__] = _target
