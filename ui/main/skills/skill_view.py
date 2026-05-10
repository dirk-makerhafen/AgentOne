from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.main_view import MainView

class SkillView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''   
        <div class="main-view-header">
            <div class="main-view-title" id="skillDetailTitle"></div>
            <div class="main-view-actions">
                <button id="btnEditSkillDetail" class="panel-head-btn" title="Edit" data-i18n-title="skills_edit" onclick="editCurrentSkill()" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg></button>
                <button id="btnDeleteSkillDetail" class="panel-head-btn" title="Delete" data-i18n-title="skills_delete" onclick="deleteCurrentSkill()" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
                <button id="btnCancelSkillDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelSkillForm()" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                <button id="btnSaveSkillDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="saveSkillForm()" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
            </div>
        </div>
            
        <div class="main-view-body" id="skillDetailBody" >
            <div class="main-view-content skill-detail-content">
                <details class="skill-frontmatter">
                    <summary>Metadata</summary>
                    <pre>
                        <code>name: apple-notes
                            description: "Manage Apple Notes via memo CLI: create, search, edit."
                            version: 1.0.0
                            author: Hermes Agent
                            license: MIT
                            platforms: [macos]
                            metadata:
                            hermes:
                                tags: [Notes, Apple, macOS, note-taking]
                                related_skills: [obsidian]
                            prerequisites:
                            commands: [memo]
                        </code>
                    </pre>
                </details>
                <h1>Apple Notes</h1>
                <p>Use <code>memo</code> to manage Apple Notes directly from the terminal. Notes sync across all Apple devices via iCloud.</p>
                <h2>Prerequisites</h2>
                <ul><li><strong>macOS</strong> with Notes.app</li><li>Install: <code>brew tap antoniorodr/memo &amp;&amp; brew install antoniorodr/memo/memo</code></li><li>Grant Automation access to Notes.app when prompted (System Settings → Privacy → Automation)</li></ul>
                <h2>When to Use</h2>
                <ul><li>User asks to create, view, or search Apple Notes</li><li>Saving information to Notes.app for cross-device access</li><li>Organizing notes into folders</li><li>Exporting notes to Markdown/HTML</li></ul>
                <h2>When NOT to Use</h2>
                <ul><li>Obsidian vault management → use the <code>obsidian</code> skill</li><li>Bear Notes → separate app (not supported here)</li><li>Quick agent-only notes → use the <code>memory</code> tool instead</li></ul>
                <h2>Quick Reference</h2>
                <h3>View Notes</h3>
                <div class="pre-header">bash</div><pre><code class="language-bash">memo notes                        # List all notes
                memo notes -f "Folder Name"       # Filter by folder
                memo notes -s "query"             # Search notes (fuzzy)</code></pre>
                <h3>Create Notes</h3>
                <div class="pre-header">bash</div><pre><code class="language-bash">memo notes -a                     # Interactive editor
                memo notes -a "Note Title"        # Quick add with title</code></pre>
                <h3>Edit Notes</h3>
                <div class="pre-header">bash</div><pre><code class="language-bash">memo notes -e                     # Interactive selection to edit</code></pre>
                <h3>Delete Notes</h3>
                <div class="pre-header">bash</div><pre><code class="language-bash">memo notes -d                     # Interactive selection to delete</code></pre>
                <h3>Move Notes</h3>
                <div class="pre-header">bash</div><pre><code class="language-bash">memo notes -m                     # Move note to folder (interactive)</code></pre>
                <h3>Export Notes</h3>
                <div class="pre-header">bash</div><pre><code class="language-bash">memo notes -ex                    # Export to HTML/Markdown</code></pre>
                <h2>Limitations</h2>
                <ul><li>Cannot edit notes containing images or attachments</li><li>Interactive prompts require terminal access (use pty=true if needed)</li><li>macOS only — requires Apple Notes.app</li></ul>
                <h2>Rules</h2>
                <ol><li value="1">Prefer Apple Notes when user wants cross-device sync (iPhone/iPad/Mac)</li><li value="2">Use the <code>memory</code> tool for agent-internal notes that don't need to sync</li><li value="3">Use the <code>obsidian</code> skill for Markdown-native knowledge management</li></ol>
            </div>
        </div>
            
        <div class="main-view-empty" id="skillDetailEmpty">
            <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            <div class="main-view-empty-title" data-i18n="skills_empty_title">Select a skill</div>
            <div class="main-view-empty-sub" data-i18n="skills_empty_sub">Pick a skill from the sidebar to view its contents, or create a new one.</div>
        </div>
    '''

    def __init__(self, subject, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
