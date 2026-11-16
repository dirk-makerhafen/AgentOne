"""Compatibility shim — moved to ``webui.features.chats.views``."""
import sys
import webui.features.chats.views as _target
sys.modules[__name__] = _target
