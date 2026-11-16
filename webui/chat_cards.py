"""Compatibility shim — moved to ``webui.features.chats.cards``."""
import sys
import webui.features.chats.cards as _target
sys.modules[__name__] = _target
