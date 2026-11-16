"""Compatibility shim — moved to ``webui.core.shell``."""
import sys
import webui.core.shell as _target
sys.modules[__name__] = _target
