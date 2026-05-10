from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView


if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView

class RightpanelView(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = """
        <div class="resize-handle" id="rightpanelResize"></div>
        <div class="panel-header">
            <span>Workspace</span>
            <span class="git-badge" id="gitBadge" style="display:none"></span>
            <div class="panel-actions">
                <button class="panel-icon-btn" id="btnCollapseWorkspacePanel" title="Hide workspace panel" onclick="toggleWorkspacePanel(false)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"/></svg></button>
                <button class="panel-icon-btn" id="btnUpDir" title="Parent directory" onclick="navigateUp()" style="display:none"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg></button>
                <button class="panel-icon-btn" id="btnNewFile" title="New file" onclick="promptNewFile()"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
                <button class="panel-icon-btn" id="btnNewFolder" title="New folder" onclick="promptNewFolder()"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></button>
                <button class="panel-icon-btn" id="btnRefreshPanel" title="Refresh" onclick="if(S.session)loadDir(S.currentDir)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></button>
                <button class="panel-icon-btn close-preview" id="btnClearPreview" title="Close preview"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                <button class="panel-icon-btn mobile-close-btn" onclick="handleWorkspaceClose()" title="Close" aria-label="Close workspace panel">×</button>
            </div>
        </div>
        <div class="breadcrumb-bar" id="breadcrumbBar" style="display:none"></div>
        <div class="file-tree" id="fileTree"></div>
        <div id="wsEmptyState" style="display:none;flex:1;align-items:center;justify-content:center;padding:24px 16px;text-align:center;color:var(--muted);font-size:12px;line-height:1.6"></div>
        <div class="preview-area" id="previewArea">
            <div class="preview-path" id="previewPath">
                <span id="previewPathText"></span>
                <span class="preview-badge" id="previewBadge"></span>
                <button id="btnOpenInBrowser" class="panel-icon-btn" style="margin-left:auto;font-size:12px;width:auto;padding:2px 8px;display:none;align-items:center;gap:4px" onclick="openInBrowser()" title="Open in new browser tab"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg> <span data-i18n="open_in_browser">Open in browser</span></button>
                <button id="btnDownloadFile" class="panel-icon-btn" style="margin-left:auto;font-size:12px;width:auto;padding:2px 8px;display:inline-flex;align-items:center;gap:4px" onclick="downloadFile(_previewCurrentPath)" title="Download file to your computer"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download</button>
                <button id="btnEditFile" class="panel-icon-btn" style="font-size:12px;width:auto;padding:2px 8px;display:none;align-items:center;gap:4px" onclick="toggleEditMode()"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg> Edit</button>
            </div>
            <pre class="preview-code" id="previewCode"></pre>
            <div class="preview-img-wrap" id="previewImgWrap" style="display:none"><img class="preview-img" id="previewImg" src="" alt=""></div>
            <div class="preview-media-wrap" id="previewMediaWrap" style="display:none"></div>
            <div class="preview-pdf-wrap" id="previewPdfWrap" style="display:none">
                <iframe class="preview-pdf-frame" id="previewPdfFrame" src="" title="PDF preview"></iframe>
            </div>
            <div class="preview-md" id="previewMd" style="display:none"></div>
            <div class="preview-html-wrap" id="previewHtmlWrap" style="display:none;flex:1;border-radius:8px;overflow:hidden;border:1px solid var(--border2)">
                <iframe id="previewHtmlIframe" style="width:100%;height:100%;border:none;background:#fff" sandbox="allow-scripts" title="HTML preview"></iframe>
            </div>
            <textarea id="previewEditArea" style="display:none;flex:1;width:100%;background:var(--code-bg);color:var(--pre-text);border:1px solid var(--border2);border-radius:8px;padding:12px;font-family:'SF Mono',ui-monospace,monospace;font-size:12px;line-height:1.6;resize:none;outline:none" oninput="_previewDirty=true;updateEditBtn()"></textarea>
        </div>
    """