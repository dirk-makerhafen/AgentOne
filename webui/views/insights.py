"""Compatibility shim — moved to ``webui.features.insights.views``."""
import sys
import webui.features.insights.views as _target
sys.modules[__name__] = _target
