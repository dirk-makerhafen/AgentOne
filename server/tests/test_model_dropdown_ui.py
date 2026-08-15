"""Tests for the grouped composer model dropdown.

Validates that clicking a group resolves a concrete (provider, model) row and
pins the session to it via the existing copy-on-write settings path.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from django.test import TestCase

from runtime.session.aimodel_picker import ModelGroup
from runtime.session.session import Session

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel

from ui.main.chat.composer.dropdown.model import ModelDropdown, ModelDropdownOption


class MockFooter:
    """Minimal ComposerFooter stand-in for ModelDropdown's parent interface."""

    def __init__(self):
        self._instance = MagicMock()
        self.model_wrap = MagicMock()

    def _add_child(self, child):
        pass

    def close_dropdowns(self):
        pass


class ModelDropdownTest(TestCase):
    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        self.p2 = ApiProvider.objects.create(name="p2")
        self.keyless = ApiProvider.objects.create(name="keyless")
        ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)
        ApiKey.objects.create(api_provider=self.p2, key="k2", enabled=True)
        self.alpha_sql = AiModel.objects.create(
            api_provider=self.p1, name="Alpha", provider_model_id="sql-alpha"
        )
        self.alpha_apisql = AiModel.objects.create(
            api_provider=self.p2, name="Alpha", provider_model_id="apisql-alpha"
        )
        self.alpha_keyless = AiModel.objects.create(
            api_provider=self.keyless, name="Alpha", provider_model_id="keyless-alpha"
        )
        AiModel.objects.create(
            api_provider=self.p1, name="Beta", provider_model_id="beta"
        )

        self.agent = AgentModel.objects.create(name="dropdown-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="dropdown-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()
        AgentModel.objects.filter(pk=self.agent.pk).update(latest_agent_version=self.av)

    def test_groups_become_single_options(self):
        dropdown = ModelDropdown(subject=Session(session_model=self.session), parent=MockFooter())
        names = {g.name for g in dropdown.model_list.query}
        self.assertIn("Alpha", names)
        alpha = next(g for g in dropdown.model_list.query if g.name == "Alpha")
        self.assertIsInstance(alpha, ModelGroup)
        self.assertEqual(alpha.provider_count, 3)

    def test_set_model_group_pins_a_group_member(self):
        dropdown = ModelDropdown(subject=Session(session_model=self.session), parent=MockFooter())
        dropdown.set_model_group("Alpha")
        runtime = Session(session_model=self.session)
        self.assertEqual(runtime.aimodel.name, "Alpha")
        self.assertIn(runtime.aimodel, {self.alpha_sql, self.alpha_apisql})
        # The pinned provider row is what the session now stores.
        self.assertIn(runtime.aimodel.api_provider, {self.p1, self.p2})

    def test_option_provider_rows_show_only_working_providers(self):
        dropdown = ModelDropdown(subject=Session(session_model=self.session), parent=MockFooter())
        dropdown.set_model_group("Alpha")
        option = ModelDropdownOption(
            subject=ModelGroup("Alpha", [self.alpha_sql, self.alpha_apisql, self.alpha_keyless]),
            parent=dropdown.model_list,
        )
        rows = {r["name"]: r for r in option.provider_rows}
        # Only providers with an API key appear — the keyless one is hidden.
        self.assertEqual(set(rows), {"p1", "p2"})
        self.assertNotIn("keyless", rows)
        # The pinned provider row is flagged active.
        active = [r["name"] for r in option.provider_rows if r["active"]]
        self.assertEqual(active, [option.parent.parent.subject.aimodel.api_provider.name])
        # …and the keyless provider is surfaced as a "needs key" note instead.
        self.assertEqual(option.missing_count, 1)
        self.assertIn("add an API key", option.missing_note)

    def test_option_toggle_providers_flips_state(self):
        dropdown = ModelDropdown(subject=Session(session_model=self.session), parent=MockFooter())
        option = ModelDropdownOption(
            subject=ModelGroup("Alpha", [self.alpha_sql, self.alpha_apisql, self.alpha_keyless]),
            parent=dropdown.model_list,
        )
        self.assertFalse(option.providers_open)
        option.toggle_providers()
        self.assertTrue(option.providers_open)
        self.assertIn("hide", option.pin_label)
        self.assertIn("hide", option.count_class)

    def test_set_specific_provider_pins_exact_provider(self):
        dropdown = ModelDropdown(subject=Session(session_model=self.session), parent=MockFooter())
        dropdown.set_specific_provider("Alpha", self.p2.pk)
        runtime = Session(session_model=self.session)
        self.assertEqual(runtime.aimodel, self.alpha_apisql)
        self.assertEqual(runtime.aimodel.api_provider, self.p2)

    def test_set_specific_provider_can_pin_keyless_provider(self):
        dropdown = ModelDropdown(subject=Session(session_model=self.session), parent=MockFooter())
        dropdown.set_specific_provider("Alpha", self.keyless.pk)
        runtime = Session(session_model=self.session)
        self.assertEqual(runtime.aimodel, self.alpha_keyless)

    def test_set_specific_provider_unknown_provider_is_noop(self):
        dropdown = ModelDropdown(subject=Session(session_model=self.session), parent=MockFooter())
        dropdown.set_specific_provider("Alpha", 9999)
        self.assertIsNone(Session(session_model=self.session).aimodel)