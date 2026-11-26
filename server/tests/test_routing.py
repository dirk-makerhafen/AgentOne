"""Route intent, candidate chain, failover decisions and route state.

The routing layer is the contract between session intent ("what may this
session run on") and ``call_llm`` ("what do we actually try, in what order").
These tests pin the strict-pin / wait-budget behaviour that smoke tests rely
on, plus the quality-tier mapping used by the UI filters.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.test import TestCase

from registry.catalog.favorites import apply_curated_favorites
from runtime.routing import (
    ACTION_FAILOVER,
    ACTION_RAISE,
    ACTION_WAIT,
    build_chain,
    decide_failure,
    get_route,
    resolve_intent,
    set_route,
)
from runtime.routing.quality import rank_satisfies, tier_bars, tier_for_rank
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.providers.ai_model import AiModel as RawModel
from server.models.providers.ai_model_offering import AiModelOffering
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel


class QualityTierTest(TestCase):
    def test_rank_buckets(self):
        self.assertEqual(tier_for_rank(10), "frontier")
        self.assertEqual(tier_for_rank(42), "excellent")
        self.assertEqual(tier_for_rank(100), "strong")
        self.assertEqual(tier_for_rank(300), "capable")
        self.assertEqual(tier_for_rank(900), "lightweight")
        self.assertEqual(tier_for_rank(None), "")

    def test_bars_and_min_tier_filter(self):
        self.assertEqual(tier_bars("frontier"), 5)
        self.assertEqual(tier_bars("strong"), 3)
        self.assertTrue(rank_satisfies(150, "strong"))
        self.assertFalse(rank_satisfies(151, "strong"))
        # Unranked models may satisfy the broad buckets but never "strong+".
        self.assertTrue(rank_satisfies(None, "capable"))
        self.assertFalse(rank_satisfies(None, "strong"))


class RoutingFixtureTest(TestCase):
    def setUp(self):
        self.p1 = ApiProvider.objects.create(name="p1", slug="p1")
        self.p2 = ApiProvider.objects.create(name="p2", slug="p2")
        self.key1 = ApiKey.objects.create(api_provider=self.p1, key="k1", enabled=True, budget=10)
        self.key2 = ApiKey.objects.create(api_provider=self.p2, key="k2", enabled=True, budget=0)
        # Alpha is served by both providers; Beta only by p1.  Ranks make
        # Alpha "Excellent" and Beta "Capable" (with tools enabled).
        self.alpha1 = self._offering(self.p1, "Alpha", "alpha-p1", rank=40, free=True)
        self.alpha2 = self._offering(self.p2, "Alpha", "alpha-p2", rank=40, free=True)
        self.beta = self._offering(self.p1, "Beta", "beta", rank=300, free=False)

        self.agent = AgentModel.objects.create(name="routing-agent")
        self.agent_version = AgentVersionModel.objects.create(
            agent=self.agent, agent_settings=SettingsModel.objects.create()
        )
        self.session_model = SessionModel.objects.create(
            name="routing-session", session_type="session"
        )
        self.session_version = SessionVersionModel.objects.create(
            session=self.session_model,
            agent=self.agent,
            pinned_agent_version=self.agent_version,
            session_settings=SettingsModel.objects.create(),
        )
        SessionModel.objects.filter(pk=self.session_model.pk).update(
            latest_session_version=self.session_version
        )
        self.session_model.refresh_from_db()
        self._settings(**{})

    def _offering(self, provider, name, provider_model_id, *, rank, free, is_cloud=True):
        return AiModelOffering.objects.create(
            api_provider=provider,
            name=name,
            provider_model_id=provider_model_id,
            leaderboard_rank=rank,
            supports_tool_call=True,
            is_free=free,
            is_cloud=is_cloud,
        )

    def _settings(self, **overrides):
        """Apply overrides through the runtime's copy-on-write setters."""
        runtime = self._runtime()
        if "aimodel" in overrides:
            runtime.set_aimodel(overrides["aimodel"])
        if "preferred_api_key" in overrides:
            runtime.set_preferred_api_key(overrides["preferred_api_key"])
        if "local_only" in overrides:
            runtime.set_local_only(overrides["local_only"])
        policy = {}
        for source, target in (
            ("route_pin", "pin"),
            ("route_failover", "failover"),
            ("route_target", "target"),
            ("route_wait_seconds", "wait_seconds"),
            ("route_constraints", "constraints"),
        ):
            if source in overrides:
                policy[target] = overrides[source]
        if policy:
            runtime.set_route_policy(**policy)

    def _runtime(self):
        return self.session_model.get_runtime()

    def _local_alpha(self):
        provider = ApiProvider.objects.create(name="local", slug="local", is_local=True)
        ApiKey.objects.create(api_provider=provider, key="local-key", enabled=True)
        return self._offering(
            provider, "Alpha", "alpha-local", rank=40, free=True, is_cloud=False
        )

    # -- intent ---------------------------------------------------------

    def test_default_session_uses_balanced_profile(self):
        intent = resolve_intent(self._runtime())
        self.assertEqual(intent.pin, "auto")
        self.assertEqual(intent.profile, "auto:balanced")
        self.assertEqual(intent.failover, "models")
        self.assertEqual(intent.wait_seconds, 10)
        self.assertTrue(intent.constraints["prefer_free"])
        self.assertEqual(intent.constraints["min_tier"], "strong")

    def test_background_workload_uses_longer_wait_budget(self):
        SessionModel.objects.filter(pk=self.session_model.pk).update(
            session_type="subtask_delegate"
        )
        self.session_model.refresh_from_db()
        # A pinned model keeps its pin but inherits the workload's wait budget.
        self._settings(aimodel=self.alpha1)
        intent = resolve_intent(self._runtime())
        self.assertEqual(intent.pin, "model")
        self.assertEqual(intent.wait_seconds, 120)

    def test_offering_key_pin_is_strict_and_zero_wait(self):
        self._settings(
            aimodel=self.alpha1,
            route_pin="offering_key",
            route_failover="none",
            route_wait_seconds=0,
            preferred_api_key=self.key1,
        )
        intent = resolve_intent(self._runtime())
        self.assertTrue(intent.is_strict)
        self.assertEqual(intent.wait_seconds, 0)
        self.assertEqual(intent.pinned_api_key_id, self.key1.pk)

    def test_explicit_auto_profile_overrides_pinned_offering(self):
        self._settings(
            aimodel=self.beta,
            route_pin="auto",
            route_target="auto:best-free",
            route_wait_seconds=10,
        )
        intent = resolve_intent(self._runtime())
        self.assertEqual(intent.pin, "auto")
        self.assertEqual(intent.profile, "auto:best-free")
        self.assertTrue(intent.constraints["free_only"])

    def test_user_default_profile_is_honoured(self):
        from unittest.mock import patch

        with patch(
            "runtime.settings.settings.get_config",
            return_value={"preferences": {"default_route": "auto:best-free"}},
        ):
            intent = resolve_intent(self._runtime())
        self.assertEqual(intent.pin, "auto")
        self.assertEqual(intent.profile, "auto:best-free")
        self.assertTrue(intent.constraints["free_only"])

    def test_explicit_pin_beats_user_default_profile(self):
        from unittest.mock import patch

        self._settings(aimodel=self.alpha1)
        with patch(
            "runtime.settings.settings.get_config",
            return_value={"preferences": {"default_route": "auto:best"}},
        ):
            intent = resolve_intent(self._runtime())
        self.assertEqual(intent.pin, "model")
        self.assertEqual(intent.target, "Alpha")
        self.assertEqual(intent.constraints.get("min_tier"), "")

    def test_agent_route_defaults_apply_to_session(self):
        agent_settings = SettingsModel.objects.create(
            aimodel=self.alpha1,
            route_pin="offering",
            route_failover="keys",
            route_wait_seconds=5,
            route_constraints={"require_tools": True},
        )
        AgentVersionModel.objects.filter(pk=self.agent_version.pk).update(
            agent_settings=agent_settings
        )
        self.agent_version.refresh_from_db()

        intent = resolve_intent(self._runtime())
        self.assertEqual(intent.pin, "offering")
        self.assertEqual(intent.failover, "keys")
        self.assertEqual(intent.wait_seconds, 5)
        self.assertEqual(intent.target, "Alpha")
        self.assertTrue(intent.constraints["require_tools"])

    def test_session_route_policy_beats_agent_defaults(self):
        agent_settings = SettingsModel.objects.create(
            aimodel=self.alpha1,
            route_pin="offering",
            route_failover="keys",
            route_wait_seconds=5,
        )
        AgentVersionModel.objects.filter(pk=self.agent_version.pk).update(
            agent_settings=agent_settings
        )
        self.agent_version.refresh_from_db()
        self._settings(route_pin="model", route_failover="providers", route_wait_seconds=1)

        intent = resolve_intent(self._runtime())
        self.assertEqual(intent.pin, "model")
        self.assertEqual(intent.failover, "providers")
        self.assertEqual(intent.wait_seconds, 1)

    # -- candidate chain ------------------------------------------------

    def test_strict_pin_has_exactly_one_candidate_and_keeps_its_key(self):
        self._settings(
            aimodel=self.alpha1,
            route_pin="offering_key",
            route_failover="none",
            route_wait_seconds=0,
            preferred_api_key=self.key1,
        )
        runtime = self._runtime()
        chain = build_chain(runtime, resolve_intent(runtime))
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0].offering.pk, self.alpha1.pk)
        self.assertEqual(chain[0].api_key.pk, self.key1.pk)

    def test_model_pin_tries_siblings_but_not_other_models(self):
        self._settings(aimodel=self.alpha1)
        runtime = self._runtime()
        chain = build_chain(runtime, resolve_intent(runtime))
        names = {c.offering.pk for c in chain}
        self.assertEqual(names, {self.alpha1.pk, self.alpha2.pk})
        self.assertNotIn(self.beta.pk, names)

    def test_offering_pin_with_provider_failover_includes_siblings(self):
        self._settings(
            aimodel=self.alpha1,
            route_pin="offering",
            route_failover="providers",
        )
        runtime = self._runtime()
        chain = build_chain(runtime, resolve_intent(runtime))
        self.assertEqual(chain[0].offering.pk, self.alpha1.pk)
        self.assertEqual({c.offering.pk for c in chain}, {self.alpha1.pk, self.alpha2.pk})

    def test_auto_profile_filters_free_only(self):
        self._settings(route_pin="auto", route_target="auto:best-free")
        runtime = self._runtime()
        chain = build_chain(runtime, resolve_intent(runtime))
        self.assertTrue(chain)
        self.assertTrue(all(c.offering.is_free for c in chain))
        self.assertNotIn(self.beta.pk, {c.offering.pk for c in chain})

    def test_auto_profile_can_fall_back_to_another_model(self):
        self._settings(route_pin="auto", route_target="auto:best")
        runtime = self._runtime()
        chain = build_chain(runtime, resolve_intent(runtime))
        self.assertGreaterEqual(len(chain), 2)
        # min_tier=excellent excludes Beta (rank 300) even with model failover.
        self.assertNotIn(self.beta.pk, {c.offering.pk for c in chain})

    # -- failure decisions ----------------------------------------------

    def test_short_rate_limit_waits_inside_budget(self):
        intent = resolve_intent(self._runtime())
        info = SimpleNamespace(kind="rate_limit", message="retry later", retry_after=5, scope="key")
        decision = decide_failure(info, intent=intent)
        self.assertEqual(decision.action, ACTION_WAIT)
        self.assertEqual(decision.wait_seconds, 5)

    def test_long_rate_limit_fails_over(self):
        intent = resolve_intent(self._runtime())
        info = SimpleNamespace(
            kind="rate_limit", message="quota exceeded", retry_after=3600, scope="key"
        )
        decision = decide_failure(info, intent=intent)
        self.assertEqual(decision.action, ACTION_FAILOVER)

    def test_strict_pin_never_waits_or_fails_over(self):
        self._settings(
            aimodel=self.alpha1,
            route_pin="offering_key",
            route_failover="none",
            route_wait_seconds=0,
        )
        intent = resolve_intent(self._runtime())
        info = SimpleNamespace(kind="rate_limit", message="quota", retry_after=5, scope="key")
        self.assertEqual(decide_failure(info, intent=intent).action, ACTION_RAISE)
        info = SimpleNamespace(kind="model_not_found", message="404", scope="model")
        self.assertEqual(decide_failure(info, intent=intent).action, ACTION_RAISE)

    def test_bad_request_is_never_retried_elsewhere(self):
        intent = resolve_intent(self._runtime())
        info = SimpleNamespace(kind="bad_request", message="context too long", scope="request")
        self.assertEqual(decide_failure(info, intent=intent).action, ACTION_RAISE)

    # -- mutable route state --------------------------------------------

    def test_set_route_does_not_mint_a_new_session_version(self):
        runtime = self._runtime()
        before = self.session_model.latest_session_version_id
        set_route(runtime, self.alpha1, self.key1, reason="initial")
        self.assertEqual(self.session_model.latest_session_version_id, before)
        row = get_route(runtime)
        self.assertEqual(row.offering_id, self.alpha1.pk)
        self.assertEqual(row.api_key_id, self.key1.pk)
        self.assertEqual(row.switch_count, 0)

        set_route(runtime, self.alpha2, self.key2, reason="rate_limit_exceeds_budget")
        row.refresh_from_db()
        self.assertEqual(row.offering_id, self.alpha2.pk)
        self.assertEqual(row.switch_count, 1)
        self.assertEqual(row.last_reason, "rate_limit_exceeds_budget")
        self.assertEqual(self.session_model.latest_session_version_id, before)

    def test_mid_chat_pin_injects_handoff_notice(self):
        from server.models.enums.message_enums import (
            MessageContentType,
            MessagePartType,
            MessageRole,
            MessageType,
        )
        from server.models.message import Message

        runtime = self._runtime()
        runtime.set_aimodel(self.alpha1)
        first = Message.objects.create(
            session=self.session_model,
            session_version=self.session_version,
            role=MessageRole.USER,
        )
        first.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content="hello",
        )

        runtime.set_aimodel(self.beta)
        notices = Message.objects.filter(
            session=self.session_model, message_type=MessageType.SYSTEM_NOTICE
        )
        self.assertEqual(notices.count(), 1)
        self.assertIn("Model switched mid-session", notices.first().parts.first().content.get())

    def test_mid_chat_switch_notice_never_dispatches_a_turn(self):
        """A switch notice is a direct append, never an inbound user message.

        Switching the model in an idle session must not enqueue
        ``ingest_user_message`` / ``process_turn`` or create a Query.  The note
        is only history for the next real user request.
        """
        from unittest.mock import patch

        from server.models.enums.message_enums import (
            MessageContentType,
            MessagePartType,
            MessageRole,
            MessageType,
        )
        from server.models.message import Message
        from server.models.queries.query import Query

        runtime = self._runtime()
        runtime.set_aimodel(self.alpha1)
        first = Message.objects.create(
            session=self.session_model,
            session_version=self.session_version,
            role=MessageRole.USER,
        )
        first.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content="hello",
        )

        with patch.object(runtime, "get_task", wraps=runtime.get_task) as get_task:
            runtime.set_aimodel(None)  # switch to automatic routing

        get_task.assert_not_called()
        self.assertFalse(Query.objects.filter(session=self.session_model).exists())
        notice = Message.objects.get(
            session=self.session_model, message_type=MessageType.SYSTEM_NOTICE
        )
        self.assertEqual(notice.role, MessageRole.USER)
        self.assertIn(
            "Continue the task from the latest user request",
            notice.parts.first().content.get(),
        )

    def test_switch_notice_skipped_while_session_has_live_work(self):
        """Never append a user-role notice for a chained turn to pick up."""
        from unittest.mock import patch

        from server.models.enums.message_enums import (
            MessageContentType,
            MessagePartType,
            MessageRole,
            MessageType,
        )
        from server.models.message import Message

        runtime = self._runtime()
        runtime.set_aimodel(self.alpha1)
        first = Message.objects.create(
            session=self.session_model,
            session_version=self.session_version,
            role=MessageRole.USER,
        )
        first.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content="hello",
        )

        with patch.object(runtime, "_has_active_call", return_value=True):
            runtime.set_aimodel(self.beta)

        self.assertFalse(
            Message.objects.filter(
                session=self.session_model, message_type=MessageType.SYSTEM_NOTICE
            ).exists()
        )

    def test_switch_notice_skipped_while_query_is_waiting(self):
        """A queued query must not get a user-role notice appended under it."""
        from server.models.enums.message_enums import (
            MessageContentType,
            MessagePartType,
            MessageRole,
            MessageType,
        )
        from server.models.message import Message
        from server.models.queries.query import Query, QueryStatus

        runtime = self._runtime()
        runtime.set_aimodel(self.alpha1)
        first = Message.objects.create(
            session=self.session_model,
            session_version=self.session_version,
            role=MessageRole.USER,
        )
        first.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content="hello",
        )
        Query.objects.create(
            session=self.session_model,
            session_version=self.session_version,
            status=QueryStatus.WAITING,
            trigger_message=first,
        )

        runtime.set_aimodel(self.beta)

        self.assertFalse(
            Message.objects.filter(
                session=self.session_model, message_type=MessageType.SYSTEM_NOTICE
            ).exists()
        )

    # -- local-only scope policy ---------------------------------------

    def test_session_local_only_forces_constraint_and_local_chain(self):
        local_alpha = self._local_alpha()
        self._settings(
            local_only=True,
            route_pin="auto",
            route_target="auto:best",
            route_constraints={"local_only": False},
        )
        runtime = self._runtime()
        intent = resolve_intent(runtime)
        self.assertTrue(intent.constraints["local_only"])
        chain = build_chain(runtime, intent)
        self.assertEqual({c.offering.pk for c in chain}, {local_alpha.pk})

    def test_strict_cloud_pin_never_runs_under_local_only_policy(self):
        self._local_alpha()
        self._settings(
            aimodel=self.alpha1,
            route_pin="offering_key",
            route_failover="none",
            route_wait_seconds=0,
            preferred_api_key=self.key1,
        )
        self._settings(local_only=True)
        runtime = self._runtime()
        chain = build_chain(runtime, resolve_intent(runtime))
        self.assertEqual(chain, [])

    def test_offering_pin_falls_back_to_local_sibling_only(self):
        local_alpha = self._local_alpha()
        self._settings(
            aimodel=self.alpha1,
            route_pin="offering",
            route_failover="providers",
        )
        self._settings(local_only=True)
        runtime = self._runtime()
        chain = build_chain(runtime, resolve_intent(runtime))
        self.assertEqual({c.offering.pk for c in chain}, {local_alpha.pk})

    def test_project_policy_applies_to_sessions_and_descendants(self):
        from server.models.project import Project

        local_alpha = self._local_alpha()
        project = Project.objects.create(name="local-project", local_only=True)
        self.session_model.parent_project = project
        self.session_model.save(update_fields=["parent_project"])
        child = SessionModel.objects.create(
            name="local-child",
            parent_session=self.session_model,
            session_type="subtask_delegate",
        )
        SessionVersionModel.objects.create(
            session=child,
            agent=self.agent,
            pinned_agent_version=self.agent_version,
            session_settings=SettingsModel.objects.create(),
        )

        # An explicit false on the session/child cannot clear the project flag.
        self._settings(local_only=False, route_pin="auto", route_target="auto:best")
        for runtime in (self._runtime(), child.get_runtime()):
            intent = resolve_intent(runtime)
            self.assertTrue(intent.constraints["local_only"])
            chain = build_chain(runtime, intent)
            self.assertEqual({c.offering.pk for c in chain}, {local_alpha.pk})

    def test_workspace_policy_is_inherited(self):
        from server.models.workspace import WorkspaceModel

        local_alpha = self._local_alpha()
        workspace = WorkspaceModel.objects.create(
            name="local-workspace", path="/tmp", local_only=True
        )
        version = SessionVersionModel.objects.create(
            session=self.session_model,
            agent=self.agent,
            pinned_agent_version=self.agent_version,
            session_settings=SettingsModel.objects.create(local_only=False),
            workspace=workspace,
            version_number=self.session_version.version_number + 1,
        )
        SessionModel.objects.filter(pk=self.session_model.pk).update(
            latest_session_version=version
        )
        self.session_model.refresh_from_db()
        runtime = self._runtime()
        intent = resolve_intent(runtime)
        self.assertTrue(intent.constraints["local_only"])
        self.assertEqual(
            {c.offering.pk for c in build_chain(runtime, intent)}, {local_alpha.pk}
        )


class CuratedFavoritesTest(TestCase):
    def test_curated_stars_survive_reload_and_user_stars_win(self):
        keep = RawModel.objects.create(slug="keep", name="Keep")
        user = RawModel.objects.create(
            slug="user-star", name="User Star", is_favorite=True, favorite_origin="user"
        )
        stale = RawModel.objects.create(
            slug="stale", name="Stale", is_favorite=True, favorite_origin="curated"
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "models").mkdir()
            (root / "models" / "favorites.yaml").write_text(
                "favorites:\n  - keep\n  - user-star\n", encoding="utf-8"
            )
            apply_curated_favorites(root)

        keep.refresh_from_db()
        user.refresh_from_db()
        stale.refresh_from_db()
        self.assertTrue(keep.is_favorite)
        self.assertEqual(keep.favorite_origin, "curated")
        self.assertTrue(user.is_favorite)
        self.assertEqual(user.favorite_origin, "user")
        self.assertFalse(stale.is_favorite)
        self.assertEqual(stale.favorite_origin, "")
