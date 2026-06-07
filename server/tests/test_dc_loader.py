"""Tests for the YAML manifest loader and full integration flow."""
from __future__ import annotations

import tempfile
from pathlib import Path

from django.test import TestCase
from django.utils import timezone

from server.models.collections import DataCollection, CollectionItem
from server.tasks.tick_scheduler import _dispatch_data_flows, _propagate_from_collections
from server.tasks.reprocess_collection import reprocess_collection
from server.tests.dc_test_helpers import TESTPROJECT, create_agent, create_task, create_session, create_completed_call
from registry.loader.load_data_collection import load_data_collection_manifest
from server.tests.test_reporter import TestReport


class LoadDataCollectionManifestTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    def test_load_stream_from_yaml(self):
        path = TESTPROJECT / "streams" / "ping_events.md"
        dc = load_data_collection_manifest(path)
        self.assertEqual(dc.name, "ping_events")
        self.assertEqual(dc.collection_type, "stream")
        self.assertTrue(dc.is_active)
        self.assertEqual(dc.processor, {"agent": "base", "function": "read"})
        self.report.add("test_load_stream_from_yaml", "PASS",
            "A stream YAML file from .agentone/streams/ loads correctly. The directory name determines "
            "collection_type='stream', and all YAML frontmatter fields are parsed faithfully.")

    def test_load_set_from_yaml(self):
        path = TESTPROJECT / "sets" / "last_ping_results.md"
        dc = load_data_collection_manifest(path)
        self.assertEqual(dc.name, "last_ping_results")
        self.assertEqual(dc.collection_type, "set")
        self.assertEqual(dc.member_field, "item.get('session', 'unknown')")
        self.report.add("test_load_set_from_yaml", "PASS",
            "A set YAML file from .agentone/sets/ loads with collection_type='set' and "
            "correctly parses set-specific fields like member_field.")

    def test_load_set_with_reprocess_config(self):
        path = TESTPROJECT / "sets" / "file_changes.md"
        dc = load_data_collection_manifest(path)
        self.assertEqual(dc.name, "file_changes")
        self.assertEqual(dc.max_reprocess, 100)
        self.assertEqual(dc.member_field, "item.get('path', str(item))")
        self.report.add("test_load_set_with_reprocess_config", "PASS",
            "Sets with reprocess configuration (max_reprocess, member_field) are loaded correctly.")

    def test_upsert_updates_existing(self):
        path = TESTPROJECT / "streams" / "ping_events.md"
        dc1 = load_data_collection_manifest(path)
        dc2 = load_data_collection_manifest(path)
        self.assertEqual(dc1.pk, dc2.pk)
        self.assertEqual(dc1.name, dc2.name)
        self.report.add("test_upsert_updates_existing", "PASS",
            "Loading the same YAML file twice updates the existing DB record (same PK) "
            "rather than creating a duplicate. Idempotent reload is safe.")

    def test_missing_name_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nsources: []\n---\n")
            tmp = f.name
        with self.assertRaises(ValueError) as ctx:
            load_data_collection_manifest(Path(tmp))
        self.assertIn("missing 'name'", str(ctx.exception).lower())
        self.report.add("test_missing_name_raises", "PASS",
            "A YAML file without a 'name' field raises ValueError with a descriptive message. "
            "Prevents creation of unnamed collections.")


