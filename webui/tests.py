"""Tests for the htmx UI app (pure helpers + routing + render smoke).

The chat render path is exercised end-to-end by the views; these tests pin the
pieces that are easy to break silently: markdown sanitisation, the SSE trigger
string, the URL contract, the sidebar wiring, and the log tail helper.
"""

from __future__ import annotations

import pytest
from django.test import override_settings
from django.urls import reverse

from webui.core.markdown import render_markdown
from webui.templatetags.webui import get_item, static_v
from webui.core.layout import NAV_SECTIONS, SIDEBAR_TEMPLATES
from webui.features.logs.views import _resolve, log_files, tail


@pytest.fixture(autouse=True)
def _disable_webui_login(settings):
    """Most tests exercise fragments directly; auth has dedicated tests."""
    settings.WEBUI_LOGIN_REQUIRED = False


def _assert_panel_is_rightbar(content: bytes, route: str) -> None:
    """The embedded assistant must be a sibling of the content column.

    Regression guard: the panel was once nested inside ``.webui-entity-content``,
    which pushed it below the page content instead of docking it on the right.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "html.parser")
    panel = soup.find(id="entity-assistant-panel")
    assert panel is not None, route
    layout = panel.parent
    assert layout is not None and "webui-entity-layout" in (layout.get("class") or []), (
        f"{route}: assistant panel parent is {layout.get('class') if layout else None}"
    )
    content_column = layout.find(class_="webui-entity-content")
    assert content_column is not None, route
    assert panel not in content_column.descendants, route


def test_markdown_renders_fenced_code_with_language():
    html = render_markdown("```python\nprint('hi')\n```")
    assert 'class="language-python"' in html


def test_markdown_opens_external_links_in_new_tab():
    html = render_markdown("[site](https://example.com)")
    assert 'target="_blank"' in html
    assert 'href="https://example.com"' in html


def test_markdown_keeps_boost_only_for_in_app_links():
    """hx-boost partial navigation must not swallow downloads or assets."""
    in_app = render_markdown("[chat](/app/chat/7)")
    assert 'hx-boost="false"' not in in_app

    asset = render_markdown("[file](/media/report.pdf)")
    assert 'href="/media/report.pdf"' in asset
    assert 'hx-boost="false"' in asset

    external = render_markdown("[site](https://example.com)")
    assert 'target="_blank"' in external
    assert 'hx-boost="false"' not in external


def test_markdown_strips_scripts_and_event_handlers():
    html = render_markdown('<script>alert(1)</script><img src=x onerror=alert(1)>')
    assert "<script" not in html
    assert "onerror" not in html


def test_markdown_is_cached_and_stable():
    text = "**bold** and `code`"
    assert render_markdown(text) == render_markdown(text)


def test_url_names_reverse():
    assert reverse("webui:dashboard") == "/app/"
    assert reverse("webui:chats") == "/app/chats"
    assert reverse("webui:chats_sidebar") == "/app/chats/sidebar"
    assert reverse("webui:sse") == "/app/sse/"
    assert reverse("webui:new_chat") == "/app/chat/new"
    assert reverse("webui:chat", args=[12]) == "/app/chat/12"
    assert reverse("webui:thread", args=[12]) == "/app/chat/12/thread"
    assert reverse("webui:send", args=[12]) == "/app/chat/12/send"
    assert reverse("webui:chat_header", args=[12]) == "/app/chat/12/header"
    assert reverse("webui:chat_toc", args=[12]) == "/app/chat/12/toc"
    assert reverse("webui:chat_action", args=[12]) == "/app/chat/12/action"
    assert reverse("webui:chat_todo_action", args=[12]) == "/app/chat/12/todos"
    assert reverse("webui:call_cancel", args=[12, 34]) == "/app/chat/12/calls/34/cancel"
    assert (
        reverse("webui:edit_message", args=[12, 34])
        == "/app/chat/12/message/34/edit"
    )
    assert reverse("webui:clear_conversation", args=[12]) == "/app/chat/12/clear"
    assert reverse("webui:import_conversation", args=[12]) == "/app/chat/12/import"
    assert reverse("webui:chat_panel", args=[12]) == "/app/chat/12/panel"
    assert reverse("webui:chat_panel_tab", args=[12, "tasks"]) == "/app/chat/12/panel/tasks"
    assert (
        reverse("webui:chat_panel_body", args=[12, "tasks"])
        == "/app/chat/12/panel/tasks/body"
    )
    assert reverse("webui:chat_setting", args=[12]) == "/app/chat/12/setting"
    assert reverse("webui:subagent_open", args=[12]) == "/app/chat/12/subagent"
    assert reverse("webui:query_detail", args=[34]) == "/app/query/34/detail"
    assert reverse("webui:entity_assistant_open", args=["agent", 5]) == "/app/assistant/agent/5"
    assert reverse("webui:assistant_panel", args=["agent", 5]) == "/app/assistant/agent/5/panel"
    assert reverse("webui:assistant_overview_panel", args=["agents"]) == "/app/assistant/overview/agents/panel"
    assert reverse("webui:assistant_overview_open", args=["agents"]) == "/app/assistant/overview/agents/open"
    assert reverse("webui:agents") == "/app/agents"
    assert reverse("webui:agent_create") == "/app/agents/new"
    assert reverse("webui:agent_edit", args=[5]) == "/app/agents/5/edit"
    assert reverse("webui:agent_delete", args=[5]) == "/app/agents/5/delete"
    assert reverse("webui:agent", args=[5]) == "/app/agents/5"
    assert reverse("webui:projects") == "/app/projects"
    assert reverse("webui:project_create") == "/app/projects/new"
    assert reverse("webui:project_edit", args=[5]) == "/app/projects/5/edit"
    assert reverse("webui:project", args=[5]) == "/app/projects/5"
    assert reverse("webui:workspaces") == "/app/workspaces"
    assert reverse("webui:workspace_create") == "/app/workspaces/new"
    assert reverse("webui:workspace_edit", args=[5]) == "/app/workspaces/5/edit"
    assert reverse("webui:workspace_delete", args=[5]) == "/app/workspaces/5/delete"
    assert reverse("webui:workspace_manager_open", args=[5]) == "/app/workspaces/5/manager"
    assert reverse("webui:workspace", args=[5]) == "/app/workspaces/5"
    assert reverse("webui:skills") == "/app/skills"
    assert reverse("webui:skill_edit", args=[5]) == "/app/skills/5/edit"
    assert reverse("webui:skill_delete", args=[5]) == "/app/skills/5/delete"
    assert reverse("webui:skill", args=[5]) == "/app/skills/5"
    assert reverse("webui:cron") == "/app/cron"
    assert reverse("webui:cron_create") == "/app/cron/new"
    assert reverse("webui:cronjob", args=[5]) == "/app/cron/5"
    assert reverse("webui:cron_edit", args=[5]) == "/app/cron/5/edit"
    assert reverse("webui:cron_delete", args=[5]) == "/app/cron/5/delete"
    assert reverse("webui:cron_duplicate", args=[5]) == "/app/cron/5/duplicate"
    assert reverse("webui:cron_run_now", args=[5]) == "/app/cron/5/run"
    assert reverse("webui:cron_toggle", args=[5]) == "/app/cron/5/toggle"
    assert reverse("webui:cron_call_cancel", args=[5, 6]) == "/app/cron/5/calls/6/cancel"
    assert reverse("webui:collections") == "/app/collections"
    assert reverse("webui:collection_create") == "/app/collections/new"
    assert reverse("webui:collection", args=[5]) == "/app/collections/5"
    assert reverse("webui:collection_edit", args=[5]) == "/app/collections/5/edit"
    assert reverse("webui:collection_delete", args=[5]) == "/app/collections/5/delete"
    assert reverse("webui:collection_reprocess", args=[5]) == "/app/collections/5/reprocess"
    assert reverse("webui:collection_toggle", args=[5]) == "/app/collections/5/toggle"
    assert reverse("webui:workitems") == "/app/workitems"
    assert reverse("webui:workitems_board") == "/app/workitems/board"
    assert reverse("webui:workitem_create") == "/app/workitems/new"
    assert reverse("webui:workitem", args=[5]) == "/app/workitems/5"
    assert reverse("webui:workitem_action", args=[5]) == "/app/workitems/5/action"
    assert reverse("webui:workitem_update", args=[5]) == "/app/workitems/5/update"
    assert reverse("webui:workitem_delete", args=[5]) == "/app/workitems/5/delete"
    assert reverse("webui:insights") == "/app/insights"
    assert reverse("webui:insights_tab", args=["analytics"]) == "/app/insights/analytics"
    assert reverse("webui:model_probe", args=[9]) == "/app/insights/models/9/probe"
    assert reverse("webui:model_probe_status", args=[9]) == "/app/insights/models/9/probe/status"
    assert reverse("webui:model_detail", args=[9]) == "/app/insights/models/9/detail"
    assert reverse("webui:provider_detail", args=[9]) == "/app/insights/providers/9/detail"
    assert reverse("webui:logs") == "/app/logs"
    assert reverse("webui:logs_tail") == "/app/logs/tail"
    assert reverse("webui:settings") == "/app/settings"
    assert reverse("webui:settings_tab", args=["system"]) == "/app/settings/system"
    assert reverse("webui:settings_save", args=["system"]) == "/app/settings/system/save"
    assert reverse("webui:settings_provider_key", args=[7]) == "/app/settings/providers/7/key"
    assert reverse("webui:settings_provider_test", args=[7]) == "/app/settings/providers/7/test"
    assert reverse("webui:settings_provider_probe", args=[7]) == "/app/settings/providers/7/probe"


def test_static_v_appends_mtime_cache_buster():
    assert "?v=" in static_v("webui/app.js")


def test_assets_referenced_by_the_base_layout_exist():
    """The webui shell depends on the legacy design-token stylesheet.

    It used to live in the deleted ``ui`` app and survived only in a stale
    ``_staticfiles`` build, so a clean ``collectstatic`` silently dropped it.
    """
    from django.contrib.staticfiles import finders

    for path in ("css/main.css", "webui/app.css", "webui/app.js"):
        assert finders.find(path), path


def test_get_item_filter_looks_up_dict_keys():
    assert get_item({"ready": 3}, "ready") == 3
    assert get_item({"ready": 3}, "missing") is None
    assert get_item(None, "ready") is None


def test_collapsed_tool_card_reports_active_subcalls():
    """The collapsed summary chip must reflect a live sub-call tree.

    ``_tool_entry`` used to hardcode zero counts "for lazy loading", but the
    detail pane is only fetched on expand, so the chips never rendered.  Ended
    calls stay cheap (no tree walk); running ones carry the counts.
    """
    from webui.features.chats.parts.thread import _tool_entry

    class _Call:
        pk = 7
        status = "ACTIVE"
        status_detail = "ACTIVE_RUNNING"
        task_definition = None
        task_definition_version = None
        created_at = None
        ended_at = None
        updated_at = None

        def count_subcalls(self, **_kwargs):
            return {"active": 2, "finished": 1, "executing": [(8, 1)], "truncated": False}

    class _Part:
        tool_call = _Call()
        content_id = None

    entry = _tool_entry(_Part())
    assert entry["subcalls"] == {
        "active": 2,
        "finished": 1,
        "executing": 1,
        "waiting": 1,
        "truncated": False,
    }


def test_every_nav_section_has_a_sidebar_component():
    from webui.core.components import get_spec

    for key, _label in NAV_SECTIONS:
        assert key in SIDEBAR_TEMPLATES, key
        spec = get_spec(f"{key}-sidebar")
        assert spec.template == "layout/_sidebar_frame.html"
        assert reverse(f"webui:{key}_sidebar").startswith("/app/")


def test_component_registry_covers_chat_and_sidebars():
    from webui.core.components import _REGISTRY

    for name in (
        "chat-header",
        "chat-thread",
        "chat-message",
        "chat-query",
        "chat-response",
        "chat-toc",
        "chat-composer",
        "chat-panel",
    ):
        assert name in _REGISTRY, name


def test_log_tail_reads_the_last_lines(tmp_path):
    path = tmp_path / "test.log"
    path.write_text("\n".join(f"line {i}" for i in range(1, 21)))
    with override_settings(LOG_DIR=str(tmp_path)):
        assert log_files() == ["test.log"]
        content = tail(path, lines=3)
        assert content.splitlines() == ["line 18", "line 19", "line 20"]
        assert _resolve("test.log") == path.resolve()


def test_log_resolve_rejects_path_traversal(tmp_path):
    (tmp_path / "inside.log").write_text("ok")
    (tmp_path.parent / "outside.log").write_text("no")
    with override_settings(LOG_DIR=str(tmp_path)):
        with pytest.raises(Exception):
            _resolve("../outside.log")


@pytest.mark.django_db
def test_layout_pages_render(client):
    """Every full page renders against an empty database."""
    for route in _layout_routes() + [reverse("webui:workitems_board")]:
        response = client.get(route)
        assert response.status_code == 200, route


def _layout_routes() -> list[str]:
    return [
        reverse("webui:dashboard"),
        reverse("webui:chats"),
        reverse("webui:agents"),
        reverse("webui:projects"),
        reverse("webui:workspaces"),
        reverse("webui:skills"),
        reverse("webui:cron"),
        reverse("webui:collections"),
        reverse("webui:workitems"),
        reverse("webui:memory"),
        reverse("webui:memory_playbook"),
        reverse("webui:memory_improvements"),
        reverse("webui:insights"),
        reverse("webui:insights_tab", args=["analytics"]),
        reverse("webui:insights_tab", args=["providers"]),
        reverse("webui:insights_tab", args=["models"]),
        reverse("webui:logs"),
        reverse("webui:settings"),
        reverse("webui:settings_tab", args=["preferences"]),
        reverse("webui:settings_tab", args=["system"]),
    ]


@pytest.mark.django_db
def test_boosted_layout_routes_render_fragments(client):
    """Boosted page requests return a swappable shell (not a full document load)."""
    for route in _layout_routes():
        response = client.get(route, HTTP_HX_REQUEST="true")
        assert response.status_code == 200, route
        content = response.content
        assert b"<!DOCTYPE" not in content, route
        assert b"<html" in content, route
        assert b"<head>" in content, route
        assert b"<title>" in content, route
        assert b"<body>" in content, route
        assert b'id="sidebar"' in content, route
        # Full base shell assets/SSE wiring must not be re-sent on boosted nav.
        assert b'hx-ext="sse"' not in content, route


@pytest.mark.django_db
def test_full_page_load_keeps_document_shell(client):
    response = client.get(reverse("webui:dashboard"))
    assert b"<!DOCTYPE html>" in response.content
    assert b'<body hx-boost="true"' in response.content
    assert b'hx-ext="sse"' in response.content
    assert "HX-Request" in response["Vary"]


@pytest.mark.django_db
def test_pages_are_gzipped_when_the_client_accepts_it(client):
    """Chat pages are hundreds of kilobytes; gzip is the cheapest speed-up."""
    import gzip

    plain = client.get(reverse("webui:dashboard"))
    assert "Content-Encoding" not in plain.headers

    packed = client.get(reverse("webui:dashboard"), HTTP_ACCEPT_ENCODING="gzip, deflate")
    assert packed["Content-Encoding"] == "gzip"
    assert "Accept-Encoding" in packed["Vary"]
    assert int(packed["Content-Length"]) == len(packed.content)
    html = gzip.decompress(packed.content)
    # The CSRF token rotates per request, so compare shape, not the bytes.
    assert len(html) == len(plain.content)
    assert b"<!DOCTYPE html>" in html
    assert b'id="sidebar"' in html


@pytest.mark.django_db
def test_boosted_navigation_returns_body_fragment(client):
    """hx-boost swaps ``<body>`` innerHTML; boosted responses provide a shell.

    Normal clicks must not re-download or re-execute the whole document, but
    the payload still has to carry the shell (rail + sidebar) and a ``<title>``
    (and ``<head>`` for page-specific assets) for htmx to apply.
    """
    response = client.get(
        reverse("webui:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_BOOSTED="true",
    )
    assert response.status_code == 200
    assert "HX-Request" in response["Vary"]
    content = response.content
    assert b"<!DOCTYPE" not in content
    assert b"<html" in content
    assert b"<head><title>" in content
    assert b"<body>" in content
    assert b"Dashboard" in content
    assert b'id="sidebar"' in content
    # Persistent body/SSE wiring lives on the existing document body element.
    assert b'hx-boost="true"' not in content
    assert b'hx-ext="sse"' not in content
    assert b"htmx.min.js" not in content
    assert b"app.css" not in content
    # htmx pushes from this header instead of the clicked element's internal
    # state, which an SSE/component swap can clear mid-flight.
    assert response["HX-Push-Url"] == "/app/"


@pytest.mark.django_db
def test_boosted_navigation_pushes_full_request_path(client):
    response = client.get(
        reverse("webui:dashboard") + "?panel=subagents",
        HTTP_HX_REQUEST="true",
        HTTP_HX_BOOSTED="true",
    )
    assert response.status_code == 200
    assert response["HX-Push-Url"] == "/app/?panel=subagents"


@pytest.mark.django_db
def test_fragment_endpoints_are_unaffected_by_boost(client):
    """Explicit fragment URLs keep returning fragments for boosted requests."""
    response = client.get(reverse("webui:chats_sidebar"), HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert b"<!DOCTYPE" not in response.content
    assert b'id="sidebar"' in response.content

    board = client.get(reverse("webui:workitems_board"), HTTP_HX_REQUEST="true")
    assert board.status_code == 200
    assert b"<!DOCTYPE" not in board.content
    assert b'id="workitems-board"' in board.content


@pytest.mark.django_db
@override_settings(WEBUI_LOGIN_REQUIRED=True)
def test_htmx_navigation_to_login_uses_hx_redirect(client):
    """A 302 would be followed by XHR and swapped into <body>; use HX-Redirect."""
    response = client.get(reverse("webui:dashboard"), HTTP_HX_REQUEST="true")
    assert response.status_code == 204
    assert response["HX-Redirect"].startswith("/accounts/login/")


@pytest.mark.django_db
@override_settings(WEBUI_LOGIN_REQUIRED=True)
def test_login_page_renders(client):
    """Anonymous redirects land here, so the registration template must exist."""
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert b"Sign in" in response.content


@pytest.mark.django_db
def test_manifest_entity_detail_pages_render(client, tmp_path):
    """Detail templates resolve their edit/delete forms and access controls."""
    from server.models.agents.agent import AgentModel
    from server.models.cron import Cronjob
    from server.models.project import Project
    from server.models.skills.skill import SkillModel
    from server.models.workspace import WorkspaceModel

    project = Project.objects.create(
        name="webui-project",
        agentone_dir=str(tmp_path / "project-agentone"),
    )
    workspace = WorkspaceModel.objects.create(
        name="webui-workspace",
        path=str(tmp_path),
        parent_project=project,
        agentone_dir=str(tmp_path / "workspace-agentone"),
    )
    agent = AgentModel.objects.create(name="webui-agent", parent_project=project)
    skill = SkillModel.objects.create(name="webui-skill", parent_project=project)
    cron = Cronjob.objects.create(
        name="webui-cron", schedule="0 0 * * *", parent_project=project
    )

    routes = [
        reverse("webui:agent", args=[agent.pk]),
        reverse("webui:project", args=[project.pk]),
        reverse("webui:workspace", args=[workspace.pk]),
        reverse("webui:skill", args=[skill.pk]),
        reverse("webui:cronjob", args=[cron.pk]),
    ]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, route
        assert b'id="entity-assistant-panel"' in response.content
        _assert_panel_is_rightbar(response.content, route)


@pytest.mark.django_db
def test_sidebar_fragment_renders_for_every_section(client):
    for key, _label in NAV_SECTIONS:
        response = client.get(reverse(f"webui:{key}_sidebar"))
        assert response.status_code == 200, key
        assert b'class="sidebar"' in response.content


@pytest.mark.django_db
def test_sidebar_project_filter_scopes_and_persists(client):
    from server.models.agents.agent import AgentModel
    from server.models.cron import Cronjob
    from server.models.project import Project
    from server.models.skills.skill import SkillModel

    alpha = Project.objects.create(name="Alpha project")
    beta = Project.objects.create(name="Beta project")
    AgentModel.objects.create(name="alpha-agent", parent_project=alpha)
    AgentModel.objects.create(name="beta-agent", parent_project=beta)
    SkillModel.objects.create(name="alpha-skill", parent_project=alpha)
    SkillModel.objects.create(name="beta-skill", parent_project=beta)
    Cronjob.objects.create(name="alpha-cron", schedule="0 0 * * *", parent_project=alpha)
    Cronjob.objects.create(name="beta-cron", schedule="0 0 * * *", parent_project=beta)

    filtered = client.get(reverse("webui:agents"), {"project": alpha.pk})
    assert b'<option value="%d" selected>Alpha project</option>' % alpha.pk in filtered.content

    # The page's own agent table still lists everything; only the sidebar is
    # scoped. This also guards against page context overwriting sidebar keys.
    from bs4 import BeautifulSoup

    sidebar = BeautifulSoup(filtered.content, "html.parser").find(id="sidebar")
    assert "alpha-agent" in sidebar.get_text()
    assert "beta-agent" not in sidebar.get_text()
    assert "beta-agent" in filtered.content.decode()

    # Later sidebar requests without the query parameter keep the saved
    # selection (the legacy ProjectSelector behaved the same across tabs).
    agents_side = client.get(reverse("webui:agents_sidebar"))
    assert b"alpha-agent" in agents_side.content
    assert b"beta-agent" not in agents_side.content
    skills_side = client.get(reverse("webui:skills_sidebar"))
    assert b"alpha-skill" in skills_side.content
    assert b"beta-skill" not in skills_side.content
    cron_side = client.get(reverse("webui:cron_sidebar"))
    assert b"alpha-cron" in cron_side.content
    assert b"beta-cron" not in cron_side.content

    # Empty value clears it.
    client.get(reverse("webui:agents"), {"project": ""})
    cleared = client.get(reverse("webui:agents_sidebar"))
    assert b"alpha-agent" in cleared.content
    assert b"beta-agent" in cleared.content


@pytest.mark.django_db
def test_chat_action_htmx_header_returns_header_fragment(client):
    from server.models.sessions.session import SessionModel

    session = SessionModel.objects.create(name="hx-header")
    response = client.post(
        reverse("webui:chat_action", args=[session.pk]),
        {"action": "pin", "surface": "header"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert b'id="chat-header"' in response.content or b"webui-chat-header" in response.content


@pytest.mark.django_db
def test_chat_action_htmx_panel_returns_panel_body(client):
    from server.models.sessions.session import SessionModel
    from server.models.agents.agent import AgentModel
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.sessions.session_version import SessionVersionModel

    session = SessionModel.objects.create(name="hx-panel")
    agent = AgentModel.objects.create(name="hx-agent")
    av = AgentVersionModel.objects.create(agent=agent, version_number=1)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
    sv = SessionVersionModel.objects.create(
        session=session, agent=agent, pinned_agent_version=av, version_number=1
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=sv)
    session.refresh_from_db()

    response = client.post(
        reverse("webui:chat_action", args=[session.pk]),
        {"action": "upgrade_agent", "surface": "panel", "panel": "details"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert b'id="chat-panel-body"' in response.content
    from server.models.sessions.session import SessionModel

    session = SessionModel.objects.create(name="next-test")
    response = client.post(
        reverse("webui:chat_action", args=[session.pk]),
        {"action": "pin", "next": "/app/chats"},
    )
    assert response.status_code == 302
    assert response["Location"] == "/app/chats"

    response = client.post(
        reverse("webui:chat_action", args=[session.pk]),
        {"action": "pin", "next": "https://example.com/"},
    )
    assert response["Location"] == reverse("webui:chat", args=[session.pk])


@pytest.mark.django_db
def test_workitem_create_detail_and_fsm_action(client):
    """Create → detail → mark_ready → board shows the queued item."""
    from server.models.workitems.enums import WorkItemStatus
    from server.models.workitems.work_item import WorkItem

    response = client.post(
        reverse("webui:workitem_create"),
        {"title": "Ship the htmx UI", "body": "port the screens", "priority": "10"},
    )
    assert response.status_code == 302
    item = WorkItem.objects.get(title="Ship the htmx UI")
    assert item.status == WorkItemStatus.BACKLOG

    detail = client.get(reverse("webui:workitem", args=[item.pk]))
    assert detail.status_code == 200
    assert b"Ship the htmx UI" in detail.content
    assert b'id="entity-assistant-panel"' in detail.content
    _assert_panel_is_rightbar(detail.content, reverse("webui:workitem", args=[item.pk]))

    action = client.post(
        reverse("webui:workitem_action", args=[item.pk]),
        {"action": "mark_ready"},
    )
    assert action.status_code == 302
    item.refresh_from_db()
    assert item.status == WorkItemStatus.READY

    board = client.get(reverse("webui:workitems_board"))
    assert board.status_code == 200
    assert b"Ship the htmx UI" in board.content


@pytest.mark.django_db
def test_workitem_board_hides_terminal_items_by_default(client):
    from server.models.workitems.enums import WorkItemStatus
    from server.models.workitems.work_item import WorkItem

    WorkItem.objects.create(title="Finished work", status=WorkItemStatus.DONE)
    WorkItem.objects.create(title="Open work", status=WorkItemStatus.BACKLOG)

    default = client.get(reverse("webui:workitems_board"), HTTP_HX_REQUEST="true")
    assert b"Open work" in default.content
    assert b"Finished work" not in default.content

    with_terminal = client.get(
        reverse("webui:workitems_board"),
        {"terminal": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert b"Finished work" in with_terminal.content

    # htmx gets the bare fragment; a direct visit gets the full shell.
    fragment = client.get(
        reverse("webui:workitems_board"), HTTP_HX_REQUEST="true"
    )
    assert b"<html" not in fragment.content
    assert b'id="workitems-board"' in fragment.content


@pytest.mark.django_db
def test_archive_without_next_returns_to_chats(client):
    from server.models.sessions.session import SessionModel

    session = SessionModel.objects.create(name="archive-test")
    response = client.post(
        reverse("webui:chat_action", args=[session.pk]),
        {"action": "archive"},
    )
    assert response["Location"] == reverse("webui:chats")


# ---------------------------------------------------------------------------
# Chat status cards, paging, panel todos and provider settings
# ---------------------------------------------------------------------------

def _session_with_version(name="card-session"):
    from server.models.agents.agent import AgentModel
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.sessions.session import SessionModel
    from server.models.sessions.session_version import SessionVersionModel

    agent = AgentModel.objects.create(name=f"{name}-agent")
    agent_version = AgentVersionModel.objects.create(agent=agent, version_number=1)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=agent_version)
    session = SessionModel.objects.create(name=name)
    session_version = SessionVersionModel.objects.create(
        session=session,
        agent=agent,
        pinned_agent_version=agent_version,
        version_number=1,
    )
    SessionModel.objects.filter(pk=session.pk).update(
        latest_session_version=session_version
    )
    session.refresh_from_db()
    return session, session_version


def _task_call(session, session_version, *, detail, name="some_task", args=None):
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.task_definition import TaskDefinition

    definition = TaskDefinition.objects.create(name=name)
    return AgentTaskCall.objects.create(
        session=session,
        session_version=session_version,
        task_definition=definition,
        status=TaskCallStatus.WAITING,
        status_detail=detail,
        carguments_json=args or {},
        requires_approval=False,
        max_subtask_errors=0,
        max_subtask_error_rate=0,
        limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=0,
        max_retries=0,
        retry_delay=0,
        retry_requires_approval=False,
    )


@pytest.mark.django_db
def test_queue_card_renders_and_cancel_removes_call(client):
    from server.models.enums.task_enums import TaskCallStatusDetail
    from server.models.tasks.agent_task_call import AgentTaskCall

    session, version = _session_with_version("queue")
    call = _task_call(
        session,
        version,
        detail=TaskCallStatusDetail.WAITING_QUEUE,
        name="ingest_user_message",
        args={"message": [{"role": "user", "parts": [{"content": "queued hello"}]}]},
    )

    page = client.get(reverse("webui:chat", args=[session.pk]))
    assert page.status_code == 200
    assert b"1 queued" in page.content
    assert b"queued hello" in page.content

    from bs4 import BeautifulSoup

    card = BeautifulSoup(page.content, "html.parser").find(id="queue-card")
    assert card is not None
    cancel_form = card.select_one("form.webui-queue-row")
    # The view returns the whole card, so the cancel form replaces the card.
    assert cancel_form["hx-target"] == "#queue-card"
    assert cancel_form["hx-swap"] == "outerHTML"

    response = client.post(
        reverse("webui:queue_action", args=[session.pk]),
        {"action": "cancel", "call_id": call.pk},
    )
    assert response.status_code == 200
    assert not AgentTaskCall.objects.filter(pk=call.pk).exists()
    assert b"queued hello" not in response.content


@pytest.mark.django_db
def test_composer_footer_swap_targets_itself_not_thread(client):
    """The footer sits inside the composer form, which sets ``hx-target="#thread"``.

    ``hx-target`` is inherited, so an SSE refresh without its own target would
    replace the whole thread with the footer markup and make the chat disappear.
    """
    from server.models.sessions.session import SessionModel

    session = SessionModel.objects.create(name="footer-target")

    footer = client.get(reverse("webui:chat_composer_footer", args=[session.pk]))
    assert footer.status_code == 200
    footer_content = footer.content.decode()
    assert 'id="composer-footer"' in footer_content
    assert 'hx-target="this"' in footer_content

    page = client.get(reverse("webui:chat", args=[session.pk]))
    assert page.status_code == 200
    page_content = page.content.decode()
    assert 'class="composer-box webui-composer"' in page_content
    assert 'hx-target="#thread"' in page_content
    assert 'hx-target="this"' in page_content


@pytest.mark.django_db
def test_guardrail_approval_and_deny_call_scheduler(client):
    from unittest.mock import patch

    from server.models.enums.task_enums import TaskCallStatusDetail

    session, version = _session_with_version("approval")
    call = _task_call(
        session,
        version,
        detail=TaskCallStatusDetail.HALTED_APPROVAL,
        name="run_shell",
        args={"command": "ls", "guardrail_reason": "write access"},
    )

    page = client.get(reverse("webui:chat", args=[session.pk]))
    assert b"Commands awaiting approval" in page.content
    assert b"run_shell" in page.content

    with patch("runtime.tasks.call_scheduler.CallScheduler.approve_taskcall") as approve:
        response = client.post(
            reverse("webui:call_action", args=[call.pk]),
            {"action": "approve"},
        )
    assert response.status_code == 200
    approve.assert_called_once_with(call.pk)

    with patch("runtime.tasks.call_scheduler.CallScheduler.deny_taskcall") as deny:
        client.post(
            reverse("webui:call_action", args=[call.pk]),
            {"action": "deny", "feedback": "not now"},
        )
    deny.assert_called_once_with(call.pk, feedback="not now")


@pytest.mark.django_db
def test_question_card_answers_single_select(client):
    from unittest.mock import patch

    from server.models.enums.task_enums import TaskCallStatusDetail

    session, version = _session_with_version("question")
    call = _task_call(
        session,
        version,
        detail=TaskCallStatusDetail.HALTED_APPROVAL,
        name="ask_user",
        args={
            "questions": [
                {
                    "question": "Pick one",
                    "header": "Choice",
                    "options": [
                        {"label": "Alpha", "description": "first"},
                        {"label": "Beta", "description": "second"},
                    ],
                    "multiSelect": False,
                }
            ]
        },
    )

    page = client.get(reverse("webui:chat", args=[session.pk]))
    assert b"Questions for you" in page.content
    assert b"Pick one" in page.content

    with patch("runtime.tasks.call_scheduler.CallScheduler.answer_question_call") as answer:
        response = client.post(
            reverse("webui:call_action", args=[call.pk]),
            {"action": "answer", "qidx": "0", "option": "1"},
        )
    assert response.status_code == 200
    answer.assert_called_once_with(call.pk, {"Pick one": "Beta"})


@pytest.mark.django_db
def test_turn_approval_resets_counters_and_dispatches(client):
    from unittest.mock import MagicMock, patch

    from server.models.message import Message
    from server.models.sessions.session import SessionModel

    session, version = _session_with_version("turn-limit")
    Message.objects.create(session=session, session_version=version, role="assistant")

    runtime = MagicMock()
    runtime.needs_approval.return_value = False
    runtime.current_unattended_turn_count = 0
    runtime.max_unattended_turns = 0
    runtime.aimodel = None
    task = MagicMock()
    runtime.get_task.return_value = task

    with patch.object(SessionModel, "get_runtime", return_value=runtime):
        response = client.post(
            reverse("webui:turn_approval", args=[session.pk]),
            {"action": "approve"},
        )
    assert response.status_code == 200
    runtime.reset_turn_count.assert_called_once()
    runtime.reset_unattended_turn_count.assert_called_once()
    task.delay.assert_called_once()


@pytest.mark.django_db
def test_thread_fragment_full_page_and_load_older(client):
    from server.models.message import Message

    session, version = _session_with_version("paging")
    for index in range(3):
        Message.objects.create(
            session=session, session_version=version, role="user"
        )

    fragment = client.get(
        reverse("webui:thread", args=[session.pk]),
        {"limit": "1"},
    )
    assert b'id="thread-inner"' in fragment.content
    assert b"Load older messages" in fragment.content

    full = client.get(
        reverse("webui:thread", args=[session.pk]),
        {"limit": "2", "full": "1"},
    )
    assert b'id="thread"' in full.content
    # "Load older" button uses thread_older_limit = min(limit + DEFAULT_LIMIT, 2000)
    # where DEFAULT_LIMIT=120, so it becomes 122
    assert b'?limit=122' in full.content


@pytest.mark.django_db
def test_panel_todos_tab_renders(client):
    session, _version = _session_with_version("todos")
    response = client.get(reverse("webui:chat_panel_tab", args=[session.pk, "todos"]))
    assert response.status_code == 200
    assert b"todo_append" in response.content


@pytest.mark.django_db
def test_chat_page_panel_tabs_swap_the_whole_body(client):
    """Tab clicks must replace #chat-panel-body, not just its children.

    htmx caches an element's request URL when it processes the node. Patching
    hx-get in place therefore left SSE refreshes pointed at the tab that was
    rendered with the page, so the panel snapped back to Details.
    """
    from bs4 import BeautifulSoup

    session, _version = _session_with_version("panel-tab-swap")
    page = client.get(reverse("webui:chat", args=[session.pk]))
    soup = BeautifulSoup(page.content, "html.parser")
    tabs = soup.select("button.webui-panel-tab")
    assert tabs
    for tab in tabs:
        assert tab.get("hx-target") == "#chat-panel-body"
        assert tab.get("hx-swap") == "outerHTML"
        assert "/panel/" in tab.get("hx-get") and tab["hx-get"].endswith("/body")


@pytest.mark.django_db
def test_panel_body_carries_the_visible_tab_refresh_url(client):
    from bs4 import BeautifulSoup

    session, _version = _session_with_version("panel-body-tab")
    expected = reverse("webui:chat_panel_tab", args=[session.pk, "settings"])
    response = client.get(
        reverse("webui:chat_panel_body", args=[session.pk, "settings"])
    )
    assert response.status_code == 200
    body = BeautifulSoup(response.content, "html.parser").find(id="chat-panel-body")
    assert body is not None
    assert body.get("hx-get") == expected
    assert "AgentTaskCall.session" in (body.get("hx-trigger") or "")
    disinherit = (body.get("hx-disinherit") or "").split()
    assert {"hx-target", "hx-swap", "hx-sync"} <= set(disinherit)
    assert "hx-boost" not in disinherit
    assert b'id="settings-name"' in response.content


@pytest.mark.django_db
def test_history_filters_are_one_form_and_can_clear_resolved_view(client):
    """All history controls belong to one form so a toggle keeps every filter.

    ``resolved_view`` defaults to true server-side, so the form sends an
    explicit false (hidden input) for the unchecked case; the checkbox follows
    it because QueryDict.get() returns the last value.
    """
    from bs4 import BeautifulSoup

    session, _version = _session_with_version("history-filters")
    response = client.get(reverse("webui:chat_panel_tab", args=[session.pk, "history"]))
    assert response.status_code == 200
    soup = BeautifulSoup(response.content, "html.parser")
    form = soup.find(id="history-filters")
    assert form is not None
    assert form.get("hx-get") == reverse(
        "webui:chat_panel_tab", args=[session.pk, "history"]
    )
    assert form.get("hx-target") == "#chat-panel-body"
    assert form.get("hx-swap") == "innerHTML"
    assert form.get("hx-trigger") == "submit, change"
    # No duplicate q field and no CSRF token on a GET form.
    assert len(form.select('input[name="q"]')) == 1
    assert not form.select('input[name="csrfmiddlewaretoken"]')
    hidden = form.select_one('input[type="hidden"][name="resolved_view"]')
    assert hidden is not None and hidden["value"] == "false"
    for name in ("resolved_view", "include_hidden", "include_subsessions"):
        boxes = form.select(f'input[type="checkbox"][name="{name}"]')
        assert len(boxes) == 1
        assert not boxes[0].get("hx-include")


@pytest.mark.django_db
def test_panel_body_unknown_tab_falls_back_to_details(client):
    from bs4 import BeautifulSoup

    session, _version = _session_with_version("panel-body-fallback")
    response = client.get(
        reverse("webui:chat_panel_body", args=[session.pk, "nope"])
    )
    assert response.status_code == 200
    body = BeautifulSoup(response.content, "html.parser").find(id="chat-panel-body")
    assert body.get("hx-get") == reverse(
        "webui:chat_panel_tab", args=[session.pk, "details"]
    )


@pytest.mark.django_db
def test_missing_legacy_session_panel_tabs_render(client, tmp_path):
    from server.models.sessions.session_version import SessionVersionModel
    from server.models.workspace import WorkspaceModel

    session, _version = _session_with_version("right-panel-parity")
    workspace = WorkspaceModel.objects.create(
        name="panel-workspace",
        path=str(tmp_path),
        agentone_dir=str(tmp_path / ".agentone"),
    )
    (tmp_path / "folder").mkdir()
    (tmp_path / "example.txt").write_text("contents")

    version = session.latest_session_version
    SessionVersionModel.objects.filter(pk=version.pk).update(workspace=workspace)

    for tab in ("workspace", "settings", "capabilities", "calls"):
        response = client.get(
            reverse("webui:chat_panel_tab", args=[session.pk, tab])
        )
        assert response.status_code == 200
    workspace_panel = client.get(
        reverse("webui:chat_panel_tab", args=[session.pk, "workspace"])
    )
    assert b"example.txt" in workspace_panel.content
    assert b"folder" in workspace_panel.content

    outside = tmp_path.parent / "outside-panel-file.txt"
    outside.write_text("must not be shown")
    escaped = client.get(
        reverse("webui:chat_panel_tab", args=[session.pk, "workspace"]),
        {"path": "../outside-panel-file.txt"},
    )
    assert b"must not be shown" not in escaped.content
    assert b"Directory is unavailable." in escaped.content


@pytest.mark.django_db
def test_workspace_detail_browses_files_and_blocks_escape(client, tmp_path):
    from server.models.workspace import WorkspaceModel

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    nested = workspace_path / "folder"
    nested.mkdir()
    (nested / "example.txt").write_text("contents")
    workspace = WorkspaceModel.objects.create(
        name="workspace-files",
        path=str(workspace_path),
        agentone_dir=str(workspace_path / ".agentone"),
    )

    response = client.get(reverse("webui:workspace", args=[workspace.pk]))
    assert response.status_code == 200
    assert b'class="webui-entity-layout"' in response.content
    assert b'class="webui-entity-assistant rightbar" id="entity-assistant-panel"' in response.content
    assert b"example.txt" not in response.content
    assert b"folder/" in response.content

    nested_response = client.get(
        reverse("webui:workspace", args=[workspace.pk]),
        {"files": "folder"},
    )
    assert nested_response.status_code == 200
    assert b"example.txt" in nested_response.content

    outside = tmp_path / "outside.txt"
    outside.write_text("must not be shown")
    escaped = client.get(
        reverse("webui:workspace", args=[workspace.pk]),
        {"files": "../outside.txt"},
    )
    assert b"must not be shown" not in escaped.content
    assert b"Directory is unavailable." in escaped.content


@pytest.mark.django_db
def test_workspace_folder_tree_is_shared_by_chat_panel_and_detail(client, tmp_path):
    """Both surfaces render one tree partial; folders lazy-load their children."""
    from bs4 import BeautifulSoup
    from server.models.sessions.session_version import SessionVersionModel
    from server.models.workspace import WorkspaceModel

    session, _version = _session_with_version("shared-folder-tree")
    workspace_path = tmp_path / "tree-workspace"
    (workspace_path / "folder" / "nested").mkdir(parents=True)
    (workspace_path / "folder" / "example.txt").write_text("contents")
    workspace = WorkspaceModel.objects.create(
        name="tree-workspace",
        path=str(workspace_path),
        agentone_dir=str(workspace_path / ".agentone"),
    )
    SessionVersionModel.objects.filter(pk=session.latest_session_version.pk).update(
        workspace=workspace
    )

    panel = BeautifulSoup(
        client.get(reverse("webui:chat_panel_tab", args=[session.pk, "workspace"])).content,
        "html.parser",
    )
    detail = BeautifulSoup(
        client.get(reverse("webui:workspace", args=[workspace.pk])).content,
        "html.parser",
    )
    expected_target = {"panel": "#chat-panel-body", "page": "#workspace-directory"}
    for soup, surface in ((panel, "panel"), (detail, "page")):
        browser = soup.select_one(".dt-browser")
        assert browser is not None
        crumb = browser.select_one(".dt-crumbs .dt-crumb")
        assert crumb is not None
        # Controls name their own target; hosts no longer leak hx-target/hx-swap.
        assert crumb["hx-target"] == expected_target[surface]
        assert crumb["hx-swap"] == "innerHTML"
        refresh = browser.select_one(".dt-actions button")
        assert refresh["hx-target"] == expected_target[surface]
        folder = browser.select_one("details.dt-folder")
        assert folder is not None
        assert folder["hx-trigger"] == "toggle once"
        assert folder["hx-target"] == "find .dt-children"
        assert reverse("webui:workspace_directory_children", args=[workspace.pk]) in folder["hx-get"]
        assert f"surface={surface}" in folder["hx-get"]
        # Children are lazy: the file lives inside the collapsed folder.
        assert "example.txt" not in str(browser)

    assert "hx-target" not in panel.select_one(".dt-host-panel").attrs
    assert "hx-target" not in detail.select_one("#workspace-directory").attrs

    children = client.get(
        reverse("webui:workspace_directory_children", args=[workspace.pk]),
        {"path": "folder", "surface": "panel"},
    )
    assert children.status_code == 200
    assert b"example.txt" in children.content
    child_soup = BeautifulSoup(children.content, "html.parser")
    nested = child_soup.select_one("details.dt-folder")
    assert nested is not None
    assert "surface=panel" in nested["hx-get"]

    outside = tmp_path / "outside.txt"
    outside.write_text("must not be shown")
    escaped = client.get(
        reverse("webui:workspace_directory_children", args=[workspace.pk]),
        {"path": "../outside.txt", "surface": "page"},
    )
    assert b"must not be shown" not in escaped.content
    assert b"Directory is unavailable." in escaped.content


@pytest.mark.django_db
def test_workspace_manager_reports_missing_agent(client, tmp_path):
    from server.models.workspace import WorkspaceModel

    workspace = WorkspaceModel.objects.create(
        name="workspace-manager",
        path=str(tmp_path),
        agentone_dir=str(tmp_path / ".agentone"),
    )
    response = client.post(
        reverse("webui:workspace_manager_open", args=[workspace.pk])
    )
    assert response.status_code == 302
    assert response["Location"].endswith("?error=manager-agent")


def test_agent_capabilities_preserve_disallowed_names():
    from types import SimpleNamespace

    from webui.features.agents.views import _capability_sections

    values = {
        "toolNames": ["shell", "read"],
        "disallowedToolNames": ["shell"],
        "taskNames": ["build"],
        "disallowedTaskNames": [],
    }
    version = SimpleNamespace(resolve_setting=lambda name: values.get(name, []))
    sections = _capability_sections(version)
    tools = {row["name"]: row["allowed"] for row in sections[0]["rows"]}
    assert tools == {"read": True, "shell": False}
    assert sections[1]["rows"] == [{"name": "build", "allowed": True}]


@pytest.mark.django_db
def test_collection_detail_lists_derived_flows(client):
    from server.models.collections.data_collection import DataCollection

    source = DataCollection.objects.create(name="upstream-flow", collection_type="stream")
    derived = DataCollection.objects.create(
        name="downstream-flow",
        collection_type="set",
        sources=[{"type": "stream", "stream": source.name}],
    )
    response = client.get(reverse("webui:collection", args=[source.pk]))
    assert response.status_code == 200
    assert b"downstream-flow" in response.content
    assert reverse("webui:collection", args=[derived.pk]).encode() in response.content


@pytest.mark.django_db
def test_entity_assistant_launch_creates_scoped_chat(client, monkeypatch):
    from server.models.agents.agent import AgentModel
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.sessions.session import SessionModel
    from webui.core import assistants

    subject = AgentModel.objects.create(name="assistant-target")
    assistant = AgentModel.objects.create(name="AgentOne")
    version = AgentVersionModel.objects.create(agent=assistant, version_number=1)
    AgentModel.objects.filter(pk=assistant.pk).update(latest_agent_version=version)
    monkeypatch.setattr(
        assistants,
        "_assistant_scope",
        lambda kind, item: ("AgentOne", None, None),
    )

    response = client.post(
        reverse("webui:entity_assistant_open", args=["agent", subject.pk])
    )
    assert response.status_code == 302
    assert response["Location"].startswith("/app/chat/")
    assert SessionModel.objects.filter(
        latest_session_version__agent=assistant,
        name__startswith="AgentOne - assistant-target",
    ).exists()

    embedded = client.post(
        reverse("webui:entity_assistant_open", args=["agent", subject.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert embedded.status_code == 200
    assert b'id="entity-assistant-panel"' in embedded.content
    assert b'class="webui-entity-assistant-composer"' in embedded.content
    assert b'hx-target="#thread"' in embedded.content


@pytest.mark.django_db
def test_overview_pages_render_embedded_assistant_panels(client, monkeypatch):
    from webui.core import assistants

    assistant_names = {kind: "AgentOne" for kind in (
        "dashboard", "agents", "projects", "workspaces", "cronjobs", "workitems",
    )}
    monkeypatch.setattr(
        assistants,
        "_overview_scope",
        lambda kind, project: (assistant_names[kind], project, None),
    )
    monkeypatch.setattr(assistants, "_sessions_for_scope", lambda *_args: [])

    for path in (
        reverse("webui:dashboard"),
        reverse("webui:agents"),
        reverse("webui:projects"),
        reverse("webui:workspaces"),
        reverse("webui:cron"),
        reverse("webui:workitems"),
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert b'id="entity-assistant-panel"' in response.content, path
        _assert_panel_is_rightbar(response.content, path)


@pytest.mark.django_db
def test_workitems_overview_assistant_preserves_project_scope(client, monkeypatch):
    from server.models.project import Project
    from webui.core import assistants

    project = Project.objects.create(name="Assistant project scope")
    monkeypatch.setattr(
        assistants,
        "_overview_scope",
        lambda _kind, requested_project: (
            "AgentOne",
            requested_project,
            None,
        ),
    )
    monkeypatch.setattr(assistants, "_sessions_for_scope", lambda *_args: [])

    response = client.get(
        reverse("webui:workitems"),
        {"project": project.pk},
    )
    assert response.status_code == 200
    assert b'hx-post="/app/assistant/overview/workitems/open"' in response.content
    assert (
        f'<input type="hidden" name="project" value="{project.pk}">'.encode()
        in response.content
    )


@pytest.mark.django_db
def test_provider_and_model_insight_details_render(client):
    from server.models.providers.ai_model import AiModel
    from server.models.providers.api_provider import ApiProvider

    provider = ApiProvider.objects.create(
        name="Insight Provider",
        url="https://provider.example",
        limit_request_per_minute=12,
    )
    model = AiModel.objects.create(
        api_provider=provider,
        name="Insight Model",
        provider_model_id="model-v1",
        context_length=12345,
        supports_tool_call=True,
    )
    providers = client.get(reverse("webui:insights_tab", args=["providers"]))
    models = client.get(reverse("webui:insights_tab", args=["models"]))
    assert providers.status_code == models.status_code == 200
    assert b"Insight Provider" in providers.content
    assert b"12 RPM" in providers.content
    assert f"#model-{model.pk}".encode() in providers.content
    assert b"Insight Model" in models.content
    assert f"#provider-{provider.pk}".encode() in models.content
    model_detail = client.get(reverse("webui:model_detail", args=[model.pk]))
    provider_detail = client.get(reverse("webui:provider_detail", args=[provider.pk]))
    assert model_detail.status_code == provider_detail.status_code == 200
    assert reverse("webui:model_probe", args=[model.pk]).encode() in model_detail.content
    assert b"Insight Provider" in provider_detail.content


@pytest.mark.django_db
def test_model_probe_dispatches_specific_model(client, monkeypatch):
    import importlib

    from django.core.cache import cache

    from server.models.providers.ai_model import AiModel
    from server.models.providers.api_provider import ApiProvider
    probe_module = importlib.import_module("server.tasks.probe_model")

    provider = ApiProvider.objects.create(name="Model Probe Provider")
    model = AiModel.objects.create(
        api_provider=provider,
        name="Model Probe Target",
        provider_model_id="target",
    )
    dispatched = []

    class FakeTask:
        @staticmethod
        def delay(model_pk):
            dispatched.append(model_pk)

    monkeypatch.setattr(probe_module, "probe_model", FakeTask())
    monkeypatch.setattr(probe_module, "get_cached_result", lambda _pk: None)
    monkeypatch.setattr(probe_module, "is_running", lambda _pk: False)
    response = client.post(
        reverse("webui:model_probe", args=[model.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert b"Testing Model Probe Target" in response.content
    assert dispatched == [model.pk]
    cache.delete(f"webui:probe:model-requested:{model.pk}")


@pytest.mark.django_db
def test_chat_todo_controls_save_auto_state_and_clear(client, monkeypatch):
    from server.models.sessions.session import SessionModel

    session, _version = _session_with_version("todo-controls")
    state = {}
    cleared = []

    class Anchor:
        @staticmethod
        def delay(**kwargs):
            cleared.append(kwargs)

    class FakeRuntime:
        @staticmethod
        def _set_session_setting(name, value):
            state[name] = value

        @staticmethod
        def get_task(name):
            return Anchor() if name == "todolist_action" else None

        @staticmethod
        def get_tool(_name):
            return None

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    endpoint = reverse("webui:chat_todo_action", args=[session.pk])
    assert client.post(endpoint, {"action": "auto"}).status_code == 302
    assert state["todo_auto_process"] is True
    assert client.post(endpoint, {"action": "pause"}).status_code == 302
    assert state["todo_auto_process"] is False
    assert client.post(endpoint, {"action": "clear"}).status_code == 302
    assert cleared == [{"action": "clear"}]
    assert client.post(endpoint, {"action": "unknown"}).status_code == 400


@pytest.mark.django_db
def test_chat_call_cancel_is_limited_to_session(client, monkeypatch):
    from server.models.enums.task_enums import TaskCallStatusDetail
    from server.tasks import recovery_scheduler

    session, version = _session_with_version("call-cancel")
    call = _task_call(session, version, detail=TaskCallStatusDetail.WAITING_QUEUE)
    cancelled = []
    monkeypatch.setattr(
        recovery_scheduler, "_force_end_call", lambda target: cancelled.append(target.pk)
    )
    response = client.post(
        reverse("webui:call_cancel", args=[session.pk, call.pk])
    )
    assert response.status_code == 302
    assert cancelled == [call.pk]


@pytest.mark.django_db
def test_chat_setting_override_and_reset(client):
    session, _version = _session_with_version("right-panel-settings")
    endpoint = reverse("webui:chat_setting", args=[session.pk])

    saved = client.post(endpoint, {"name": "max_turns", "value": "5"})
    assert saved.status_code == 200
    assert b'value="5"' in saved.content
    session.refresh_from_db()
    assert session.latest_session_version.session_settings.max_turns == 5

    reset = client.post(endpoint, {"name": "max_turns", "action": "reset"})
    assert reset.status_code == 200
    session.refresh_from_db()
    assert session.latest_session_version.session_settings.max_turns is None

    invalid = client.post(endpoint, {"name": "reasoning_effort", "value": "invalid"})
    assert invalid.status_code == 400


@pytest.mark.django_db
def test_chat_settings_panel_is_grouped_and_autosaves(client):
    session, _version = _session_with_version("settings-layout")
    response = client.get(
        reverse("webui:chat_panel_tab", args=[session.pk, "settings"])
    )
    assert response.status_code == 200
    for title in (b"Behavior", b"Limits", b"Compaction", b"Access", b"Prompts"):
        assert title in response.content
    # The redesign removed the scattered per-field Save buttons.
    assert b">Save<" not in response.content
    assert b"webui-form-row" in response.content

    renamed = client.post(
        reverse("webui:chat_config", args=[session.pk]),
        {"panel": "settings", "name": "renamed-session"},
        HTTP_HX_REQUEST="true",
    )
    assert renamed.status_code == 200
    session.refresh_from_db()
    assert session.name == "renamed-session"
    assert session.name_is_auto is False


@pytest.mark.django_db
def test_chat_capabilities_panel_uses_chips(client):
    session, _version = _session_with_version("capabilities-layout")
    response = client.get(
        reverse("webui:chat_panel_tab", args=[session.pk, "capabilities"])
    )
    assert response.status_code == 200
    assert b"webui-panel-card" in response.content
    assert b"webui-chip-wrap" in response.content
    assert b"Effective for this session" in response.content


@pytest.mark.django_db
def test_settings_providers_tab_masks_keys(client):
    """The providers table shows key badges (count/masked), not full keys.
    Full masked keys are shown in the provider detail rightbar."""
    from server.models.providers.api_key import ApiKey
    from server.models.providers.api_provider import ApiProvider

    provider = ApiProvider.objects.create(name="Test Provider")
    ApiKey.objects.create(
        api_provider=provider, key="sk-1234567890abcdef", comment="primary"
    )

    response = client.get(reverse("webui:settings_tab", args=["providers"]))
    assert response.status_code == 200
    assert b"Test Provider" in response.content
    # Full key never appears in table
    assert b"sk-1234567890abcdef" not in response.content
    # Table shows key badge with count (new UI: key-badge key-ok with ✓ 1)
    assert b"key-badge key-ok" in response.content
    assert b"\xe2\x9c\x93 1" in response.content  # ✓ 1
    # Masked key only appears in detail view
    detail = client.get(reverse("webui:provider_detail", args=[provider.pk]))
    assert detail.status_code == 200
    assert b"primary" in detail.content  # key comment shown
    assert b"enabled" in detail.content  # key status shown
    assert b"sk-1234567890abcdef" not in detail.content  # full key still masked


@pytest.mark.django_db
def test_settings_provider_probe_shows_in_status_column(client, monkeypatch):
    """Probe status is shown as a badge in the table's Status column (new UI).
    The polling probe row is only used in the provider detail rightbar."""
    from server.models.providers.api_provider import ApiProvider
    import webui.features.settings.views as settings_views

    provider = ApiProvider.objects.create(name="Probe Provider")
    monkeypatch.setattr(
        settings_views,
        "_provider_probe",
        lambda _provider: {"verdict": "running", "model_pk": 1},
    )

    page = client.get(reverse("webui:settings_tab", args=["providers"]))
    assert page.status_code == 200
    # In the new UI, probe status shows as a badge in the Status column
    # key-badge key-warn with "testing…"
    assert b"key-badge key-warn" in page.content
    assert b"testing" in page.content
    # No separate polling probe row in the table
    assert b'id="provider-probe-%d"' % provider.pk not in page.content
    # The dedicated probe endpoint still exists for the rightbar detail
    fragment = client.get(
        reverse("webui:settings_provider_probe", args=[provider.pk])
    )
    assert fragment.status_code == 200
    assert b'Running a smoke-test turn' in fragment.content


@pytest.mark.django_db
def test_settings_provider_key_add_toggle_delete(client):
    from server.models.providers.api_key import ApiKey
    from server.models.providers.api_provider import ApiProvider

    provider = ApiProvider.objects.create(name="Key Provider")
    add = client.post(
        reverse("webui:settings_provider_key", args=[provider.pk]),
        {"action": "add", "comment": "new", "key": "secret-key"},
    )
    assert add.status_code == 302
    key = ApiKey.objects.get(api_provider=provider, key="secret-key")

    client.post(
        reverse("webui:settings_provider_key", args=[provider.pk]),
        {"action": "toggle", "key_id": key.pk},
    )
    key.refresh_from_db()
    assert key.enabled is False

    client.post(
        reverse("webui:settings_provider_key", args=[provider.pk]),
        {"action": "delete", "key_id": key.pk},
    )
    assert not ApiKey.objects.filter(pk=key.pk).exists()


# ---------------------------------------------------------------------------
# Composer config, message actions, transcript/export, templates, probe
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_chat_page_renders_composer_config(client):
    from server.models.workspace import WorkspaceModel

    WorkspaceModel.objects.create(name="Config Space", path="/tmp/config-space")
    session, _version = _session_with_version("config")
    response = client.get(reverse("webui:chat", args=[session.pk]))
    assert response.status_code == 200
    assert b'class="webui-composer-config"' in response.content
    assert b'name="model"' in response.content
    assert b'name="reasoning"' in response.content
    assert b'name="workspace"' in response.content

    # Live chat state must be refetched on back/forward, not restored stale.
    assert b'hx-history="false"' in response.content
    boosted = client.get(
        reverse("webui:chat", args=[session.pk]), HTTP_HX_REQUEST="true"
    )
    assert b'hx-history="false"' in boosted.content


@pytest.mark.django_db
def test_chat_config_persists_overrides(client, monkeypatch):
    from server.models.sessions.session import SessionModel

    session, _version = _session_with_version("config-post")

    calls = {}

    class FakeRuntime:
        def set_aimodel_by_name(self, name):
            calls["model"] = name

        def set_reasoning_effort(self, value):
            calls["reasoning"] = value

        def set_workspace(self, workspace):
            calls["workspace"] = workspace

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    response = client.post(
        reverse("webui:chat_config", args=[session.pk]),
        {"model": "gpt-test", "reasoning": "high", "workspace": ""},
    )
    assert response.status_code == 302
    assert calls == {"model": "gpt-test", "reasoning": "high", "workspace": None}


@pytest.mark.django_db
def test_fork_chat_redirects_to_child(client, monkeypatch):
    from server.models.sessions.session import SessionModel

    session, _version = _session_with_version("fork")
    message = _user_message(session, _version, "fork here")

    class FakeAgent:
        def get_version_model(self):
            return object()

    class FakeChild:
        class model:
            pk = 4242

    class FakeRuntime:
        agent = FakeAgent()

        def fork(self, **kwargs):
            assert kwargs["anchor"].pk == message.pk
            return FakeChild()

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    response = client.post(
        reverse("webui:fork_chat", args=[session.pk]), {"message_id": message.pk}
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("webui:chat", args=[4242])


def _user_message(session, version, text):
    from server.models.content import GenericContent
    from server.models.enums.message_enums import (
        MessageContentType,
        MessagePartType,
        MessageRole,
    )
    from server.models.message import Message, MessagePart

    message = Message.objects.create(
        session=session, session_version=version, role=MessageRole.USER
    )
    MessagePart.objects.create(
        message=message,
        type=MessagePartType.MESSAGE,
        content=GenericContent.from_text(text),
        content_type=MessageContentType.TEXT,
    )
    return message


@pytest.mark.django_db
def test_chat_transcript_and_export_downloads(client):
    import json

    session, version = _session_with_version("downloads")
    _user_message(session, version, "hello transcript")

    transcript = client.get(reverse("webui:chat_transcript", args=[session.pk]))
    assert transcript.status_code == 200
    assert transcript["Content-Disposition"].startswith("attachment;")
    assert b"hello transcript" in transcript.content

    export = client.get(reverse("webui:chat_export", args=[session.pk]))
    assert export.status_code == 200
    assert export["Content-Disposition"].endswith('.json"')
    payload = json.loads(export.content)
    assert payload["session"]["pk"] == session.pk
    assert payload["messages"][0]["parts"][0]["content"] == "hello transcript"


@pytest.mark.django_db
def test_panel_templates_tab_renders_empty_state(client):
    session, _version = _session_with_version("templates-empty")
    response = client.get(
        reverse("webui:chat_panel_tab", args=[session.pk, "templates"])
    )
    assert response.status_code == 200
    assert b"No templates yet" in response.content


@pytest.mark.django_db
def test_template_preview_reports_unknown_template(client):
    session, _version = _session_with_version("templates-preview")
    response = client.post(
        reverse("webui:template_preview", args=[session.pk]),
        {"name": "does-not-exist"},
    )
    assert response.status_code == 200
    assert b"not found" in response.content.lower()


@pytest.mark.django_db
def test_provider_test_dispatches_probe(client, monkeypatch):
    import importlib

    from server.models.providers.api_provider import ApiProvider

    probe_module = importlib.import_module("server.tasks.probe_model")
    provider = ApiProvider.objects.create(name="Probe Provider")

    class FakeModel:
        pk = 77

    dispatched = {}

    class FakeTask:
        @staticmethod
        def delay(pk):
            dispatched["pk"] = pk

    monkeypatch.setattr(
        "runtime.test_run.best_usable_model", lambda provider_pk: FakeModel()
    )
    monkeypatch.setattr(probe_module, "probe_model", FakeTask())

    response = client.post(
        reverse("webui:settings_provider_test", args=[provider.pk])
    )
    assert response.status_code == 302
    assert dispatched["pk"] == 77

    fragment = client.post(
        reverse("webui:settings_provider_test", args=[provider.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert fragment.status_code == 200
    assert b'id="provider-probe-' in fragment.content
    assert b'Running a smoke-test turn' in fragment.content


@pytest.mark.django_db
def test_connection_banner_is_present(client):
    response = client.get(reverse("webui:dashboard"))
    assert b'id="connection-banner"' in response.content


def test_image_parts_accepts_only_image_data_uris():
    import json

    from webui.features.chats.views import _image_parts

    raw = json.dumps(
        [
            {"name": "a.png", "content": "data:image/png;base64,AAAA"},
            {"name": "evil", "content": "javascript:alert(1)"},
            "data:image/jpeg;base64,BBBB",
        ]
    )
    parts = _image_parts(raw)
    assert [part["content"] for part in parts] == [
        "data:image/png;base64,AAAA",
        "data:image/jpeg;base64,BBBB",
    ]
    assert all(part["content_type"] == "IMAGE" for part in parts)
    assert _image_parts("not json") == []


@pytest.mark.django_db
def test_send_message_passes_image_parts(client, monkeypatch):
    import json

    from server.models.sessions.session import SessionModel

    session, _version = _session_with_version("attach")
    captured = {}

    class FakeRuntime:
        def add_user_message(self, spec):
            captured["spec"] = spec

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    response = client.post(
        reverse("webui:send", args=[session.pk]),
        {
            "text": "look at this",
            "images": json.dumps(
                [{"name": "a.png", "content": "data:image/png;base64,AAAA"}]
            ),
        },
    )
    assert response.status_code == 200
    spec = captured["spec"]
    assert [part["content_type"] for part in spec] == ["IMAGE", "TEXT"]
    assert b"data:image/png;base64,AAAA" in response.content


@pytest.mark.django_db
def test_sidebar_search_filters_chats(client):
    _session_with_version("alpha chat")
    _session_with_version("beta chat")
    response = client.get(reverse("webui:chats_sidebar"), {"q": "alpha"})
    assert response.status_code == 200
    assert b"alpha chat" in response.content
    assert b"beta chat" not in response.content


@pytest.mark.django_db
def test_chat_header_shows_context_usage(client, monkeypatch):
    from server.models.sessions.session import SessionModel

    session, _version = _session_with_version("usage")

    class FakeRuntime:
        def context_usage(self):
            return {
                "used_context_tokens": 1000,
                "max_context_tokens": 10000,
                "used_context_percent": 10.0,
            }

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    response = client.get(reverse("webui:chat_header", args=[session.pk]))
    assert response.status_code == 200
    assert b"10%" in response.content
    assert b"ctx-ring-value" in response.content
    assert b"1k of 10k" in response.content

    # SSE triggers live on the component wrapper, not inside the partial.
    component = client.get(
        reverse("webui:component", args=["chat-header", session.pk]),
        {"render": "htmx"},
    )
    assert component.status_code == 200
    assert b"10%" in component.content
    assert b"sse:Query.session:" in component.content
    assert b"sse:SessionModel:" in component.content


# ---------------------------------------------------------------------------
# Remaining-gap ports: command palette, ToC, message editing, conversation
# management, sidebar activity, agent picker
# ---------------------------------------------------------------------------

def test_fmt_tokens_and_ring_geometry():
    from webui.features.chats.session_ui import _RING_CIRCUMFERENCE, _fmt_tokens

    assert _fmt_tokens(999) == "999"
    assert _fmt_tokens(1000) == "1k"
    assert _fmt_tokens(1_500_000) == "1.5M"
    assert _fmt_tokens(10_000_000) == "10M"
    assert _fmt_tokens("nope") == "0"
    assert _RING_CIRCUMFERENCE > 61.0


@pytest.mark.django_db
def test_usage_summary_exposes_ring_fields(monkeypatch):
    from server.models.sessions.session import SessionModel
    from webui.features.chats.session_ui import usage_summary

    session, _version = _session_with_version("ring")

    class FakeRuntime:
        def context_usage(self):
            return {
                "used_context_tokens": 9500,
                "max_context_tokens": 10000,
                "used_context_percent": 95.0,
                "tokens_send": 1200,
                "tokens_received": 800,
                "tokens_cached": 400,
                "tokens_reasoning": 100,
            }

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    usage = usage_summary(session)
    assert usage["level"] == "high"
    assert usage["percent_label"] == "95%"
    assert usage["used_label"] == "10k"
    assert usage["window_label"] == "10k"
    assert float(usage["ring_offset"]) >= 0.0


@pytest.mark.django_db
def test_command_options_merge_commands_and_tools(monkeypatch):
    from types import SimpleNamespace

    from server.models.sessions.session import SessionModel
    from webui.features.chats.session_ui import command_options

    session, _version = _session_with_version("commands")
    schema = {
        "properties": {
            "target": {"type": "string", "description": "where to look"},
            "depth": {"type": "integer", "description": "levels"},
        },
        "required": ["target"],
    }

    class FakeRuntime:
        allowedCommandNames = ["tree"]
        allowedToolNames = ["grep"]
        allowedCommands = [
            SimpleNamespace(
                task_definition=SimpleNamespace(name="tree", description="list files"),
                function_schema=schema,
            )
        ]
        allowedTools = [
            SimpleNamespace(
                task_definition=SimpleNamespace(name="grep", description="search"),
                function_schema=None,
            ),
            SimpleNamespace(
                task_definition=SimpleNamespace(name="not-allowed", description=""),
                function_schema=None,
            ),
        ]

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    options = {item["name"]: item for item in command_options(session)}
    assert set(options) == {"tree", "grep"}
    assert options["tree"]["fields"][0]["name"] == "target"
    assert options["tree"]["fields"][0]["required"] is True
    assert options["tree"]["fields"][1]["input_type"] == "number"
    assert options["grep"]["fields"] == []


@pytest.mark.django_db
def test_compaction_segments_and_around_window():
    from server.models.enums.message_enums import MessageType
    from server.models.message import Message
    from webui.features.chats.parts.thread import build_thread
    from webui.features.chats.session_ui import compaction_segments

    session, version = _session_with_version("toc")
    first = _user_message(session, version, "first")
    boundary = Message.objects.create(
        session=session,
        session_version=version,
        role="user",
        message_type=MessageType.COMPACTION,
    )
    last = _user_message(session, version, "last")

    segments = compaction_segments(session)
    assert [seg["pk"] for seg in segments] == [boundary.pk]

    window = build_thread(session, limit=50, end_pk=boundary.pk)
    pks = [row.obj.pk for row in window if row.kind == "message"]
    assert boundary.pk in pks
    assert last.pk not in pks
    assert first.pk in pks


def _system_message(session, version, role, message_type, texts, part_type):
    from server.models.content import GenericContent
    from server.models.enums.message_enums import MessageContentType
    from server.models.message import Message, MessagePart

    message = Message.objects.create(
        session=session, session_version=version, role=role, message_type=message_type
    )
    for text in texts:
        MessagePart.objects.create(
            message=message,
            type=part_type,
            content=GenericContent.from_text(text),
            content_type=MessageContentType.TEXT,
        )
    return message


@pytest.mark.django_db
def test_compaction_renders_as_collapsed_system_card(client):
    from bs4 import BeautifulSoup
    from runtime.session_bootstrap import COMPACTION_BOOTSTRAP_SENTINEL
    from server.models.enums.message_enums import (
        MessagePartType,
        MessageRole,
        MessageType,
    )

    session, version = _session_with_version("compaction-card")
    boundary = _system_message(
        session,
        version,
        MessageRole.USER,
        MessageType.COMPACTION,
        [
            "It is now 2026-11-19 10:00, your working dir is '/work/repo'.\n",
            "Old messages before this summary have been compacted to save context tokens. Summary:\n",
            "## Handoff\nKeep the tests green.",
            COMPACTION_BOOTSTRAP_SENTINEL + " frozen]",
            "agent instructions here",
        ],
        MessagePartType.COMPACTION,
    )
    body = client.get(reverse("webui:component", args=["chat-message", boundary.pk])).content.decode()
    soup = BeautifulSoup(body, "html.parser")

    row = soup.select_one(".msg-row.webui-compaction-row")
    assert row is not None
    card = row.select_one("details.system-card.compaction-card")
    assert card is not None
    assert not card.has_attr("open"), "compaction card must start collapsed"
    assert card.get("data-open-key") == f"compaction-{boundary.pk}"
    assert "Context compacted" in card.select_one(".system-card-title").get_text()
    sub = card.select_one(".system-card-sub").get_text(" ")
    assert "2026-11-19 10:00" in sub
    assert "/work/repo" in sub
    assert "Keep the tests green" in sub  # preview comes from the summary
    # Markdown summary is rendered, not shown as raw text.
    assert "Keep the tests green" in card.select_one(".system-card-body").get_text()
    assert card.select_one(".system-card-body h2") is not None
    assert "Re-pinned bootstrap" in card.select_one(".system-card-section summary").get_text()


@pytest.mark.django_db
def test_reflection_renders_as_collapsed_system_card(client):
    from bs4 import BeautifulSoup
    from server.models.enums.message_enums import (
        MessagePartType,
        MessageRole,
        MessageType,
    )

    session, version = _session_with_version("reflection-card")
    report = _system_message(
        session,
        version,
        MessageRole.INFO,
        MessageType.REFLECTION,
        ["Reflection report:\n\n## WHAT\nThe agent retried twice.\n\n## WHY\nUnclear instruction."],
        MessagePartType.MESSAGE,
    )
    body = client.get(reverse("webui:component", args=["chat-message", report.pk])).content.decode()
    soup = BeautifulSoup(body, "html.parser")

    row = soup.select_one(".msg-row.webui-reflection-row")
    assert row is not None
    assert "webui-notice" not in (row.get("class") or [])
    card = row.select_one("details.system-card.reflection-card")
    assert card is not None
    assert not card.has_attr("open"), "reflection card must start collapsed"
    assert card.get("data-open-key") == f"reflection-{report.pk}"
    assert "Reflection report" in card.select_one(".system-card-title").get_text()
    assert "The agent retried twice" in card.select_one(".system-card-sub").get_text()
    rendered = card.select_one(".system-card-body")
    assert "The agent retried twice" in rendered.get_text()
    assert rendered.select_one("h2") is not None
    assert "Reflection report:" not in rendered.get_text()


@pytest.mark.django_db
def test_edit_message_rewrites_and_truncates(client, monkeypatch):
    from server.models.enums.message_enums import MessagePartType
    from server.models.message import Message
    from server.models.sessions.session import SessionModel

    session, version = _session_with_version("edit")
    original = _user_message(session, version, "old prompt")
    later = _user_message(session, version, "later prompt")
    dispatched = {}

    class FakeTask:
        def delay(self, **kwargs):
            dispatched.update(kwargs)

    class FakeRuntime:
        def reset_turn_count(self):
            dispatched["turn_reset"] = True

        def reset_unattended_turn_count(self):
            dispatched["unattended_reset"] = True

        def get_task(self, name):
            dispatched["task"] = name
            return FakeTask()

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    response = client.post(
        reverse("webui:edit_message", args=[session.pk, original.pk]),
        {"text": "new prompt"},
    )
    assert response.status_code == 302
    original.refresh_from_db()
    part = original.parts.filter(type=MessagePartType.MESSAGE).first()
    assert part.content.get() == "new prompt"
    assert not Message.objects.filter(pk=later.pk).exists()
    assert dispatched["task"] == "process_turn"
    assert dispatched["message"].pk == original.pk
    assert dispatched["turn_reset"] and dispatched["unattended_reset"]


@pytest.mark.django_db
def test_clear_conversation_removes_messages(client, monkeypatch):
    from server.models.sessions.session import SessionModel

    session, version = _session_with_version("clear")
    _user_message(session, version, "one")
    _user_message(session, version, "two")
    calls = {}

    class FakeRuntime:
        def reset_turn_count(self):
            calls["turn"] = True

        def reset_unattended_turn_count(self):
            calls["unattended"] = True

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    response = client.post(reverse("webui:clear_conversation", args=[session.pk]))
    assert response.status_code == 302
    assert session.related_messages.count() == 0
    assert calls == {"turn": True, "unattended": True}


@pytest.mark.django_db
def test_import_conversation_creates_messages(client):
    import json

    from django.core.files.uploadedfile import SimpleUploadedFile

    from server.models.sessions.session import SessionModel

    session, _version = _session_with_version("import")
    payload = {
        "messages": [
            {
                "role": "user",
                "message_type": "user_chat",
                "parts": [{"type": "MESSAGE", "content_type": "TEXT", "content": "hi"}],
            },
            {
                "role": "assistant",
                "message_type": "assistant_message",
                "parts": [
                    {"type": "MESSAGE", "content_type": "TEXT", "content": "hello"},
                    {"type": "TOOLCALL", "content_type": "TEXT", "content": "skipped"},
                ],
            },
        ]
    }
    upload = SimpleUploadedFile(
        "chat.json", json.dumps(payload).encode("utf-8"), content_type="application/json"
    )
    response = client.post(
        reverse("webui:import_conversation", args=[session.pk]), {"file": upload}
    )
    assert response.status_code == 302
    messages = list(session.related_messages.order_by("pk"))
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].prev_message_id is None
    assert messages[1].prev_message_id == messages[0].pk
    assert messages[1].parts.count() == 1
    assert messages[1].parts.first().content.get() == "hello"


@pytest.mark.django_db
def test_chat_action_move_sets_project(client):
    from server.models.project import Project
    from server.models.sessions.session import SessionModel

    session = SessionModel.objects.create(name="move-me")
    project = Project.objects.create(name="Moved Here")
    response = client.post(
        reverse("webui:chat_action", args=[session.pk]),
        {"action": "move", "project": project.pk},
    )
    assert response.status_code == 302
    session.refresh_from_db()
    assert session.parent_project_id == project.pk


@pytest.mark.django_db
def test_sidebar_marks_streaming_and_approval_sessions(client):
    from server.models.enums.task_enums import TaskCallStatusDetail
    from server.models.queries.query import Query, QueryStatus

    streaming, streaming_version = _session_with_version("streaming chat")
    waiting, waiting_version = _session_with_version("approval chat")
    idle, _idle_version = _session_with_version("idle chat")

    Query.objects.create(
        session=streaming,
        session_version=streaming_version,
        status=QueryStatus.ACTIVE,
    )
    call = _task_call(
        waiting,
        waiting_version,
        detail=TaskCallStatusDetail.HALTED_APPROVAL,
        name="guardrail",
    )
    from server.models.tasks.agent_task_call import AgentTaskCall

    AgentTaskCall.objects.filter(pk=call.pk).update(requires_approval=True)

    response = client.get(reverse("webui:chats_sidebar"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "is-streaming" in body
    assert "needs-approval" in body
    assert idle.name in body


@pytest.mark.django_db
def test_chat_config_sets_agent(client, monkeypatch):
    from server.models.agents.agent import AgentModel
    from server.models.sessions.session import SessionModel

    session, _version = _session_with_version("agent-picker")
    agent = AgentModel.objects.create(name="chosen-agent")
    applied = {}

    class FakeRuntime:
        def set_agent(self, value):
            applied["agent"] = value

    monkeypatch.setattr(SessionModel, "get_runtime", lambda self: FakeRuntime())
    response = client.post(
        reverse("webui:chat_config", args=[session.pk]), {"agent": agent.pk}
    )
    assert response.status_code == 302
    assert applied["agent"].pk == agent.pk


@pytest.mark.django_db
def test_terminal_output_renders_polled_buffer(client, monkeypatch):
    from server.models.terminal import TerminalSession
    import runtime.terminal as terminal_module

    session, _version = _session_with_version("terminal")
    TerminalSession.objects.create(
        session=session,
        name="default",
        tmux_session_name=f"agentone-test-{session.pk}-default",
        status="running",
        cwd="/tmp",
    )

    def fake_poll(session_model, name="default", lines=200):
        assert session_model.pk == session.pk
        assert name == "default"
        return {"status": "success", "terminal": name, "output": "$ echo hi\nhi"}

    monkeypatch.setattr(terminal_module, "poll_output", fake_poll)
    response = client.get(
        reverse("webui:terminal_output", args=[session.pk, "default"])
    )
    assert response.status_code == 200
    assert b"echo hi" in response.content
    assert b"webui-terminal-output" in response.content


@pytest.mark.django_db
def test_terminal_output_ignores_unknown_terminal(client):
    session, _version = _session_with_version("terminal-missing")
    response = client.get(
        reverse("webui:terminal_output", args=[session.pk, "nope"])
    )
    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.django_db
def test_root_redirects_to_new_ui_for_authenticated_users(client):
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user("root-user", password="x")
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/app/"


@pytest.mark.django_db
def test_root_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@override_settings(WEBUI_LOGIN_REQUIRED=True)
def test_app_requires_login_when_enabled(client):
    response = client.get(reverse("webui:dashboard"))
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
    assert "next=/app/" in response["Location"]


@pytest.mark.django_db
@override_settings(WEBUI_LOGIN_REQUIRED=True)
def test_app_allows_authenticated_user(client):
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user("ui-user", password="x")
    client.force_login(user)
    response = client.get(reverse("webui:dashboard"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_cron_create_edit_duplicate_run_and_delete(client, tmp_path, monkeypatch):
    """Cron jobs round-trip through create, edit, duplicate and delete (DB-only)."""
    from unittest.mock import patch

    from server.models.agents.agent import AgentModel
    from server.models.cron import Cronjob
    from server.models.project import Project

    project = Project.objects.create(
        name="cron-project", agentone_dir=str(tmp_path / "project-agentone")
    )
    agent = AgentModel.objects.create(name="cron-agent", parent_project=project)

    response = client.post(
        reverse("webui:cron_create"),
        {
            "name": "hourly-report",
            "schedule": "0 * * * *",
            "agent": str(agent.pk),
            "parent_project": str(project.pk),
            "message": "Write the report",
        },
    )
    assert response.status_code == 302
    cron = Cronjob.objects.get(name="hourly-report")
    assert cron.agent_id == agent.pk
    assert cron.next_run_at is not None
    assert cron.message.get() == "Write the report"

    response = client.post(
        reverse("webui:cron_edit", args=[cron.pk]),
        {
            "name": "daily-report",
            "schedule": "@daily",
            "agent": str(agent.pk),
            "parent_project": str(project.pk),
            "message": "Write the daily report",
        },
    )
    assert response.status_code == 302
    cron.refresh_from_db()
    assert cron.name == "daily-report"
    assert cron.schedule == "@daily"

    response = client.post(reverse("webui:cron_duplicate", args=[cron.pk]))
    assert response.status_code == 302
    copy = Cronjob.objects.get(name="daily-report-copy")
    assert copy.function_type == ""

    with patch("webui.features.cron.views.execute_cron_job") as execute:
        response = client.post(reverse("webui:cron_run_now", args=[cron.pk]))
    assert response.status_code == 302
    execute.assert_called_once_with(cron.pk)

    response = client.post(reverse("webui:cron_delete", args=[cron.pk]))
    assert response.status_code == 302
    assert not Cronjob.objects.filter(pk=cron.pk).exists()


@pytest.mark.django_db
def test_collection_edit_reprocess_and_delete(client, monkeypatch):
    from unittest.mock import patch

    from server.models.collections.data_collection import DataCollection

    collection = DataCollection.objects.create(name="webui-flow", collection_type="stream")

    response = client.post(
        reverse("webui:collection_edit", args=[collection.pk]),
        {
            "name": "webui-flow-renamed",
            "collection_type": "set",
            "is_active": "on",
            "description": "edited",
            "sources": '[{"type": "stream", "stream": "input"}]',
            "processor": '{"agent": "processor", "function": "handle"}',
            "on_removed": '{"agent": "cleaner", "function": "remove"}',
            "member_field": "item.id",
            "score_field": "item.score",
            "retroactive_on_source_change": "5",
            "max_reprocess": "7",
        },
    )
    assert response.status_code == 302
    collection.refresh_from_db()
    assert collection.name == "webui-flow-renamed"
    assert collection.collection_type == "set"
    assert collection.sources == [{"type": "stream", "stream": "input"}]
    assert collection.processor == {"agent": "processor", "function": "handle"}
    assert collection.on_removed == {"agent": "cleaner", "function": "remove"}
    assert collection.member_field == "item.id"
    assert collection.retroactive_on_source_change == 5
    assert collection.max_reprocess == 7

    with patch("server.tasks.reprocess_collection.reprocess_collection.delay") as delay:
        response = client.post(reverse("webui:collection_reprocess", args=[collection.pk]))
    assert response.status_code == 302
    assert "reprocessed=1" in response["Location"]
    delay.assert_called_once_with("webui-flow-renamed")

    response = client.post(reverse("webui:collection_delete", args=[collection.pk]))
    assert response.status_code == 302
    assert not DataCollection.objects.filter(pk=collection.pk).exists()


@pytest.mark.django_db
def test_workitem_board_filters_and_delete(client):
    from server.models.agents.agent import AgentModel
    from server.models.workitems.enums import WorkItemStatus
    from server.models.workitems.work_item import WorkItem

    agent_a = AgentModel.objects.create(name="filter-agent-a")
    agent_b = AgentModel.objects.create(name="filter-agent-b")
    WorkItem.objects.create(
        title="Review this", assigned_agent=agent_a,
        status=WorkItemStatus.IN_REVIEW, requires_verification=True,
    )
    WorkItem.objects.create(
        title="Blocked task", assigned_agent=agent_b,
        status=WorkItemStatus.BLOCKED,
    )
    WorkItem.objects.create(
        title="Backlog task", assigned_agent=agent_a,
        status=WorkItemStatus.BACKLOG,
    )

    page = client.get(
        reverse("webui:workitems_board"),
        {"assignee": "filter-agent-a"},
        HTTP_HX_REQUEST="true",
    )
    assert b"Review this" in page.content
    assert b"Backlog task" in page.content
    assert b"Blocked task" not in page.content

    page = client.get(
        reverse("webui:workitems_board"),
        {"verify": "required"},
        HTTP_HX_REQUEST="true",
    )
    assert b"Review this" in page.content
    assert b"Backlog task" not in page.content

    page = client.get(
        reverse("webui:workitems_board"),
        {"actionable": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert b"Review this" in page.content
    assert b"Blocked task" in page.content
    assert b"Backlog task" not in page.content

    item = WorkItem.objects.get(title="Review this")
    response = client.post(reverse("webui:workitem_delete", args=[item.pk]))
    assert response.status_code == 302
    assert not WorkItem.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_sidebar_nests_child_sessions_and_counts_subagents(client):
    """The chat sidebar shows child sessions under their parent."""
    from server.models.sessions.session import SessionModel

    parent = SessionModel.objects.create(name="Parent chat")
    SessionModel.objects.create(name="Child subagent", parent_session=parent)

    response = client.get(reverse("webui:chats_sidebar"))
    assert response.status_code == 200
    content = response.content
    assert b"Parent chat" in content
    assert b"Child subagent" in content
    assert b"session-tree-child" in content
    assert b"1 subagents" in content


@pytest.mark.django_db
def test_insights_analytics_filters_and_dashboard_inspect(client):
    from server.models.agents.agent import AgentModel
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.queries.response import Response, ResponseStatus
    from server.models.sessions.session import SessionModel
    from server.models.sessions.session_version import SessionVersionModel
    from server.models.settings import SettingsModel
    from server.models.tasks.agent_task_call import AgentTaskCall

    agent = AgentModel.objects.create(name="insights-agent")
    agent_version = AgentVersionModel.objects.create(
        agent=agent, agent_settings=SettingsModel.objects.create()
    )
    session = SessionModel.objects.create(name="insights-session")
    session_version = SessionVersionModel.objects.create(
        session=session, agent=agent, pinned_agent_version=agent_version
    )

    Response.objects.create(
        session=session,
        session_version=session_version,
        status=ResponseStatus.SUCCESS,
        provider_name="provA",
        model_name="modelA",
        prompt_tokens=10,
        completion_tokens=5,
    )
    Response.objects.create(
        session=session,
        session_version=session_version,
        status=ResponseStatus.SUCCESS,
        provider_name="provB",
        model_name="modelB",
        prompt_tokens=20,
        completion_tokens=7,
    )

    page = client.get(
        reverse("webui:insights_tab", args=["analytics"]),
        {"provider": "provA", "range": "7d"},
    )
    assert page.status_code == 200
    assert page.context["provider_filter"] == "provA"
    assert page.context["range_key"] == "7d"
    assert [row["provider_name"] for row in page.context["providers"]] == ["provA"]

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page.content, "html.parser")
    form = soup.select_one("form.insights-filters")
    # Filter responses are full shells; select just the main view and stop the
    # form's swap attrs leaking onto its Reset link.
    assert form.get("hx-select") == ".main-view"
    assert "hx-target" in (form.get("hx-disinherit") or "")
    assert {row["model_name"] for row in page.context["models"]} == {"modelA"}
    assert page.context["analytics_stats"][0]["label"] == "Requests"

    page = client.get(
        reverse("webui:insights_tab", args=["analytics"]),
        {"range": "all", "model": "modelB"},
    )
    assert page.context["range_key"] == "all"
    assert {row["model_name"] for row in page.context["models"]} == {"modelB"}

    AgentTaskCall.objects.create(
        session=session,
        session_version=session_version,
        status="NEW",
        requires_approval=False,
        max_subtask_errors=0,
        max_subtask_error_rate=0,
        limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=0,
        max_retries=0,
        retry_delay=0,
        retry_requires_approval=False,
    )
    page = client.get(
        reverse("webui:insights_tab", args=["dashboard"]),
        {"agent": "insights-agent", "status": "NEW"},
    )
    assert page.context["inspect"]["count"] == 1
    assert page.context["inspect"]["agent"] == "insights-agent"

    page = client.get(
        reverse("webui:insights_tab", args=["dashboard"]), {"agent": "nobody"}
    )
    assert page.context["inspect"]["count"] == 0

    from webui.features.insights.views import _analytics_buckets

    assert _analytics_buckets("24h")[1] == "hour"
    assert _analytics_buckets("7d")[1] == "day"
    assert _analytics_buckets("30d")[1] == "day"
    assert _analytics_buckets("90d")[1] == "week"


@pytest.mark.django_db
def test_workspace_create_edit_access_roundtrip_and_delete(client, tmp_path):
    from server.models.workspace import WorkspaceModel

    ws_path = tmp_path / "roundtrip-space"
    ws_path.mkdir()
    payload = {
        "name": "roundtrip-space",
        "path": str(ws_path),
        "color": "#123456",
        "description": "temporary",
        "storage": "inline",
        "access_read_default": "ask",
        "access_read_allow": "src/**\nlib/**",
        "access_read_ask": "docs/**",
        "access_read_deny": "secrets/**",
        "access_write_default": "deny",
        "access_write_allow": "out/**",
    }
    response = client.post(reverse("webui:workspace_create"), payload)
    assert response.status_code == 302
    workspace = WorkspaceModel.objects.get(name="roundtrip-space")
    assert workspace.path == str(ws_path)
    assert workspace.color == "#123456"
    assert workspace.access["read"]["default"] == "ask"
    assert workspace.access["read"]["allow"] == ["src/**", "lib/**"]
    assert workspace.access["write"]["default"] == "deny"
    assert workspace.access["write"]["allow"] == ["out/**"]
    assert (ws_path / ".agentone").is_dir()

    payload.update(
        {
            "name": "roundtrip-space-edited",
            "description": "edited",
            "access_read_default": "deny",
            "access_read_allow": "changed/**",
            "access_write_default": "allow",
        }
    )
    response = client.post(reverse("webui:workspace_edit", args=[workspace.pk]), payload)
    assert response.status_code == 302
    workspace.refresh_from_db()
    assert workspace.name == "roundtrip-space-edited"
    assert workspace.description == "edited"
    assert workspace.access["read"]["default"] == "deny"
    assert workspace.access["read"]["allow"] == ["changed/**"]
    assert workspace.access["write"]["default"] == "allow"

    response = client.post(reverse("webui:workspace_delete", args=[workspace.pk]))
    assert response.status_code == 302
    assert not WorkspaceModel.objects.filter(pk=workspace.pk).exists()


@pytest.mark.django_db
def test_settings_tab_shows_identity_fields(client):
    session, _version = _session_with_version("settings-identity")
    response = client.get(
        reverse("webui:chat_panel_tab", args=[session.pk, "settings"])
    )
    assert response.status_code == 200
    assert b"settings-identity" in response.content
    assert b"settings-identity-agent" in response.content
    assert b"settings-name" in response.content
    assert b"v1" in response.content


@pytest.mark.django_db
def test_subagent_tab_lists_active_children_and_close(client):
    from server.models.sessions.session import SessionModel
    from server.models.enums.session_enums import SessionType

    session, _version = _session_with_version("subagents-close")
    child = SessionModel.objects.create(
        name="child-session",
        parent_session=session,
        session_type=SessionType.SUBSESSION,
    )
    response = client.get(
        reverse("webui:chat_panel_tab", args=[session.pk, "subagents"])
    )
    assert response.status_code == 200
    assert b"child-session" in response.content
    assert b"0 msgs" in response.content

    closed = client.post(
        reverse("webui:subagent_close", args=[session.pk, child.pk])
    )
    assert closed.status_code == 200
    child.refresh_from_db()
    assert child.is_active is False


@pytest.mark.django_db
def test_terminal_tab_shows_liveness_and_kill(client, monkeypatch):
    from server.models.terminal import TerminalSession
    import runtime.terminal as terminal_module

    session, _version = _session_with_version("terminal-kill")
    TerminalSession.objects.create(
        session=session,
        name="build",
        tmux_session_name=f"agentone-test-{session.pk}-build",
        status="running",
        cwd="/tmp",
    )
    monkeypatch.setattr(
        terminal_module,
        "list_terminals",
        lambda session_model: [
            {
                "name": "build",
                "status": "running",
                "tmux": f"agentone-test-{session.pk}-build",
                "alive": True,
                "cwd": "/tmp",
                "last_active_at": None,
            }
        ],
    )
    killed = {}
    monkeypatch.setattr(
        terminal_module,
        "kill_terminal",
        lambda session_model, name="default": killed.update(name=name),
    )
    response = client.get(
        reverse("webui:chat_panel_tab", args=[session.pk, "terminals"])
    )
    assert response.status_code == 200
    assert b"build" in response.content
    assert b"tmux live" in response.content

    response = client.post(
        reverse("webui:terminal_kill", args=[session.pk, "build"])
    )
    assert response.status_code == 200
    assert killed == {"name": "build"}


@pytest.mark.django_db
def test_new_chat_honours_agent_workspace_name_and_description(client, tmp_path):
    from server.models.sessions.session import SessionModel
    from server.models.workspace import WorkspaceModel

    agent = _session_with_version("new-chat-agent")[0].latest_session_version.agent
    workspace = WorkspaceModel.objects.create(
        name="new-chat-workspace",
        path=str(tmp_path),
        agentone_dir=str(tmp_path / ".agentone"),
    )
    response = client.post(
        reverse("webui:new_chat"),
        {
            "agent": agent.pk,
            "workspace": workspace.pk,
            "name": "custom-chat-name",
            "description": "Talk about the audit",
        },
    )
    assert response.status_code == 302
    session = SessionModel.objects.get(name="custom-chat-name")
    assert response["Location"] == reverse("webui:chat", args=[session.pk])
    version = session.latest_session_version
    assert version.description == "Talk about the audit"
    assert version.workspace_id == workspace.pk
    assert version.agent_id == agent.pk
    assert session.name_is_auto is False


@pytest.mark.django_db
def test_chats_page_offers_new_chat_form(client):
    from server.models.workspace import WorkspaceModel

    _session_with_version("chats-form")
    WorkspaceModel.objects.create(name="form-workspace", path="/tmp/form-workspace")
    response = client.get(reverse("webui:chats"))
    assert response.status_code == 200
    assert b'id="new-chat"' in response.content
    assert b"form-workspace" in response.content
