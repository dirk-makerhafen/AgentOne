from django.urls import path

from webui import events, views

app_name = "webui"

urlpatterns = [
    # Shell ---------------------------------------------------------------
    path("", views.dashboard, name="dashboard"),
    path("chats", views.chats, name="chats"),
    path("sidebar", views.sidebar_fragment, name="sidebar"),
    path("sse/", events.sse_stream, name="sse"),
    # Chat ----------------------------------------------------------------
    path("chat/new", views.new_chat, name="new_chat"),
    path("chat/<int:session_id>", views.chat_page, name="chat"),
    path("chat/<int:session_id>/thread", views.thread_fragment, name="thread"),
    path("chat/<int:session_id>/send", views.send_message, name="send"),
    path("chat/<int:session_id>/header", views.chat_header, name="chat_header"),
    path(
        "chat/<int:session_id>/composer-footer",
        views.chat_composer_footer,
        name="chat_composer_footer",
    ),
    path(
        "chat/<int:session_id>/composer-action",
        views.composer_action,
        name="composer_action",
    ),
    path("chat/<int:session_id>/toc", views.chat_toc, name="chat_toc"),
    path(
        "chat/<int:session_id>/terminal/<str:name>",
        views.terminal_output,
        name="terminal_output",
    ),
    path(
        "chat/<int:session_id>/terminal/<str:name>/kill",
        views.terminal_kill,
        name="terminal_kill",
    ),
    path("chat/<int:session_id>/action", views.chat_action, name="chat_action"),
    path(
        "chat/<int:session_id>/todos",
        views.chat_todo_action,
        name="chat_todo_action",
    ),
    path("chat/<int:session_id>/config", views.chat_config, name="chat_config"),
    path("chat/<int:session_id>/fork", views.fork_chat, name="fork_chat"),
    path(
        "chat/<int:session_id>/message/<int:message_id>/edit",
        views.edit_message,
        name="edit_message",
    ),
    path(
        "chat/<int:session_id>/clear",
        views.clear_conversation,
        name="clear_conversation",
    ),
    path(
        "chat/<int:session_id>/import",
        views.import_conversation,
        name="import_conversation",
    ),
    path("chat/<int:session_id>/transcript", views.chat_transcript, name="chat_transcript"),
    path("chat/<int:session_id>/export", views.chat_export, name="chat_export"),
    path(
        "chat/<int:session_id>/templates/preview",
        views.template_preview,
        name="template_preview",
    ),
    path(
        "chat/<int:session_id>/templates/run",
        views.template_run,
        name="template_run",
    ),
    path(
        "chat/<int:session_id>/templates/delete",
        views.template_delete,
        name="template_delete",
    ),
    path("chat/<int:session_id>/queue", views.queue_action, name="queue_action"),
    path(
        "chat/<int:session_id>/turn-approval",
        views.turn_approval,
        name="turn_approval",
    ),
    path(
        "chat/<int:session_id>/ratelimit",
        views.ratelimit_action,
        name="ratelimit_action",
    ),
    path("call/<int:call_id>/action", views.call_action, name="call_action"),
    path(
        "chat/<int:session_id>/calls/<int:call_id>/cancel",
        views.call_cancel,
        name="call_cancel",
    ),
    path("chat/<int:session_id>/panel", views.chat_panel, name="chat_panel"),
    path("chat/<int:session_id>/setting", views.chat_setting, name="chat_setting"),
    path("chat/<int:session_id>/subagent", views.subagent_open, name="subagent_open"),
    path(
        "chat/<int:session_id>/subagent/<int:child_id>/close",
        views.subagent_close,
        name="subagent_close",
    ),
    path(
        "chat/<int:session_id>/panel/<str:tab>",
        views.chat_panel_tab,
        name="chat_panel_tab",
    ),
    path("query/<int:query_id>/detail", views.query_detail, name="query_detail"),
    path("call/<int:call_id>/detail", views.call_detail, name="call_detail"),
    path(
        "assistant/<str:kind>/<int:item_id>",
        views.entity_assistant_open,
        name="entity_assistant_open",
    ),
    path(
        "assistant/<str:kind>/<int:item_id>/panel",
        views.assistant_panel,
        name="assistant_panel",
    ),
    path(
        "assistant/overview/<str:kind>/panel",
        views.assistant_overview_panel,
        name="assistant_overview_panel",
    ),
    path(
        "assistant/overview/<str:kind>/open",
        views.assistant_overview_open,
        name="assistant_overview_open",
    ),
    # Agents --------------------------------------------------------------
    path("agents", views.agents, name="agents"),
    path("agents/new", views.agent_create, name="agent_create"),
    path("agents/<int:agent_id>/edit", views.agent_edit, name="agent_edit"),
    path("agents/<int:agent_id>/delete", views.agent_delete, name="agent_delete"),
    path("agents/<int:agent_id>", views.agent_detail, name="agent"),
    # Projects ------------------------------------------------------------
    path("projects", views.projects, name="projects"),
    path("projects/new", views.project_create, name="project_create"),
    path("projects/<int:project_id>/edit", views.project_edit, name="project_edit"),
    path("projects/<int:project_id>", views.project_detail, name="project"),
    # Workspaces ----------------------------------------------------------
    path("workspaces", views.workspaces, name="workspaces"),
    path("workspaces/new", views.workspace_create, name="workspace_create"),
    path("workspaces/<int:workspace_id>/edit", views.workspace_edit, name="workspace_edit"),
    path("workspaces/<int:workspace_id>/delete", views.workspace_delete, name="workspace_delete"),
    path(
        "workspaces/<int:workspace_id>/manager",
        views.workspace_manager_open,
        name="workspace_manager_open",
    ),
    path("workspaces/<int:workspace_id>", views.workspace_detail, name="workspace"),
    # Skills --------------------------------------------------------------
    path("skills", views.skills, name="skills"),
    path("skills/<int:skill_id>/edit", views.skill_edit, name="skill_edit"),
    path("skills/<int:skill_id>/delete", views.skill_delete, name="skill_delete"),
    path("skills/<int:skill_id>", views.skill_detail, name="skill"),
    # Cron ----------------------------------------------------------------
    path("cron", views.cronjobs, name="cron"),
    path("cron/new", views.cron_create, name="cron_create"),
    path("cron/<int:cron_id>", views.cron_detail, name="cronjob"),
    path("cron/<int:cron_id>/edit", views.cron_edit, name="cron_edit"),
    path("cron/<int:cron_id>/delete", views.cron_delete, name="cron_delete"),
    path("cron/<int:cron_id>/duplicate", views.cron_duplicate, name="cron_duplicate"),
    path("cron/<int:cron_id>/run", views.cron_run_now, name="cron_run_now"),
    path("cron/<int:cron_id>/toggle", views.cron_toggle, name="cron_toggle"),
    path(
        "cron/<int:cron_id>/calls/<int:call_id>/cancel",
        views.cron_call_cancel,
        name="cron_call_cancel",
    ),
    # Collections ---------------------------------------------------------
    path("collections", views.collections, name="collections"),
    path("collections/new", views.collection_create, name="collection_create"),
    path("collections/<int:collection_id>", views.collection_detail, name="collection"),
    path(
        "collections/<int:collection_id>/toggle",
        views.collection_toggle,
        name="collection_toggle",
    ),
    path(
        "collections/<int:collection_id>/edit",
        views.collection_edit,
        name="collection_edit",
    ),
    path(
        "collections/<int:collection_id>/delete",
        views.collection_delete,
        name="collection_delete",
    ),
    path(
        "collections/<int:collection_id>/reprocess",
        views.collection_reprocess,
        name="collection_reprocess",
    ),
    # Work items ----------------------------------------------------------
    path("workitems", views.workitems, name="workitems"),
    path("workitems/board", views.workitems_board, name="workitems_board"),
    path("workitems/new", views.workitem_create, name="workitem_create"),
    path("workitems/<int:workitem_id>", views.workitem_detail, name="workitem"),
    path(
        "workitems/<int:workitem_id>/action",
        views.workitem_action,
        name="workitem_action",
    ),
    path(
        "workitems/<int:workitem_id>/update",
        views.workitem_update,
        name="workitem_update",
    ),
    path(
        "workitems/<int:workitem_id>/delete",
        views.workitem_delete,
        name="workitem_delete",
    ),
    # Insights / logs / settings ------------------------------------------
    path("insights", views.insights, {"tab": "dashboard"}, name="insights"),
    path("insights/<str:tab>", views.insights, name="insights_tab"),
    path("insights/models/<int:model_id>/probe", views.model_probe, name="model_probe"),
    path(
        "insights/models/<int:model_id>/probe/status",
        views.model_probe_status,
        name="model_probe_status",
    ),
    path(
        "insights/models/<int:model_id>/detail",
        views.model_detail,
        name="model_detail",
    ),
    path(
        "insights/providers/<int:provider_id>/detail",
        views.provider_detail,
        name="provider_detail",
    ),
    path("logs", views.logs, name="logs"),
    path("logs/tail", views.logs_tail, name="logs_tail"),
    path("settings", views.settings_page, {"tab": "appearance"}, name="settings"),
    path("settings/<str:tab>", views.settings_page, name="settings_tab"),
    path("settings/<str:tab>/save", views.settings_save, name="settings_save"),
    path(
        "settings/providers/<int:provider_id>/key",
        views.settings_provider_key,
        name="settings_provider_key",
    ),
    path(
        "settings/providers/<int:provider_id>/test",
        views.settings_provider_test,
        name="settings_provider_test",
    ),

    # Memory --------------------------------------------------------------
    path("memory", views.memory, name="memory"),
    path("memory/<str:node_id>", views.memory_node, name="memory_node"),
    path("memory/improvements", views.memory_improvements, name="memory_improvements"),
    path(
        "memory/improvements/queue",
        views.memory_improvements_queue,
        name="memory_improvements_queue",
    ),
    path(
        "memory/node/<str:node_id>/queue",
        views.memory_node_queue,
        name="memory_node_queue",
    ),

]
