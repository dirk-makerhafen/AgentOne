from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView


class ClarifyCard(ModelView):
    DOM_ELEMENT_CLASS = 'clarify-card'
    DOM_ELEMENT_EXTRAS = 'role="dialog" aria-labelledby="clarifyHeading" aria-describedby="clarifyQuestion clarifyHint" style="display:none"'
    TEMPLATE_STR = '''
        <div class="clarify-inner">
            <div class="clarify-header">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 17h.01"/>
                    <path d="M9.09 9a3 3 0 1 1 5.82 1c0 2-3 2-3 4"/>
                    <circle cx="12" cy="12" r="10"/>
                </svg>
                <span id="clarifyHeading" data-i18n="clarify_heading">Clarification needed</span>
                <span class="clarify-countdown" id="clarifyCountdown"></span>
            </div>
            <div class="clarify-question" id="clarifyQuestion"></div>
            <div class="clarify-choices" id="clarifyChoices"></div>
            <div class="clarify-response">
                <input class="clarify-input" id="clarifyInput" type="text" data-i18n-placeholder="clarify_input_placeholder" placeholder="Type your response…">
                <button class="clarify-submit" id="clarifySubmit" onclick="respondClarify()" data-i18n="clarify_send">Send</button>
            </div>
            <div class="clarify-hint" id="clarifyHint" data-i18n="clarify_hint">Pick a choice, or type your own answer below.</div>
        </div>
    '''

    
'''
<div class="clarify-card visible" id="clarifyCard" role="dialog" aria-labelledby="clarifyHeading" aria-describedby="clarifyQuestion clarifyHint">
        <div class="clarify-inner">
          <div class="clarify-header">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 17h.01"></path><path d="M9.09 9a3 3 0 1 1 5.82 1c0 2-3 2-3 4"></path><circle cx="12" cy="12" r="10"></circle></svg>
            <span id="clarifyHeading" data-i18n="clarify_heading">Clarification needed</span>
            <span class="clarify-countdown" id="clarifyCountdown">66s</span>
          </div>
          <div class="clarify-question" id="clarifyQuestion">You have provided the path `/obsidian`.

Should I do one of the following:
1. **Change the active workspace** to `/obsidian` and suspend our work on the agent loading overhaul?
2. **Integrate Obsidian functionality** (i.e., using note-taking concepts) into the agent definition or skill loading process in `/Users/Dirk/AgentOne/`?
3. **Ignore the path** and continue with the development plan for the agent overhaul in `/Users/Dirk/AgentOne/`?</div>
          <div class="clarify-choices" id="clarifyChoices" style="display: none;"></div>
          <div class="clarify-response">
            <input class="clarify-input" id="clarifyInput" type="text" data-i18n-placeholder="clarify_input_placeholder" placeholder="Type your response…">
            <button class="clarify-submit" id="clarifySubmit" onclick="respondClarify()" data-i18n="clarify_send">Send</button>
          </div>
          <div class="clarify-hint" id="clarifyHint" data-i18n="clarify_hint">Pick a choice, or type your own answer below.</div>
        </div>
      </div>
      '''