"""Compatibility shim — moved to ``webui.core.assistants``."""
import sys
import webui.core.assistants as _target
sys.modules[__name__] = _target
