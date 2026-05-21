from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView


class RightPanelWorkspace(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''

    <div class="panel-header">
      <span>Workspace</span>
      <span class="git-badge dirty" id="gitBadge" style="">main · 139∆ ↑15</span>
      <div class="panel-actions">
        <button class="panel-icon-btn" id="btnCollapseWorkspacePanel" title="Hide workspace panel" onclick="toggleWorkspacePanel(false)">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"></polyline></svg>
</button>
        <button class="panel-icon-btn" id="btnUpDir" title="Parent directory" onclick="navigateUp()" style="display: none;">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
</button>
        <button class="panel-icon-btn" id="btnNewFile" title="New file" onclick="promptNewFile()">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
</button>
        <button class="panel-icon-btn" id="btnNewFolder" title="New folder" onclick="promptNewFolder()">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</button>
        <button class="panel-icon-btn" id="btnRefreshPanel" title="Refresh" onclick="if(S.session)loadDir(S.currentDir)">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
</button>
        <button class="panel-icon-btn close-preview" id="btnClearPreview" title="Hide workspace panel" style="display: none;">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
</button>
        <button class="panel-icon-btn mobile-close-btn" onclick="handleWorkspaceClose()" title="Close" aria-label="Close workspace panel">×</button>
      </div>
    </div>
    <div class="breadcrumb-bar" id="breadcrumbBar" style="display: none;">
<span class="breadcrumb-seg breadcrumb-link">~</span>
<span class="breadcrumb-sep">/</span>
<span class="breadcrumb-seg breadcrumb-link">ui</span>
<span class="breadcrumb-sep">/</span>
<span class="breadcrumb-seg breadcrumb-current">consumer.py</span>
</div>
    <div class="file-tree" id="fileTree" style="">
        <div class="file-item" draggable="true" style="padding-left: 8px;">
            <span class="file-tree-toggle">▸</span>
            <span class="file-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            </span>
            <span class="file-name">.agentone</span>
<button class="file-del-btn" title="Delete">×</button>
            </div>
            <div class="file-item" draggable="true" style="padding-left: 8px;">
            <span class="file-tree-toggle">▸</span>
            <span class="file-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            </span>
            <span class="file-name">.git</span>
            <button class="file-del-btn" title="Delete">×</button>
        </div>
        <div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▾</span>
        <span class="file-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
        </span>
        <span class="file-name">.pytest_cache</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">v</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">.gitignore</span>
<span class="file-size">0.0k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">CACHEDIR.TAG</span>
<span class="file-size">0.2k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">README.md</span>
<span class="file-size">0.3k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">__pycache__</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▾</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">config</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">__pycache__</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">__init__.py</span>
<span class="file-size">0.2k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">asgi.py</span>
<span class="file-size">0.5k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">celery.py</span>
<span class="file-size">0.8k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">settings.py</span>
<span class="file-size">3.8k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">settings_local.py</span>
<span class="file-size">0.3k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">urls.py</span>
<span class="file-size">4.0k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">wsgi.py</span>
<span class="file-size">0.4k</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">docs</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">launcher</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">old</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">registry</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">runtime</span>
<button class="file-del-btn" title="Delete">×</button>
</div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">server</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">tools</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-tree-toggle">▾</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">ui</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▾</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">__pycache__</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 40px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
</span>
<span class="file-name" title="Double-click to rename">app.cpython-312.pyc</span>
<span class="file-size">1.3k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 40px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
</span>
<span class="file-name" title="Double-click to rename">app_view.cpython-312.pyc</span>
<span class="file-size">3.7k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 40px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
</span>
<span class="file-name" title="Double-click to rename">consumer.cpython-312.pyc</span>
<span class="file-size">2.4k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">chat</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">lib</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">main</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">overlay</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">panels</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">sidebar</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">static</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-tree-toggle">▸</span>
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</span>
<span class="file-name">templates</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">.DS_Store</span>
<span class="file-size">6.0k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">app.py</span>
<span class="file-size">0.9k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">app_view.py</span>
<span class="file-size">3.5k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">consumer.py</span>
<span class="file-size">1.8k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 24px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">README.md</span>
<span class="file-size">6.1k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">.DS_Store</span>
<span class="file-size">6.0k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">.gitignore</span>
<span class="file-size">0.4k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">.pylintrc</span>
<span class="file-size">0.2k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">agentone_public.py</span>
<span class="file-size">1.0k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">cert.pem</span>
<span class="file-size">1.0k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">db.sqlite3</span>
<span class="file-size">43048.0k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">key.pem</span>
<span class="file-size">1.6k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">manage.py</span>
<span class="file-size">0.2k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">ollama_models_download.py</span>
<span class="file-size">5.7k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">requirements.txt</span>
<span class="file-size">0.3k</span>
<button class="file-del-btn" title="Delete">×</button></div><div class="file-item" draggable="true" style="padding-left: 8px;">
<span class="file-icon">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>
</span>
<span class="file-name" title="Double-click to rename">w.py</span>
<span class="file-size">0.4k</span>
<button class="file-del-btn" title="Delete">×</button></div></div>
    <div id="wsEmptyState" style="display:none;flex:1;align-items:center;justify-content:center;padding:24px 16px;text-align:center;color:var(--muted);font-size:12px;line-height:1.6"></div>
    <div class="preview-area" id="previewArea">
      <div class="preview-path" id="previewPath">
        <span id="previewPathText">
</span>
        <span class="preview-badge code" id="previewBadge">.py</span>
        <button id="btnOpenInBrowser" class="panel-icon-btn" style="margin-left:auto;font-size:12px;width:auto;padding:2px 8px;display:none;align-items:center;gap:4px" onclick="openInBrowser()" title="Open in new browser tab">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg> <span data-i18n="open_in_browser">Open in browser</span>
</button>
        <button id="btnDownloadFile" class="panel-icon-btn" style="margin-left:auto;font-size:12px;width:auto;padding:2px 8px;display:inline-flex;align-items:center;gap:4px" onclick="downloadFile(_previewCurrentPath)" title="Download file to your computer">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download</button>
        <button id="btnEditFile" class="panel-icon-btn" style="font-size: 12px; width: auto; padding: 2px 8px; align-items: center; gap: 4px;" onclick="toggleEditMode()" title="Edit this file">✎ Edit</button>
      </div>
      <pre class="preview-code" id="previewCode"></pre>
      <div class="preview-img-wrap" id="previewImgWrap" style="display:none"><img class="preview-img" id="previewImg" src="" alt=""></div>
      <div class="preview-media-wrap" id="previewMediaWrap" style="display:none"></div>
      <div class="preview-pdf-wrap" id="previewPdfWrap" style="display:none">
        <iframe class="preview-pdf-frame" id="previewPdfFrame" src="" title="PDF preview"></iframe>
      </div>
      <div class="preview-md" id="previewMd" style="display:none"></div>
      <div class="preview-html-wrap" id="previewHtmlWrap" style="display:none;flex:1;border-radius:8px;overflow:hidden;border:1px solid var(--border2)">
        <iframe id="previewHtmlIframe" style="width:100%;height:100%;border:none;background:#fff" sandbox="allow-scripts" title="HTML preview" src=""></iframe>
      </div>
      <textarea id="previewEditArea" style="display:none;flex:1;width:100%;background:var(--code-bg);color:var(--pre-text);border:1px solid var(--border2);border-radius:8px;padding:12px;font-family:'SF Mono',ui-monospace,monospace;font-size:12px;line-height:1.6;resize:none;outline:none" oninput="_previewDirty=true;updateEditBtn()"></textarea>
    </div>

'''


