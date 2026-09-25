"""Stub-render + wiring tests for the settings providers rightbar detail (no DB)."""
from __future__ import annotations
from types import SimpleNamespace

import jinja2


def _render(template_str, **context):
    env = jinja2.Environment(autoescape=True)
    return env.from_string(template_str).render(**context)


def _row(pk, **overrides):
    base = dict(
        id=pk, name=f"P{ pk }", is_local=False, model_count=3,
        limits="10 RPM", key_state="keys", key_count=1,
        description="A provider", api_key_url="", setup_instructions="",
    )
    base.update(overrides)
    return base


def _panel_pyview(**overrides):
    base = dict(
        provider_rows=[_row(1), _row(2, key_state="none", description="No key yet")],
        _expanded_id=None, _detail_id=None, expanded_keys=[],
        key_visibility_btn="Reveal all", input_type="password", uid="t1",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestProvidersTableDetail:
    def test_rows_open_detail_in_rightbar(self):
        from ui.main.settings.panels.providers import SettingPanelProviders

        html = _render(SettingPanelProviders.TEMPLATE_STR, pyview=_panel_pyview())
        assert "open_provider(1)" in html
        assert "open_provider(2)" in html
        assert "clickable" in html

    def test_detail_row_highlighted(self):
        from ui.main.settings.panels.providers import SettingPanelProviders

        html = _render(
            SettingPanelProviders.TEMPLATE_STR, pyview=_panel_pyview(_detail_id=2)
        )
        assert html.count("selected") >= 1

    def test_action_buttons_do_not_trigger_row(self):
        from ui.main.settings.panels.providers import SettingPanelProviders

        html = _render(SettingPanelProviders.TEMPLATE_STR, pyview=_panel_pyview())
        assert "event.stopPropagation(); pyview.open_add(2)" in html
        assert "event.stopPropagation(); pyview.toggle_expanded(1)" in html

    def test_find_rightpanel_walks_parents(self):
        from ui.main.settings.panels.providers import SettingPanelProviders

        sentinel = object()
        root = SimpleNamespace(parent=None, rightpanel=sentinel)
        main = SimpleNamespace(parent=root)
        settings = SimpleNamespace(parent=main)
        view = object.__new__(SettingPanelProviders)
        view._parent_ref = settings
        assert view._find_rightpanel() is sentinel

    def test_find_rightpanel_none_without_chain(self):
        from ui.main.settings.panels.providers import SettingPanelProviders

        view = object.__new__(SettingPanelProviders)
        view._parent_ref = SimpleNamespace(parent=None)
        assert view._find_rightpanel() is None


class TestProviderDetailDescription:
    def _detail(self, data, url="https://example.com"):
        from ui.main.rightpanel.provider.rightpanel_provider import RightPanelProvider

        view = object.__new__(RightPanelProvider)
        view._subject_ref = SimpleNamespace(data=data, url=url)
        return view

    def test_prefers_description(self):
        d = self._detail({"description": "Full blurb here."})
        assert d.full_description == "Full blurb here."

    def test_falls_back_to_setup_then_url(self):
        assert self._detail({"setup_instructions": "1. Sign up"}).full_description == "1. Sign up"
        assert self._detail({}).full_description == "https://example.com"

    def test_template_has_about_section(self):
        from ui.main.rightpanel.provider.rightpanel_provider import RightPanelProvider

        assert "About" in RightPanelProvider.TEMPLATE_STR
        assert "full_description" in RightPanelProvider.TEMPLATE_STR


class TestSectionSwitchClearsDetail:
    def test_leaving_providers_closes_rightbar(self):
        from ui.main.settings.settings import SettingsView

        calls = []
        providers_panel = SimpleNamespace(
            clear_detail=lambda: calls.append("clear"),
        )
        rightpanel = SimpleNamespace(close=lambda: calls.append("close"))
        main = SimpleNamespace(rightpanel=rightpanel)
        view = object.__new__(SettingsView)
        view._parent_ref = main
        view.settings_sections = {"providers": providers_panel, "system": object()}
        view.update = lambda: None
        view.switchSettingsSection("system")
        assert calls == ["clear", "close"]
        assert view.selected_settings_panel_name == "system"
