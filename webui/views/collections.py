"""Compatibility shim — moved to ``webui.features.collections.views``."""
import sys
import webui.features.collections.views as _target
sys.modules[__name__] = _target
