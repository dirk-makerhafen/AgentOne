from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView


class ApprovalCard(ModelView):
    DOM_ELEMENT_CLASS = 'approval-card'
    DOM_ELEMENT_EXTRAS = 'role="alertdialog" aria-labelledby="approvalHeading" aria-describedby="approvalDesc" style="display:none"'
    TEMPLATE_STR = '''
        <div class="approval-inner">
            <div class="approval-header">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                <span id="approvalHeading" data-i18n="approval_heading">Approval required</span>
            </div>
            <div class="approval-desc" id="approvalDesc"></div>
            <div class="approval-cmd" id="approvalCmd"></div>
            <div class="approval-counter" id="approvalCounter" style="display:none1;font-size:0.75em;opacity:0.6;margin-top:4px;"></div>
            <div class="approval-btns">
                <button class="approval-btn once" id="approvalBtnOnce" onclick="respondApproval('once')" title="Allow this one command (Enter)" data-i18n-title="approval_btn_once_title">
                    <span class="approval-btn-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <polyline points="20 6 9 17 4 12"/>
                    </svg>
                    </span>
                    <span class="approval-btn-label" data-i18n="approval_btn_once">Allow once</span>
                    <kbd class="approval-kbd">↵</kbd>
                </button>
                <button class="approval-btn session" id="approvalBtnSession" onclick="respondApproval('session')" title="Allow for this session">
                    <span class="approval-btn-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                    </span>
                    <span class="approval-btn-label" data-i18n="approval_btn_session">Allow session</span>
                </button>
                <button class="approval-btn always" id="approvalBtnAlways" onclick="respondApproval('always')" title="Always allow this command pattern">
                    <span class="approval-btn-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    </span>
                    <span class="approval-btn-label" data-i18n="approval_btn_always">Always allow</span>
                </button>
                <button class="approval-btn deny" id="approvalBtnDeny" onclick="respondApproval('deny')" title="Deny — do not run this command">
                    <span class="approval-btn-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                    </span>
                    <span class="approval-btn-label" data-i18n="approval_btn_deny">Deny</span>
                </button>
                <button class="approval-btn yolo" id="approvalSkipAll" onclick="toggleYoloFromApproval()" title="Skip all approvals this session" data-i18n-title="approval_skip_all_title">
                    <span class="approval-btn-icon" aria-hidden="true">⚡</span>
                    <span class="approval-btn-label" data-i18n="approval_skip_all">Skip all</span>
                </button>
            </div>
        </div>
    '''
