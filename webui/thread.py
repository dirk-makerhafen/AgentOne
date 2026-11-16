"""Compatibility shim — moved to ``webui.features.chats.thread``."""
import sys
import webui.features.chats.thread as _target
sys.modules[__name__] = _target
