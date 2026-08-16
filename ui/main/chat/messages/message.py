from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.enums.message_enums import MessageRole
from server.models.message import Message
from server.models.queries.query import Query
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

from ui.main.chat.messages.assistant_message import AssistantMessageView
from ui.main.chat.messages.query import QueryView
from ui.main.chat.messages.user_message import UserMessageView

class MessageView(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "MessageView msg-row"
    TEMPLATE_STR = '''{{ pyview.view.render() }}'''

    def __init__(self, subject: Message|Query, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)
        if isinstance(subject, Message):
            if subject.role == MessageRole.ASSISTANT:
                self.view = AssistantMessageView(subject, self)
            else:
                self.view = UserMessageView(subject=subject, parent=self)
            self.role = self.subject.role
        else:
            self.view = QueryView(subject=subject, parent=self)
            self.role = "query"

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return  f"style='display:flex;' data-pk='{self.subject.pk}' data-role='{self.role}'  "

    def fork(self, message_id):
        """Fork the conversation starting at *message_id*.

        Creates a new child session (a permanent user branch) whose message
        chain links back to the forked-from message via ``prev_message``, so
        the branch inherits the conversation history up to and including that
        message.  A hidden anchor message heads the new session's chain so the
        next user turn continues from the fork point.  The UI then switches to
        the new branch.

        Mirrors ``spawn_subtask`` (``.agentone/scripts/subagents``), except
        the branch is a normal user-facing SESSION (not a ``SUBTASK_FORK``),
        because the user keeps chatting there instead of a subagent.
        """
        from time import time
        from runtime.session.session import Session as RuntimeSession
        from server.models.enums.message_enums import MessageContentType, MessagePartType
        from server.models.enums.session_enums import SessionType

        try:
            fork_point = Message.objects.get(pk=message_id)
        except Message.DoesNotExist:
            return

        parent_session = fork_point.session.get_runtime()

        agent_version = parent_session.agent.get_version_model()
        if agent_version is None:
            from server.models.agents.agent_version import AgentVersionModel
            agent_version = (
                AgentVersionModel.objects.filter(agent=parent_session.agent.model)
                .order_by("-version_number")
                .first()
            )
        if agent_version is None:
            return

        session_name = f"p{parent_session.model.pk}:fork:{int(time())}"
        child_sv = agent_version.get_or_create_session(
            name=session_name,
            description=f"Forked from message #{message_id}",
            workspace=parent_session.workspace,
            parent_session_version=parent_session.get_version_model(),
            session_type=SessionType.SESSION,
        )
        child_session = RuntimeSession(session_model=child_sv.session, pinned_session_version=child_sv)
        child_version = child_session.get_version_model()

        # Anchor the branch's message chain to the fork point.  Hidden from
        # LLM context, but keeps the UI chain (and later prev_message links)
        # walking back into the parent conversation.
        anchor = Message.objects.create(
            role=MessageRole.USER,
            session=child_version.session,
            session_version=child_version,
            prev_message=fork_point,
            hide_from_context=True,
        )
        anchor.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content=f"Forked here from session #{parent_session.model.pk}.",
        )

        main_panel = self._main_panel()
        if main_panel is not None:
            from ui.main.chat.chat import Chat
            main_panel.create_and_open_tab(Chat, child_version.session)

    def _main_panel(self):
        """Return the app's MainView (``main_panel``) from an ancestor view."""
        node = self
        try:
            while node is not None:
                main_panel = getattr(node, "main_panel", None)
                if main_panel is not None:
                    return main_panel
                node = getattr(node, "parent", None)
        except Exception:
            return None
        return None

#animation: smoothAppear .5s ease-out forwards;




