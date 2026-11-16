"""Compatibility shim — moved to ``webui.features.agents.views``."""
import sys
import webui.features.agents.views as _target
sys.modules[__name__] = _target
