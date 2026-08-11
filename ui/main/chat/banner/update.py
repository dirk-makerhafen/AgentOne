from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
if TYPE_CHECKING:
    from ui.main.chat.chat import Chat

class UpdateBanner(PyHtmlView):
    DOM_ELEMENT_CLASS = 'update-banner'
    TEMPLATE_STR = '''
        <div style="display:flex;flex-direction:column;flex:1;min-width:0">
            <span id="updateMsg"></span>
            <a id="updateWhatsNew" href="#" target="_blank" rel="noopener" style="font-size:11px;color:var(--accent);text-decoration:underline;display:none1;margin-left:8px;white-space:nowrap">What's new?</a>
            <div id="updateError" style="display:none1;font-size:12px;color:var(--error,#e05);margin-top:4px;word-break:break-word"></div>
        </div>
        <div style="display:flex;gap:8px;flex-shrink:0;flex-wrap:wrap">
            <button class="update-btn" onclick="dismissUpdate()">Later</button>
            <button class="update-btn update-primary" id="btnApplyUpdate" onclick="applyUpdates()">Update Now</button>
            <button class="update-btn" id="btnForceUpdate" style="display:none1;background:var(--error,#e05);color:#fff;border-color:var(--error,#e05)" onclick="forceUpdate(this)">Force update</button>
        </div>
    '''

    def __init__(self, subject:Session, parent: Chat, **kwargs):
        super().__init__(subject, parent, **kwargs)