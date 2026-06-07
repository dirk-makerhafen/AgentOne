"""End-to-end ordered-set tests with real processor functions via Celery eager mode.

Each processor is a real Python function defined under
``testproject/.agentone/agents/loop_agent/scripts/``, loaded through the
YAML manifest pipeline, and executed by ``BoundTask.call()`` at runtime.

Key behaviours verified:
 1. Stream → set: processor transforms items; results stored as ``CollectionItem.value``
 2. Set → set: downstream processor filters items (returns ``None`` to exclude)
 3. ``member_field`` / ``score_field`` extract from the **processor result**, not raw args
 4. Changing ``member_field`` on a set triggers item removal + ``on_removed``
 5. Downstream sets reflect upstream changes after re-processing
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from server.models.collections import CollectionItem
from server.models.enums.task_enums import TaskCallStatusDetail
from server.models.tasks.agent_task_call import AgentTaskCall
from server.tasks.reprocess_collection import reprocess_collection
from server.tests.dc_test_helpers import (
    TESTPROJECT,
    create_agent,
    create_task,
    create_session,
    create_completed_call,
)
from server.tests.helpers import AgentMdTestMixin
from registry.loader.load_data_collection import load_data_collection_manifest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPTS_DIR = TESTPROJECT / "agents" / "loop_agent" / "scripts"


def _total_cleanup_calls(cleanup_task_def) -> int:
    """Count ALL AgentTaskCalls (any status) whose task matches *cleanup_task_def*."""
    return AgentTaskCall.objects.filter(
        task_instance__task_definition_version__task_definition=cleanup_task_def,
    ).count()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class OrderedSetPipelineTest(AgentMdTestMixin, TestCase):
    """End-to-end ordered-set integration using real processor functions."""

    SCRIPTS_DIR = SCRIPTS_DIR

    @classmethod
    def setUpTestData(cls):
        # ── Install-repo + agent from YAML manifests ────────────────────
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.agent, cls.av = cls.load_agent("loop_agent")

        # ── Helper tasks / sessions ──────────────────────────────────────
        cls.source_task = create_task(
            "generate_message", group="", agent=cls.agent,
        )
        cls.session, cls.sv = create_session(cls.agent, cls.av)

        # Find the cleanup task-def loaded from YAML
        from server.models.tasks.task_definition import TaskDefinition
        cls.cleanup_task = TaskDefinition.objects.get(
            name="cleanup", parent_agent=cls.agent,
        )

        # ── YAML data-collection manifests ──────────────────────────────
        cls.stream = load_data_collection_manifest(
            TESTPROJECT / "streams" / "ordered_set_test_stream.md"
        )
        cls.set_a = load_data_collection_manifest(
            TESTPROJECT / "sets" / "set_a.md"
        )
        cls.set_b = load_data_collection_manifest(
            TESTPROJECT / "sets" / "set_b.md"
        )

        # ── 100 source calls with msg + num ────────────────────────────
        for i in range(100):
            create_completed_call(
                cls.agent, cls.source_task, cls.session, cls.sv,
                carguments={"msg": f"hello from {i}", "num": i},
            )

    def setUp(self):
        """Apply patches and clear state before each test.

        - ``RuntimeFolder.ensure_folder`` -> return the real scripts directory
          so that ``BoundTask.call()`` imports functions from source (bypasses
          the install-repo git checkout).
        """
        self.rf_patcher = patch(
            "runtime.runtime_folder.RuntimeFolder.ensure_folder",
            return_value=self.SCRIPTS_DIR,
        )
        self.rf_patcher.start()
        CollectionItem.objects.all().delete()

    def tearDown(self):
        self.rf_patcher.stop()

    # ------------------------------------------------------------------
    # Stream → Set  (append_processed → filter_zero)
    # ------------------------------------------------------------------

    def test_populates_set_a_from_stream_via_reprocess(self):
        """100 source calls → stream → set_a filter_zero keeps items without '0' in msg."""
        reprocess_collection("ordered_set_test_stream")
        reprocess_collection("set_a")

        items = CollectionItem.objects.filter(collection=self.set_a)
        # filter_zero returns None when "0" in msg → multiples of 10 filtered
        self.assertEqual(items.count(), 90)

        members = {item.member for item in items}
        for i in range(100):
            if "0" in str(i):
                self.assertNotIn(str(i), members, f"member '{i}' should be excluded")
            else:
                self.assertIn(str(i), members, f"member '{i}' should be included")

    def test_set_a_values_from_processor_result(self):
        """CollectionItem.value should be the processor return dict."""
        reprocess_collection("ordered_set_test_stream")
        reprocess_collection("set_a")

        # Pick one known-good item (num=5 → msg="hello from 5" → passes filter)
        item = CollectionItem.objects.get(
            collection=self.set_a, member="5",
        )
        self.assertEqual(item.value, {"msg": "hello from 5", "num": 5})

    def test_set_a_member_field_dedup(self):
        """Two calls with same num produce only one set item (dedup)."""
        create_completed_call(
            self.agent, self.source_task, self.session, self.sv,
            carguments={"msg": "duplicate", "num": 42},
        )
        reprocess_collection("ordered_set_test_stream")
        reprocess_collection("set_a")

        items = CollectionItem.objects.filter(
            collection=self.set_a, member="42",
        )
        self.assertEqual(items.count(), 1)

    # ------------------------------------------------------------------
    # Set → Set  (set_a → filter_one)
    # ------------------------------------------------------------------

    def test_set_to_set_filtering(self):
        """set_b via filter_one excludes items with '1' in msg."""
        reprocess_collection("ordered_set_test_stream")
        reprocess_collection("set_a")    # 90 items (multiples of 10 excluded)
        reprocess_collection("set_b")    # filter_one: items with "1" in msg excluded

        items = CollectionItem.objects.filter(collection=self.set_b)
        # set_a items (no "0") minus items with "1" in the digit string
        self.assertEqual(items.count(), 72)

        members = {item.member for item in items}
        for i in range(100):
            if "0" in str(i) or "1" in str(i):
                self.assertNotIn(str(i), members, f"member '{i}' should be excluded")
            else:
                self.assertIn(str(i), members, f"member '{i}' should be included")

    # ------------------------------------------------------------------
    # member_field change → removal detection + on_removed
    # ------------------------------------------------------------------

    def test_filter_change_via_member_field_collapse(self):
        """Changing member_field from individual num to tens-group reduces items."""
        reprocess_collection("ordered_set_test_stream")
        reprocess_collection("set_a")
        self.assertEqual(
            CollectionItem.objects.filter(collection=self.set_a).count(), 90,
        )

        # Group by tens: num//10 → 10 groups (0..9)
        self.set_a.member_field = "str(item.get('num', -1) // 10)"
        self.set_a.score_field = "float(item.get('num', -1) // 10)"
        self.set_a.save()

        reprocess_collection("set_a")
        items = CollectionItem.objects.filter(collection=self.set_a)
        self.assertEqual(items.count(), 10)

    def test_on_removed_fires_when_items_collapsed(self):
        """Item collapse via member_field change triggers on_removed."""
        reprocess_collection("ordered_set_test_stream")
        reprocess_collection("set_a")
        cleanup_before = _total_cleanup_calls(self.cleanup_task)

        self.set_a.member_field = "str(item.get('num', -1) // 10)"
        self.set_a.score_field = "float(item.get('num', -1) // 10)"
        self.set_a.save()
        reprocess_collection("set_a")

        cleanup_after = _total_cleanup_calls(self.cleanup_task)
        removed_count = cleanup_after - cleanup_before
        self.assertGreaterEqual(
            removed_count, 1,
            f"Expected at least one on_removed call, got {removed_count}",
        )

    # ------------------------------------------------------------------
    # Downstream cascade
    # ------------------------------------------------------------------

    def test_downstream_set_b_updates_after_upstream_change(self):
        """After set_a member_field changes, set_b reflects new upstream state."""
        reprocess_collection("ordered_set_test_stream")
        reprocess_collection("set_a")
        reprocess_collection("set_b")
        self.assertEqual(
            CollectionItem.objects.filter(collection=self.set_b).count(), 72,
        )

        # Collapse set_a into 10 groups → on reprocess set_a goes 90→10 items
        self.set_a.member_field = "str(item.get('num', -1) // 10)"
        self.set_a.score_field = "float(item.get('num', -1) // 10)"
        self.set_a.save()
        reprocess_collection("set_a")

        # Reprocess set_b from updated set_a (10 items) → filter_one
        reprocess_collection("set_b")
        items = CollectionItem.objects.filter(collection=self.set_b)
        # Verify the count changed from the original (72) — reflecting new
        # upstream membership.
        self.assertNotEqual(items.count(), 72,
                            "set_b count should differ after upstream change")
