"""Memory: read-only view of synthesized memory nodes + improvement proposals."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from server.models.project import Project
from webui.core.assistants import assistant_overview_context
from webui.core.layout import render_page

from webui.features.memory.data import build_inventory, find_node


def _project_id(request) -> int | None:
    raw = (request.GET.get("project") or request.POST.get("project") or "").strip()
    return int(raw) if raw.isdigit() else None


def _inventory(project_id):
    return build_inventory(project_id=project_id)


def _memory_assistant(request, project_id: int | None) -> dict:
    """Memory pages share one scoped chat with the memory agent."""
    project = Project.objects.filter(pk=project_id).first() if project_id else None
    return assistant_overview_context(
        "memory", project, request.GET.get("assistant_session")
    )


MEMORY_FILTERS = (
    ("attention", "Needs attention"),
    ("all", "All nodes"),
)


def _filter_options(inventory):
    counts = {
        "all": len(inventory.nodes),
        "attention": sum(1 for node in inventory.nodes if _node_needs_attention(node)),
    }
    return tuple((key, label, counts[key]) for key, label in MEMORY_FILTERS)


def _node_needs_attention(node) -> bool:
    return bool(node.stale or node.errors)


def memory(request):
    project_id = _project_id(request)
    inventory = _inventory(project_id)
    errors = [f"{node.id}: {error}" for node in inventory.nodes for error in node.errors]

    node_filter = (request.GET.get("filter") or "attention").strip()
    if node_filter not in {key for key, _ in MEMORY_FILTERS}:
        node_filter = "attention"

    scopes = []
    for scope in inventory.scopes:
        nodes = [
            node
            for node in scope.nodes
            if node_filter == "all" or (node_filter == "attention" and _node_needs_attention(node))
        ]
        if nodes:
            scopes.append(replace(scope, nodes=nodes))

    filter_options = _filter_options(inventory)
    attention_count = dict((key, count) for key, _label, count in filter_options)["attention"]
    context = {
        "inventory": inventory,
        "scopes": scopes,
        "totals": inventory.totals,
        "warnings": inventory.warnings,
        "errors": errors,
        "attention_count": attention_count,
        "node_filter": node_filter,
        "node_filters": filter_options,
        "project_id": project_id,
        "projects": list(Project.objects.order_by("name")),
    }
    context.update(_memory_assistant(request, project_id))
    return render_page(request, "memory", "memory/list.html", context, active_id="overview")


def memory_playbook(request):
    project_id = _project_id(request)
    return redirect(f"/app/memory?{urlencode({'project': project_id})}" if project_id else "/app/memory")


def memory_node(request, node_id):
    project_id = _project_id(request)
    inventory = _inventory(project_id)
    node = find_node(inventory, node_id)
    if node is None:
        return redirect("webui:memory")
    tabs = (
        ("overview", "Overview"),
        ("facts", "Facts"),
        ("reflections", "Reflections"),
        ("sources", "Sources"),
    )
    tab = (request.GET.get("tab") or "overview").strip()
    if tab not in {key for key, _ in tabs}:
        tab = "overview"
    context = {
        "node": node,
        "inventory": inventory,
        "tab": tab,
        "tabs": tabs,
        "project_id": project_id,
        "projects": list(Project.objects.order_by("name")),
        "reflections_raw": node.read_reflections(),
        "sources_raw": node.read_sources_raw(),
    }
    context.update(_memory_assistant(request, project_id))
    return render_page(request, "memory", "memory/detail.html", context, active_id="overview")


@require_POST
def memory_node_queue(request, node_id):
    project_id = _project_id(request)
    return redirect(f"/app/memory/{node_id}?{urlencode({'project': project_id})}" if project_id else f"/app/memory/{node_id}")


def memory_improvements(request):
    project_id = _project_id(request)
    return redirect(f"/app/memory?{urlencode({'project': project_id})}" if project_id else "/app/memory")


@require_POST
def memory_improvements_queue(request):
    project_id = _project_id(request)
    return redirect(f"/app/memory?{urlencode({'project': project_id})}" if project_id else "/app/memory")
