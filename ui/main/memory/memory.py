
<div id="mainMemory" class="main-view">
    <div class="main-view-header">
        <div class="main-view-title" id="memoryDetailTitle"></div>
        <div class="main-view-actions">
            <button id="btnEditMemoryDetail" class="panel-head-btn" title="Edit" aria-label="Edit" data-i18n-title="edit" onclick="editCurrentMemory()" style="display:none">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 20h9"/>
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
            </svg>
            </button>
            <button id="btnCancelMemoryDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelMemoryEdit()" style="display:none">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
            </button>
            <button id="btnSaveMemoryDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="submitMemorySave()" style="display:none">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
            </button>
        </div>
    </div>
    <div class="main-view-body" id="memoryDetailBody" style="display:none"></div>
    <div class="main-view-empty" id="memoryDetailEmpty">
        <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2z"/>
            <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2z"/>
        </svg>
        <div class="main-view-empty-title" data-i18n="memory_empty_title">Select a memory section</div>
        <div class="main-view-empty-sub" data-i18n="memory_empty_sub">Pick a section from the sidebar to view or edit its contents.</div>
    </div>
</div>