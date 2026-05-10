<div class="mobile-overlay" id="mobileOverlay" onclick="closeMobileSidebar()"></div>
<div class="app-dialog-overlay" id="appDialogOverlay" style="display:none" aria-hidden="true">
    <div class="app-dialog" id="appDialog" role="dialog" aria-modal="true" aria-labelledby="appDialogTitle" aria-describedby="appDialogDesc">
        <div class="app-dialog-header">
        <div class="app-dialog-title" id="appDialogTitle">Confirm action</div>
        <button class="app-dialog-close" id="appDialogClose" type="button" aria-label="Close dialog">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
        </div>
        <div class="app-dialog-desc" id="appDialogDesc"></div>
        <input class="app-dialog-input" id="appDialogInput" type="text" style="display:none">
        <div class="app-dialog-actions">
        <button class="app-dialog-btn" id="appDialogCancel" type="button" data-i18n="cancel">Cancel</button>
        <button class="app-dialog-btn confirm" id="appDialogConfirm" type="button">Confirm</button>
        </div>
    </div>
</div>