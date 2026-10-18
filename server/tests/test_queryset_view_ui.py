"""Tests for QuerySetView: flat list-subject support and reactive lists.

The composer model dropdown groups ``AiModel`` rows by canonical name and
passes that list of dicts straight to ``QuerySetView`` instead of a Django
QuerySet.  These tests pin the generalization so QuerySets keep working too.

The second half pins the ``observable_keys`` upgrade: on a ``create`` event
the new row is inserted (only that wrapper), on ``delete`` it is removed, and
``update`` is left to the row views.  A fake redis + fake UI instance stand in
for the consumer-side plumbing, and ``insert_element`` is stubbed so no real
rendering/DOM round-trips are needed.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import fakeredis
from django.test import SimpleTestCase, TestCase

from runtime import observables
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView


class _Item(ModelView):
    DOM_ELEMENT_CLASS = "item"


class Thing:
    """Named model stand-in so ``_meta.model.__name__`` resolves to "Thing"."""


class _ThingMeta:
    model = Thing


class _Thing:
    """ORM-ish row: has ``pk`` and a ``_meta.model`` for name resolution."""

    _meta = _ThingMeta

    def __init__(self, label, pk=None):
        self.label = label
        self.pk = pk if pk is not None else label


class _WeakList(list):
    """Plain lists can't be weak-referenced, and QuerySetView is itself a
    ModelView that weak-refs its subject — so list subjects must be a list
    subclass (as ``ModelGroupList`` is)."""


class MockParent:
    def __init__(self):
        self._instance = MagicMock()

    def _add_child(self, child):
        pass


class QuerySetViewListSubjectTest(TestCase):
    def _view(self, subject, **kwargs):
        return QuerySetView(
            subject=subject, parent=MockParent(), item_class=_Item, **kwargs
        )

    def test_plain_list_subject_wraps_items(self):
        things = _WeakList([_Thing("a"), _Thing("b"), _Thing("c")])
        view = self._view(subject=things)
        view.set_visible(True)
        self.assertEqual([i.subject for i in view.get_items()], list(things))
        self.assertTrue(all(i.parent is view for i in view.get_items()))

    def test_dict_subject_items_supported(self):
        groups = _WeakList([_Thing("Alpha"), _Thing("Beta")])
        view = self._view(subject=groups)
        view.set_visible(True)
        self.assertEqual(view.get_items()[0].subject.label, "Alpha")

    def test_queryset_like_subject_iterated_via_all(self):
        class FakeQuerySet:
            def all(self):
                return [_Thing(7), _Thing(8), _Thing(9)]

        view = self._view(subject=FakeQuerySet())
        view.set_visible(True)
        self.assertEqual(
            [i.subject.label for i in view.get_items()], [7, 8, 9]
        )

    def test_filter_function_applied_to_list_items(self):
        things = _WeakList([_Thing("a"), _Thing("b"), _Thing("c")])
        view = self._view(
            subject=things,
            filter_function=lambda item: item.subject.label == "b",
        )
        view.set_visible(True)
        self.assertEqual([i.subject for i in view.get_items()], [things[0], things[2]])

    def test_recreate_rebuilds_from_list(self):
        things = _WeakList([_Thing("a"), _Thing("b")])
        view = self._view(subject=things)
        view.set_visible(True)
        view._recreate()
        self.assertEqual([i.subject for i in view.get_items()], list(things))


# ---------------------------------------------------------------------------
# Reactive (observable_keys) support
# ---------------------------------------------------------------------------


class FakeInstance:
    """Minimal stand-in for PyHtmlGuiInstance (subscription bookkeeping)."""

    def __init__(self, instance_key="test-instance"):
        from ui.lib.pyHtmlGui.pyhtmlgui.lib.weakFunctionReferences import (
            WeakFunctionReferences,
        )

        self.instance_key = instance_key
        self._function_references = WeakFunctionReferences()
        self.observed_views = {}
        self.js_calls = []

    def call_javascript(self, name, args=None, skip_results=False):
        self.js_calls.append((name, args))

    def add_css_string(self, *args, **kwargs):
        pass


class ReactiveParent:
    def __init__(self, instance):
        self._instance = instance

    def _add_child(self, child):
        pass


class _RecordingQuerySetView(QuerySetView):
    """Records DOM insertions instead of rendering into a fake JS bridge."""

    def __init__(self, *args, **kwargs):
        self.inserted = []
        super().__init__(*args, **kwargs)

    def insert_element(self, index, element):
        self.inserted.append((index, element))
        return True


class QuerySetViewReactiveTest(SimpleTestCase):
    def setUp(self):
        self.redis = fakeredis.FakeStrictRedis(decode_responses=True)
        self.patch = patch.object(
            observables, "get_redis", return_value=self.redis
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.instance = FakeInstance()

    def _pks(self, view):
        return [w.subject.pk for w in view.get_items()]

    def _view(self, things, **kwargs):
        return _RecordingQuerySetView(
            subject=things,
            parent=ReactiveParent(self.instance),
            item_class=_Item,
            **kwargs,
        )

    def _obs(self, key):
        return self.redis.hget("agentone:obs:" + key, self.instance.instance_key)

    # -- subscription bookkeeping --------------------------------------

    def test_observable_keys_registers_on_init(self):
        view = self._view(_WeakList(), observable_keys="Thing.session:5")
        self.assertEqual(view._observable_keys, ["Thing.session:5"])
        self.assertIsNotNone(self._obs("Thing.session:5"))
        self.assertIn("Thing.session:5", self.instance.observed_views)

    def test_set_observable_keys_replaces_previous(self):
        view = self._view(_WeakList(), observable_keys="Thing.session:5")
        view.set_observable_keys("Other.key:1")
        self.assertIsNone(self._obs("Thing.session:5"))
        self.assertIsNotNone(self._obs("Other.key:1"))
        self.assertEqual(view._observable_keys, ["Other.key:1"])

    def test_delete_unsubscribes(self):
        view = self._view(_WeakList(), observable_keys="Thing.session:5")
        view.delete()
        self.assertIsNone(self._obs("Thing.session:5"))
        self.assertEqual(view._observed_function_ids, [])

    def test_no_instance_is_a_noop(self):
        view = QuerySetView(
            subject=_WeakList(),
            parent=ReactiveParent(None),
            item_class=_Item,
            observable_keys="Thing.session:5",
        )
        self.assertEqual(view._observable_keys, ["Thing.session:5"])

    # -- create --------------------------------------------------------

    def test_create_inserts_only_the_new_row(self):
        things = _WeakList([_Thing("a", pk=1)])
        view = self._view(things, observable_keys="Thing.session:5")
        view.set_visible(True)
        self.assertEqual(self._pks(view), [1])

        things.append(_Thing("b", pk=2))
        view._on_orm_event(model="Thing", pk=2, action="create")

        self.assertEqual(self._pks(view), [1, 2])
        # Inserted at index 1 in the rendered order, one DOM call only.
        self.assertEqual(len(view.inserted), 1)
        self.assertEqual(view.inserted[0][0], 1)
        self.assertEqual(view.inserted[0][1].subject.pk, 2)

    def test_create_duplicate_event_is_ignored(self):
        things = _WeakList([_Thing("a", pk=1)])
        view = self._view(things, observable_keys="Thing.session:5")
        view.set_visible(True)
        things.append(_Thing("b", pk=2))
        view._on_orm_event(model="Thing", pk=2, action="create")
        view._on_orm_event(model="Thing", pk=2, action="create")
        self.assertEqual(self._pks(view), [1, 2])
        self.assertEqual(len(view.inserted), 1)

    def test_create_ignored_when_row_not_in_list(self):
        things = _WeakList([_Thing("a", pk=1)])
        view = self._view(things, observable_keys="Thing.session:5")
        view.set_visible(True)
        # A new row that does not match the list's queryset/filters.
        view._on_orm_event(model="Thing", pk=99, action="create")
        self.assertEqual(self._pks(view), [1])
        self.assertEqual(view.inserted, [])

    def test_create_respects_filter_function(self):
        things = _WeakList([_Thing("a", pk=1)])
        view = self._view(
            things,
            observable_keys="Thing.session:5",
            filter_function=lambda w: w.subject.pk == 2,
        )
        view.set_visible(True)
        things.append(_Thing("b", pk=2))
        view._on_orm_event(model="Thing", pk=2, action="create")
        self.assertEqual(self._pks(view), [1])
        self.assertEqual(view.inserted, [])

    def test_create_keeps_queryset_order(self):
        # Newest-first order (as order_by("-created_at") would give).
        things = _WeakList([_Thing("b", pk=2), _Thing("a", pk=1)])
        view = self._view(things, observable_keys="Thing.session:5")
        view.set_visible(True)
        self.assertEqual(self._pks(view), [2, 1])

        things.insert(0, _Thing("c", pk=3))
        view._on_orm_event(model="Thing", pk=3, action="create")
        self.assertEqual(self._pks(view), [3, 2, 1])
        self.assertEqual(view.inserted[0][0], 0)

    def test_create_honours_sort_key(self):
        things = _WeakList([_Thing("a", pk=1), _Thing("c", pk=3)])
        view = self._view(
            things,
            observable_keys="Thing.session:5",
            sort_key=lambda w: w.subject.pk,
        )
        view.set_visible(True)
        things.append(_Thing("b", pk=2))
        view._on_orm_event(model="Thing", pk=2, action="create")
        self.assertEqual(self._pks(view), [1, 2, 3])
        self.assertEqual(view.inserted[0][0], 1)

    # -- delete --------------------------------------------------------

    def test_delete_removes_matching_row_only(self):
        things = _WeakList([_Thing("a", pk=1,), _Thing("b", pk=2)])
        view = self._view(things, observable_keys="Thing.session:5")
        view.set_visible(True)

        things.remove(things[1])
        view._on_orm_event(model="Thing", pk=2, action="delete")
        self.assertEqual(self._pks(view), [1])

    def test_delete_wrong_model_is_ignored(self):
        things = _WeakList([_Thing("a", pk=1)])
        view = self._view(things, observable_keys="Thing.session:5")
        view.set_visible(True)
        view._on_orm_event(model="Other", pk=1, action="delete")
        self.assertEqual(self._pks(view), [1])

    # -- update / visibility -------------------------------------------

    def test_update_event_is_ignored(self):
        things = _WeakList([_Thing("a", pk=1)])
        view = self._view(things, observable_keys="Thing.session:5")
        view.set_visible(True)
        view._on_orm_event(model="Thing", pk=1, action="update")
        self.assertEqual(self._pks(view), [1])
        self.assertEqual(view.inserted, [])

    def test_event_while_invisible_defers_to_next_show(self):
        things = _WeakList([_Thing("a", pk=1)])
        view = self._view(things, observable_keys="Thing.session:5")
        view.set_visible(True)
        view.set_visible(False)

        things.append(_Thing("b", pk=2))
        view._on_orm_event(model="Thing", pk=2, action="create")
        self.assertEqual(view.get_items(), [])

        view.set_visible(True)
        self.assertEqual(self._pks(view), [1, 2])