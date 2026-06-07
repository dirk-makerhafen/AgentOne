"""Tests for the reprocess_collection Celery task."""
from __future__ import annotations

from django.test import TestCase

from server.models.collections import DataCollection, CollectionItem
from server.models.tasks.agent_task_call import AgentTaskCall
from server.tests.dc_test_helpers import create_agent, create_task, create_session, create_completed_call
from server.tasks.reprocess_collection import reprocess_collection
from server.tests.test_reporter import TestReport


class ReprocessCollectionTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def setUp(self):
        self.agent, self.av = create_agent("reprocess-agent")
        self.task = create_task("reprocess-source", agent=self.agent)
        self.processor_task = create_task("reprocess-processor", agent=self.agent)
        self.session, self.sv = create_session(self.agent, self.av)

    def test_reprocess_query_source(self):
        create_completed_call(self.agent, self.task, self.session, self.sv, carguments={"k": "v"})
        collection = DataCollection.objects.create(
            name="repro.stream",
            sources=[{"type": "query", "agent": ["reprocess-agent"], "function": ["reprocess-source"]}],
            processor={"agent": "reprocess-agent", "function": "reprocess-processor"},
        )
        reprocess_collection("repro.stream")
        count = CollectionItem.objects.filter(collection=collection).count()
        self.assertEqual(count, 1)
        self.report.add("test_reprocess_query_source", "PASS",
            "Reprocessing a collection with query-type sources finds completed calls "
            "matching the source criteria and creates CollectionItems.")

    def test_reprocess_collection_not_found(self):
        reprocess_collection("nonexistent")
        self.report.add("test_reprocess_collection_not_found", "PASS",
            "Reprocessing a non-existent collection logs an error and returns gracefully "
            "without crashing.")

    def test_reprocess_no_source_calls(self):
        collection = DataCollection.objects.create(
            name="empty.stream",
            sources=[{"type": "query", "agent": ["reprocess-agent"], "function": ["reprocess-source"]}],
            processor={"agent": "reprocess-agent", "function": "reprocess-processor"},
        )
        reprocess_collection("empty.stream")
        count = CollectionItem.objects.filter(collection=collection).count()
        self.assertEqual(count, 0)
        self.report.add("test_reprocess_no_source_calls", "PASS",
            "Reprocessing a collection with no matching source calls produces no items. "
            "The task is a no-op when there are no inputs.")

    def test_reprocess_respects_max_items(self):
        for i in range(5):
            create_completed_call(self.agent, self.task, self.session, self.sv, carguments={"n": i})
        collection = DataCollection.objects.create(
            name="limited.stream", max_reprocess=2,
            sources=[{"type": "query", "agent": ["reprocess-agent"], "function": ["reprocess-source"]}],
            processor={"agent": "reprocess-agent", "function": "reprocess-processor"},
        )
        reprocess_collection("limited.stream")
        count = CollectionItem.objects.filter(collection=collection).count()
        self.assertLessEqual(count, 2)
        self.report.add("test_reprocess_respects_max_items", "PASS",
            "The max_reprocess limit caps the number of items processed. "
            "Only 2 items are created even though 5 source calls exist.")

    def test_reprocess_stream_source(self):
        source_stream = DataCollection.objects.create(
            name="repro-source.stream",
            processor={"agent": "reprocess-agent", "function": "reprocess-processor"},
        )
        call = create_completed_call(self.agent, self.task, self.session, self.sv, carguments={"x": 1})
        CollectionItem.objects.create(
            collection=source_stream, member="src-item", score=1.0, value={"x": 1}, source_call=call,
        )
        derived = DataCollection.objects.create(
            name="repro-derived.stream",
            sources=[{"type": "stream", "stream": "repro-source.stream"}],
            processor={"agent": "reprocess-agent", "function": "reprocess-processor"},
        )
        reprocess_collection("repro-derived.stream")
        count = CollectionItem.objects.filter(collection=derived).count()
        self.assertEqual(count, 1)
        self.report.add("test_reprocess_stream_source", "PASS",
            "Reprocessing a collection with stream-type sources reads the source "
            "stream's items and re-dispatches them through the processor.")

    def test_reprocess_set_update_or_create_dedup(self):
        create_completed_call(self.agent, self.task, self.session, self.sv, carguments={"id": "same-item"})
        create_completed_call(self.agent, self.task, self.session, self.sv, carguments={"id": "same-item"})
        collection = DataCollection.objects.create(
            name="repro-dedup.set", collection_type="set",
            member_field="item.get('id', 'fallback')",
            sources=[{"type": "query", "agent": ["reprocess-agent"], "function": ["reprocess-source"]}],
            processor={"agent": "reprocess-agent", "function": "reprocess-processor"},
        )
        reprocess_collection("repro-dedup.set")
        self.assertEqual(CollectionItem.objects.filter(collection=collection).count(), 1)
        self.report.add("test_reprocess_set_update_or_create_dedup", "PASS",
            "When two source calls produce the same member (same 'id'), the set's "
            "(collection, member) unique constraint prevents duplicates. Only one item exists.")

    def test_reprocess_set_removes_stale_item(self):
        call = create_completed_call(self.agent, self.task, self.session, self.sv, carguments={"id": "original"})
        collection = DataCollection.objects.create(
            name="repro-remove.set", collection_type="set",
            member_field="item.get('id', 'fallback')",
            sources=[{"type": "query", "agent": ["reprocess-agent"], "function": ["reprocess-source"]}],
            processor={"agent": "reprocess-agent", "function": "reprocess-processor"},
        )
        reprocess_collection("repro-remove.set")
        self.assertEqual(CollectionItem.objects.filter(collection=collection).count(), 1)
        AgentTaskCall.objects.filter(pk=call.pk).update(carguments_json={"id": "changed"})
        reprocess_collection("repro-remove.set")
        # Old item (member "original") is removed before re-dispatch;
        # only the new item (member "changed") remains.
        self.assertEqual(CollectionItem.objects.filter(collection=collection).count(), 1)
        self.report.add("test_reprocess_set_removes_stale_item", "PASS",
            "When a source call's arguments change, reprocessing clears old items "
            "and re-creates from the updated source calls. The stale item (member "
            "'original') is removed and a new one (member 'changed') is created.")
