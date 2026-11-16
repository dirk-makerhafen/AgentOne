"""Compatibility shim — moved to ``webui.core.events``."""
import sys
import webui.core.events as _target
sys.modules[__name__] = _target
