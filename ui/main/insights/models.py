"""Models insight view — canonical model catalog as a table.

``AiModel`` rows are per-provider; this view groups them by canonical
identity (``canonical_id`` → ``leaderboard_id`` → ``name``) and shows one
row per model: size, capability modes, leaderboard rank, how many providers
serve it, and on how many of those we hold an API key.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.models.providers.ai_model import AiModel
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


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


class ModelsView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">Models</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Refresh" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content" style="max-width:1200px">
                <div class="analytics-card">
                    <div class="analytics-card-title">Model catalog</div>
                    <div class="analytics-card-sub">Grouped across providers — rank is the leaderboard position (~ marks an estimate)</div>
                    <table class="insights-table">
                        <thead><tr>
                            <th class="sortable" onclick="pyview.apply_sort('name')">Model{{ pyview.sort_arrow('name') }}</th>
                            <th class="sortable" onclick="pyview.apply_sort('params')">Params{{ pyview.sort_arrow('params') }}</th>
                            <th>Modes</th>
                            <th class="sortable" onclick="pyview.apply_sort('rank')">Rank{{ pyview.sort_arrow('rank') }}</th>
                            <th class="num sortable" onclick="pyview.apply_sort('providers')">Providers{{ pyview.sort_arrow('providers') }}</th>
                            <th class="num sortable" onclick="pyview.apply_sort('with_key')">With key{{ pyview.sort_arrow('with_key') }}</th>
                        </tr></thead>
                        <tbody>
                        {% for row in pyview.model_rows %}
                        <tr class="clickable{% if row.id == pyview._selected_id %} selected{% endif %}" onclick="pyview.open_model({{ row.id }})">
                            <td><strong>{{ row.name }}</strong>{% if row.developer %} <span class="muted">{{ row.developer }}</span>{% endif %}</td>
                            <td>{{ row.params }}</td>
                            <td>{% for mode in row.modes %}<span class="mode-badge">{{ mode }}</span>{% endfor %}{% if not row.modes %}<span class="muted">—</span>{% endif %}</td>
                            <td>{{ row.rank }}</td>
                            <td class="num">{{ row.providers }}</td>
                            <td class="num">{{ row.with_key }}</td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._sort_col = "rank"
        self._sort_desc = False
        self._selected_id: int | None = None

    def refresh(self) -> None:
        self.update()

    def open_model(self, model_id: int) -> None:
        from ui.main.rightpanel.model.rightpanel_model import RightPanelModel
        model = AiModel.objects.filter(pk=model_id).first()
        if model is None:
            return
        self._selected_id = model.pk
        self.parent.parent.rightpanel.set_view(RightPanelModel, model)
        self.update()

    def apply_sort(self, col: str) -> None:
        """Header click: toggle direction on repeat, else sort the column
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
                if m.api_provider.data.get("default_api_key")
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
