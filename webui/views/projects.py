"""Compatibility shim — moved to ``webui.features.projects.views``."""
import sys
import webui.features.projects.views as _target
sys.modules[__name__] = _target
