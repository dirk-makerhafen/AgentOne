"""Compatibility shim — moved to ``webui.features.insights.model_detail``."""
import sys
import webui.features.insights.model_detail as _target
sys.modules[__name__] = _target
