

from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class ResponseView(PyHtmlView):
    DOM_ELEMENT_CLASS = 'LLMResponseView conversation-log-item log-type-llm llm-response-item'
    TEMPLATE_STR = """
        <div class="message-header">
            <strong>[{{ pyview.subject.created_at }}]</strong> <strong>LLM Response : </strong>
            {{ pyview.subject.prompt_tokens }}/{{ pyview.subject.completion_tokens }} tokens
            <button class="btn btn-xs btn-default log-btn" onclick="pyview.toggle_raw()"><i class="fa fa-code"></i> raw</button>
        </div>
        <div id="raw_json_container_llm_response_{{ pyview.subject.id }}" class="message-content {{ 'hidden' if pyview.is_raw_hidden else '' }}">
            <pre>{{ pyview.subject.data }}</pre>
        </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_raw_hidden = True

    def toggle_raw(self):
        self.is_raw_hidden = not self.is_raw_hidden
        self.update()

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp() )}"'
    