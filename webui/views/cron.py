"""Compatibility shim — moved to ``webui.features.cron.views``."""
import sys
import webui.features.cron.views as _target
sys.modules[__name__] = _target
