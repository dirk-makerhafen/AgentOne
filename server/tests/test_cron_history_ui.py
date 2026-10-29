"""Stub-render tests for the cron right-panel history tab (no DB)."""
from __future__ import annotations

from types import SimpleNamespace

import jinja2


def _entry(pk: int, status: str, can_cancel: bool) -> dict:
    return {
        "pk": pk,
        "status": status,
        "badge": "",
        "since": "now",
        "can_cancel": can_cancel,
    }


def _render(entries) -> str:
    from ui.main.rightpanel.cron.rightpanel_cron_history import (
        RightPanelCronHistory,
    )

    env = jinja2.Environment(autoescape=True)
    return env.from_string(RightPanelCronHistory.TEMPLATE_STR).render(
        pyview=SimpleNamespace(entries=entries)
    )


class TestCronHistoryTemplate:
    def test_cancel_button_rendered_for_running_and_waiting_runs(self):
        html = _render([
            _entry(7, "WAITING", True),
            _entry(8, "ACTIVE", True),
        ])
        assert "cancelCall(7)" in html
        assert "cancelCall(8)" in html

    def test_no_cancel_button_for_finished_runs(self):
        html = _render([_entry(9, "ENDED", False)])
        assert "cancelCall(9)" not in html

    def test_empty_state(self):
        assert "No executions yet." in _render([])
