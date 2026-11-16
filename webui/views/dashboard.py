"""Compatibility shim — moved to ``webui.features.dashboard.views``."""
import sys
import webui.features.dashboard.views as _target
sys.modules[__name__] = _target
