from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.agents.session import Session
from server.models.message import Message
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observableList import ObservableList
from ui.lib.pyHtmlGui.pyhtmlgui.view.observable_list_view import ObservableListView
from ui.main.chat.messages.message import MessageView
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.chat.chat import Chat


class ObservableMessageListView(ObservableListView):
    TEMPLATE_STR = '''
        {% for item in pyview.get_items() %}
            {{ item.render() }}
        {% endfor %}
       
    '''
class Messages(ModelView):
    DOM_ELEMENT_CLASS = 'messages'
    TEMPLATE_STR = '''
    <style>

@keyframes smoothAppear {
  0% {
    opacity: 0;
    transform: translateY(50%); /* Starts slightly lower */
  }
  100% {
    opacity: 1;
    transform: translateY(0);    /* Ends in its natural position */
  }
}
    </style>
            <button id="scrollToBottomBtn" class="scroll-to-bottom-btn" aria-label="Scroll to bottom" onclick="e=document.getElementById('{{pyview.uid}}');e.scrollTo(0, e.scrollHeight);" style="display:none1">↓</button>

            <div class="empty-state" id="emptyState" style="display:none">
                <div class="empty-logo"></div>
                <h2 data-i18n="empty_title">What can I help with?</h2>
                <p data-i18n="empty_subtitle">Ask anything, run commands, explore files, or manage your scheduled tasks.</p>
            </div>
            
            <div id="top-sentinel" style="height: 1px;position:relative;top:"></div>
            {{ pyview.messages_view.render() }}
            <div id="bottom-sentinel" style="height: 1px;"></div>    

            <span onclick="pyview.up()">UP</span>
            <span onclick="pyview.down()">DOWN</span>
            <div id="liveCompressionCards" class="live-compression-cards"></div>

            <div id="liveToolCards" style="display:none1;max-width:800px;margin:0 auto;width:100%;padding:0 24px;"></div>

            
            <script>
                // Functions to manage your data
                function loadMoreBottomItems() {
                    pyview.down();
                    console.log("Loading new items at bottom, unloading top items...");
                }

                function loadMoreTopItems() {
                    pyview.up();
                    console.log("Loading older items at top, unloading bottom items...");
                }

                // Configuration for the observer
                 options = {
                    //root: document.getElementById('{{pyview.uid}}'), // Uses the browser viewport (change to your container element if nested)
                    // "20% 0px" extends the detection zone vertically by 20% outside the viewport
                    rootMargin: '10% 0px 10% 0px', 
                    threshold: 0 // Trigger as soon as the sentinel hits the 20% margin zone
                };

                 var observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        console.log(entry);
                        // Only trigger if the element enters our 20% buffer zone
                        if (entry.isIntersecting) {
                             console.log(entry.target);
                            pyview.update_list(entry.target.dataset.pk);
                            if (entry.target.id === 'bottom-sentinel') {
                                //loadMoreBottomItems();
                            } else if (entry.target.id === 'top-sentinel') {
                                //loadMoreTopItems();
                            };
                        }
                    });
                }, options);

                // Start watching the top and bottom boundaries
                observer.observe(document.getElementById('top-sentinel'));
                observer.observe(document.getElementById('bottom-sentinel'));
            </script>

    '''

    def __init__(self, subject: Session, parent: Chat, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.max_visible_items = 20
        self.min_id = 0
        self.max_id = 2^32

        self.message_list = ObservableList()

        first_messages = list(reversed(list(Message.objects.filter(session_version__session=self.subject.model ).order_by("-pk")[:self.max_visible_items])))
        if first_messages:
            self.min_id = first_messages[0].pk
        if len(first_messages) > 1:
            self.max_id = first_messages[-1].pk
        self.message_list.extend(first_messages)

        self.messages_view = ObservableListView(
            subject=self.message_list, 
            parent=self, 
            item_class=MessageView,
            dom_element_class="messages-inner",
            
        )
    def update_list(self, center_pk):
        if not center_pk:
            return
        print("update_list", center_pk)
        if int(center_pk) in [x.pk for x in self.message_list[:7]]:
            self.up()
        if int(center_pk) in [x.pk for x in self.message_list[-7:]]:
            self.down()   
        

    def up(self):
        xs = list(Message.objects.filter(session_version__session=self.subject.model, pk__lt=self.min_id ).order_by("-pk")[:1])
        for x in xs:
            self.message_list.insert(0, x)
        self.min_id = self.message_list[0].pk
        while len(self.message_list) > self.max_visible_items:
            del self.message_list[-1]
        self.max_id = self.message_list[-1].pk
        print("foo", [x.pk for x in self.message_list])
        print("MINMAX UP", self.min_id, self.max_id)
        print("len", len(self.message_list))

    def down(self):
        x = list(Message.objects.filter(session_version__session=self.subject.model, pk__gt=self.max_id ).order_by("pk")[:1])
        self.message_list.extend(x)
        self.max_id = self.message_list[-1].pk
        while len(self.message_list) > self.max_visible_items:
            del self.message_list[0]
        self.min_id = self.message_list[0].pk
        print("foo", [x.pk for x in self.message_list])
        print("MINMAX DOWN", self.min_id, self.max_id)
        print("len", len(self.message_list))