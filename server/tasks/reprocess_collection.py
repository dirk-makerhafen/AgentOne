"""Celery task to reprocess a data collection's source items through its processor.

For **sets**: uses per-source-call diffing — runs the processor for each source
call, compares old vs new result, and only cascades deletions downstream for
items that actually changed (member changed or processor returned None).

No wholesale delete: items whose source call produces the same member are
updated in place without triggering downstream work.
"""
from __future__ import annotations

from celery import shared_task


def _cascade_deletion(removed_items: list) -> None:
    """Walk ``source_item`` links and delete downstream items recursively.

    For each downstream collection that loses items, fires ``on_removed``.
    """
    from server.models.collections import DataCollection, CollectionItem

    queue = list(removed_items)
    per_collection_calls: dict[int, set] = {}

    while queue:
        item = queue.pop()
        downstream = list(
            CollectionItem.objects.filter(source_item=item)
            .select_related("source_call")
        )
        queue.extend(downstream)

        for d_item in downstream:
            col_id = d_item.collection_id
            if d_item.source_call:
                per_collection_calls.setdefault(col_id, set()).add(d_item.source_call)

        if downstream:
            pks = [d.pk for d in downstream]
            CollectionItem.objects.filter(pk__in=pks).delete()

    from server.tasks.tick_scheduler import _trigger_on_removed
    for col_id, calls in per_collection_calls.items():
        col = DataCollection.objects.get(pk=col_id)
        _trigger_on_removed(col, list(calls))


@shared_task(name="tasks.reprocess_collection")
def reprocess_collection(collection_name: str, max_items: int = 0) -> None:
    """Reprocess source items for *collection_name* through its processor.

    For **query-type sources**: finds matching ``AgentTaskCall`` records and
    re-dispatches them.

    For **stream/set-type sources**: reads the source collection's
    ``CollectionItem`` records and re-dispatches their ``source_call``
    through this collection's processor.

    For **sets** (``collection_type == \"set\"``): per-source-call diffing.
    The processor is run for each source call; if the result differs from the
    existing item (different member, or None where an item previously existed),
    the old item is removed and cascaded downstream.
    """
    from server.models.collections import DataCollection, CollectionItem
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail
    from server.tasks.tick_scheduler import (
        _matches_data_flow_source,
        _dispatch_processor,
        _trigger_on_removed,
    )

    try:
        collection = DataCollection.objects.get(name=collection_name)
    except DataCollection.DoesNotExist:
        print(f"[reprocess] collection '{collection_name}' not found")
        return

    limit = max_items or collection.max_reprocess or 0

    # ── Gather source items ─────────────────────────────────────────────
    source_calls: list[AgentTaskCall] = []
    for source_def in collection.sources or []:
        src_type = source_def.get("type", "query")

        if src_type == "query":
            qs = AgentTaskCall.objects.filter(
                status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
            ).select_related(
                "session",
                "task_instance__task_definition_version__task_definition__parent_agent",
                "session_version__agent__parent_project",
            ).order_by("-pk")

            matched = [c for c in qs if _matches_data_flow_source(c, source_def)]
            source_calls.extend(matched)

        elif src_type in ("stream", "set"):
            source_name = source_def.get(src_type, "")
            if not source_name:
                continue
            try:
                source_col = DataCollection.objects.get(name=source_name)
            except DataCollection.DoesNotExist:
                print(f"[reprocess] source collection '{source_name}' not found")
                continue
            items_qs = CollectionItem.objects.filter(
                collection=source_col,
            ).select_related("source_call").order_by("-pk")
            if limit:
                items_qs = items_qs[:limit]
            for item in items_qs:
                if item.source_call:
                    source_calls.append(item.source_call)

    if limit and len(source_calls) > limit:
        source_calls = source_calls[:limit]

    if not source_calls:
        print(f"[reprocess] no source items found for '{collection_name}'")
        return

    # ── Per-source-call processing (sets) or simple dispatch (streams) ──
    is_set = collection.collection_type == "set"
    removed: list[CollectionItem] = []

    if is_set:
        # Snapshot existing items before any changes
        existing = list(
            CollectionItem.objects.filter(collection=collection)
            .select_related("source_call")
            .order_by("pk")
        )
        old_by_member = {item.member: item for item in existing}
        new_members: set[str] = set()

    for call in source_calls:
        if is_set:
            member = _dispatch_processor(collection, call)
            if member is not None:
                new_members.add(member)
        else:
            _dispatch_processor(collection, call)

    # ── For sets: detect removals, cascade, fire on_removed ────────────
    if is_set:
        for member, item in old_by_member.items():
            if member not in new_members and item.source_call:
                removed.append(item)

        if removed:
            _cascade_deletion(removed)
            removed_calls = [item.source_call for item in removed]
            _trigger_on_removed(collection, removed_calls)

            rm_pks = [r.pk for r in removed]
            CollectionItem.objects.filter(pk__in=rm_pks).delete()

    print(
        f"[reprocess] '{collection_name}': {len(source_calls)} source items processed, "
        f"{len(removed)} removed"
    )
