"""Tests for data-flow dispatch and propagation."""
from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from server.models.collections import DataCollection, CollectionItem
from server.tests.dc_test_helpers import create_agent, create_task, create_session, create_completed_call
from server.tasks.tick_scheduler import _dispatch_data_flows, _propagate_from_collections
from server.tests.test_reporter import TestReport


class DispatchDataFlowsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def setUp(self):
        self.agent, self.av = create_agent("dispatch-agent")
        self.task = create_task("dispatch-func", agent=self.agent)
        self.session, self.sv = create_session(self.agent, self.av)
        self.call = create_completed_call(self.agent, self.task, self.session, self.sv, carguments={"key": "val"})
        self.processor_task = create_task("processor-task", agent=self.agent)

    def test_dispatch_creates_collection_item(self):
        DataCollection.objects.create(
            name="dispatch-test.stream",
            sources=[{"type": "query", "agent": ["dispatch-agent"], "function": ["dispatch-func"]}],
            processor={"agent": "dispatch-agent", "function": "processor-task"},
        )
        _dispatch_data_flows()
        count = CollectionItem.objects.filter(collection__name="dispatch-test.stream").count()
        self.assertEqual(count, 1)
        self.report.add("test_dispatch_creates_collection_item", "PASS",
            "A completed call matching query-type source criteria triggers _dispatch_data_flows "
            "to create exactly one CollectionItem in the target collection.")

    def test_dispatch_skips_inactive_flow(self):
        DataCollection.objects.create(
            name="inactive.stream", is_active=False,
            sources=[{"type": "query", "agent": ["dispatch-agent"], "function": ["dispatch-func"]}],
            processor={"agent": "dispatch-agent", "function": "processor-task"},
        )
        _dispatch_data_flows()
        count = CollectionItem.objects.filter(collection__name="inactive.stream").count()
        self.assertEqual(count, 0)
        self.report.add("test_dispatch_skips_inactive_flow", "PASS",
            "Inactive (is_active=False) collections are skipped entirely during dispatch. "
            "No items are created even when source criteria match.")

    def test_dispatch_skips_no_query_source(self):
        DataCollection.objects.create(
            name="no-query.stream",
            sources=[{"type": "stream", "stream": "some-other"}],
            processor={"agent": "dispatch-agent", "function": "processor-task"},
        )
        _dispatch_data_flows()
        count = CollectionItem.objects.filter(collection__name="no-query.stream").count()
        self.assertEqual(count, 0)
        self.report.add("test_dispatch_skips_no_query_source", "PASS",
            "Dispatch only processes collections with query-type sources. "
            "Stream/set-type sources are handled by _propagate_from_collections instead.")

    def test_dispatch_respects_source_criteria(self):
        DataCollection.objects.create(
            name="no-match.stream",
            sources=[{"type": "query", "agent": ["other-agent"], "function": ["dispatch-func"]}],
            processor={"agent": "dispatch-agent", "function": "processor-task"},
        )
        _dispatch_data_flows()
        count = CollectionItem.objects.filter(collection__name="no-match.stream").count()
        self.assertEqual(count, 0)
        self.report.add("test_dispatch_respects_source_criteria", "PASS",
            "Calls that do not match the source criteria (wrong agent) are not dispatched. "
            "Source filtering is precise.")

    def test_dispatch_only_one_item_per_tick(self):
        agent2, av2 = create_agent("dispatch-agent2")
        session2, sv2 = create_session(agent2, av2)
        create_completed_call(agent2, self.task, session2, sv2, carguments={"another": "call"})
        DataCollection.objects.create(
            name="multi-match.stream",
            sources=[{"type": "query", "agent": ["dispatch-agent*"], "function": ["dispatch-func"]}],
            processor={"agent": "dispatch-agent", "function": "processor-task"},
        )
        _dispatch_data_flows()
        count = CollectionItem.objects.filter(collection__name="multi-match.stream").count()
        self.assertEqual(count, 1)
        self.report.add("test_dispatch_only_one_item_per_tick", "PASS",
            "Only one item per flow per tick is dispatched (conservative throttling). "
            "Even when multiple calls match, only the first is processed. "
            "This prevents flooding during catch-up after downtime.")

    def test_stream_auto_member_and_score(self):
        DataCollection.objects.create(
            name="auto.stream",
            sources=[{"type": "query", "agent": ["dispatch-agent"], "function": ["dispatch-func"]}],
            processor={"agent": "dispatch-agent", "function": "processor-task"},
        )
        _dispatch_data_flows()
        item = CollectionItem.objects.get(collection__name="auto.stream")
        self.assertEqual(len(item.member), 32)
        self.assertIsInstance(item.score, float)
        self.assertGreater(item.score, 0)
        self.report.add("test_stream_auto_member_and_score", "PASS",
            "Streams automatically generate a 32-char hash member and float timestamp score. "
            "No manual configuration is needed for stream items.")


class PropagateFromCollectionsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def setUp(self):
        self.agent, self.av = create_agent("prop-agent")
        self.source_task = create_task("prop-source", agent=self.agent)
        self.processor_task = create_task("prop-processor", agent=self.agent)
        self.session, self.sv = create_session(self.agent, self.av)

        self.source_stream = DataCollection.objects.create(
            name="source.stream",
            sources=[{"type": "query", "agent": ["prop-agent"], "function": ["prop-source"]}],
            processor={"agent": "prop-agent", "function": "prop-processor"},
        )
        self.derived_stream = DataCollection.objects.create(
            name="derived.stream",
            sources=[{"type": "stream", "stream": "source.stream"}],
            processor={"agent": "prop-agent", "function": "prop-processor"},
        )

        self.source_call = create_completed_call(
            self.agent, self.source_task, self.session, self.sv, carguments={"msg": "propagate"},
        )
        self.item = CollectionItem.objects.create(
            collection=self.source_stream, member="prop-item", score=1.0,
            value={"msg": "propagate"}, source_call=self.source_call,
        )

    def test_propagate_picks_up_recent_item(self):
        _propagate_from_collections()
        count = CollectionItem.objects.filter(collection__name="derived.stream").count()
        self.assertEqual(count, 1)
        self.report.add("test_propagate_picks_up_recent_item", "PASS",
            "A recent item in the source stream (within the 30s window) is propagated "
            "to the derived stream that sources from it.")

    def test_propagate_skips_old_item(self):
        CollectionItem.objects.filter(pk=self.item.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=1),
        )
        self.item.refresh_from_db()
        _propagate_from_collections()
        count = CollectionItem.objects.filter(collection__name="derived.stream").count()
        self.assertEqual(count, 0)
        self.report.add("test_propagate_skips_old_item", "PASS",
            "Items older than the 30s propagation window are skipped. "
            "This prevents re-processing of stale items on every tick.")

    def test_propagate_set_source(self):
        DataCollection.objects.create(
            name="source.set", collection_type="set",
            processor={"agent": "prop-agent", "function": "prop-processor"},
        )
        DataCollection.objects.create(
            name="derived-from-set.stream",
            sources=[{"type": "set", "set": "source.set"}],
            processor={"agent": "prop-agent", "function": "prop-processor"},
        )
        call = create_completed_call(
            self.agent, self.source_task, self.session, self.sv, carguments={"x": 1},
        )
        CollectionItem.objects.create(
            collection=DataCollection.objects.get(name="source.set"), member="set-item", score=1.0, value={"x": 1}, source_call=call,
        )
        _propagate_from_collections()
        count = CollectionItem.objects.filter(collection__name="derived-from-set.stream").count()
        self.assertEqual(count, 1)
        self.report.add("test_propagate_set_source", "PASS",
            "Set-type sources also propagate their new items to derived flows. "
            "Both stream→derived and set→derived propagation work.")
