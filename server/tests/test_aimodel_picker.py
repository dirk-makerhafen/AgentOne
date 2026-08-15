"""Tests for the composer model-grouping / provider-picker helpers.

Covers ``runtime/session/aimodel_picker.py`` and the ``Session`` wiring that
relies on it (default-model fallback and ``set_aimodel_by_name``).
"""
from __future__ import annotations

from unittest import mock

from django.test import TestCase
from django.utils import timezone

from runtime.session.aimodel_picker import available_aimodels, model_groups, pick_aimodel
from runtime.session.session import Session

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from server.models.queries.query import QueryStatus
from server.models.queries.response import Response, ResponseStatus
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel


class AimodelPickerTest(TestCase):
    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1")
        self.p2 = ApiProvider.objects.create(name="p2")
        ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True)
        ApiKey.objects.create(api_provider=self.p2, key="k2", enabled=True)

        # "Alpha" is served by p1 and p2 (the same model, two providers).
        self.alpha_sql = AiModel.objects.create(
            api_provider=self.p1, name="Alpha", provider_model_id="sql-alpha"
        )
        self.alpha_apisql = AiModel.objects.create(
            api_provider=self.p2, name="Alpha", provider_model_id="apisql-alpha"
        )
        # Single-provider model.
        self.beta = AiModel.objects.create(
            api_provider=self.p1, name="Beta", provider_model_id="beta"
        )
        # Excluded rows: a disabled member and a provider without any key.
        self.alpha_disabled = AiModel.objects.create(
            api_provider=self.p2, name="Alpha", provider_model_id="disabled", enabled=False
        )
        self.keyless = ApiProvider.objects.create(name="keyless")
        self.gamma = AiModel.objects.create(
            api_provider=self.keyless, name="Gamma", provider_model_id="gamma"
        )
        # A keyless provider serving an already-usable name: it should count in
        # the group badge but must never be chosen by the picker.
        self.alpha_keyless = AiModel.objects.create(
            api_provider=self.keyless, name="Alpha", provider_model_id="keyless-alpha"
        )

        # Minimal session fixture (needed for Response rows + Session wrapper).
        self.agent = AgentModel.objects.create(name="picker-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="picker-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(latest_session_version=self.sv)
        self.session.refresh_from_db()
        AgentModel.objects.filter(pk=self.agent.pk).update(latest_agent_version=self.av)

    def _success_response(self, aimodel):
        return Response.objects.create(
            query=None,
            session=self.session,
            session_version=self.sv,
            status=ResponseStatus.SUCCESS,
            aimodel=aimodel,
        )

    # ------------------------------------------------------------------
    # Grouping
    # ------------------------------------------------------------------

    def test_available_excludes_disabled_and_keyless(self):
        names = {m.name for m in available_aimodels()}
        self.assertNotIn("Gamma", names)
        self.assertEqual(
            [m.name for m in available_aimodels()].count("Alpha"), 2
        )

    def test_groups_by_name_with_distinct_provider_count(self):
        groups = {g.name: g for g in model_groups()}
        # The badge counts every enabled provider serving the name, keyed or not.
        self.assertEqual(groups["Alpha"].provider_count, 3)
        self.assertEqual(len(groups["Alpha"].members), 3)
        self.assertEqual(groups["Beta"].provider_count, 1)
        self.assertNotIn("Gamma", groups)

    def test_group_members_include_keyless_provider(self):
        alpha = next(g for g in model_groups() if g.name == "Alpha")
        provider_ids = {m.api_provider_id for m in alpha.members}
        self.assertEqual(provider_ids, {self.p1.id, self.p2.id, self.keyless.id})
        # …but picking still only returns a usable (keyed) member.
        self.assertIn(pick_aimodel("Alpha"), {self.alpha_sql, self.alpha_apisql})

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def test_pick_returns_member_of_group(self):
        picked = pick_aimodel("Alpha")
        self.assertIn(picked, {self.alpha_sql, self.alpha_apisql})

    def test_pick_excludes_throttled_provider(self):
        self.p1.limit_request_per_minute = 1
        self.p1.save(update_fields=["limit_request_per_minute"])
        self._success_response(self.alpha_sql)
        # p1 is now at/over its 1 RPM cap → p2 must be chosen.
        self.assertEqual(pick_aimodel("Alpha"), self.alpha_apisql)

    def test_pick_falls_back_when_all_throttled(self):
        self.p1.limit_request_per_minute = 1
        self.p2.limit_request_per_minute = 1
        self.p1.save(update_fields=["limit_request_per_minute"])
        self.p2.save(update_fields=["limit_request_per_minute"])
        self._success_response(self.alpha_sql)
        self._success_response(self.alpha_apisql)
        picked = pick_aimodel("Alpha")
        self.assertIn(picked, {self.alpha_sql, self.alpha_apisql})

    def test_pick_unknown_name_returns_none(self):
        self.assertIsNone(pick_aimodel("Does Not Exist"))

    # ------------------------------------------------------------------
    # Session wiring
    # ------------------------------------------------------------------

    def test_set_aimodel_by_name_pins_a_group_member(self):
        runtime = Session(session_model=self.session)
        picked = runtime.set_aimodel_by_name("Alpha")
        self.assertIn(picked, {self.alpha_sql, self.alpha_apisql})
        self.assertEqual(runtime.aimodel, picked)
        self.assertEqual(runtime.aimodel.name, "Alpha")

    def test_default_aimodel_uses_picker(self):
        with mock.patch(
            "runtime.settings.get_default_model_name", return_value="Alpha"
        ):
            runtime = Session(session_model=self.session)
            self.assertIn(runtime.aimodel, {self.alpha_sql, self.alpha_apisql})

    def test_default_aimodel_unknown_name_returns_none(self):
        with mock.patch(
            "runtime.settings.get_default_model_name", return_value="Nope"
        ):
            runtime = Session(session_model=self.session)
            self.assertIsNone(runtime.aimodel)