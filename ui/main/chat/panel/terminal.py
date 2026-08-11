from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView



class TerminalPanel(PyHtmlView):
    DOM_ELEMENT_CLASS = 'composer-terminal-panel'
    DOM_ELEMENT_EXTRAS = 'style="display:none"'
    TEMPLATE_STR = '''
        <div class="composer-terminal-inner">
            <div class="composer-terminal-resize-handle" id="terminalResizeHandle" role="separator" aria-orientation="horizontal" aria-label="Resize terminal" tabindex="0"></div>
            <div class="composer-terminal-header">
                <div class="composer-terminal-title">
                    <span data-i18n="terminal_title">Terminal</span>
                    <span class="composer-terminal-dot" aria-hidden="true">·</span>
                    <span id="terminalWorkspaceLabel"></span>
                </div>
                <div class="composer-terminal-actions">
                    <button type="button" class="composer-terminal-action" id="btnTerminalClear" onclick="clearComposerTerminal()" data-i18n="terminal_clear">Clear</button>
                    <button type="button" class="composer-terminal-action" id="btnTerminalCopy" onclick="copyComposerTerminalOutput()" data-i18n="terminal_copy_output">Copy output</button>
                    <button type="button" class="composer-terminal-action" id="btnTerminalRestart" onclick="restartComposerTerminal()" data-i18n="terminal_restart">Restart</button>
                    <button type="button" class="composer-terminal-action" id="btnTerminalCollapse" onclick="collapseComposerTerminal()" data-i18n="terminal_collapse">Collapse</button>
                    <button type="button" class="composer-terminal-action" id="btnTerminalClose" onclick="closeComposerTerminal()" data-i18n="terminal_close">Close</button>
                </div>
            </div>
            <div class="composer-terminal-viewport" id="terminalViewport" onclick="focusComposerTerminalInput()">
                <div class="composer-terminal-surface" id="terminalSurface" aria-label="Workspace terminal"></div>
            </div>
        </div>
        <div class="composer-terminal-dock" id="composerTerminalDock" hidden>
            <div class="composer-terminal-dock-title">
                <span class="composer-terminal-dock-dot" aria-hidden="true"></span>
                <span data-i18n="terminal_title">Terminal</span>
                <span class="composer-terminal-dot" aria-hidden="true">·</span>
                <span id="terminalDockWorkspaceLabel"></span>
            </div>
            <div class="composer-terminal-actions">
                <button type="button" class="composer-terminal-action" id="btnTerminalExpand" onclick="expandComposerTerminal()" data-i18n="terminal_expand">Expand</button>
                <button type="button" class="composer-terminal-action" id="btnTerminalDockClose" onclick="closeComposerTerminal()" data-i18n="terminal_close">Close</button>
            </div>
        </div>
    
    '''
