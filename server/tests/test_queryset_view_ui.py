"""Tests for the flat list-subject support added to QuerySetView.

The composer model dropdown groups ``AiModel`` rows by canonical name and
passes that list of dicts straight to ``QuerySetView`` instead of a Django
QuerySet.  These tests pin the generalization so QuerySets keep working too.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from django.test import TestCase

from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView


class _Item(ModelView):
    DOM_ELEMENT_CLASS = "item"


class _Thing:
    def __init__(self, label):
        self.label = label


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