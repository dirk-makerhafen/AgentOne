"""Tests for the insight Providers/Models table views.

Views are exercised via ``object.__new__`` (no UI harness needed): the row
properties are pure functions of the database.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.providers.ai_model import AiModel
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.queries.response import Response
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from ui.main.insights.models import ModelsView
from ui.main.insights.providers import ProvidersView
from ui.main.rightpanel.model.rightpanel_model import RightPanelModel
from ui.main.rightpanel.provider.rightpanel_provider import RightPanelProvider


def _detail(view_cls, subject):
    view = object.__new__(view_cls)
    view._subject_ref = subject
    return view


def _rows(view_cls, sort_col=None, sort_desc=None):
    view = object.__new__(view_cls)
    defaults = {"ProvidersView": ("name", False), "ModelsView": ("rank", False)}
    default_col, default_desc = defaults[view_cls.__name__]
    view._sort_col = sort_col or default_col
    view._sort_desc = default_desc if sort_desc is None else sort_desc
    if view_cls is ProvidersView:
        return ProvidersView.provider_rows.fget(view)
    return ModelsView.model_rows.fget(view)


def _view(view_cls):
    """Bare view with sort state but a no-op ``update()`` for sort tests."""
    view = object.__new__(view_cls)
    view._sort_col = "name" if view_cls is ProvidersView else "rank"
    view._sort_desc = False
    view.update = lambda: None
    return view


class InsightTablesTest(TestCase):
    def setUp(self):
        agent = AgentModel.objects.create(name="insight-agent")
        av = AgentVersionModel.objects.create(
            agent=agent, agent_settings=SettingsModel.objects.create()
        )
        self.session = SessionModel.objects.create(name="insight-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session, agent=agent, pinned_agent_version=av
        )
        SessionModel.objects.filter(pk=self.session.pk).update(latest_session_version=self.sv)
        self.session.refresh_from_db()

    def _provider(self, name, **kwargs):
        return ApiProvider.objects.create(name=name, **kwargs)

    def _model(self, provider, name, **kwargs):
        return AiModel.objects.create(api_provider=provider, name=name, **kwargs)

    def _response(self, model, age, status="SUCCESS", prompt=100, comp=50):
        dt = timezone.now() - age
        response = Response.objects.create(
            query=None,
            session=self.session,
            session_version=self.sv,
            status=status,
            aimodel=model,
            model_name=model.name,
            provider_name=model.api_provider.name,
            prompt_tokens=prompt,
            completion_tokens=comp,
        )
        # created_at is auto_now_add — backdate via queryset update.
        Response.objects.filter(pk=response.pk).update(created_at=dt, updated_at=dt)
        return response

    # ------------------------------------------------------------------
    # Providers view
    # ------------------------------------------------------------------

    def test_provider_usage_windows(self):
        provider = self._provider("win", limit_request_per_minute=20, limit_tokens_per_day=1000000)
        model = self._model(provider, "m")
        self._response(model, timedelta(hours=2))              # in all windows
        self._response(model, timedelta(days=5), prompt=200, comp=100)   # 7d + 30d
        self._response(model, timedelta(days=20), prompt=400, comp=200)  # 30d only
        self._response(model, timedelta(days=40))              # outside
        self._response(model, timedelta(hours=1), status="FAILURE")      # excluded

        (row,) = [r for r in _rows(ProvidersView) if r["name"] == "win"]
        self.assertEqual(row["req_24h"], "1")
        self.assertEqual(row["tok_24h"], "150")
        self.assertEqual(row["req_7d"], "2")
        self.assertEqual(row["tok_7d"], "450")
        self.assertEqual(row["req_30d"], "3")
        self.assertEqual(row["tok_30d"], "1,050")
        self.assertIn("20 RPM", row["limits"])
        self.assertIn("1000000 TPD", row["limits"])

    def test_provider_key_states(self):
        keyed = self._provider("keyed")
        ApiKey.objects.create(api_provider=keyed, key="sk-x", enabled=True)
        ApiKey.objects.create(api_provider=keyed, key="sk-old", enabled=False)
        builtin = self._provider("builtin")
        builtin.data = {"default_api_key": "public"}
        builtin.save()
        self._provider("bare")

        rows = {r["name"]: r for r in _rows(ProvidersView)}
        self.assertEqual((rows["keyed"]["key_state"], rows["keyed"]["key_count"]), ("keys", 1))
        self.assertEqual(rows["builtin"]["key_state"], "built-in")
        self.assertEqual(rows["bare"]["key_state"], "none")

    def test_disabled_provider_excluded(self):
        provider = self._provider("gone", enabled=False)
        self._model(provider, "m")
        self.assertNotIn("gone", [r["name"] for r in _rows(ProvidersView)])

    # ------------------------------------------------------------------
    # Models view
    # ------------------------------------------------------------------

    def test_model_grouping_and_key_counts(self):
        p1 = self._provider("mp1")
        p2 = self._provider("mp2")
        ApiKey.objects.create(api_provider=p1, key="sk-1", enabled=True)
        shared = {"canonical_id": "testdev/shared", "developer": "TestDev",
                  "leaderboard_id": "shared", "leaderboard_rank": 7,
                  "total_parameters": 120, "supports_reasoning": True, "vision": True}
        self._model(p1, "Shared Model", provider_model_id="shared-a", **shared)
        self._model(p2, "Shared Model", provider_model_id="shared-b",
                    supports_tool_call=True, **{k: v for k, v in shared.items()
                                                if k not in ("supports_reasoning", "vision")})

        (row,) = [r for r in _rows(ModelsView) if r["name"] == "Shared Model"]
        self.assertEqual(row["developer"], "TestDev")
        self.assertEqual(row["params"], "120B")
        self.assertEqual(row["rank"], "#7")
        self.assertEqual(row["providers"], 2)
        self.assertEqual(row["with_key"], 1)
        self.assertEqual(sorted(row["modes"]), ["Reason", "Tools", "Vision"])

    def test_estimated_rank_and_sorting(self):
        p = self._provider("sp")
        self._model(p, "Ranked", canonical_id="c/ranked", leaderboard_rank=3)
        self._model(p, "Estimated", canonical_id="c/est",
                    leaderboard_rank=25, leaderboard_rank_is_estimate=True)
        self._model(p, "Unranked", canonical_id="c/unranked")
        self._model(p, "Small", canonical_id="c/small", total_parameters=0.5)

        rows = {r["name"]: r for r in _rows(ModelsView)}
        self.assertEqual(rows["Ranked"]["rank"], "#3")
        self.assertEqual(rows["Estimated"]["rank"], "~25")
        self.assertEqual(rows["Unranked"]["rank"], "—")
        self.assertEqual(rows["Small"]["params"], "500M")
        names = [r["name"] for r in _rows(ModelsView)]
        self.assertLess(names.index("Ranked"), names.index("Estimated"))
        self.assertLess(names.index("Estimated"), names.index("Unranked"))

    def test_disabled_model_excluded(self):
        p = self._provider("dp")
        self._model(p, "Hidden", canonical_id="c/hidden", enabled=False)
        self.assertNotIn("Hidden", [r["name"] for r in _rows(ModelsView)])

    # ------------------------------------------------------------------
    # Detail views
    # ------------------------------------------------------------------

    def test_provider_detail(self):
        provider = self._provider(
            "detail", url="https://example.com/api/v1",
            limit_request_per_minute=20, litellm_prefix="",
        )
        provider.data = {"default_api_key": "", "setup_instructions": "sign up"}
        provider.save()
        ApiKey.objects.create(api_provider=provider, key="sk-x", enabled=True, comment="main")
        ApiKey.objects.create(api_provider=provider, key="sk-old", enabled=False)
        model = self._model(provider, "dm", provider_model_id="dm-free", leaderboard_rank=5)
        self._response(model, timedelta(hours=2))

        detail = _detail(RightPanelProvider, provider)
        self.assertEqual(len(detail.key_rows), 2)
        self.assertEqual(
            detail.limit_rows, [("RPM", 20)]
        )
        usage = dict(detail.usage_rows)
        self.assertEqual(usage["24h"], "1 req · 150 tok")
        self.assertEqual(usage["30d"], "1 req · 150 tok")
        self.assertEqual(
            detail.model_rows,
            [{"id": model.pk, "name": "dm", "provider_model_id": "dm-free"}],
        )

    def test_model_detail(self):
        p1 = self._provider("qp1")
        p2 = self._provider("qp2")
        ApiKey.objects.create(api_provider=p1, key="sk-1", enabled=True)
        shared = {"canonical_id": "testdev/q", "developer": "Q",
                  "leaderboard_rank": 9, "total_parameters": 30,
                  "context_length": 200000, "supports_tool_call": True}
        m1 = self._model(p1, "Q Model", provider_model_id="q-a", **shared)
        m1.data = {"conditions": "free lane"}
        m1.save()
        self._model(p2, "Q Model", provider_model_id="q-b",
                    **{k: v for k, v in shared.items() if k != "supports_tool_call"})

        detail = _detail(RightPanelModel, m1)
        self.assertEqual(detail.group_name, "Q Model")
        self.assertEqual(detail.group_rank, "#9")
        self.assertEqual(detail.group_params, "30B")
        self.assertEqual(detail.group_context, "200k")
        self.assertEqual(detail.group_modes, ["Tools"])
        rows = {r["provider"]: r for r in detail.provider_rows}
        self.assertEqual(rows["qp1"]["key_note"], "✓ key")
        self.assertEqual(rows["qp2"]["key_note"], "no key")
        self.assertEqual(rows["qp1"]["conditions"], "free lane")

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def test_provider_sort_toggle(self):
        view = _view(ProvidersView)
        self.assertEqual((view._sort_col, view._sort_desc), ("name", False))
        view.apply_sort("tok_7d")
        self.assertEqual((view._sort_col, view._sort_desc), ("tok_7d", True))
        view.apply_sort("tok_7d")
        self.assertEqual((view._sort_col, view._sort_desc), ("tok_7d", False))
        view.apply_sort("name")
        self.assertEqual((view._sort_col, view._sort_desc), ("name", False))
        self.assertEqual(view.sort_arrow("name"), " ▲")
        self.assertEqual(view.sort_arrow("tok_7d"), "")

    def test_provider_sort_orders_rows(self):
        p1 = self._provider("aaa")
        p2 = self._provider("zzz")
        m1 = self._model(p1, "m1")
        m2 = self._model(p2, "m2")
        self._response(m2, timedelta(hours=1))
        names = [r["name"] for r in _rows(ProvidersView)]
        self.assertEqual(names[:2], ["aaa", "zzz"])
        names = [r["name"] for r in _rows(ProvidersView, sort_col="req_24h", sort_desc=True)]
        self.assertEqual(names[:2], ["zzz", "aaa"])

    def test_model_sort_orders_rows(self):
        p = self._provider("mp")
        self._model(p, "Beta", canonical_id="c/beta", leaderboard_rank=10)
        self._model(p, "Alpha", canonical_id="c/alpha", leaderboard_rank=2)
        names = [r["name"] for r in _rows(ModelsView)]
        self.assertEqual(names[:2], ["Alpha", "Beta"])
        names = [r["name"] for r in _rows(ModelsView, sort_col="name", sort_desc=True)]
        self.assertEqual(names[:2], ["Beta", "Alpha"])
        view = _view(ModelsView)
        view.apply_sort("rank")
        self.assertTrue(view._sort_desc)
        names = [r["name"] for r in _rows(ModelsView, sort_col="rank", sort_desc=True)]
        self.assertEqual(names[:2], ["Beta", "Alpha"])
