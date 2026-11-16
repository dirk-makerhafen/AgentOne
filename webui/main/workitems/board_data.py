"""Compatibility shim — moved to ``webui.features.workitems.board``."""
import sys
import webui.features.workitems.board as _target
sys.modules[__name__] = _target
