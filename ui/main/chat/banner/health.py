from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView



class HealthBanner(PyHtmlView):
    DOM_ELEMENT_CLASS = 'agent-health-banner'
    DOM_ELEMENT_EXTRAS = 'role="alert" aria-live="assertive" hidden'
    TEMPLATE_STR = '''
        <div class="agent-health-copy">
            <strong id="agentHealthTitle">AgentOne is not responding</strong>
            <span id="agentHealthDetails">The gateway heartbeat failed. Messages may not be delivered until it comes back.</span>
        </div>
        <button class="agent-health-dismiss" id="agentHealthDismiss" type="button" onclick="dismissAgentHealthAlert()" aria-label="Dismiss AgentOne heartbeat alert">Dismiss</button>
    '''
