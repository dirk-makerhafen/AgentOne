"""Compatibility shim — moved to ``webui.features.workspaces.sidebar_helper``."""
import sys
import webui.features.workspaces.sidebar_helper as _target
sys.modules[__name__] = _target
