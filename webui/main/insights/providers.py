"""Compatibility shim — moved to ``webui.features.insights.providers``."""
import sys
import webui.features.insights.providers as _target
sys.modules[__name__] = _target
