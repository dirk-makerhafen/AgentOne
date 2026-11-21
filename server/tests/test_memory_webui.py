"""Tests for the compact memory webui (data helpers + rendered pages)."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

import pytest
from django.urls import reverse

import runtime.memory_improvements as improvements_module
from webui.features.memory import data as memory_data
from webui.features.memory import views as memory_views
from webui.features.memory.data import MemoryScopeRef, build_inventory, effective_directives


@pytest.fixture(autouse=True)
def _disable_webui_login(settings):
    settings.WEBUI_LOGIN_REQUIRED = False


REFLECTION = """---
schema: agentone.playbook/1
directives:
  - id: PB-1
    fingerprint: offer-tea
    rule: "Offer tea to guests."
    trigger: "a guest arrives"
    routing: prompt
    status: active
    support: 2
  - id: PB-2
    fingerprint: opt-in-rule
    rule: "Optional behaviour."
    routing: skill
    status: candidate
---
"""

IMPROVEMENTS = """---
schema: agentone.improvements/1
proposals:
  - id: IMP-1
    fingerprint: add-tea-skill
    kind: skill
    status: candidate
    summary: "Add a tea-making skill"
---
"""

SOURCES = """---
generated_at: "2026-01-01T00:00:00Z"
sources:
  - path: chat.md
    type: session
    last_processed_hash: "aaaa"
    current_hash: "bbbb"
    changed_chars: 42
---
"""


def _write_node(root, reflection=REFLECTION, improvements=IMPROVEMENTS):
    root.mkdir(parents=True, exist_ok=True)
    (root / "memory.md").write_text("# Facts\nThe agent likes tea.", encoding="utf-8")
    if reflection is not None:
        (root / "reflection.md").write_text(reflection, encoding="utf-8")
    if improvements is not None:
        (root / "improvements.md").write_text(improvements, encoding="utf-8")
    (root / ".memory_sources.md").write_text(SOURCES, encoding="utf-8")


@pytest.fixture
def memory_tree(tmp_path, monkeypatch):
    """A global memory tree with one stale node, served to every memory view."""
    root = tmp_path / "memory"
    _write_node(root)

    def _inventory(project_id=None):
        del project_id  # views and the sidebar pass a project filter we ignore here
        return build_inventory(
            refs=[MemoryScopeRef("global", "global", "Global", root)]
        )

    monkeypatch.setattr(memory_data, "build_inventory", _inventory)
    monkeypatch.setattr(memory_views, "build_inventory", _inventory)
    monkeypatch.setattr(memory_views, "queued_work_items", lambda: {}, raising=False)
    monkeypatch.setattr(improvements_module, "queued_work_items", lambda: {})
    return _inventory()


def test_effective_directives_dedupes_and_keeps_most_specific(tmp_path):
    global_root = tmp_path / "global"
    agent_root = global_root / "agents" / "agent_7"
    _write_node(global_root)
    _write_node(agent_root, reflection=REFLECTION.replace("PB-1", "PB-1-AGENT"), improvements=None)
    inventory = build_inventory(
        refs=[MemoryScopeRef("global", "global", "Global", global_root)]
    )
    inventory.nodes[0].agent_pk = 7

    rows = effective_directives(inventory.nodes, "active")
    assert len(rows) == 1
    assert rows[0]["source"] == "Global"
    assert rows[0]["layer"] == "Agent"
    assert rows[0]["fingerprint"] == "offer-tea"
    assert rows[0]["rule"] == "Offer tea to guests."


def test_injectable_only_excludes_harness_and_memory_routing(tmp_path):
    root = tmp_path / "memory"
    _write_node(
        root,
        reflection="""---
schema: agentone.playbook/1
directives:
  - id: PB-H
    fingerprint: harness-bug
    rule: "Work around a harness bug."
    routing: harness
    status: active
    support: 1
  - id: PB-F
    fingerprint: known-fact
    rule: "Remember this fact."
    routing: memory
    status: active
    support: 1
  - id: PB-P
    fingerprint: real-rule
    rule: "Do the useful thing."
    routing: prompt
    status: active
    support: 1
