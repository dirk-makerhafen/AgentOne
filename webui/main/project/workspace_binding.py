"""Compatibility shim — moved to ``webui.features.projects.binding``."""
import sys
import webui.features.projects.binding as _target
sys.modules[__name__] = _target
