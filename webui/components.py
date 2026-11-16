"""Compatibility shim — moved to ``webui.core.components``."""
import sys
import webui.core.components as _target
sys.modules[__name__] = _target