r'''
    
    <div class="tool-card-row">
    <div class="tool-card open">
      <div class="tool-card-header" onclick="this.closest('.tool-card').classList.toggle('open')">
        
        <span class="tool-card-icon"><svg width="16px" height="16px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>
</span>
        <span class="tool-card-name">skill_view</span>
        <span class="tool-card-preview">{"success": true, "name": "obsidian", "description": "Read, search, and create notes in the Obsidian vault.", "tags": [], "related_skills": [], "content": "---\nname: obsidian\ndescription: Read, search, and create notes in the Obsidian vault.\n---\n\n# Obsidian Vault\n\n**Location:** Set via `OBSIDIAN_VAULT_PATH` environment variable (e.g.</span>
        <span class="tool-card-toggle"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="9 18 15 12 9 6"></polyline></svg>
</span>
      </div>
      <div class="tool-card-detail">
        <div class="tool-card-args">
<div>
<span class="tool-arg-key">name</span> <span class="tool-arg-val">obsidian</span>
</div>
</div>
        <div class="tool-card-result">
          <pre>{"success": true, "name": "obsidian", "description": "Read, search, and create notes in the Obsidian vault.", "tags": [], "related_skills": [], "content": "---\nname: obsidian\ndescription: Read, search, and create notes in the Obsidian vault.\n---\n\n# Obsidian Vault\n\n**Location:** Set via `OBSIDIAN_VAULT_PATH` environment variable (e.g. in `~/.agentone/.env`).\n\nIf unset, defaults to `~/Documents/Obsidian Vault`.\n\nNote: Vault paths may contain spaces - always quote them.\n\n## Read a note\n\n```bash\nVAULT=\"${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\"\ncat \"$VAULT/Note Name.md\"\n```\n\n## List notes\n\n```bash\nVAULT=\"${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\"\n\n# All notes\nfind \"$VAULT\" -name \"*.md\" -type f\n\n# In a specific folder\nls \"$VAULT/Subfolder/\"\n```\n\n## Search\n\n```bash\nVAULT=\"${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\"\n\n# By filename\nfind \"$VAULT\" -name \"*.md\" -iname \"*keyword*\"\n\n# By content\ngrep -rli \"keyword\" \"$VAULT\" --include=\"*.md\"\n```\n\n## Create a note\n\n```bash\nVAULT=\"${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\"\ncat &gt; \"$VAULT/New Note.md\" &lt;&lt; 'ENDNOTE'\n# Title\n\nContent here.\nENDNOTE\n```\n\n## Append to a note\n\n```bash\nVAULT=\"${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\"\necho \"\nNew content here.\" &gt;&gt; \"$VAULT/Existing Note.md\"\n```\n\n## Wikilinks\n\nObsidian links notes with `[[Note Name]]` syntax. When creating notes, use these to link related content.\n", "path": "note-taking/obsidian/SKILL.md", "skill_dir": "/Users/Dirk/.agentone/skills/note-taking/obsidian", "linked_files": null, "usage_hint": null, "required_environment_variables": [], "required_commands": [], "missing_required_environment_variables": [], "missing_credential_files": [], "missing_required_commands": [], "setup_needed": false, "setup_skipped": false, "readiness_status": "available"}</pre>
          <button class="tool-card-more" data-full="{&quot;success&quot;: true, &quot;name&quot;: &quot;obsidian&quot;, &quot;description&quot;: &quot;Read, search, and create notes in the Obsidian vault.&quot;, &quot;tags&quot;: [], &quot;related_skills&quot;: [], &quot;content&quot;: &quot;---\nname: obsidian\ndescription: Read, search, and create notes in the Obsidian vault.\n---\n\n# Obsidian Vault\n\n**Location:** Set via `OBSIDIAN_VAULT_PATH` environment variable (e.g. in `~/.agentone/.env`).\n\nIf unset, defaults to `~/Documents/Obsidian Vault`.\n\nNote: Vault paths may contain spaces - always quote them.\n\n## Read a note\n\n```bash\nVAULT=\&quot;${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\&quot;\ncat \&quot;$VAULT/Note Name.md\&quot;\n```\n\n## List notes\n\n```bash\nVAULT=\&quot;${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\&quot;\n\n# All notes\nfind \&quot;$VAULT\&quot; -name \&quot;*.md\&quot; -type f\n\n# In a specific folder\nls \&quot;$VAULT/Subfolder/\&quot;\n```\n\n## Search\n\n```bash\nVAULT=\&quot;${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\&quot;\n\n# By filename\nfind \&quot;$VAULT\&quot; -name \&quot;*.md\&quot; -iname \&quot;*keyword*\&quot;\n\n# By content\ngrep -rli \&quot;keyword\&quot; \&quot;$VAULT\&quot; --include=\&quot;*.md\&quot;\n```\n\n## Create a note\n\n```bash\nVAULT=\&quot;${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\&quot;\ncat &gt; \&quot;$VAULT/New Note.md\&quot; &lt;&lt; 'ENDNOTE'\n# Title\n\nContent here.\nENDNOTE\n```\n\n## Append to a note\n\n```bash\nVAULT=\&quot;${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}\&quot;\necho \&quot;\nNew content here.\&quot; &gt;&gt; \&quot;$VAULT/Existing Note.md\&quot;\n```\n\n## Wikilinks\n\nObsidian links notes with `[[Note Name]]` syntax. When creating notes, use these to link related content.\n&quot;, &quot;path&quot;: &quot;note-taking/obsidian/SKILL.md&quot;, &quot;skill_dir&quot;: &quot;/Users/Dirk/.agentone/skills/note-taking/obsidian&quot;, &quot;linked_files&quot;: null, &quot;usage_hint&quot;: null, &quot;required_environment_variables&quot;: [], &quot;required_commands&quot;: [], &quot;missing_required_environment_variables&quot;: [], &quot;missing_credential_files&quot;: [], &quot;missing_required_commands&quot;: [], &quot;setup_needed&quot;: false, &quot;setup_skipped&quot;: false, &quot;readiness_status&quot;: &quot;available&quot;}" data-short="{&quot;success&quot;: true, &quot;name&quot;: &quot;obsidian&quot;, &quot;description&quot;: &quot;Read, search, and create notes in the Obsidian vault.&quot;, &quot;tags&quot;: [], &quot;related_skills&quot;: [], &quot;content&quot;: &quot;---\nname: obsidian\ndescription: Read, search, and create notes in the Obsidian vault.\n---\n\n# Obsidian Vault\n\n**Location:** Set via `OBSIDIAN_VAULT_PATH` environment variable (e.g." onclick="event.stopPropagation();const p=this.previousElementSibling;const full=this.dataset.full;const short=this.dataset.short;p.textContent=p.textContent===short?full:short;this.textContent=p.textContent===short?'Show more':'Show less'">Show less</button>
        </div>
      </div>
    </div>
</div>





<div class="assistant-segment" data-msg-idx="35" data-raw-text="It looks like we are shifting context! I have successfully loaded the `obsidian` skill.

From now on, when working with notes, I will utilize the tools defined in the **Obsidian Vault** skill.

**Obsidian Capability Summary:** I can read, search, and create notes within your configured Obsidian vault. This gives us powerful capabilities for structured knowledge management—perfect for documenting architectural decisions, keeping personal research notes, or even storing temporary scratchpad ideas during development.

**Next Steps:**

Since your active workspace is set to `/obsidian`, I assume you want to work within the context of your local note-taking system.

What would you like to do with the Obsidian vault now? For example:
1.  **Search:** &quot;Search my vault for all notes related to 'Django models' or 'agent architecture'.&quot;
2.  **Read:** &quot;Show me the contents of the note titled 'Agent Overhaul Plan'.&quot;
3.  **Create:** &quot;Create a new note titled 'Meeting Minutes - [Date]'.&quot;">
<div class="thinking-card open">
<div class="thinking-card-header" onclick="this.parentElement.classList.toggle('open')">
<span class="thinking-card-icon"><svg width="16px" height="16px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M12 2a7 7 0 0 1 7 7c0 2.5-1.3 4.7-3.2 6H8.2C6.3 13.7 5 11.5 5 9a7 7 0 0 1 7-7z"></path><line x1="9" y1="17" x2="15" y2="17"></line><line x1="10" y1="20" x2="14" y2="20"></line></svg>
</span>
<span class="thinking-card-label">Thinking</span>
<span class="thinking-card-toggle"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="9 18 15 12 9 6"></polyline></svg>
</span>
</div>
<div class="thinking-card-body"><pre>The user provided a directory path `/obsidian` and is likely trying to indicate a shift in context or provide a new workspace directory. However, the existing workspace is `/Users/Dirk/AgentOne`, and the user's input format is simply a path, which might be an attempt to move directories or signal an interest in the Obsidian concept (note-taking).

Given the context of the previous interaction (complex software development planning), and the user's last message being only a path `/obsidian` without an explicit command, I must:
1.  Acknowledge the new path.
2.  Assume the user is referencing the Obsidian note-taking functionality or directory.
3.  Check if the planned analysis of `/Users/Dirk/AgentOne/` should pause.
4.  Confirm the intended action for `/obsidian`.

Since the user provided the new path without a command, the most useful immediate action is to ask for clarification, especially since I just provided a multi-step plan that needs to be executed within the context of `/Users/Dirk/AgentOne/`. I should use the `clarify` tool because the user's intent is highly ambiguous.

Goal: Get the user to confirm if they want to:
A. Change the working directory to `/obsidian` (and thus suspend the development plan).
B. Use the content/concept of Obsidian in the current development task.
C. Simply provide an unrelated path.The user provided a path/keyword `/obsidian` and then responded to my clarification request by essentially giving a command: "load the skill".

1.  **Tool Analysis:** I have a skill named `obsidian` within the `note-taking` category.
2.  **Interpretation:** The user has explicitly requested to interact with this skill.
3.  **Action:** I must load the `obsidian` skill using `skill_view(name='obsidian')` before I can assist the user with its functionality or integrate it into the wider project plan. This is a direct, actionable request.
4.  **Context Shift:** The user is directing the flow away from the complex plan and towards a specific tool/documentation, so I must execute this request first.The user asked me to load the `obsidian` skill. I successfully loaded it.

Now that the user has explicitly pivoted the conversation to the `obsidian` skill and has loaded the skill, I must:
1.  Acknowledge the pivot.
2.  Update the active workspace to reflect the change, which is implied by the user's last action.
3.  Acknowledge the core purpose of the skill.
4.  Since the previous task (Agent Overhaul Plan) was complex, I should save the current state of memory to reflect this pivot, while still keeping the memory of the agent system in mind.

**Plan:**
1.  Inform the user that the active context is now the `obsidian` skill.
2.  Summarize the purpose of the `obsidian` tool (Reading, searching, and creating notes in the Obsidian Vault).
3.  Since the previous plan was complex, I will update my memory to *add* a note about the Obsidian vault path for future reference, assuming the user intends to use it with the existing path/vault name structure.
4.  Ask the user what they want to do with the Obsidian vault now (e.g., search, create notes, etc.).It looks like we are shifting context! I have successfully loaded the `obsidian` skill.

From now on, when working with notes, I will utilize the tools defined in the **Obsidian Vault** skill.

**Obsidian Capability Summary:** I can read, search, and create notes within your configured Obsidian vault. This gives us powerful capabilities for structured knowledge management—perfect for documenting architectural decisions, keeping personal research notes, or even storing temporary scratchpad ideas</pre>
</div>
</div>
<div class="msg-body"><p>It looks like we are shifting context! I have successfully loaded the <code>obsidian</code> skill.</p>
<p>From now on, when working with notes, I will utilize the tools defined in the <strong>Obsidian Vault</strong> skill.</p>
<p><strong>Obsidian Capability Summary:</strong> I can read, search, and create notes within your configured Obsidian vault. This gives us powerful capabilities for structured knowledge management—perfect for documenting architectural decisions, keeping personal research notes, or even storing temporary scratchpad ideas during development.</p>
<p><strong>Next Steps:</strong></p>
<p>Since your active workspace is set to <code>/obsidian</code>, I assume you want to work within the context of your local note-taking system.</p>
<p>What would you like to do with the Obsidian vault now? For example:<br></p>
<ol>
<li value="1"> <strong>Search:</strong> "Search my vault for all notes related to 'Django models' or 'agent architecture'."</li>
<li value="2"> <strong>Read:</strong> "Show me the contents of the note titled 'Agent Overhaul Plan'."</li><li value="3"> <strong>Create:</strong> "Create a new note titled 'Meeting Minutes - [Date]'."</li>
</ol>
<p>
</p>
</div>
<div class="msg-foot msg-foot-with-usage">
<span class="msg-duration-inline">Done in 3m 19s</span>
<span class="msg-usage-inline">89.4k in · 1.1k out</span>
<span class="msg-time" title="11.5.2026, 12:23:00">12:23</span>
<span class="msg-actions">
<button class="msg-action-btn msg-tts-btn" title="Listen" onclick="speakMessage(this)">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
</button>
<button class="msg-action-btn" title="Fork from here" onclick="forkFromMessage(36)">
<   svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg>
</button>
<button class="msg-copy-btn msg-action-btn" title="Copy" onclick="copyMsg(this)">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
</button>
<button class="msg-action-btn" title="Regenerate response" onclick="regenerateResponse(this)">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M3 2v6h6"></path><path d="M3 8a9 9 0 1 0 2.64-4.36L3 8"></path></svg>
</button>
</span>
</div>
</div>


    
    '''