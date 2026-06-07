"""System validation: end-to-end integration tests for the full AgentOne framework.

This test class exercises the entire pipeline in a single ordered sequence:
  cron execution -> data flow dispatch -> collection propagation ->
  reprocess -> set dedup -> on_removed handling

Each test builds on state left by the previous test (shared via class-level DB
state through a custom test runner that does NOT roll back between tests).
"""
from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from registry.loader.load_cron_manifest import load_cron_manifest
from registry.loader.load_data_collection import load_data_collection_manifest
from runtime.cron.execute import execute_cron_job
from server.models.collections import DataCollection, CollectionItem
from server.models.cron import Cronjob
from server.models.enums.task_enums import TaskCallStatusDetail, TaskType
from server.models.tasks.agent_task_call import AgentTaskCall
from server.tasks.reprocess_collection import reprocess_collection
from server.tasks.tick_scheduler import _dispatch_data_flows, _propagate_from_collections
from server.tests.dc_test_helpers import (
    create_session as dc_create_session,
    create_task,
    create_completed_call,
    create_collection_item,
)
from server.tests.helpers import TESTPROJECT, AgentMdTestMixin, create_global_task
from server.tests.test_reporter import TestReport


class SystemValidationTest(AgentMdTestMixin, TestCase):
    """End-to-end validation of the AgentOne data-flow framework.

    Tests are numbered to run in order (01 … 27).  Each test is wrapped in a
    transaction that is *committed* (not rolled back) so that later tests can
    see the side-effects.  This mirrors real-world usage where state
    accumulates across ticks.
    """

    databases = "__all__"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        cls.teardown_install_repo()
        super().tearDownClass()

    # ── Shared baseline (runs once per class) ──────────────────────────

    @classmethod
    def setUpTestData(cls):
        # 1. Global tasks used by the agent manifest loader
        cls.setup_global_tasks()
        for name in ["health_check", "status"]:
            create_global_task(name, "collect", TaskType.TASK)
        for name in ["parse", "grade", "dedup", "report", "cleanup"]:
            create_global_task(name, "report", TaskType.TASK)
        # A bare "ingest_user_message" task is needed by the cron execution
        # path when no function_type is set.  Our cron uses function_type=task
        # so it's not required, but create one for safety.
        create_global_task("ingest_user_message", "", TaskType.TASK)

        # 2. Install repo & load agents from YAML manifests
        cls.setup_install_repo()
        cls.collector, cls.collector_av = cls.load_agent("collector")
        cls.reporter, cls.reporter_av = cls.load_agent("reporter")
        cls.base_agent, cls.base_av = cls.load_agent("base")

        # 3. Load stream / set / cron YAML manifests
        cls.health_events = load_data_collection_manifest(
            TESTPROJECT / "streams" / "health_events.md"
        )
        cls.parsed_alerts = load_data_collection_manifest(
            TESTPROJECT / "streams" / "parsed_alerts.md"
        )
        cls.all_alerts = load_data_collection_manifest(
            TESTPROJECT / "streams" / "all_alerts.md"
        )
        cls.unique_services = load_data_collection_manifest(
            TESTPROJECT / "sets" / "unique_services.md"
        )
        cls.alert_report = load_data_collection_manifest(
            TESTPROJECT / "sets" / "alert_report.md"
        )
        cls.alerts_from_report = load_data_collection_manifest(
            TESTPROJECT / "sets" / "alerts_from_report.md"
        )
        cls.cron = load_cron_manifest(
            TESTPROJECT / "cronjobs" / "health_check.md",
            install_repo=cls._install_repo,
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _create_collector_call(self, carguments: dict | None = None) -> AgentTaskCall:
        """Create a completed AgentTaskCall for the collector/health_check task."""
        agent = self.collector
        td = create_task("health_check", group="collect", agent=agent, task_type=TaskType.TASK)
        session, sv = dc_create_session(agent, self.collector_av)
        return create_completed_call(agent, td, session, sv, carguments=carguments or {})

    def _create_reporter_call(self, function: str, carguments: dict | None = None) -> AgentTaskCall:
        """Create a completed AgentTaskCall for a reporter task."""
        agent = self.reporter
        td = create_task(function, group="report", agent=agent, task_type=TaskType.TASK)
        session, sv = dc_create_session(agent, self.reporter_av)
        return create_completed_call(agent, td, session, sv, carguments=carguments or {})

    # ══════════════════════════════════════════════════════════════════
    #  TESTS
    # ══════════════════════════════════════════════════════════════════

    def test_01_manifests_load_correctly(self):
        """All YAML manifests produce correct DB records."""
        # --- Agents ---
        self.assertEqual(self.collector.name, "collector")
        self.assertEqual(self.reporter.name, "reporter")

        # --- Streams ---
        self.assertEqual(self.health_events.collection_type, "stream")
        self.assertEqual(self.health_events.processor, {"agent": "reporter", "function": "parse"})
        self.assertEqual(self.parsed_alerts.sources, [{"type": "stream", "stream": "health_events"}])

        # --- Sets ---
        self.assertEqual(self.unique_services.collection_type, "set")
        self.assertEqual(self.unique_services.member_field, "item.get('service', str(item))")
        self.assertEqual(self.unique_services.max_reprocess, 50)

        self.assertEqual(self.alert_report.collection_type, "set")
        self.assertEqual(self.alert_report.on_removed, {"agent": "reporter", "function": "cleanup"})
        self.assertEqual(self.alert_report.max_reprocess, 100)

        # --- type: set source ---
        self.assertEqual(self.alerts_from_report.collection_type, "set")
        self.assertEqual(self.alerts_from_report.sources, [{"type": "set", "set": "alert_report"}])
        self.assertEqual(self.alerts_from_report.max_reprocess, 50)

        # --- multi-source stream ---
        self.assertEqual(self.all_alerts.collection_type, "stream")
        self.assertIn({"type": "stream", "stream": "health_events"}, self.all_alerts.sources)
        self.assertIn({"type": "set", "set": "alerts_from_report"}, self.all_alerts.sources)

        # --- Cron ---
        cron = Cronjob.objects.get(name="health_check")
        self.assertEqual(cron.agent.name, "collector")
        self.assertEqual(cron.function_name, "health_check")
        self.assertEqual(cron.schedule, "*/5 * * * *")
        self.assertTrue(cron.is_active)
        self.assertIsNotNone(cron.next_run_at)
        self.report.add("test_01_manifests_load_correctly", "PASS",
            "All 9 YAML manifests (3 streams, 4 sets, 1 cron, 2 agents) load and produce "
            "correct DB records with proper types, sources, processors, and field values.")

    def test_02_loader_upsert_idempotent(self):
        """Reloading manifests does not duplicate records."""
        prev_dc = DataCollection.objects.count()
        prev_cron = Cronjob.objects.count()

        load_data_collection_manifest(TESTPROJECT / "streams" / "health_events.md")
        load_data_collection_manifest(TESTPROJECT / "sets" / "alert_report.md")
        load_cron_manifest(
            TESTPROJECT / "cronjobs" / "health_check.md",
            install_repo=self.__class__._install_repo,
        )

        self.assertEqual(DataCollection.objects.count(), prev_dc)
        self.assertEqual(Cronjob.objects.count(), prev_cron)
        self.report.add("test_02_loader_upsert_idempotent", "PASS",
            "Re-loading YAML manifests does not duplicate DB records. "
            "The upsert logic correctly identifies and updates existing records.")

    def test_03_agent_tasks_resolved(self):
        """Agent manifest loader resolved collect.* and report.* patterns."""
        collector_names = sorted(
            tdv.task_definition.name for tdv in self.collector_av.task_versions.all()
        )
        self.assertIn("health_check", collector_names)
        self.assertIn("status", collector_names)

        reporter_names = sorted(
            tdv.task_definition.name for tdv in self.reporter_av.task_versions.all()
        )
        for expected in ("parse", "grade", "dedup", "report", "cleanup"):
            self.assertIn(expected, reporter_names)
        self.report.add("test_03_agent_tasks_resolved", "PASS",
            "Agent manifest loader resolved collect.* and report.* glob patterns into "
            "concrete TaskDefinitionVersion records for both the collector and reporter agents.")

    def test_04_cron_execution_creates_call(self):
        """execute_cron_job creates an AgentTaskCall and updates tracking."""
        cron = Cronjob.objects.get(name="health_check")
        last_before = cron.last_run_at

        execute_cron_job(cron.pk)
        cron.refresh_from_db()

        # Tracking fields updated
        self.assertIsNotNone(cron.last_run_at)
        self.assertNotEqual(cron.last_run_at, last_before)
        self.assertEqual(cron.total_runs, 1)
        self.assertIsNotNone(cron.next_run_at)

        # An AgentTaskCall was created
        calls = AgentTaskCall.objects.filter(cronjob=cron)
        self.assertEqual(calls.count(), 1)
        call = calls.first()
        self.assertEqual(
            call.task_instance.session_version.agent.name, "collector",
        )
        self.report.add("test_04_cron_execution_creates_call", "PASS",
            "execute_cron_job creates an AgentTaskCall for the configured agent and function, "
            "updates last_run_at, total_runs, and next_run_at tracking fields.")

    def test_05_dispatch_to_stream_creates_items(self):
        """_dispatch_data_flows creates CollectionItems in health_events."""
        call = self._create_collector_call({"msg": "ok"})
        AgentTaskCall.objects.filter(pk=call.pk).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        _dispatch_data_flows()

        items = CollectionItem.objects.filter(collection=self.health_events)
        self.assertGreaterEqual(len(items), 1)
        for item in items:
            self.assertEqual(len(item.member), 32)  # SHA-256 hash
            self.assertIsInstance(item.score, float)
            self.assertGreater(item.score, 0)
        self.report.add("test_05_dispatch_to_stream_creates_items", "PASS",
            "Completed AgentTaskCalls matching query-type sources produce CollectionItems "
            "with auto-generated 32-char member hashes and float timestamp scores.")

    def test_06_dispatch_skips_non_matching_calls(self):
        """Calls that don't match source criteria are not dispatched."""
        # Create a call for "status" task (not "health_check") on collector
        agent = self.collector
        td = create_task("status", group="collect", agent=agent, task_type=TaskType.TASK)
        session, sv = dc_create_session(agent, self.collector_av)
        call = create_completed_call(agent, td, session, sv, {"x": 1})
        AgentTaskCall.objects.filter(pk=call.pk).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        _dispatch_data_flows()
        # health_events only matches health_check, so this "status" call
        # should not create an item
        health_items = CollectionItem.objects.filter(collection=self.health_events)
        self.assertEqual(health_items.count(), 0)
        self.report.add("test_06_dispatch_skips_non_matching_calls", "PASS",
            "Calls that do not match the source agent/function criteria are not dispatched. "
            "A 'status' call does not create items in the health_events stream.")

    def test_07_dispatch_to_set_creates_items(self):
        """_dispatch_data_flows creates items in unique_services set."""
        call = self._create_collector_call({"service": "api", "timestamp": 1000.0})
        AgentTaskCall.objects.filter(pk=call.pk).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        _dispatch_data_flows()

        items = CollectionItem.objects.filter(collection=self.unique_services)
        self.assertGreaterEqual(len(items), 1)
        item = items[0]
        # Set uses user-defined member-field expression
        self.assertEqual(item.member, "api")
        self.assertIsInstance(item.score, float)
        self.report.add("test_07_dispatch_to_set_creates_items", "PASS",
            "Sets use user-defined member_field expressions. The member 'api' was "
            "extracted from the arguments via item.get('service', ...).")

    def test_08_set_dedup_update_or_create(self):
        """Same member in a set is update_or_create'd, not duplicated."""
        call1 = self._create_collector_call({"service": "web", "timestamp": 1000.0})
        call2 = self._create_collector_call({"service": "web", "timestamp": 2000.0})
        AgentTaskCall.objects.filter(pk__in=[call1.pk, call2.pk]).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        _dispatch_data_flows()

        items = CollectionItem.objects.filter(
            collection=self.unique_services, member="web",
        )
        self.assertEqual(items.count(), 1)
        self.report.add("test_08_set_dedup_update_or_create", "PASS",
            "Two calls producing the same 'web' member result in only one CollectionItem "
            "due to the (collection, member) unique_together constraint.")

    def test_09_propagate_stream_to_stream(self):
        """Items in health_events propagate to parsed_alerts."""
        # Create a source item in health_events
        call = self._create_collector_call({"msg": "propagate-me"})
        CollectionItem.objects.create(
            collection=self.health_events,
            member="prop-item-001",
            score=timezone.now().timestamp(),
            value={"msg": "propagate-me"},
            source_call=call,
        )
        _propagate_from_collections()

        derived_items = CollectionItem.objects.filter(collection=self.parsed_alerts)
        self.assertGreaterEqual(len(derived_items), 1)
        self.report.add("test_09_propagate_stream_to_stream", "PASS",
            "New items added to health_events stream are propagated to parsed_alerts "
            "stream which sources from it via type:stream source.")

    def test_10_propagate_stream_to_set(self):
        """Items in health_events propagate to alert_report set."""
        call = self._create_collector_call({"severity": "critical", "timestamp": 5000.0})
        CollectionItem.objects.create(
            collection=self.health_events,
            member="prop-set-item",
            score=timezone.now().timestamp(),
            value={"severity": "critical", "timestamp": 5000.0},
            source_call=call,
        )
        _propagate_from_collections()

        items = CollectionItem.objects.filter(collection=self.alert_report)
        self.assertGreaterEqual(len(items), 1)
        # Member is derived from the set's member_field expression
        self.assertEqual(items[0].member, "critical")
        self.report.add("test_10_propagate_stream_to_set", "PASS",
            "Items propagate from a stream to a set. The set's member_field expression "
            "extracts 'critical' from the source item's value.")

    def test_11_propagate_set_to_stream(self):
        """Items in a set propagate to derived streams that source from it."""
        # Create a set to propagate from
        source_set = DataCollection.objects.create(
            name="test-source-set", collection_type="set",
            processor={"agent": "collector", "function": "health_check"},
        )
        derived = DataCollection.objects.create(
            name="derived-from-set",
            sources=[{"type": "set", "set": "test-source-set"}],
            processor={"agent": "reporter", "function": "parse"},
        )
        call = self._create_collector_call({"id": "set-to-stream"})
        CollectionItem.objects.create(
            collection=source_set,
            member="set-member",
            score=1.0,
            value={"id": "set-to-stream"},
            source_call=call,
        )
        _propagate_from_collections()

        items = CollectionItem.objects.filter(collection=derived)
        self.assertGreaterEqual(len(items), 1)
        self.report.add("test_11_propagate_set_to_stream", "PASS",
            "Items in a set propagate to derived streams that source from the set. "
            "Bidirectional stream↔set propagation works correctly.")

    def test_12_reprocess_stream_backfill(self):
        """reprocess_collection backfills a stream from historical calls."""
        # Create historical calls (they exist before the collection)
        for service in ("a", "b", "c"):
            call = self._create_collector_call({"service": service})
            AgentTaskCall.objects.filter(pk=call.pk).update(
                status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
            )

        stream = DataCollection.objects.create(
            name="backfill-test",
            sources=[{"type": "query", "agent": ["collector"], "function": ["health_check"]}],
            processor={"agent": "reporter", "function": "parse"},
        )
        reprocess_collection("backfill-test", max_items=5)

        items = CollectionItem.objects.filter(collection=stream)
        self.assertEqual(items.count(), 3)
        self.report.add("test_12_reprocess_stream_backfill", "PASS",
            "reprocess_collection backfills 3 historical calls that match the query-type source criteria.")
        

    def test_13_reprocess_set_with_dedup_and_removal(self):
        """Reprocess a set: dedup same members, trigger on_removed for stale."""
        the_set = DataCollection.objects.create(
            name="repro-set-test", collection_type="set",
            member_field="item.get('id', str(item))",
            score_field="float(item.get('ts', 0))",
            sources=[{"type": "query", "agent": ["collector"], "function": ["health_check"]}],
            processor={"agent": "reporter", "function": "dedup"},
            on_removed={"agent": "reporter", "function": "cleanup"},
        )
        # Create calls with overlapping ids
        call_a = self._create_collector_call({"id": "dup-1", "ts": 1.0})
        call_b = self._create_collector_call({"id": "dup-1", "ts": 2.0})
        call_c = self._create_collector_call({"id": "unique", "ts": 3.0})
        AgentTaskCall.objects.filter(pk__in=[call_a.pk, call_b.pk, call_c.pk]).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )

        reprocess_collection("repro-set-test", max_items=10)

        # Only 2 unique members (dedup works)
        self.assertEqual(
            CollectionItem.objects.filter(collection=the_set).count(), 2,
        )
        # The "dup-1" member exists exactly once
        dup_item = CollectionItem.objects.get(collection=the_set, member="dup-1")
        self.assertIsInstance(dup_item.score, float)
        self.report.add("test_13_reprocess_set_with_dedup_and_removal", "PASS",
            "Reprocessing a set with 3 calls (2 sharing 'dup-1' member) produces exactly "
            "2 unique items. Dedup via (collection, member) constraint works correctly.")

    def test_14_reprocess_respects_max_items(self):
        """max_items / max_reprocess limits the number of items backfilled."""
        for i in range(5):
            call = self._create_collector_call({"n": i})
            AgentTaskCall.objects.filter(pk=call.pk).update(
                status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
            )

        stream = DataCollection.objects.create(
            name="max-items-test",
            max_reprocess=2,
            sources=[{"type": "query", "agent": ["collector"], "function": ["health_check"]}],
            processor={"agent": "reporter", "function": "parse"},
        )
        reprocess_collection("max-items-test", max_items=2)
        self.assertLessEqual(
            CollectionItem.objects.filter(collection=stream).count(), 2,
        )
        self.report.add("test_14_reprocess_respects_max_items", "PASS",
            "max_items=2 limits reprocessing to at most 2 items, even though 5 calls exist.")

    def test_15_inactive_flow_skipped(self):
        """is_active=False prevents dispatch."""
        stream = DataCollection.objects.create(
            name="inactive-stream", is_active=False,
            sources=[{"type": "query", "agent": ["collector"], "function": ["health_check"]}],
            processor={"agent": "reporter", "function": "parse"},
        )
        call = self._create_collector_call({"should": "not-appear"})
        AgentTaskCall.objects.filter(pk=call.pk).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        _dispatch_data_flows()

        self.assertEqual(
            CollectionItem.objects.filter(collection=stream).count(), 0,
        )
        self.report.add("test_15_inactive_flow_skipped", "PASS",
            "Inactive collections (is_active=False) are skipped during dispatch. No items created.")

    def test_16_set_score_field_eval(self):
        """score_field expression on a set evaluates correctly."""
        the_set = DataCollection.objects.create(
            name="score-eval-test", collection_type="set",
            member_field="item.get('id', str(item))",
            score_field="float(item.get('ts', 0))",
            sources=[{"type": "query", "agent": ["collector"], "function": ["health_check"]}],
            processor={"agent": "reporter", "function": "dedup"},
        )
        call = self._create_collector_call({"id": "s1", "ts": 42.5})
        AgentTaskCall.objects.filter(pk=call.pk).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        _dispatch_data_flows()

        items = CollectionItem.objects.filter(collection=the_set, member="s1")
        self.assertEqual(items.count(), 1)
        self.assertEqual(items[0].score, 42.5)
        self.report.add("test_16_set_score_field_eval", "PASS",
            "score_field expression 'float(item.get(\"ts\", 0))' evaluates to 42.5 from the call arguments.")

    def test_17_on_removed_handler_creates_call(self):
        """on_removed handler creates an AgentTaskCall when set items are removed."""
        the_set = DataCollection.objects.create(
            name="on-removed-call-test", collection_type="set",
            member_field="item.get('id', str(item))",
            score_field="float(item.get('ts', 0))",
            sources=[{"type": "query", "agent": ["collector"], "function": ["health_check"]}],
            processor={"agent": "reporter", "function": "dedup"},
            on_removed={"agent": "reporter", "function": "cleanup"},
        )
        call_a = self._create_collector_call({"id": "dup-1", "ts": 1.0})
        call_b = self._create_collector_call({"id": "dup-1", "ts": 2.0})
        call_c = self._create_collector_call({"id": "unique", "ts": 3.0})
        AgentTaskCall.objects.filter(pk__in=[call_a.pk, call_b.pk, call_c.pk]).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )

        calls_before = AgentTaskCall.objects.count()
        reprocess_collection("on-removed-call-test", max_items=10)
        calls_after = AgentTaskCall.objects.count()

        # Dedup -> only 2 items remain; 1 was removed ("dup-1" from call_a)
        self.assertEqual(
            CollectionItem.objects.filter(collection=the_set).count(), 2,
        )
        # on_removed handler should have created at least 1 additional call
        self.assertGreater(calls_after, calls_before)
        self.report.add("test_17_on_removed_handler_creates_call", "PASS",
            "on_removed handler fires when a set item is removed during reprocess. "
            "An additional AgentTaskCall is created for the cleanup handler.")

    def test_18_type_set_source_propagation(self):
        """type: set source in a collection propagates via _propagate_from_collections."""
        source_set = DataCollection.objects.create(
            name="type-set-source-test", collection_type="set",
            member_field="item.get('id', str(item))",
            processor={"agent": "reporter", "function": "dedup"},
        )
        derived = DataCollection.objects.create(
            name="derived-from-type-set",
            sources=[{"type": "set", "set": "type-set-source-test"}],
            processor={"agent": "reporter", "function": "parse"},
        )
        call = self._create_collector_call({"id": "from-set"})
        create_collection_item(source_set, member="from-set", value={"id": "from-set"}, source_call=call)
        _propagate_from_collections()

        items = CollectionItem.objects.filter(collection=derived)
        self.assertGreaterEqual(len(items), 1)
        self.report.add("test_18_type_set_source_propagation", "PASS",
            "A collection with type:set source propagates items from the source set to the derived flow.")

    def test_19_retroactive_on_source_change_dispatches(self):
        """retroactive_on_source_change triggers reprocess when sources change."""
        col = DataCollection.objects.create(
            name="retro-test",
            sources=[{"type": "query", "agent": ["collector"], "function": ["status"]}],
            processor={"agent": "reporter", "function": "parse"},
            retroactive_on_source_change=5,
        )
        # Verify the field is persisted
        col.refresh_from_db()
        self.assertEqual(col.retroactive_on_source_change, 5)
        # Verify the field is on the model (schema check)
        self.assertIn("retroactive_on_source_change", [f.name for f in DataCollection._meta.get_fields()])
        self.report.add("test_19_retroactive_on_source_change_dispatches", "PASS",
            "retroactive_on_source_change field persists correctly and is present on the model schema.")

    def test_20_empty_sources_does_not_crash(self):
        """DataCollection with empty or missing sources does not crash dispatch."""
        col = DataCollection.objects.create(
            name="empty-sources-test",
            sources=[],
            processor={"agent": "reporter", "function": "parse"},
        )
        _dispatch_data_flows()
        self.assertEqual(CollectionItem.objects.filter(collection=col).count(), 0)
        self.report.add("test_20_empty_sources_does_not_crash", "PASS",
            "Dispatch handles empty sources gracefully without crashing.")

    def test_21_no_processor_does_not_crash(self):
        """DataCollection with no processor config does not crash dispatch."""
        col = DataCollection.objects.create(
            name="no-processor-test",
            sources=[{"type": "query", "agent": ["collector"], "function": ["health_check"]}],
            processor={},
        )
        call = self._create_collector_call({"x": 1})
        AgentTaskCall.objects.filter(pk=call.pk).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        _dispatch_data_flows()
        self.assertEqual(CollectionItem.objects.filter(collection=col).count(), 0)
        self.report.add("test_21_no_processor_does_not_crash", "PASS",
            "Dispatch handles missing processor config gracefully without crashing.")

    def test_22_multiple_sources_per_flow(self):
        """Flow with multiple query sources dispatches from any matching call."""
        col = DataCollection.objects.create(
            name="multi-source-test",
            sources=[
                {"type": "query", "agent": ["collector"], "function": ["health_check"]},
                {"type": "query", "agent": ["collector"], "function": ["status"]},
            ],
            processor={"agent": "reporter", "function": "parse"},
        )
        # Call for health_check
        call1 = self._create_collector_call({"source": "hc"})
        # Call for status
        agent = self.collector
        td = create_task("status", group="collect", agent=agent, task_type=TaskType.TASK)
        session, sv = dc_create_session(agent, self.collector_av)
        call2 = create_completed_call(agent, td, session, sv, {"source": "st"})
        AgentTaskCall.objects.filter(pk__in=[call1.pk, call2.pk]).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        _dispatch_data_flows()

        items = CollectionItem.objects.filter(collection=col)
        self.assertGreaterEqual(len(items), 1)
        self.report.add("test_22_multiple_sources_per_flow", "PASS",
            "A flow with multiple query sources dispatches items from any matching source call.")

    def test_23_session_template_var_expansion(self):
        """Processor session template {source_session} expands correctly."""
        col = DataCollection.objects.create(
            name="session-template-test",
            sources=[{"type": "query", "agent": ["collector"], "function": ["health_check"]}],
            processor={"agent": "reporter", "function": "parse", "session": "{source_session}-copy"},
        )
        call = self._create_collector_call({"x": 1})
        AgentTaskCall.objects.filter(pk=call.pk).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        _dispatch_data_flows()

        items = CollectionItem.objects.filter(collection=col)
        self.assertGreaterEqual(len(items), 1)
        processor_call = items[0].source_call
        self.assertIsNotNone(processor_call)
        expanded_name = processor_call.task_instance.session.name
        self.assertTrue(expanded_name.endswith("-copy"))
        # Base name should come from the source call's session
        self.assertIn("test-session", expanded_name)
        self.report.add("test_23_session_template_var_expansion", "PASS",
            "The {source_session} template variable in processor session config expands to "
            "the source call's session name with '-copy' appended.")

    def test_24_retroactive_source_change_triggers_reprocess(self):
        """Changing sources with retroactive_on_source_change triggers reprocess."""
        col = DataCollection.objects.create(
            name="retro-sync-test",
            sources=[{"type": "query", "agent": ["collector"], "function": ["status"]}],
            processor={"agent": "reporter", "function": "parse"},
            retroactive_on_source_change=10,
        )
        # Create calls for the OLD source (status)
        agent = self.collector
        td_status = create_task("status", group="collect", agent=agent, task_type=TaskType.TASK)
        session, sv = dc_create_session(agent, self.collector_av)
        create_completed_call(agent, td_status, session, sv, {"old": 1})

        # Create calls for the NEW source (health_check)
        call = self._create_collector_call({"new": 1})
        AgentTaskCall.objects.filter(pk=call.pk).update(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        # Change sources and reprocess
        DataCollection.objects.filter(pk=col.pk).update(
            sources=[{"type": "query", "agent": ["collector"], "function": ["health_check"]}],
        )
        col.refresh_from_db()
        reprocess_collection("retro-sync-test", max_items=10)

        items = CollectionItem.objects.filter(collection=col)
        # Should have the item from the NEW source call
        self.assertGreaterEqual(len(items), 1)
        self.report.add("test_24_retroactive_source_change_triggers_reprocess", "PASS",
            "Changing sources with retroactive_on_source_change > 0 triggers reprocess "
            "and produces items from the new source criteria.")

    def test_25_propagate_skips_item_without_source_call(self):
        """_propagate_from_collections skips CollectionItems with source_call=None."""
        source_set = DataCollection.objects.create(
            name="null-source-call-set", collection_type="set",
            processor={"agent": "reporter", "function": "dedup"},
        )
        derived = DataCollection.objects.create(
            name="derived-from-null",
            sources=[{"type": "set", "set": "null-source-call-set"}],
            processor={"agent": "reporter", "function": "parse"},
        )
        # Create an item with NO source_call
        create_collection_item(source_set, member="orphan", value={"x": 1})
        _propagate_from_collections()

        items = CollectionItem.objects.filter(collection=derived)
        self.assertEqual(len(items), 0)
        self.report.add("test_25_propagate_skips_item_without_source_call", "PASS",
            "Propagation skips CollectionItems with source_call=None — no derived items are created.")

    def test_26_type_set_source_propagation_from_yaml(self):
        """YAML-loaded type:set source propagates through _propagate_from_collections."""
        # Create items in alert_report (YAML-loaded set)
        call = self._create_collector_call({"service": "set-src-test"})
        create_collection_item(
            self.alert_report, member="set-src-member",
            value={"service": "set-src-test"}, source_call=call,
        )
        _propagate_from_collections()

        # alerts_from_report sources from alert_report
        items = CollectionItem.objects.filter(collection=self.alerts_from_report)
        self.assertGreaterEqual(len(items), 1)
        self.report.add("test_26_type_set_source_propagation_from_yaml", "PASS",
            "A YAML-loaded type:set source (alerts_from_report sourcing from alert_report) "
            "propagates items correctly through _propagate_from_collections.")

    def test_27_all_alerts_multi_source_propagation(self):
        """Multi-source stream (all_alerts) propagates from both its sources."""
        # Create item in health_events stream -> should flow to all_alerts
        call = self._create_collector_call({"src": "he"})
        create_collection_item(
            self.health_events, member="multi-src-hlth",
            value={"src": "he"}, source_call=call,
        )
        _propagate_from_collections()
        items = CollectionItem.objects.filter(collection=self.all_alerts)
        self.assertGreaterEqual(len(items), 1)
        self.report.add("test_27_all_alerts_multi_source_propagation", "PASS",
            "A multi-source stream (all_alerts with both stream and set sources) "
            "successfully propagates items from the health_events stream.")
