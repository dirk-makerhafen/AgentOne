"""Tests for ui/model_observer.py — ModelObserver event routing."""
from __future__ import annotations

from unittest.mock import MagicMock
from django.test import SimpleTestCase
from ui.model_observer import ModelObserver


class ModelObserverWatchTest(SimpleTestCase):
    def setUp(self):
        self.obs = ModelObserver()

    def test_watch_adds_subscription(self):
        view = MagicMock()
        self.obs.watch(MagicMock(_meta=MagicMock(model_name="task")),
                       callback_name="on_update", view=view)
        self.assertIn("task", self.obs._subscriptions)
        self.assertEqual(len(self.obs._subscriptions["task"]), 1)

    def test_watch_validates_callback_exists(self):
        view = object()
        model = MagicMock(_meta=MagicMock(model_name="task"))
        with self.assertRaises(ValueError):
            self.obs.watch(model, callback_name="nonexistent", view=view)

    def test_watch_without_view_skips_validation(self):
        model = MagicMock(_meta=MagicMock(model_name="task"))
        self.obs.watch(model, callback_name="nonexistent")
        self.assertEqual(len(self.obs._subscriptions["task"]), 1)


class ModelObserverDispatchTest(SimpleTestCase):
    def setUp(self):
        self.obs = ModelObserver()

    def test_dispatch_calls_matching_callback(self):
        view = MagicMock()
        self.obs.watch(
            MagicMock(_meta=MagicMock(model_name="message")),
            filter={"session_id": 5},
            callback_name="on_created",
            view=view,
            action="create",
        )
        self.obs.dispatch(
            "message", "create", pk=42, filter_context={"session_id": 5, "session_version_id": 3}
        )
        view.on_created.assert_called_once_with(42, "create", {"session_id": 5, "session_version_id": 3})

    def test_dispatch_skips_wrong_action(self):
        view = MagicMock()
        self.obs.watch(
            MagicMock(_meta=MagicMock(model_name="message")),
            callback_name="on_created",
            view=view,
            action="create",
        )
        self.obs.dispatch("message", "update", pk=42, filter_context={})
        view.on_created.assert_not_called()

    def test_dispatch_skips_non_matching_filter(self):
        view = MagicMock()
        self.obs.watch(
            MagicMock(_meta=MagicMock(model_name="message")),
            filter={"session_id": 5},
            callback_name="on_created",
            view=view,
        )
        self.obs.dispatch("message", "create", pk=42, filter_context={"session_id": 99})
        view.on_created.assert_not_called()

    def test_dispatch_matches_empty_filter_always(self):
        view = MagicMock()
        self.obs.watch(
            MagicMock(_meta=MagicMock(model_name="message")),
            callback_name="on_created",
            view=view,
        )
        self.obs.dispatch("message", "create", pk=42, filter_context={})
        view.on_created.assert_called_once()

    def test_dispatch_ignores_other_model(self):
        view = MagicMock()
        self.obs.watch(
            MagicMock(_meta=MagicMock(model_name="message")),
            callback_name="on_created",
            view=view,
        )
        self.obs.dispatch("taskcall", "create", pk=1, filter_context={})
        view.on_created.assert_not_called()

    def test_dispatch_skips_dead_weakref(self):
        import gc
        class _Ephemeral:
            def on_created(self, pk, action, ctx):
                pass
        view = _Ephemeral()
        self.obs.watch(
            MagicMock(_meta=MagicMock(model_name="message")),
            callback_name="on_created",
            view=view,
        )
        del view
        gc.collect()
        self.obs.dispatch("message", "create", pk=42, filter_context={})
        self.assertNotIn("message", self.obs._subscriptions)

    def test_dispatch_skips_nonexistent_callback(self):
        view = MagicMock(spec=[])  # no methods
        model = MagicMock(_meta=MagicMock(model_name="message"))
        self.obs._subscriptions["message"].append({
            "filter": {},
            "callback_name": "on_created",
            "view_ref": MagicMock(return_value=view),
            "action": None,
        })
        self.obs.dispatch("message", "create", pk=42, filter_context={})
        # should not raise

    def test_dispatch_callback_exception_does_not_crash(self):
        view = MagicMock()
        view.on_created.side_effect = RuntimeError("boom")
        self.obs.watch(
            MagicMock(_meta=MagicMock(model_name="message")),
            callback_name="on_created",
            view=view,
        )
        # should not raise
        self.obs.dispatch("message", "create", pk=42, filter_context={})


class ModelObserverUnwatchTest(SimpleTestCase):
    def setUp(self):
        self.obs = ModelObserver()

    def test_unwatch_removes_all_subscriptions_for_view(self):
        view = MagicMock()
        model = MagicMock(_meta=MagicMock(model_name="message"))
        self.obs.watch(model, callback_name="on_a", view=view)
        self.obs.watch(model, callback_name="on_b", view=view)
        self.assertEqual(len(self.obs._subscriptions["message"]), 2)
        self.obs.unwatch(view)
        self.assertNotIn("message", self.obs._subscriptions)

    def test_unwatch_other_view_unaffected(self):
        view_a = MagicMock()
        view_b = MagicMock()
        model = MagicMock(_meta=MagicMock(model_name="message"))
        self.obs.watch(model, callback_name="on_a", view=view_a)
        self.obs.watch(model, callback_name="on_b", view=view_b)
        self.obs.unwatch(view_a)
        self.assertEqual(len(self.obs._subscriptions["message"]), 1)

    def test_unwatch_no_subscriptions_does_not_crash(self):
        view = MagicMock()
        self.obs.unwatch(view)


class ModelObserverMatchesTest(SimpleTestCase):
    def test_exact_match(self):
        self.assertTrue(ModelObserver._matches(
            {"session_id": 5}, {"session_id": 5, "session_version_id": 3}
        ))

    def test_partial_context_is_fine(self):
        self.assertTrue(ModelObserver._matches(
            {"session_id": 5}, {"session_id": 5}
        ))

    def test_missing_key_fails(self):
        self.assertFalse(ModelObserver._matches(
            {"session_id": 5}, {"session_version_id": 3}
        ))

    def test_value_mismatch_fails(self):
        self.assertFalse(ModelObserver._matches(
            {"session_id": 5}, {"session_id": 99}
        ))

    def test_empty_filter_matches_anything(self):
        self.assertTrue(ModelObserver._matches({}, {"session_id": 5}))
        self.assertTrue(ModelObserver._matches({}, {}))
