"""Compatibility shim — moved to ``webui.features.memory.views``."""
import sys
import webui.features.memory.views as _target
sys.modules[__name__] = _target
