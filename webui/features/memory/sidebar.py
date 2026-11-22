import logging

log = logging.getLogger(__name__)


def build_sidebar_context(request, project_id, ctx):
    from webui.features.memory.data import build_inventory

    empty = {"memory_totals": {"nodes": 0, "stale": 0, "attention": 0}}
    try:
        inventory = build_inventory(project_id=project_id)
        ctx.update(
            {
                "memory_totals": {
                    **inventory.totals,
                    "attention": sum(1 for node in inventory.nodes if node.stale or node.errors),
                }
            }
        )
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("Failed to build memory sidebar context")
        ctx.update(empty)


def sidebar_keys(context):
    return ("Project", "WorkItem")


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("memory", sidebar_keys)
