"""Compatibility shim — moved to ``webui.features.insights.provider_detail``."""
import sys
import webui.features.insights.provider_detail as _target
sys.modules[__name__] = _target
