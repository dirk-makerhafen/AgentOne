"""Compatibility shim — moved to ``webui.core.markdown``."""
import sys
import webui.core.markdown as _target
sys.modules[__name__] = _target
