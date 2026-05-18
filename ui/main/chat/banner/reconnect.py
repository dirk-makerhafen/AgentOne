
from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView

class ReconnectBanner(ModelView):
    DOM_ELEMENT_CLASS = 'reconnect-banner'
    TEMPLATE_STR = '''
        <span id="reconnectMsg">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:-1px">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            A response may have been in progress when you last left. Reload messages?
        </span>
        <div style="display:flex;gap:8px;flex-shrink:0">
            <button class="reconnect-btn" onclick="dismissReconnect()">Dismiss</button>
            <button class="reconnect-btn" onclick="refreshSession()">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:-1px">
                <polyline points="23 4 23 10 17 10"/>
                <polyline points="1 20 1 14 7 14"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            Reload
            </button>
        </div>
    '''
