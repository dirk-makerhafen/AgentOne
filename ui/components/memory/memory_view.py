from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class MemoryItemView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="memory-track-item-wrapper layer-{{ pyview.subject.layer }}" id="memory-item-wrapper-{{ pyview.subject.id }}">
    <li class="memory-item" id="memory-item-{{ pyview.subject.id }}">
        <div class="memory-item-header">
            <span class="memory-item-index">[{{ pyview.subject.id }}]</span>
            <div class="memory-item-actions-main">
                <button class="btn btn-xs btn-default add-memory-btn" title="Add new item here" data-item-id="{{ pyview.subject.id }}" data-item-track="{{ pyview.subject.track }}" data-item-layer="{{ pyview.subject.layer }}" onclick="pyview.add_memory_item()"><i class="fa fa-plus"></i></button>
                <button class="btn btn-xs btn-default delete-memory-btn" title="Delete this item" data-item-id="{{ pyview.subject.id }}" data-item-track="{{ pyview.subject.track }}" data-item-layer="{{ pyview.subject.layer }}" onclick="pyview.delete_memory_item()"><i class="fa fa-trash"></i></button>
            </div>
        </div>
        <div class="memory-item-body">
            <pre class="memory-item-content"  id="memory-item-content-{{ pyview.subject.id }}"
                 contenteditable="true"
                 onfocus="pyview.handle_memory_focus()">{{ pyview.subject.content.content }}</pre>
            <div class="memory-edit-actions {% if not pyview.is_editing %}hidden{% endif %}" id="memory-edit-actions-{{ pyview.subject.id }}">
                <button class="btn btn-xs btn-success save-memory-btn" data-item-id="{{ pyview.subject.id }}" onclick="pyview.save_memory_edit(document.getElementById('memory-item-content-{{pyview.subject.id}}').innerText)">Save</button>
                <button class="btn btn-xs btn-default cancel-memory-btn" data-item-id="{{ pyview.subject.id }}" onclick="pyview.cancel_memory_edit()">Cancel</button>
            </div>
        </div>
    </li>
</div>
    """
    def __init__(self, subject, parent,  **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self.is_editing = False

    def add_memory_item(self):
        self.parent.add_new_memory_item(self.subject.track, self.subject.layer, self.subject.id)

    def delete_memory_item(self):
        self.parent.delete_memory_item(self.subject.id)

    def handle_memory_focus(self): 
        self.is_editing = True
        self.update()

    def handle_memory_blur(self): 
        # This will be handled by save/cancel buttons, not blur directly
        pass

    def save_memory_edit(self, new_content):
        if self.subject.content != new_content:
            # Assuming MemoryModel has a content field and a save method
            self.subject.content = new_content
            self.subject.save() # This should trigger a websocket update for the model
        self.is_editing = False
        self.update()

    def cancel_memory_edit(self):
        self.is_editing = False
        self.update()

    def _on_subject_died(self, wr) -> None:
        pass

class MemoryView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="memory-controls">
        <div class="memory-tabs">
            {% for track in pyview.subject.tracks %}
                 <button class="memory-track-btn {{ 'active' if track == pyview.subject.active_track else '' }}" onclick="pyview.set_active_track('{{ track }}')">{{ track }}</button>
            {% endfor %}
        </div>
    </div>
    <div class="memory-list-container">
        <div>

                {% for item in pyview.get() %}
                    {{ item }}
                {% endfor %}
           
        </div>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self._item_views = {}
        self.active_track = "status"

    def get(self):
        r = MemoryItem.objects.filter(agent_instance=self.subject.agent_instance,track=self.active_track, layer="short_term" )
        #r = self.subject.get()
        print("self.subject.", self.subject, list(r))
        for item in  list(r):
            print(item)
            if item.id not in self._item_views:
                self._item_views[item.id] = MemoryItemView(item, self)
            yield self._item_views[item.id].render()

    def render_item(self, item):
        print("renderitem", item)
 
    def set_active_track(self, track):
        self.active_track = track.lower()
        self.update()
        
    def add_new_memory_item(self, track, layer, after_item_id):
        # Create a new MemoryModel instance
        new_memory_item = MemoryItem.objects.create(
            instance=self.subject, 
            track=track, 
            layer=layer, 
            content="[New Memory Item]"
        )

        # Refresh the subject's items to include the new one
        self.subject.refresh_from_db()
        self.update()

    def delete_memory_item(self, item_id):
        # Delete the MemoryModel instance
        MemoryItem.objects.filter(id=item_id).delete()

        # Refresh the subject's items to reflect the deletion
        self.subject.refresh_from_db()
        self.update()

    def _on_subject_died(self, wr) -> None:
        pass