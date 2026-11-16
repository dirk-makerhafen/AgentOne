"""Compatibility shim — moved to ``webui.features.workitems.views``."""
import sys
import webui.features.workitems.views as _target
sys.modules[__name__] = _target
