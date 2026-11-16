"""Memory: read-only view of synthesized memory nodes + improvement proposals."""

from __future__ import annotations

from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, redirect
from types import SimpleNamespace
from django.views.decorators.http import require_POST

from server.models.project import Project
from webui.views.common import render_page

from ui.main.memory.memory_data import (
    build_inventory,
    find_node,
    unique_proposals,
)
from runtime.memory_improvements import (
    queued_work_items,
    queue_proposals,
)


def _project_id(request) -> int | None:
    raw = (request.GET.get("project") or request.POST.get("project") or "").strip()
    return int(raw) if raw.isdigit() else None


def _inventory(project_id):
    return build_inventory(project_id=project_id)


def _queued():
    return queued_work_items()


def _proposal_rows(inventory, queued):
    rows = []
    for proposal in unique_proposals(inventory.nodes):
        fp = str(proposal.get("fingerprint") or "")
        item = queued.get(fp)
        queueable = bool(fp) and proposal.get("kind") in (
            "prompt", "system_prompt", "skill", "tool", "script", "harness"
        ) and proposal.get("status") != "retired"
        rows.append({**proposal, "queued": item, "queueable": queueable})
    return rows


def memory(request):
    project_id = _project_id(request)
    inventory = _inventory(project_id)
    proposals = unique_proposals(inventory.nodes)
    queued = _queued()
    queued_count = sum(1 for p in proposals if str(p.get("fingerprint")) in queued)
    errors = []
    for node in inventory.nodes:
        for error in node.errors:
            errors.append(f"{node.id}: {error}")
    context = {
        "inventory": inventory,
        "scopes": inventory.scopes,
        "totals": inventory.totals,
        "stale_nodes": inventory.stale_nodes,
        "warnings": inventory.warnings,
        "errors": errors,
        "proposals_count": len(proposals),
        "queued_count": queued_count,
        "project_id": project_id,
        "projects": list(Project.objects.order_by("name")),
        "queued_param": request.GET.get("queued", ""),
    }
    context["pyview"] = SimpleNamespace(**{k: v for k, v in context.items() if k != "pyview"})
    return render_page(request, "memory", "webui/memory/overview.html", context)


def memory_node(request, node_id):
    project_id = _project_id(request)
    inventory = _inventory(project_id)
    node = find_node(inventory, node_id)
    if node is None:
        inventory = _inventory(None)
        node = find_node(inventory, node_id)
    if node is None:
        return redirect("webui:memory")
    queued = _queued()
    proposal_rows = []
    for proposal in node.proposals:
        fp = str(proposal.get("fingerprint") or "")
        proposal_rows.append(
            {
                **proposal,
                "path": node.improvements_path.as_posix(),
                "queued": queued.get(fp),
                "queueable": bool(fp)
                and proposal.get("kind")
                in ("prompt", "system_prompt", "skill", "tool", "script", "harness"),
            }
        )
    open_proposal_count = len(
        [row for row in proposal_rows if row.get("status") != "retired"]
    )
    queueable_count = len(
        [
            row
            for row in proposal_rows
            if row["queueable"] and not row["queued"] and row.get("status") != "retired"
        ]
    )
    context = {
        "node": node,
        "inventory": inventory,
        "proposal_rows": proposal_rows,
        "open_proposal_count": open_proposal_count,
        "queueable_count": queueable_count,
        "queued_param": request.GET.get("queued", ""),
        "project_id": project_id,
        "projects": list(Project.objects.order_by("name")),
    }
    context["pyview"] = SimpleNamespace(**{k: v for k, v in context.items() if k != "pyview"})
    return render_page(request, "memory", "webui/memory/node.html", context)


@require_POST
def memory_node_queue(request, node_id):
    inventory = _inventory(None)
    node = find_node(inventory, node_id)
    if node is None:
        return redirect("webui:memory")

    fingerprints = request.POST.getlist("fingerprint")
    if not fingerprints:
        single = (request.POST.get("fingerprint") or "").strip()
        if single:
            fingerprints = [single]
    if request.POST.get("all") == "1":
        fingerprints = None

    proposals = [
        {**{k: v for k, v in proposal.items()}, "path": node.improvements_path.as_posix()}
        for proposal in node.proposals
    ]
    project = None
    pid = node.scope.project_id
    if pid is not None:
        project = Project.objects.filter(pk=pid).first()

    existing = _queued()
    created, skipped = queue_proposals(
        proposals, project=project, fingerprints=fingerprints, existing=existing
    )
    params = {"queued": len(created)}
    if skipped and not created:
        params["error"] = skipped[0].get("reason", "nothing")
    url = reverse_url("webui:memory_node", node_id)
    return redirect(f"{url}?{urlencode(params)}")


