"""Compatibility shim — moved to ``webui.features.workspaces.workspace``."""
import sys
import webui.features.workspaces.workspace as _target
sys.modules[__name__] = _target
