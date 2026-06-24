from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from django.conf import settings

from server.models.providers.ai_model import AiModel
from ui.lib.model_view import ModelView
from ui.main.agent.agent_view import AgentView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


class AgentCreateView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">New agent</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Cancel" onclick="pyview.cancel()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
                <button class="panel-head-btn primary" title="Save" onclick="pyview.save()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">
                <form class="detail-form" onsubmit="event.preventDefault(); pyview.save();">

                    <div class="detail-form-row">
                        <label for="acName">Name</label>
                        <input type="text" id="acName" value="{{ pyview._form_data.name }}" placeholder="my-agent" required="" autocomplete="off" onchange="pyview.setField('name', this.value)">
                    </div>

                    <div class="detail-form-row">
                        <label for="acExtends">Extends</label>
                        <input type="text" id="acExtends" value="{{ pyview._form_data.extends }}" placeholder="baseagent" autocomplete="off" onchange="pyview.setField('extends', this.value)">
                    </div>

                    <div class="detail-form-row">
                        <label for="acModel">Model</label>
                        <select id="acModel" onchange="pyview.setField('model', this.value)">
                            <option value="">-- Default --</option>
                            {% for m in pyview.model_list %}
                            <option value="{{ m.name }}"{% if pyview._form_data.model == m.name %} selected{% endif %}>{{ m.name }}</option>
                            {% endfor %}
                        </select>
                    </div>

                    <div class="detail-form-row">
                        <label for="acReasoning">Reasoning effort</label>
                        <select id="acReasoning" onchange="pyview.setField('reasoning_effort', this.value)">
                            {% for val in ['none', 'minimal', 'low', 'medium', 'high', 'xhigh'] %}
                            <option value="{{ val }}"{% if pyview._form_data.reasoning_effort == val %} selected{% endif %}>{{ val }}</option>
                            {% endfor %}
                        </select>
                    </div>

                    <div class="detail-form-row">
                        <label for="acMaxTurns">Max turns</label>
                        <input type="number" id="acMaxTurns" value="{{ pyview._form_data.max_turns }}" min="0" onchange="pyview.setField('max_turns', this.value)">
                    </div>

                    <div class="detail-form-row">
                        <label for="acMaxUnattended">Max unattended turns</label>
                        <input type="number" id="acMaxUnattended" value="{{ pyview._form_data.max_unattended_turns }}" min="0" onchange="pyview.setField('max_unattended_turns', this.value)">
                    </div>

                    <div class="detail-form-row">
                        <label for="acDescription">Description / system prompt</label>
                        <textarea id="acDescription" rows="8" placeholder="Optional description and system prompt" onchange="pyview.setField('description', this.value)">{{ pyview._form_data.description }}</textarea>
                    </div>

                    <div id="acError" class="detail-form-error" style="display:{% if pyview._form_error %}block{% else %}none{% endif %}">
                        {{ pyview._form_error }}
                    </div>

                </form>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: Any, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._form_data: dict[str, str] = {
            "name": "",
            "extends": "baseagent",
            "model": "",
            "reasoning_effort": "medium",
            "max_turns": "2",
            "max_unattended_turns": "0",
            "description": "",
        }
        self._form_error: str = ""

    @property
    def model_list(self) -> list[AiModel]:
        return list(AiModel.objects.all().order_by("name"))

    def setField(self, field: str, value: str) -> None:
        self._form_data[field] = value
        self.update()

    def save(self) -> None:
        fd = self._form_data
        name = fd.get("name", "").strip()
        if not name:
            self._form_error = "Name is required."
            self.update()
            return

        agents_dir = Path(settings.BASE_DIR) / ".agentone" / "agents" / name
        agent_md_path = agents_dir / "agent.md"

        if agent_md_path.exists():
            self._form_error = f"Agent '{name}' already exists."
            self.update()
            return

        frontmatter: dict[str, Any] = {"name": name}
        extends = fd.get("extends", "").strip()
        if extends:
            frontmatter["extends"] = extends
        model = fd.get("model", "").strip()
        if model:
            frontmatter["model"] = model
        reffort = fd.get("reasoning_effort", "").strip()
        if reffort:
            frontmatter["reasoningEffort"] = reffort
        try:
            mt = int(fd.get("max_turns", "0"))
            if mt > 0:
                frontmatter["maxTurns"] = mt
        except (ValueError, TypeError):
            pass
        try:
            mut = int(fd.get("max_unattended_turns", "0"))
            if mut > 0:
                frontmatter["maxUnattendedTurns"] = mut
        except (ValueError, TypeError):
            pass

        body = fd.get("description", "").strip()

        try:
            agents_dir.mkdir(parents=True, exist_ok=True)
            lines = ["---", yaml.dump(frontmatter, default_flow_style=False).strip(), "---"]
            if body:
                lines.append("")
                lines.append(body)
            agent_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            self._form_error = f"Failed to write agent file: {e}"
            self.update()
            return

        try:
            from django.core.management import call_command
            call_command("reload_all", settings.BASE_DIR)
        except Exception as e:
            self._form_error = f"Agent file created but sync failed: {e}"
            self.update()
            return

        self._form_error = ""
        parent = self._find_main_view()
        if parent:
            from server.models.agents.agent import AgentModel
            agent_model = AgentModel.objects.filter(name=name).first()
            if agent_model:
                parent.create_and_open_tab(AgentView, agent_model)
        self.close_tab()

    def cancel(self) -> None:
        self.close_tab()

    def _find_main_view(self):
        from ui.main.main_view import MainView
        p = self.parent
        while p and not isinstance(p, MainView):
            p = p.parent
        return p

    def close_tab(self) -> None:
        parent = self._find_main_view()
        if parent:
            parent.close_tab(self)