def reverse_url(name, *args, **kwargs):
    from django.urls import reverse

    return reverse(name, args=args, kwargs=kwargs)


def memory_improvements(request):
    project_id = _project_id(request)
    inventory = _inventory(project_id)
    queued = _queued()
    rows = _proposal_rows(inventory, queued)

    kind_filter = (request.GET.get("kind") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    scope_filter = (request.GET.get("scope") or "").strip()
    search = (request.GET.get("search") or "").strip()
    hide_queued = request.GET.get("hide_queued") == "1"

    filtered = []
    for row in rows:
        if kind_filter and row.get("kind") != kind_filter:
            continue
        if status_filter and row.get("status") != status_filter:
            continue
        if scope_filter:
            source = str(row.get("source") or "")
            if not source.lower().startswith(scope_filter.lower()):
                continue
        if search:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in ("summary", "detail", "id", "source", "node_label", "trigger")
            ).lower()
            if search.lower() not in haystack:
                continue
        if hide_queued and row.get("queued"):
            continue
        filtered.append(row)

    kind_options = sorted({str(r.get("kind")) for r in rows if r.get("kind")})
    status_options = sorted({str(r.get("status")) for r in rows if r.get("status")})
    scope_options = sorted(
        {str(r.get("source") or "").split("·")[0].strip().lower() for r in rows}
    )

    counts = {
        "total": len(filtered),
        "queued": sum(1 for r in filtered if r.get("queued")),
        "queueable": sum(
            1
            for r in filtered
            if not r.get("queued")
            and r.get("kind")
            in ("prompt", "system_prompt", "skill", "tool", "script", "harness")
            and r.get("status") != "retired"
        ),
    }

    context = {
        "inventory": inventory,
        "proposals": filtered,
        "all_proposals": rows,
        "kind_options": kind_options,
        "status_options": status_options,
        "scope_options": scope_options,
        "kind_filter": kind_filter,
        "status_filter": status_filter,
        "scope_filter": scope_filter,
        "search": search,
        "hide_queued": hide_queued,
        "counts": counts,
        "project_id": project_id,
        "projects": list(Project.objects.order_by("name")),
        "queued_param": request.GET.get("queued", ""),
    }
    context["pyview"] = SimpleNamespace(**{k: v for k, v in context.items() if k != "pyview"})
    return render_page(request, "memory", "webui/memory/improvements.html", context)


@require_POST
def memory_improvements_queue(request):
    project_id = _project_id(request)
    inventory = _inventory(project_id)
    queued_before = _queued()
    rows = _proposal_rows(inventory, queued_before)

    fingerprints = request.POST.getlist("fingerprint")
    if not fingerprints:
        single = (request.POST.get("fingerprint") or "").strip()
        if single:
            fingerprints = [single]
    queue_all = request.POST.get("all") == "1"

    # Group proposals by owning project so each work item lands in the right scope.
    groups: dict = {}
    for row in rows:
        if not queue_all and fingerprints and str(row.get("fingerprint")) not in fingerprints:
            continue
        if row.get("queued"):
            continue
        pid = row.get("project_id")
        if pid is None:
            pid = project_id
        project = Project.objects.filter(pk=pid).first() if pid is not None else None
        groups.setdefault(id(project), (project, []))[1].append(row)

    existing = queued_before
    created = []
    skipped = []
    for project, ps in groups.values():
        c, s = queue_proposals(ps, project=project, existing=existing)
        created.extend(c)
        skipped.extend(s)

    params = {"queued": len(created)}
    if skipped and not created:
        params["error"] = skipped[0].get("reason", "nothing")
    base = reverse_url("webui:memory_improvements")
    if project_id is not None:
        params["project"] = project_id
    return redirect(f"{base}?{urlencode(params)}")