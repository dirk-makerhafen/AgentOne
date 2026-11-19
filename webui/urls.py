from django.urls import path

from webui.core import components, events
from webui.core.components import section_sidebar
from webui.core import assistants as assistants_views
from webui.features.agents import views as agents_views
from webui.features.chats import views as chats_views
from webui.features.collections import views as collections_views
from webui.features.cron import views as cron_views
from webui.features.dashboard import views as dashboard_views
from webui.features.insights import views as insights_views
from webui.features.logs import views as logs_views
from webui.features.memory import views as memory_views
from webui.features.projects import views as projects_views
from webui.features.settings import views as settings_views
from webui.features.skills import views as skills_views
from webui.features.workitems import views as workitems_views
from webui.features.workspaces import views as workspaces_views

app_name = "webui"

urlpatterns = [
    # Shell ---------------------------------------------------------------
    path("", dashboard_views.dashboard, name="dashboard"),
    path("chats", dashboard_views.chats, name="chats"),
    path("sse/", events.sse_stream, name="sse"),
    path("sse/watch", events.sse_watch, name="sse_watch"),
    # Components ----------------------------------------------------------
    path("c/<str:name>", components.render_component, name="component_root"),
    path("c/<str:name>/<int:pk>", components.render_component, name="component"),
    # Section sidebars (cached, independently refreshed) -------------------
    path("dashboard/sidebar", section_sidebar, {"section": "dashboard"}, name="dashboard_sidebar"),
    path("chats/sidebar", section_sidebar, {"section": "chats"}, name="chats_sidebar"),
    path("agents/sidebar", section_sidebar, {"section": "agents"}, name="agents_sidebar"),
    path("projects/sidebar", section_sidebar, {"section": "projects"}, name="projects_sidebar"),
    path("workspaces/sidebar", section_sidebar, {"section": "workspaces"}, name="workspaces_sidebar"),
    path("skills/sidebar", section_sidebar, {"section": "skills"}, name="skills_sidebar"),
    path("cron/sidebar", section_sidebar, {"section": "cron"}, name="cron_sidebar"),
    path("collections/sidebar", section_sidebar, {"section": "collections"}, name="collections_sidebar"),
    path("workitems/sidebar", section_sidebar, {"section": "workitems"}, name="workitems_sidebar"),
    path("memory/sidebar", section_sidebar, {"section": "memory"}, name="memory_sidebar"),
    path("insights/sidebar", section_sidebar, {"section": "insights"}, name="insights_sidebar"),
    path("logs/sidebar", section_sidebar, {"section": "logs"}, name="logs_sidebar"),
    path("settings/sidebar", section_sidebar, {"section": "settings"}, name="settings_sidebar"),
    # Chat ----------------------------------------------------------------
    path("chats/<int:session_id>", chats_views.chat_page, name="chat_by_id"),
    path("chat/new", chats_views.new_chat, name="new_chat"),
    path("chat/<int:session_id>", chats_views.chat_page, name="chat"),
    path("chat/<int:session_id>/thread", chats_views.thread_fragment, name="thread"),
    path("chat/<int:session_id>/send", chats_views.send_message, name="send"),
    path("chat/<int:session_id>/header", chats_views.chat_header, name="chat_header"),
    path("chat/<int:session_id>/composer-footer", chats_views.chat_composer_footer, name="chat_composer_footer"),
    path("chat/<int:session_id>/composer-action", chats_views.composer_action, name="composer_action"),
    path("chat/<int:session_id>/toc", chats_views.chat_toc, name="chat_toc"),
    path("chat/<int:session_id>/terminal/<str:name>", chats_views.terminal_output, name="terminal_output"),
    path("chat/<int:session_id>/terminal/<str:name>/kill", chats_views.terminal_kill, name="terminal_kill"),
    path("chat/<int:session_id>/action", chats_views.chat_action, name="chat_action"),
    path("chat/<int:session_id>/todos", chats_views.chat_todo_action, name="chat_todo_action"),
    path("chat/<int:session_id>/config", chats_views.chat_config, name="chat_config"),
    path("chat/<int:session_id>/fork", chats_views.fork_chat, name="fork_chat"),
    path("chat/<int:session_id>/message/<int:message_id>/edit", chats_views.edit_message, name="edit_message"),
    path("chat/<int:session_id>/clear", chats_views.clear_conversation, name="clear_conversation"),
    path("chat/<int:session_id>/import", chats_views.import_conversation, name="import_conversation"),
    path("chat/<int:session_id>/transcript", chats_views.chat_transcript, name="chat_transcript"),
    path("chat/<int:session_id>/export", chats_views.chat_export, name="chat_export"),
    path("chat/<int:session_id>/templates/preview", chats_views.template_preview, name="template_preview"),
    path("chat/<int:session_id>/templates/run", chats_views.template_run, name="template_run"),
    path("chat/<int:session_id>/templates/delete", chats_views.template_delete, name="template_delete"),
    path("chat/<int:session_id>/queue", chats_views.queue_action, name="queue_action"),
    path("chat/<int:session_id>/turn-approval", chats_views.turn_approval, name="turn_approval"),
    path("chat/<int:session_id>/ratelimit", chats_views.ratelimit_action, name="ratelimit_action"),
    path("call/<int:call_id>/action", chats_views.call_action, name="call_action"),
    path("chat/<int:session_id>/calls/<int:call_id>/cancel", chats_views.call_cancel, name="call_cancel"),
    path("chat/<int:session_id>/panel", chats_views.chat_panel, name="chat_panel"),
    path("chat/<int:session_id>/setting", chats_views.chat_setting, name="chat_setting"),
    path("chat/<int:session_id>/subagent", chats_views.subagent_open, name="subagent_open"),
    path("chat/<int:session_id>/subagent/<int:child_id>/close", chats_views.subagent_close, name="subagent_close"),
    path("chat/<int:session_id>/panel/<str:tab>", chats_views.chat_panel_tab, name="chat_panel_tab"),
    path("chat/<int:session_id>/panel/<str:tab>/body", chats_views.chat_panel_body, name="chat_panel_body"),
    path("query/<int:query_id>/detail", chats_views.query_detail, name="query_detail"),
    path("call/<int:call_id>/detail", chats_views.call_detail, name="call_detail"),
    path("chat/<int:session_id>/history/inspect", chats_views.inspect_history_item, name="inspect_history_item"),
    path("response/<int:response_id>/detail", chats_views.response_detail, name="response_detail"),
    path("assistant/<str:kind>/<int:item_id>", assistants_views.entity_assistant_open, name="entity_assistant_open"),
    path("assistant/<str:kind>/<int:item_id>/panel", assistants_views.assistant_panel, name="assistant_panel"),
    path("assistant/overview/<str:kind>/panel", assistants_views.assistant_overview_panel, name="assistant_overview_panel"),
    path("assistant/overview/<str:kind>/open", assistants_views.assistant_overview_open, name="assistant_overview_open"),
    # Agents --------------------------------------------------------------
    path("agents", agents_views.agents, name="agents"),
    path("agents/new", agents_views.agent_create, name="agent_create"),
    path("agents/<int:agent_id>/edit", agents_views.agent_edit, name="agent_edit"),
    path("agents/<int:agent_id>/delete", agents_views.agent_delete, name="agent_delete"),
    path("agents/<int:agent_id>", agents_views.agent_detail, name="agent"),
    # Projects ------------------------------------------------------------
    path("projects", projects_views.projects, name="projects"),
    path("projects/new", projects_views.project_create, name="project_create"),
    path("projects/<int:project_id>/edit", projects_views.project_edit, name="project_edit"),
    path("projects/<int:project_id>", projects_views.project_detail, name="project"),
    # Workspaces ----------------------------------------------------------
    path("workspaces", workspaces_views.workspaces, name="workspaces"),
    path("workspaces/new", workspaces_views.workspace_create, name="workspace_create"),
    path("workspaces/<int:workspace_id>/edit", workspaces_views.workspace_edit, name="workspace_edit"),
    path("workspaces/<int:workspace_id>/delete", workspaces_views.workspace_delete, name="workspace_delete"),
    path("workspaces/<int:workspace_id>/manager", workspaces_views.workspace_manager_open, name="workspace_manager_open"),
    path("workspaces/<int:workspace_id>/directory", workspaces_views.workspace_directory, name="workspace_directory"),
    path("workspaces/<int:workspace_id>/directory/children", workspaces_views.workspace_directory_children, name="workspace_directory_children"),
    path("workspaces/<int:workspace_id>", workspaces_views.workspace_detail, name="workspace"),
    # Skills --------------------------------------------------------------
    path("skills", skills_views.skills, name="skills"),
    path("skills/<int:skill_id>/edit", skills_views.skill_edit, name="skill_edit"),
    path("skills/<int:skill_id>/delete", skills_views.skill_delete, name="skill_delete"),
    path("skills/<int:skill_id>", skills_views.skill_detail, name="skill"),
    # Cron ----------------------------------------------------------------
    path("cron", cron_views.cronjobs, name="cron"),
    path("cron/new", cron_views.cron_create, name="cron_create"),
    path("cron/<int:cron_id>", cron_views.cron_detail, name="cronjob"),
    path("cron/<int:cron_id>/edit", cron_views.cron_edit, name="cron_edit"),
    path("cron/<int:cron_id>/delete", cron_views.cron_delete, name="cron_delete"),
    path("cron/<int:cron_id>/duplicate", cron_views.cron_duplicate, name="cron_duplicate"),
    path("cron/<int:cron_id>/run", cron_views.cron_run_now, name="cron_run_now"),
    path("cron/<int:cron_id>/toggle", cron_views.cron_toggle, name="cron_toggle"),
    path("cron/<int:cron_id>/calls/<int:call_id>/cancel", cron_views.cron_call_cancel, name="cron_call_cancel"),
    # Collections ---------------------------------------------------------
    path("collections", collections_views.collections, name="collections"),
    path("collections/new", collections_views.collection_create, name="collection_create"),
    path("collections/<int:collection_id>", collections_views.collection_detail, name="collection"),
    path("collections/<int:collection_id>/toggle", collections_views.collection_toggle, name="collection_toggle"),
    path("collections/<int:collection_id>/edit", collections_views.collection_edit, name="collection_edit"),
    path("collections/<int:collection_id>/delete", collections_views.collection_delete, name="collection_delete"),
    path("collections/<int:collection_id>/reprocess", collections_views.collection_reprocess, name="collection_reprocess"),
    # Work items ----------------------------------------------------------
    path("workitems", workitems_views.workitems, name="workitems"),
    path("workitems/board", workitems_views.workitems_board, name="workitems_board"),
    path("workitems/new", workitems_views.workitem_create, name="workitem_create"),
    path("workitems/<int:workitem_id>", workitems_views.workitem_detail, name="workitem"),
    path("workitems/<int:workitem_id>/action", workitems_views.workitem_action, name="workitem_action"),
    path("workitems/<int:workitem_id>/update", workitems_views.workitem_update, name="workitem_update"),
    path("workitems/<int:workitem_id>/delete", workitems_views.workitem_delete, name="workitem_delete"),
    # Insights / logs / settings ------------------------------------------
    path("insights", insights_views.insights, {"tab": "dashboard"}, name="insights"),
    path("insights/<str:tab>", insights_views.insights, name="insights_tab"),
    path("insights/models/<int:model_id>/probe", insights_views.model_probe, name="model_probe"),
    path("insights/models/<int:model_id>/probe/status", insights_views.model_probe_status, name="model_probe_status"),
    path("insights/models/<int:model_id>/detail", insights_views.model_detail, name="model_detail"),
    path("insights/providers/<int:provider_id>/detail", insights_views.provider_detail, name="provider_detail"),
    path("logs", logs_views.logs, name="logs"),
    path("logs/tail", logs_views.logs_tail, name="logs_tail"),
    path("settings", settings_views.settings_page, {"tab": "appearance"}, name="settings"),
    path("settings/<str:tab>", settings_views.settings_page, name="settings_tab"),
    path("settings/<str:tab>/save", settings_views.settings_save, name="settings_save"),
    path("settings/providers/<int:provider_id>/key", settings_views.settings_provider_key, name="settings_provider_key"),
    path("settings/providers/<int:provider_id>/test", settings_views.settings_provider_test, name="settings_provider_test"),
    path("settings/providers/<int:provider_id>/probe", settings_views.settings_provider_probe, name="settings_provider_probe"),

    path("memory", memory_views.memory, name="memory"),
    path("memory/playbook", memory_views.memory_playbook, name="memory_playbook"),
    path("memory/improvements", memory_views.memory_improvements, name="memory_improvements"),
    path("memory/improvements/queue", memory_views.memory_improvements_queue, name="memory_improvements_queue"),
    path("memory/node/<path:node_id>/queue", memory_views.memory_node_queue, name="memory_node_queue"),
    path("memory/<path:node_id>", memory_views.memory_node, name="memory_node"),
]
