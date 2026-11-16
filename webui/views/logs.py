"""Compatibility shim — moved to ``webui.features.logs.views``."""
import sys
import webui.features.logs.views as _target
sys.modules[__name__] = _target