---
""",
        improvements=None,
    )
    inventory = build_inventory(
        refs=[MemoryScopeRef("global", "global", "Global", root)]
    )
    rows = effective_directives(inventory.nodes, "active", injectable_only=True)
    assert [row["fingerprint"] for row in rows] == ["real-rule"]
    assert len(effective_directives(inventory.nodes, "active")) == 3


@pytest.mark.django_db
def test_sidebar_has_only_section_links(client, memory_tree):
    assert memory_tree.nodes
    response = client.get(reverse("webui:memory"))
    html = response.content.decode()
    sidebar = html.split('id="sidebar"', 1)[1].split("</aside>", 1)[0]
    assert sidebar.count('data-sidebar-active-key=') == 3
    assert "Scope root" not in sidebar
    assert "memory/node/" not in sidebar


@pytest.mark.django_db
def test_overview_filters_nodes_and_uses_compact_table(client, memory_tree):
    attention = client.get(reverse("webui:memory"), {"filter": "attention"})
    assert attention.status_code == 200
    assert b"mem-node-table" in attention.content
    assert b"Scope root" in attention.content
    assert b"The agent likes tea." not in attention.content  # no long excerpts

    empty = client.get(reverse("webui:memory"), {"filter": "proposals"})
    # The node does have a proposal, so it is still present.
    assert b"Scope root" in empty.content

    invalid = client.get(reverse("webui:memory"), {"filter": "bogus"})
    assert b'class="webui-tab active"' in invalid.content
    assert b">Needs attention (" in invalid.content


@pytest.mark.django_db
def test_playbook_shows_active_rules_and_candidates(client, memory_tree):
    response = client.get(reverse("webui:memory_playbook"))
    html = response.content.decode()
    assert response.status_code == 200
    assert "Offer tea to guests." in html
    assert "Optional behaviour." in html
    assert "Active directives" in html

    filtered = client.get(reverse("webui:memory_playbook"), {"search": "no-such-rule"})
    assert b"No active rules match this filter." in filtered.content


@pytest.mark.django_db
def test_node_detail_renders_only_the_selected_tab(client, memory_tree):
    node = memory_tree.nodes[0]
    url = reverse("webui:memory_node", args=[node.id])

    overview = client.get(url, {"tab": "overview"})
    assert b"Node overview" in overview.content
    assert b"Facts chars" in overview.content
    assert b"reflection.md</summary>" not in overview.content

    facts = client.get(url, {"tab": "facts"})
    assert b"The agent likes tea." in facts.content
    assert b"Node overview" not in facts.content

    rules = client.get(url, {"tab": "rules"})
    assert b"Playbook" in rules.content
    assert b"Offer tea to guests." in rules.content

    proposals = client.get(url, {"tab": "proposals"})
    assert b"Improvement proposals" in proposals.content
    assert b"Add a tea-making skill" in proposals.content

    sources = client.get(url, {"tab": "sources"})
    assert b"Stale sources" not in sources.content  # that tile is overview-only
    assert b"raw files" in sources.content.lower()


@pytest.mark.django_db
def test_memory_agent_is_the_memory_page_assistant(monkeypatch):
    """The memory rightbar is scoped to memory-manage, not AgentOne."""
    from server.models.project import Project
    from webui.core import assistants

    assert assistants._OVERVIEW_ASSISTANTS["memory"][0] == "memory-manage"

    project = Project.objects.create(name="Memory agent project")
    monkeypatch.setattr(assistants, "_sessions_for_scope", lambda *_args: [])
    context = assistants.assistant_overview_context("memory", project)
    assert context["assistant_title"] == "Memory agent"
    assert context["assistant_noun"] == "memory agent"
    assert context["assistant_item"]["name"] == "Memory · Memory agent project"
    assert context["assistant_open_url"] == reverse(
        "webui:assistant_overview_open", args=["memory"]
    )


@pytest.mark.django_db
def test_memory_pages_render_memory_agent_rightbar(client, memory_tree, monkeypatch):
    """All four Memory views dock the memory agent beside the content column."""
    from bs4 import BeautifulSoup
    from webui.core import assistants

    monkeypatch.setattr(
        assistants,
        "_overview_scope",
        lambda kind, project: ("memory-manage", project, None),
    )
    monkeypatch.setattr(assistants, "_sessions_for_scope", lambda *_args: [])

    urls = [
        reverse("webui:memory"),
        reverse("webui:memory_playbook"),
        reverse("webui:memory_improvements"),
        reverse("webui:memory_node", args=[memory_tree.nodes[0].id]),
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url
        soup = BeautifulSoup(response.content, "html.parser")
        panel = soup.find(id="entity-assistant-panel")
        assert panel is not None, url
        layout = panel.parent
        assert layout is not None and "webui-entity-layout" in (
            layout.get("class") or []
        ), url
        content_column = layout.find(class_="webui-entity-content")
        assert content_column is not None, url
        assert panel not in content_column.descendants, url
        assert "Memory agent" in panel.get_text(), url


@pytest.mark.django_db
def test_memory_assistant_open_creates_memory_manage_chat(client, monkeypatch):
    """The panel's New chat button starts a memory-manage session in place."""
    from server.models.agents.agent import AgentModel
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.sessions.session import SessionModel
    from webui.core import assistants

    assistant = AgentModel.objects.create(name="memory-manage")
    version = AgentVersionModel.objects.create(agent=assistant, version_number=1)
    AgentModel.objects.filter(pk=assistant.pk).update(latest_agent_version=version)
    monkeypatch.setattr(
        assistants,
        "_overview_scope",
        lambda kind, project: ("memory-manage", project, None),
    )

    panel = client.get(reverse("webui:assistant_overview_panel", args=["memory"]))
    assert panel.status_code == 200
    assert b'id="entity-assistant-panel"' in panel.content

    opened = client.post(reverse("webui:assistant_overview_open", args=["memory"]))
    assert opened.status_code == 200
    assert b'id="entity-assistant-panel"' in opened.content
    assert SessionModel.objects.filter(
        latest_session_version__agent=assistant,
        name__startswith="memory-manage -",
    ).exists()
