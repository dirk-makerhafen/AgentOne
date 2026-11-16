"""Compatibility shim — moved to ``webui.features.insights.models``."""
import sys
import webui.features.insights.models as _target
sys.modules[__name__] = _target
