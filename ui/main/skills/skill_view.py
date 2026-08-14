from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

import frontmatter
import yaml
from markupsafe import Markup

from server.models.skills.skill import SkillModel
from server.models.skills.skill_version import SkillModelVersion
from ui.lib.model_view import ModelView
from ui.main.rightpanel.skill.rightpanel_skill import RightPanelSkill

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class SkillView(ModelView):
    RIGHTPANEL_VIEW = RightPanelSkill

    DOM_ELEMENT_CLASS = "main-view"

    CSS_STR = '''
        .skill-rendered-body {
            padding: 8px 12px;
            line-height: 1.6;
            font-size: 14px;
        }
        .skill-rendered-body h1 { font-size: 18px; margin: 16px 0 8px; }
        .skill-rendered-body h2 { font-size: 16px; margin: 14px 0 6px; }
        .skill-rendered-body h3 { font-size: 14px; margin: 12px 0 4px; }
        .skill-rendered-body p  { margin: 6px 0; }
        .skill-rendered-body ul, .skill-rendered-body ol { margin: 4px 0; padding-left: 20px; }
        .skill-rendered-body li { margin: 2px 0; }
        .skill-rendered-body code {
            background: var(--card-bg);
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 13px;
        }
        .skill-rendered-body pre {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 8px 12px;
            overflow-x: auto;
        }
        .skill-rendered-body pre code {
            background: none;
            padding: 0;
        }
        .skill-rendered-body strong { font-weight: 600; }
        .skill-rendered-body blockquote {
            border-left: 3px solid var(--border);
            padding-left: 12px;
            margin: 8px 0;
            color: var(--muted);
        }
        .skill-frontmatter summary {
            cursor: pointer;
            padding: 8px 12px;
            font-weight: 500;
            color: var(--muted);
        }
        .skill-frontmatter pre {
            margin: 0 12px 8px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 8px;
            overflow-x: auto;
            font-size: 12px;
        }
    '''

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">{{ pyview.subject.name }}</div>
            <div class="main-view-actions">
                {% if not pyview._editing %}
                <button class="panel-head-btn" title="Edit skill" onclick="pyview.startEdit()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="panel-head-btn" title="Delete skill" onclick="pyview.deleteSkill()" style="color:var(--danger)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
                {% endif %}
                <button class="panel-head-btn" title="Refresh" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">

                <div class="detail-card">
                    <div class="detail-card-title">Skill</div>
                    {% if pyview._editing %}
                    <div class="detail-form-row">
                        <label>Name</label>
                        <input type="text" value="{{ pyview._edit_data.name }}" onchange="pyview.setEditField('name', this.value)">
                    </div>
                    <div style="display:flex;gap:8px;margin-top:12px">
                        <button class="panel-head-btn primary" onclick="pyview.saveEdit()" style="padding:4px 16px">Save</button>
                        <button class="panel-head-btn" onclick="pyview.cancelEdit()" style="padding:4px 16px">Cancel</button>
                    </div>
                    {% else %}
                    <div class="detail-row">
                        <div class="detail-row-label">Name</div>
                        <div class="detail-row-value"><code>{{ pyview.subject.name }}</code></div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Version</div>
                        <div class="detail-row-value">{{ pyview.version_number }}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Path</div>
                        <div class="detail-row-value"><code>{{ pyview.path }}</code></div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Description</div>
                        <div class="detail-row-value">{{ pyview.description }}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Created</div>
                        <div class="detail-row-value">{{ pyview.created_at }}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Commit</div>
                        <div class="detail-row-value"><code>{{ pyview.commit }}</code></div>
                    </div>
                    {% endif %}
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Manifest</div>
                    <details class="skill-frontmatter">
                        <summary>Metadata</summary>
                        <pre><code>{{ pyview.frontmatter_yaml }}</code></pre>
                    </details>
                    <div class="skill-rendered-body" id="skill_body_{{ pyview.uid }}">
                        {{ pyview.body_html }}
                    </div>
                    <script>
                        (function(){var el=document.getElementById('skill_body_{{ pyview.uid }}');if(el)el.innerHTML=marked.parse(el.textContent);})();
                    </script>
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Versions</div>
                    {% if pyview.all_versions %}
                        {% for v in pyview.all_versions %}
                        <div class="detail-row" style="border-bottom:1px solid var(--border)">
                            <div class="detail-row-label">v{{ v.version_number }}</div>
                            <div class="detail-row-value" style="font-size:12px">
                                {{ v.created_at }} &mdash; <code>{{ v.commit[:20] if v.commit else '—' }}</code>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="padding:12px;color:var(--muted);text-align:center">
                            No versions yet.
                        </div>
                    {% endif %}
                </div>

            </div>
        </div>
    '''

    def __init__(self, subject: SkillModel, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._editing = False
        self._edit_data: dict[str, str] = {
            "name": subject.name,
        }

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def description(self) -> str:
        v = self.subject.latest_skill_version
        return v.description if v else ""

    @property
    def path(self) -> str:
        v = self.subject.latest_skill_version
        return v.path if v else ""

    @property
    def version_number(self) -> int:
        v = self.subject.latest_skill_version
        return v.version_number if v else 0

    @property
    def created_at(self) -> str:
        v = self.subject.latest_skill_version
        return str(v.created_at) if v else ""

    @property
    def commit(self) -> str:
        v = self.subject.latest_skill_version
        return v.commit if v else ""

    @property
    def all_versions(self) -> list[SkillModelVersion]:
        return list(self.subject.versions.all().order_by("-version_number"))

    @property
    def _parsed(self) -> str | None:
        skill_path = self.path
        if not skill_path:
            return None
        md_path = Path(skill_path)
        if not md_path.is_file():
            return None
        try:
            return md_path.read_text(encoding="utf-8")
        except Exception:
            return None

    @property
    def has_manifest(self) -> bool:
        return self._parsed is not None

    @property
    def frontmatter_yaml(self) -> str:
        raw = self._parsed
        if not raw:
            return ""
        try:
            post = frontmatter.loads(raw)
            y = yaml.dump(post.metadata, default_flow_style=False, allow_unicode=True).strip()
            return y if y != "{}" else ""
        except Exception:
            return ""

    @property
    def body_html(self) -> Markup:
        raw = self._parsed
        if not raw:
            return Markup("")
        try:
            post = frontmatter.loads(raw)
            return Markup(post.content.strip())
        except Exception:
            return Markup(raw.strip())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def startEdit(self) -> None:
        self._editing = True
        self._edit_data = {
            "name": self.subject.name,
        }
        self.update()

    def cancelEdit(self) -> None:
        self._editing = False
        self.update()

    def setEditField(self, field: str, value: str) -> None:
        self._edit_data[field] = value
        self.update()

    def saveEdit(self) -> None:
        name = self._edit_data.get("name", "").strip()
        if not name:
            return
        self.subject.name = name
        self.subject.save(update_fields=["name"])
        self._editing = False
        self.update()

    def deleteSkill(self) -> None:
        self.subject.delete()
        self._close_tab()

    def refresh(self) -> None:
        self.subject.refresh_from_db()
        self.update()

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent

    def _close_tab(self) -> None:
        parent = self._find_main_view()
        if parent and hasattr(parent, "close_tab"):
            parent.close_tab(self)
