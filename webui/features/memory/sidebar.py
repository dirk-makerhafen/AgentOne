import logging

log = logging.getLogger(__name__)


def build_sidebar_context(request, project_id, ctx):
    from runtime.memory_improvements import queued_work_items
    from webui.features.memory.data import build_inventory, unique_proposals

    try:
        inventory = build_inventory(project_id=project_id)
        proposals = unique_proposals(inventory.nodes)
        queued = queued_work_items()
        queued_count = sum(1 for p in proposals if str(p.get("fingerprint")) in queued)
        ctx.update(
            {
                "memory_scopes": inventory.scopes,
                "memory_totals": inventory.totals,
                "memory_proposals_count": len(proposals),
                "memory_queued_count": queued_count,
            }
        )
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("Failed to build memory sidebar context")
        ctx.update(
            {
                "memory_scopes": [],
                "memory_totals": {"nodes": 0, "pending": 0},
                "memory_proposals_count": 0,
                "memory_queued_count": 0,
            }
        )


def sidebar_keys(context):
    return ("Project", "WorkItem")


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("memory", sidebar_keys)