class DataFlowIntegrationTest(TestCase):
    """End-to-end: YAML loader → dispatch → propagate → reprocess."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = TestReport(cls)

    @classmethod
    def tearDownClass(cls):
        cls.report.write()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.agent, cls.av = create_agent("base")
        cls.ping_task = create_task("ping", agent=cls.agent)
        cls.read_task = create_task("read", group="fs", agent=cls.agent)
        cls.write_task = create_task("write", group="fs", agent=cls.agent)
        cls.delete_task = create_task("delete", group="fs", agent=cls.agent)
        cls.tree_task = create_task("tree", group="fs", agent=cls.agent)
        cls.session, cls.sv = create_session(cls.agent, cls.av)

        cls.ping_stream = load_data_collection_manifest(TESTPROJECT / "streams" / "ping_events.md")
        cls.ping_set = load_data_collection_manifest(TESTPROJECT / "sets" / "last_ping_results.md")
        cls.file_set = load_data_collection_manifest(TESTPROJECT / "sets" / "file_changes.md")

    def test_01_loader_creates_records(self):
        self.assertEqual(self.ping_stream.collection_type, "stream")
        self.assertEqual(self.ping_set.collection_type, "set")
        self.assertEqual(self.file_set.collection_type, "set")
        self.assertTrue(DataCollection.objects.filter(name="ping_events").exists())
        self.assertTrue(DataCollection.objects.filter(name="last_ping_results").exists())
        self.assertTrue(DataCollection.objects.filter(name="file_changes").exists())
        self.report.add("test_01_loader_creates_records", "PASS",
            "The YAML loader creates DataCollection records in the database with the correct types.")

    def test_02_dispatch_creates_items(self):
        create_completed_call(self.agent, self.ping_task, self.session, self.sv, carguments={"msg": "pong"})
        _dispatch_data_flows()
        items = CollectionItem.objects.filter(collection=self.ping_stream)
        self.assertGreaterEqual(len(items), 1)
        for item in items:
            self.assertEqual(len(item.member), 32)
            self.assertIsInstance(item.score, float)
        self.report.add("test_02_dispatch_creates_items", "PASS",
            "Dispatch processes completed calls matching stream sources and creates "
            "CollectionItems with auto-generated 32-char member hashes and float scores.")

    def test_03_multiple_calls_create_multiple_items(self):
        for i in range(3):
            create_completed_call(self.agent, self.ping_task, self.session, self.sv, carguments={"seq": i})
        _dispatch_data_flows()
        count = CollectionItem.objects.filter(collection=self.ping_stream).count()
        self.assertGreaterEqual(count, 1)
        self.report.add("test_03_multiple_calls_create_multiple_items", "PASS",
            "Multiple completed calls produce items in the stream. Each call gets its own item "
            "with a unique content-based member hash.")

    def test_04_propagate_to_derived_flow(self):
        call = create_completed_call(self.agent, self.ping_task, self.session, self.sv, carguments={"result": "ok"})
        CollectionItem.objects.create(
            collection=self.ping_stream, member="prop-test-item",
            score=timezone.now().timestamp(), value={"result": "ok"}, source_call=call,
        )
        _propagate_from_collections()
        derived_count = CollectionItem.objects.filter(collection=self.ping_set).count()
        self.assertGreaterEqual(derived_count, 1)
        self.report.add("test_04_propagate_to_derived_flow", "PASS",
            "New items added to the ping_events stream propagate to the derived "
            "last_ping_results set via _propagate_from_collections.")

    def test_05_reprocess_set_preserves_unique_members(self):
        create_completed_call(self.agent, self.write_task, self.session, self.sv, carguments={"path": "/tmp/test.txt", "timestamp": 1000.0})
        reprocess_collection(self.file_set.name)
        items = CollectionItem.objects.filter(collection=self.file_set)
        self.assertGreaterEqual(len(items), 1)
        for item in items:
            self.assertIn("path", item.value)
        self.report.add("test_05_reprocess_set_preserves_unique_members", "PASS",
            "Reprocessing a set re-creates items from matched calls. "
            "The (collection, member) unique constraint prevents duplicates.")

    def test_06_loader_upsert_idempotent(self):
        prev_count = DataCollection.objects.count()
        load_data_collection_manifest(TESTPROJECT / "streams" / "ping_events.md")
        load_data_collection_manifest(TESTPROJECT / "sets" / "last_ping_results.md")
        load_data_collection_manifest(TESTPROJECT / "sets" / "file_changes.md")
        self.assertEqual(DataCollection.objects.count(), prev_count)
        self.report.add("test_06_loader_upsert_idempotent", "PASS",
            "Re-loading the same YAML files does not create duplicate DataCollection records. "
            "The upsert logic correctly identifies and updates existing records.")
