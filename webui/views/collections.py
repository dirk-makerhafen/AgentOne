"""Data collections (streams and ordered sets)."""

from __future__ import annotations

import json

from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from server.models.collections.data_collection import DataCollection
from server.models.project import Project
from webui.views.common import render_page


def collections(request):
    rows = list(
        DataCollection.objects.select_related("parent_project")
        .annotate(item_total=Count("items"))
        .order_by("name")
    )
    context = {
        "collections": rows,
        "projects": list(Project.objects.order_by("name")),
        "error": request.GET.get("error", ""),
    }
    return render_page(request, "collections", "webui/collections/list.html", context)


@require_POST
def collection_create(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        return redirect("webui:collections")
    raw_project = request.POST.get("parent_project", "")
    project = (
        Project.objects.filter(pk=int(raw_project)).first()
        if raw_project.isdigit()
        else None
    )
    collection_type = request.POST.get("collection_type") or "stream"
    if collection_type not in ("stream", "set"):
        collection_type = "stream"
    try:
        collection = DataCollection.objects.create(
            name=name,
            description=(request.POST.get("description") or "").strip(),
            collection_type=collection_type,
            parent_project=project,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return redirect("/app/collections?error=duplicate")
    return redirect("webui:collection", collection_id=collection.pk)


def _json_text(value) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def collection_detail(request, collection_id: int):
    collection = get_object_or_404(
        DataCollection.objects.select_related("parent_project"), pk=collection_id
    )
    items = list(
        collection.items.select_related("source_call").order_by("-pk")[:60]
    )
    for item in items:
        item.value_json = _json_text(item.value)
    context = {
        "collection": collection,
        "items": items,
        "derived_flows": _derived_flows(collection),
        "projects": list(Project.objects.order_by("name")),
        "sources_json": _json_text(collection.sources),
        "processor_json": _json_text(collection.processor),
        "on_removed_json": _json_text(collection.on_removed),
        "error": request.GET.get("error", ""),
        "reprocessed": request.GET.get("reprocessed") == "1",
    }
    return render_page(request, "collections", "webui/collections/detail.html", context,
                       active_id=collection.pk)


def _derived_flows(collection: DataCollection) -> list[DataCollection]:
    """Find active flows that consume this collection as a stream or set."""
    derived = []
    for candidate in DataCollection.objects.filter(is_active=True).exclude(
        pk=collection.pk
    ).order_by("name"):
        for source in candidate.sources or []:
            source_type = source.get("type")
            if source_type in ("stream", "set") and source.get(source_type) == collection.name:
                derived.append(candidate)
                break
    return derived


def _parse_json(raw: str):
    """Parse a JSON form field, returning ``(value, error)``."""
    raw = (raw or "").strip()
    if not raw:
        return None, False
    try:
        return json.loads(raw), False
    except (TypeError, ValueError):
        return None, True


@require_POST
def collection_edit(request, collection_id: int):
    collection = get_object_or_404(DataCollection, pk=collection_id)
    name = (request.POST.get("name") or "").strip()
    if not name:
        return redirect(f"/app/collections/{collection.pk}?error=name")

    collection_type = request.POST.get("collection_type") or "stream"
    if collection_type not in ("stream", "set"):
        collection_type = "stream"

    sources, sources_error = _parse_json(request.POST.get("sources") or "")
    processor, processor_error = _parse_json(request.POST.get("processor") or "")
    on_removed, removed_error = _parse_json(request.POST.get("on_removed") or "")
    if sources_error or processor_error or removed_error:
        return redirect(f"/app/collections/{collection.pk}?error=json")
    if sources is not None and not isinstance(sources, list):
        return redirect(f"/app/collections/{collection.pk}?error=json")
    if processor is not None and not isinstance(processor, dict):
        return redirect(f"/app/collections/{collection.pk}?error=json")
    if on_removed is not None and not isinstance(on_removed, dict):
        return redirect(f"/app/collections/{collection.pk}?error=json")

    try:
        retroactive = int(request.POST.get("retroactive_on_source_change") or 0)
    except ValueError:
        retroactive = collection.retroactive_on_source_change
    try:
        max_reprocess = int(request.POST.get("max_reprocess") or 0)
    except ValueError:
        max_reprocess = collection.max_reprocess

    collection.name = name
    collection.description = (request.POST.get("description") or "").strip()
    collection.collection_type = collection_type
    collection.is_active = request.POST.get("is_active") == "on"
    collection.sources = sources if sources is not None else []
    collection.processor = processor if processor is not None else {}
    collection.on_removed = on_removed if on_removed is not None else {}
    collection.member_field = (request.POST.get("member_field") or "").strip()
    collection.score_field = (request.POST.get("score_field") or "").strip()
    collection.retroactive_on_source_change = max(retroactive, 0)
    collection.max_reprocess = max(max_reprocess, 0)
    try:
        collection.save()
    except Exception:  # pylint: disable=broad-exception-caught
        return redirect(f"/app/collections/{collection.pk}?error=save")
    return redirect("webui:collection", collection_id=collection.pk)


@require_POST
def collection_delete(request, collection_id: int):
    collection = get_object_or_404(DataCollection, pk=collection_id)
    collection.delete()
    return redirect("webui:collections")


@require_POST
def collection_reprocess(request, collection_id: int):
    collection = get_object_or_404(DataCollection, pk=collection_id)
    from server.tasks.reprocess_collection import reprocess_collection

    try:
        reprocess_collection.delay(collection.name)
    except Exception:  # pylint: disable=broad-exception-caught
        return redirect(f"/app/collections/{collection.pk}?error=reprocess")
    return redirect(f"/app/collections/{collection.pk}?reprocessed=1")


@require_POST
def collection_toggle(request, collection_id: int):
    collection = get_object_or_404(DataCollection, pk=collection_id)
    collection.is_active = not collection.is_active
    collection.save(update_fields=["is_active"])
    return redirect("webui:collection", collection_id=collection.pk)
