"""Compatibility shim — moved to ``webui.features.skills.views``."""
import sys
import webui.features.skills.views as _target
sys.modules[__name__] = _target
