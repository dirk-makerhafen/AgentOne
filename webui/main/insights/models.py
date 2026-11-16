"""Model insight data helpers.

Computes a grouped/canonical model catalog across providers. The Django/htmx web UI renders
this via ``webui.views.insights`` + ``webui/templates/webui/insights/page.html``; this module
keeps the shared/sortable data logic (also exercised by ``server.tests.test_insight_tables``).
"""
from __future__ import annotations

from server.models.providers.ai_model import AiModel


MODE_LABELS = (
    ("supports_reasoning", "Reason"),
    ("supports_tool_call", "Tools"),
    ("vision", "Vision"),
    ("audio", "Audio"),
    ("video", "Video"),
)


def _params_str(total_parameters: float | None) -> str:
    if not total_parameters:
        return "—"
    if float(total_parameters) >= 1:
        return f"{total_parameters:g}B"
    return f"{float(total_parameters) * 1000:g}M"


def _rank_str(rank: int | None, is_estimate: bool) -> str:
    if rank is None:
        return "—"
    return f"~{rank}" if is_estimate else f"#{rank}"


class ModelsView:
    """Sortable model catalog data (no UI rendering)."""

    def __init__(self, *args, **kwargs):
        self._sort_col = "rank"
        self._sort_desc = False
        self._selected_id: int | None = None

    def update(self) -> None:
        """UI refresh hook (no-op outside pyHtmlGui)."""

    def apply_sort(self, col: str) -> None:
        """Toggle direction on repeat, else sort the column
        (names ascending, numbers descending)."""
        if col == self._sort_col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = col != "name"
        self.update()

    def sort_arrow(self, col: str) -> str:
        if col != self._sort_col:
            return ""
        return " ▼" if self._sort_desc else " ▲"

    @property
    def model_rows(self) -> list[dict]:
        groups: dict[str, dict] = {}
        qs = (
            AiModel.objects.filter(enabled=True, api_provider__enabled=True)
            .select_related("api_provider")
            .prefetch_related("api_provider__api_keys")
            .order_by("name")
        )
        for model in qs:
            key = model.canonical_id or model.leaderboard_id or model.name
            group = groups.setdefault(key, {"rows": []})
            group["rows"].append(model)

        rows = []
        for group in groups.values():
            members = group["rows"]
            first = members[0]
            ranks = [(m.leaderboard_rank, m.leaderboard_rank_is_estimate)
                     for m in members if m.leaderboard_rank is not None]
            best = min(ranks) if ranks else (None, False)
            provider_ids = {m.api_provider_id for m in members}
            # Distinct providers with a key (a model may repeat per provider).
            keyed_providers = {
                m.api_provider_id for m in members
                if m.api_provider.default_api_key
                or any(k.enabled for k in m.api_provider.api_keys.all())
            }
            rows.append({
                "id": first.pk,
                "name": first.name,
                "developer": first.developer,
                "_params": max((m.total_parameters or 0) for m in members),
                "modes": [label for field, label in MODE_LABELS
                          if any(getattr(m, field, False) for m in members)],
                "_rank": best[0],
                "_is_estimate": best[1],
                "_providers": len(provider_ids),
                "_with_key": len(keyed_providers),
            })

        col = self._sort_col
        desc = self._sort_desc
        if col == "rank":
            # Unranked always sorts last, either direction.
            ranked = sorted(
                (r for r in rows if r["_rank"] is not None),
                key=lambda r: r["_rank"], reverse=desc,
            )
            rows = ranked + [r for r in rows if r["_rank"] is None]
        elif col in ("params", "providers", "with_key"):
            rows.sort(key=lambda r: r[f"_{col}"], reverse=desc)
        else:
            rows.sort(key=lambda r: r["name"].lower(), reverse=desc)
        for row in rows:
            row["params"] = _params_str(row.pop("_params") or None)
            row["rank"] = _rank_str(row.pop("_rank"), row.pop("_is_estimate"))
            row["providers"] = row.pop("_providers")
            row["with_key"] = row.pop("_with_key")
        return rows
