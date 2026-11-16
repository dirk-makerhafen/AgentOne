"""Compatibility shim — moved to ``webui.features.settings.views``."""
import sys
import webui.features.settings.views as _target
sys.modules[__name__] = _target
