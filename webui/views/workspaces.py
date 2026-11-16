"""Compatibility shim — moved to ``webui.features.workspaces.views``."""
import sys
import webui.features.workspaces.views as _target
sys.modules[__name__] = _target
