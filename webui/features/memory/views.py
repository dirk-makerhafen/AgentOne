"""Memory: read-only view of synthesized memory nodes + improvement proposals."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from server.models.project import Project
from webui.core.layout import render_page

from webui.features.memory.data import (
    build_inventory,
    effective_directives,
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


MEMORY_FILTERS = (
    ("attention", "Needs attention"),
    ("all", "All nodes"),
    ("proposals", "Has proposals"),
)


def _filter_options(inventory):
    counts = {
        "all": len(inventory.nodes),
        "attention": sum(1 for node in inventory.nodes if _node_needs_attention(node)),
        "proposals": sum(1 for node in inventory.nodes if node.open_proposals),
    }
    return tuple((key, label, counts[key]) for key, label in MEMORY_FILTERS)


def _node_needs_attention(node) -> bool:
    return bool(node.stale or node.errors or node.open_proposals)


def memory(request):
    project_id = _project_id(request)
    inventory = _inventory(project_id)
    proposals = unique_proposals(inventory.nodes)
    queued = _queued()
    queued_count = sum(1 for p in proposals if str(p.get("fingerprint")) in queued)
    errors = [f"{node.id}: {error}" for node in inventory.nodes for error in node.errors]

    node_filter = (request.GET.get("filter") or "attention").strip()
    if node_filter not in {key for key, _ in MEMORY_FILTERS}:
        node_filter = "attention"

    # One compact tree table instead of a separate "needs attention" list +
    # a second full tree.  The filter just decides which rows to show.
    scopes = []
    for scope in inventory.scopes:
        nodes = [
            node
            for node in scope.nodes
            if (
                node_filter == "all"
                or (node_filter == "attention" and _node_needs_attention(node))
                or (node_filter == "proposals" and node.open_proposals)
            )
        ]
        if nodes:
            scopes.append(replace(scope, nodes=nodes))

    filter_options = _filter_options(inventory)
    attention_count = dict((key, count) for key, _label, count in filter_options)[
        "attention"
    ]
    queued_param = request.GET.get("queued", "")
    message = f"Filed {queued_param} proposal(s) as backlog work items." if queued_param else ""
    context = {
        "inventory": inventory,
        "scopes": scopes,
        "totals": inventory.totals,
        "warnings": inventory.warnings,
        "errors": errors,
        "proposals_count": len(proposals),
        "queued_count": queued_count,
        "active_directives": len(
            effective_directives(inventory.nodes, "active", injectable_only=True)
        ),
        "attention_count": attention_count,
        "node_filter": node_filter,
        "node_filters": filter_options,
        "project_id": project_id,
        "projects": list(Project.objects.order_by("name")),
        "queued_param": queued_param,
        "message": message,
        "message_ok": True,
    }
    return render_page(request, "memory", "memory/list.html", context, active_id="overview")


def memory_playbook(request):
    """The effective playbook: active directives, deduped across layers."""
    project_id = _project_id(request)
    inventory = _inventory(project_id)
    search = (request.GET.get("search") or "").strip().lower()

    def _filter(rows):
        if not search:
            return rows
        return [
            row
            for row in rows
            if search
            in " ".join(
                str(row.get(key) or "")
                for key in ("rule", "trigger", "id", "fingerprint", "routing", "source", "layer")
            ).lower()
        ]

    active_all = effective_directives(inventory.nodes, "active", injectable_only=True)
    candidates_all = effective_directives(
        inventory.nodes, "candidate", injectable_only=True
    )
    active = _filter(active_all)
    candidates = _filter(candidates_all)
    retired_count = sum(
        1
        for node in inventory.nodes
        for item in node.directives
        if str(item.get("status") or "") == "retired"
    )
    context = {
        "inventory": inventory,
        "totals": inventory.totals,
        "active": active,
        "candidates": candidates,
        "active_count": len(active_all),
        "candidate_count": len(candidates_all),
        "retired_count": retired_count,
        "search": request.GET.get("search") or "",
        "filtering": bool(search),
        "project_id": project_id,
        "projects": list(Project.objects.order_by("name")),
    }
    return render_page(
        request, "memory", "memory/playbook.html", context, active_id="playbook"
    )


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
    try:
        improvements_raw = node.improvements_path.read_text(encoding="utf-8") if node.improvements_path.is_file() else ""
    except Exception:
        improvements_raw = ""
    qp = request.GET.get("queued", "")
    tabs = (
        ("overview", "Overview"),
        ("facts", "Facts"),
        ("rules", "Rules"),
        ("proposals", "Proposals"),
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
        "proposal_rows": proposal_rows,
        "open_proposal_count": open_proposal_count,
        "queueable_count": queueable_count,
        "queued_param": qp,
        "project_id": project_id,
        "projects": list(Project.objects.order_by("name")),
        "reflection_raw": node.read_reflection(),
        "sources_raw": node.read_sources_raw(),
        "improvements_raw": improvements_raw,
        "message": f"Filed {qp} proposal(s) as backlog work items." if qp else "",
        "message_ok": True,
    }
    return render_page(
        request, "memory", "memory/detail.html", context, active_id="overview"
    )


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
    tab = (request.POST.get("tab") or "").strip()
    if tab:
        params["tab"] = tab
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
    qp = request.GET.get("queued", "")
    context["message"] = f"Filed {qp} proposal(s) as backlog work items." if qp else ""
    context["message_ok"] = True
    return render_page(request, "memory", "memory/improvements.html", context, active_id="improvements")


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
