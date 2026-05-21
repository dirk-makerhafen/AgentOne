from ui.lib.model_view import ModelView

class MemoryItemView(ModelView):
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
    CSS_STR = '''
        /* Styles for the improved Memory Tab UI */
        .memory-track-container {
            margin-bottom: 12px;
        }

        .memory-track-container h4 {
            font-size: 0.85em; /* Smaller */
            font-weight: bold;
            color: #333;
            margin-top: 0;
            margin-bottom: 4px;
            padding-left: 2px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #eee;
        }

        .memory-layer-container {
            margin-left: 5px;
            padding-left: 8px;
            border-left: 2px solid #f0f0f0;
        }

        .memory-layer-container h5 {
            font-size: 0.8em; /* Smaller */
            font-weight: bold;
            color: #666;
            margin-top: 8px;
            margin-bottom: 3px;
        }

        .memory-item {
            font-family: Menlo, Monaco, Consolas, "Courier New", monospace;
            font-size: 0.8em; /* Smaller */
            padding: 2px 4px;
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 3px;
            margin-bottom: 4px;
            word-wrap: break-word; /* Keep word-wrap */
            word-break: break-all;
            line-height: 1.4;
            /* Removed flex properties for block-level flow */
            overflow: hidden; /* Contains floated children */
        }

        .memory-item .memory-item-index { /* Corrected selector */
            text-align: center;
            font-weight: bolder;
            color: #6a6a6a;
            font-size: 1.1em;
            margin-right: 0px;
        }

        .memory-item .memory-editable-content { /* New rule for content */
            flex-grow: 1;           /* Allow content to take remaining space and wrap */
        }

        /* --- Memory Tab Structure --- */
        .memory-tabs {
            display: flex;
            flex-wrap: wrap; /* Allow tabs to wrap on small screens */
            border-bottom: 1px solid #dee2e6;
            margin-bottom: 5px;
        }

        .memory-tab-btn {
            padding: 5px 5px;
            cursor: pointer;
            border: none;
            background-color: transparent;
            font-size: 0.85em;
            font-weight: bold;
            color: #6c757d;
            border-bottom: 2px solid transparent;
            margin-bottom: -1px; /* Overlap the container's border-bottom */
            transition: all 0.2s ease-in-out;
            flex: auto;
        }

        .memory-tab-btn:hover {
            background-color: #e9ecef;
            color: #0056b3;
        }

        .memory-tab-btn.active {
            color: #007bff;
            border-bottom-color: #007bff;
        }

        .memory-content {
            display: flex;
            flex-direction: column;
        }

        .memory-track-pane {
            display: none; /* Hide panes by default */
        }

        .memory-track-pane.active {
            display: flex; /* Show only the active pane */
            flex-direction: column;
        }



        /* --- Memory Layer Structure --- */
        .memory-layer-container {
            margin-top: 5px;
            padding-top: 0;
            border-top: 1px solid #e0e0e0;
        }

        .memory-layer-container:first-child {
            margin-top: 5px;
            padding-top: 0;
            border-top: none;
        }

        .memory-layer-header {
            font-size: 0.9em;
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
        }

        /* --- Flexbox Layout for Scrolling --- */
        /* Target the dynamically generated ID of the memory tab content */
        div[id^="sidebar-tab-memory_"] {
            display: flex;
            flex-direction: column;
            height: 100%;
            max-height: 100%;
        }

        .memory-tabs {
            flex-shrink: 0; /* Prevent the tab bar from shrinking */
        }

        .memory-content {
            flex-grow: 1; /* Allow the content area to expand and fill space */
            overflow-y: auto; /* Enable vertical scrolling for the content */
            min-height: 50px; /* Prevent it from collapsing completely */
            padding: 5px;
        }
'''
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

class MemoryView(ModelView):
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