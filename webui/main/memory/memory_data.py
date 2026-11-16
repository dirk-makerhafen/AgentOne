"""Compatibility shim — moved to ``webui.features.memory.data``."""
import sys
import webui.features.memory.data as _target
sys.modules[__name__] = _target
