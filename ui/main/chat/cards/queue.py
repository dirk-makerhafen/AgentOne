                    
from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView


class QueueCard(ModelView):
    DOM_ELEMENT_CLASS = 'queue-card'
    DOM_ELEMENT_EXTRAS = 'role="region" aria-label="Queued messages" aria-live="polite"'
    TEMPLATE_STR = '''
        <div id="queueChips" class="queue-card-inner">
            <div class="queue-card-header">
                <span title="Sends automatically after the current response completes">3 queued</span>
                <span class="queue-card-header-actions">
                    <button class="queue-card-btn" title="Combine all into one message">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>
                        Combine
                    </button>
                    <button class="queue-card-icon-btn" title="Clear all queued messages" aria-label="Clear all queued messages">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                    <button class="queue-card-icon-btn" title="Hide queue (click the queue pill to show again)" aria-label="Hide queue panel">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </button>
                </span>
            </div>
            <div class="queue-card-row" role="listitem" draggable="true">
                <span class="queue-card-drag" aria-hidden="true">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="3" y="5" width="6" height="6" rx="1"></rect><path d="m3 17 2 2 4-4"></path><path d="M13 6h8"></path><path d="M13 12h8"></path><path d="M13 18h8"></path></svg>
                </span>
                <span class="queue-card-text" contenteditable="true" role="textbox" aria-label="Queued message — edit in place" draggable="false" style="">asdsadasd</span>
                <span class="queue-card-badges">
                    <span title="Model: gemma4:e4b">gemma4:e4b</span>
                </span>
                <button class="queue-card-icon-btn" aria-label="Cancel queued message" draggable="false" title="Remove from queue">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
            <div class="queue-card-row" role="listitem" draggable="true">
                <span class="queue-card-drag" aria-hidden="true">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="3" y="5" width="6" height="6" rx="1"></rect><path d="m3 17 2 2 4-4"></path><path d="M13 6h8"></path><path d="M13 12h8"></path><path d="M13 18h8"></path></svg>
                </span>
                <span class="queue-card-text" contenteditable="true" role="textbox" aria-label="Queued message — edit in place" draggable="false">asd</span>
                <span class="queue-card-badges">
                    <span title="Model: gemma4:e4b">gemma4:e4b</span>
                </span>
                <button class="queue-card-icon-btn" aria-label="Cancel queued message" draggable="false" title="Remove from queue">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
            <div class="queue-card-row" role="listitem" draggable="true">
                <span class="queue-card-drag" aria-hidden="true">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="3" y="5" width="6" height="6" rx="1"></rect><path d="m3 17 2 2 4-4"></path><path d="M13 6h8"></path><path d="M13 12h8"></path><path d="M13 18h8"></path></svg>
                </span>
                <span class="queue-card-text" contenteditable="true" role="textbox" aria-label="Queued message — edit in place" draggable="false">asdsd</span>
                <span class="queue-card-badges">
                    <span title="Model: gemma4:e4b">gemma4:e4b</span>
                </span>
                <button class="queue-card-icon-btn" aria-label="Cancel queued message" draggable="false" title="Remove from queue">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
        </div>
    '''


'''
    <div id="queueCard" class="queue-card visible" role="region" aria-label="Queued messages" aria-live="polite">
        <div id="queueChips" class="queue-card-inner"><div class="queue-card-header">
            <span title="Sends automatically after the current response completes">2 queued</span>
            <span class="queue-card-header-actions">
                <button class="queue-card-btn" title="Combine all into one message">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>
                    Combine
                </button>
                <button class="queue-card-icon-btn" title="Clear all queued messages" aria-label="Clear all queued messages">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
                <button class="queue-card-icon-btn" title="Hide queue (click the queue pill to show again)" aria-label="Hide queue panel"
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="6 9 12 15 18 9"></polyline></svg>
                </button>
            </span>
        </div>
        <div class="queue-card-row" role="listitem" draggable="true">
            <span class="queue-card-drag" aria-hidden="true">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="3" y="5" width="6" height="6" rx="1"></rect><path d="m3 17 2 2 4-4"></path><path d="M13 6h8"></path><path d="M13 12h8"></path><path d="M13 18h8"></path></svg>
            </span>
            <span class="queue-card-text" contenteditable="true" role="textbox" aria-label="Queued message — edit in place" draggable="false">asdasd</span>
            <span class="queue-card-badges">
                <span title="Model: gemma4:e4b">gemma4:e4b</span>
            </span>
            <button class="queue-card-icon-btn" aria-label="Cancel queued message" draggable="false" title="Remove from queue">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <div class="queue-card-row" role="listitem" draggable="true">
            <span class="queue-card-drag" aria-hidden="true">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="3" y="5" width="6" height="6" rx="1"></rect><path d="m3 17 2 2 4-4"></path><path d="M13 6h8"></path><path d="M13 12h8"></path><path d="M13 18h8"></path></svg>
                </span>
                <span class="queue-card-text" contenteditable="true" role="textbox" aria-label="Queued message — edit in place" draggable="false">asdsd</span>
                <span class="queue-card-badges">
                    <span title="Model: gemma4:e4b">gemma4:e4b</span>
                </span>
                <button class="queue-card-icon-btn" aria-label="Cancel queued message" draggable="false" title="Remove from queue">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
        </div>
    </div>
'''



