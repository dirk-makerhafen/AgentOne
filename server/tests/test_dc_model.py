"""Tests for DataCollection and CollectionItem models."""
from __future__ import annotations

from django.db import IntegrityError
from django.test import TestCase

from server.models.collections import DataCollection, CollectionItem
from server.tests.dc_test_helpers import create_agent, create_task, create_session, create_completed_call
from server.tests.test_reporter import TestReport


class DataCollectionModelTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def test_create_stream(self):
        dc = DataCollection.objects.create(name="test.stream")
        self.assertEqual(dc.name, "test.stream")
        self.assertEqual(dc.collection_type, "stream")
        self.assertTrue(dc.is_active)
        self.assertEqual(dc.sources, [])
        self.assertEqual(dc.processor, {})
        self.assertEqual(dc.on_removed, {})
        self.assertEqual(dc.member_field, "")
        self.assertEqual(dc.score_field, "")
        self.assertEqual(dc.retroactive_on_source_change, 0)
        self.assertEqual(dc.max_reprocess, 0)
        self.report.add("test_create_stream", "PASS",
            "Creates a stream-type DataCollection with all default values. Verifies name, type, active state, "
            "and every field has the expected default. Ensures new collections are immediately usable.")

    def test_create_set(self):
        dc = DataCollection.objects.create(
            name="test.set",
            collection_type="set",
            sources=[{"type": "query", "agent": ["base"], "function": ["ping"]}],
            processor={"agent": "base", "function": "read"},
            on_removed={"agent": "base", "function": "delete"},
            member_field="item.id",
            score_field="item.score",
            max_reprocess=50,
        )
        self.assertEqual(dc.collection_type, "set")
        self.assertEqual(len(dc.sources), 1)
        self.assertEqual(dc.processor["agent"], "base")
        self.assertEqual(dc.on_removed["function"], "delete")
        self.assertEqual(dc.member_field, "item.id")
        self.assertEqual(dc.max_reprocess, 50)
        self.report.add("test_create_set", "PASS",
            "Creates a set-type DataCollection with non-default values for every optional field. "
            "Confirms sources, processor, on_removed, member_field, and max_reprocess are all stored faithfully.")

    def test_unique_name(self):
        DataCollection.objects.create(name="unique.stream")
        with self.assertRaises(IntegrityError):
            DataCollection.objects.create(name="unique.stream")
        self.report.add("test_unique_name", "PASS",
            "Verifies that the unique constraint on DataCollection.name rejects duplicate names at the DB level. "
            "Duplicates would cause data corruption in YAML-based name lookups.")

    def test_str_stream(self):
        dc = DataCollection.objects.create(name="my.stream")
        self.assertEqual(str(dc), "Stream[my.stream]")
        self.report.add("test_str_stream", "PASS",
            "Verifies the human-readable string representation for stream collections. "
            "Used in UI and log output.")

    def test_str_set(self):
        dc = DataCollection.objects.create(name="my.set", collection_type="set")
        self.assertEqual(str(dc), "Ordered Set[my.set]")
        self.report.add("test_str_set", "PASS",
            "Verifies the human-readable string representation for ordered-set collections.")

    def test_description_default_blank(self):
        dc = DataCollection.objects.create(name="no-desc")
        self.assertEqual(dc.description, "")
        self.report.add("test_description_default_blank", "PASS",
            "Confirms description defaults to empty string, not None.")

    def test_collection_type_choices(self):
        dc = DataCollection.objects.create(name="s", collection_type="stream")
        self.assertEqual(dc.get_collection_type_display(), "Stream")
        dc2 = DataCollection.objects.create(name="t", collection_type="set")
        self.assertEqual(dc2.get_collection_type_display(), "Ordered Set")
        self.report.add("test_collection_type_choices", "PASS",
            "Checks that both COLLECTION_TYPES choices are legal and produce the correct display labels.")

    def test_sources_json_round_trip(self):
        sources = [
            {"type": "query", "agent": ["base"], "function": ["ping"]},
            {"type": "stream", "stream": "other"},
        ]
        dc = DataCollection.objects.create(name="multi-source", sources=sources)
        dc.refresh_from_db()
        self.assertEqual(dc.sources, sources)
        self.report.add("test_sources_json_round_trip", "PASS",
            "Verifies JSON serialization round-trip for the sources field. "
            "MySQL JSONField stores and retrieves complex multi-entry source lists intact.")

    def test_is_active_default_true(self):
        dc = DataCollection.objects.create(name="active-default")
        self.assertTrue(dc.is_active)
        self.report.add("test_is_active_default_true", "PASS",
            "New collections are active by default so they participate in data-flow dispatch immediately.")

    def test_is_active_false(self):
        dc = DataCollection.objects.create(name="paused", is_active=False)
        self.assertFalse(dc.is_active)
        self.report.add("test_is_active_false", "PASS",
            "Inactive collections can be created explicitly. The dispatch logic skips these.")


class CollectionItemModelTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def setUp(self):
        self.collection = DataCollection.objects.create(name="item-test.stream")

    def test_create_item(self):
        item = CollectionItem.objects.create(
            collection=self.collection, member="abc123", score=1.0, value={"msg": "hello"},
        )
        self.assertEqual(item.member, "abc123")
        self.assertEqual(item.score, 1.0)
        self.assertEqual(item.value, {"msg": "hello"})
        self.assertIsNone(item.source_call)
        self.report.add("test_create_item", "PASS",
            "Creates a minimal CollectionItem with all required fields and verifies defaults. "
            "source_call is None when not provided, as expected for manually created items.")

    def test_unique_together_collection_member(self):
        CollectionItem.objects.create(collection=self.collection, member="dup", score=1.0)
        with self.assertRaises(IntegrityError):
            CollectionItem.objects.create(collection=self.collection, member="dup", score=2.0)
        self.report.add("test_unique_together_collection_member", "PASS",
            "Verifies the (collection, member) unique constraint prevents duplicate members within a collection. "
            "This is the core dedup mechanism for sets.")

    def test_same_member_different_collection_ok(self):
        c2 = DataCollection.objects.create(name="other.stream")
        CollectionItem.objects.create(collection=self.collection, member="shared", score=1.0)
        item = CollectionItem.objects.create(collection=c2, member="shared", score=2.0)
        self.assertEqual(item.member, "shared")
        self.report.add("test_same_member_different_collection_ok", "PASS",
            "The same member string is allowed in different collections. "
            "The unique constraint is scoped to (collection, member), not global.")

    def test_score_default(self):
        item = CollectionItem.objects.create(collection=self.collection, member="default-score")
        self.assertEqual(item.score, 0.0)
        self.report.add("test_score_default", "PASS",
            "Score defaults to 0.0 when not specified, ensuring numeric ordering always works.")

    def test_value_default(self):
        item = CollectionItem.objects.create(collection=self.collection, member="default-value")
        self.assertEqual(item.value, {})
        self.report.add("test_value_default", "PASS",
            "Value defaults to empty dict, ensuring JSONField operations don't fail on missing data.")

    def test_str(self):
        item = CollectionItem.objects.create(collection=self.collection, member="str-member", score=42.5)
        self.assertEqual(str(item), "[item-test.stream] str-member (score=42.5)")
        self.report.add("test_str", "PASS",
            "String representation includes collection name, member, and score for easy debugging.")

    def test_with_source_call(self):
        agent, av = create_agent("call-agent")
        td = create_task("producer", agent=agent)
        session, sv = create_session(agent, av)
        call = create_completed_call(agent, td, session, sv)
        item = CollectionItem.objects.create(
            collection=self.collection, member="with-call", score=1.0, source_call=call,
        )
        self.assertEqual(item.source_call, call)
        self.assertIn(item, call.collection_items.all())
        self.report.add("test_with_source_call", "PASS",
            "Items can reference their producing AgentTaskCall. The reverse relation "
            "(call.collection_items) also works, enabling provenance tracking.")

    def test_cascade_delete_collection(self):
        CollectionItem.objects.create(collection=self.collection, member="cascade-test", score=1.0)
        self.collection.delete()
        self.assertEqual(CollectionItem.objects.count(), 0)
        self.report.add("test_cascade_delete_collection", "PASS",
            "Deleting a DataCollection cascades to delete all its items. "
            "Ensures no orphan CollectionItems remain.")

    def test_source_call_set_null_on_delete(self):
        agent, av = create_agent("call-agent2")
        td = create_task("producer2", agent=agent)
        session, sv = create_session(agent, av)
        call = create_completed_call(agent, td, session, sv)
        item = CollectionItem.objects.create(
            collection=self.collection, member="null-on-del", score=1.0, source_call=call,
        )
        call.delete()
        item.refresh_from_db()
        self.assertIsNone(item.source_call)
        self.report.add("test_source_call_set_null_on_delete", "PASS",
            "Deleting the source AgentTaskCall sets source_call to null (SET_NULL) rather than cascading. "
            "Preserves the collection item even when the producing call is cleaned up.")
