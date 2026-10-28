"""Cron message storage/round-trip and content-addressing regression tests."""
from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path

from django.test import TestCase, override_settings

from registry.loader.load_cron_manifest import load_cron_manifest
from runtime.cron.content import build_cron_message
from runtime.cron.file_io import cron_file_path, write_cron_file
from server.models.content import GenericContent
from server.models.cron import Cronjob


class BuildCronMessageTest(TestCase):
    def test_plain_text_without_function(self):
        message = build_cron_message("hello", "")
        self.assertEqual(message.content_type, "TEXT")
        self.assertEqual(message.get(), "hello")

    def test_json_string_with_function(self):
        message = build_cron_message('{"limit": 10}', "command")
        self.assertEqual(message.content_type, "JSON")
        self.assertEqual(message.get(), {"limit": 10})

    def test_mapping_with_function(self):
        message = build_cron_message({"limit": 10}, "task")
        self.assertEqual(message.content_type, "JSON")
        self.assertEqual(message.get(), {"limit": 10})

    def test_empty_message_with_function_is_empty_kwargs(self):
        message = build_cron_message("", "tool")
        self.assertEqual(message.content_type, "JSON")
        self.assertEqual(message.get(), {})

    def test_invalid_json_with_function_raises(self):
        with self.assertRaises(ValueError):
            build_cron_message("not json", "task")

    def test_mapping_without_function_becomes_text(self):
        message = build_cron_message({"limit": 10}, "")
        self.assertEqual(message.content_type, "TEXT")
        self.assertEqual(json.loads(message.get()), {"limit": 10})


class GenericContentAddressingTest(TestCase):
    """The primary key must always equal the SHA-256 of the stored content."""

    def test_from_text_key_matches_content(self):
        row = GenericContent.from_text("original")
        self.assertEqual(row.pk, sha256(b"original").hexdigest())
        self.assertEqual(sha256(row.content.encode()).hexdigest(), row.pk)

    def test_from_data_key_matches_content(self):
        data = {"limit": 10}
        row = GenericContent.from_data(data)
        self.assertEqual(row.content, json.dumps(data, sort_keys=True))
        self.assertEqual(sha256(row.content.encode()).hexdigest(), row.pk)


class CronArchiveScopeTest(TestCase):
    """A project load must not archive jobs owned by a workspace scope."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self._tmp, ignore_errors=True))
        self.project_dir = self._tmp / "project"
        (self.project_dir / "cronjobs").mkdir(parents=True)
        (self.project_dir / "cronjobs" / "project-job.md").write_text(
            "---\nname: project-job\nschedule: 0 9 * * *\n---\n",
            encoding="utf-8",
        )
        self.workspace_dir = self._tmp / "workspace"
        self.workspace_dir.mkdir()

    def test_project_load_keeps_workspace_crons(self):
        from registry.loader.load_project_folder import load_scope_dir
        from server.models.project import Project

        project = Project.objects.create(
            name="archive-scope-project",
            agentone_dir=self.project_dir.as_posix(),
        )
        workspace_job = Cronjob.objects.create(
            name="workspace-job",
            schedule="0 9 * * *",
            parent_project=project,
            manifest_dir=self.workspace_dir.as_posix(),
        )
        stale_job = Cronjob.objects.create(
            name="stale-job",
            schedule="0 9 * * *",
            parent_project=project,
            manifest_dir=self.project_dir.as_posix(),
        )

        load_scope_dir(self.project_dir, project)

        workspace_job.refresh_from_db()
        stale_job.refresh_from_db()
        self.assertFalse(workspace_job.is_archived)
        self.assertTrue(stale_job.is_archived)


class CronFileRoundTripTest(TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self._tmp, ignore_errors=True))
        self.override = override_settings(AGENTONE_ROOT=self._tmp)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def _write(self, name: str, **fields):
        path = self._tmp / "cronjobs" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["---", f"name: {name}", "schedule: 0 9 * * *"]
        for key, value in fields.items():
            if isinstance(value, str):
                lines.append(f"{key}: {value!r}")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_json_message_survives_write_and_reload(self):
        job = Cronjob.objects.create(
            name="json-job",
            schedule="0 9 * * *",
            function_type="command",
            function_name="update_timeline",
            message=build_cron_message({"limit": 10}, "command"),
        )
        write_cron_file(job)
        self.assertEqual(job.manifest_dir, (self._tmp / "cronjobs").as_posix())

        loaded = load_cron_manifest(
            self._tmp / "cronjobs" / "json-job.md",
            install_repo=None,
        )
        self.assertEqual(loaded.function_type, "command")
        self.assertEqual(loaded.function_name, "update_timeline")
        self.assertEqual(loaded.message.content_type, "JSON")
        self.assertEqual(loaded.message.get(), {"limit": 10})

    def test_clearing_function_fields_persists_and_retargets_message(self):
        path = self._write(
            "clear-job",
            agent="",
            function_type="command",
            function_name="update_timeline",
            message='{"limit": 10}',
        )
        job = load_cron_manifest(path, install_repo=None)
        self.assertEqual(job.function_type, "command")
        self.assertEqual(job.message.content_type, "JSON")

        path.write_text(
            "---\n"
            "name: clear-job\n"
            "schedule: 0 9 * * *\n"
            "message: run the thing\n"
            "---\n",
            encoding="utf-8",
        )
        job = load_cron_manifest(path, install_repo=None)
        self.assertEqual(job.function_type, "")
        self.assertEqual(job.function_name, "")
        self.assertEqual(job.message.content_type, "TEXT")
        self.assertEqual(job.message.get(), "run the thing")

    def test_clearing_function_fields_via_write_round_trips(self):
        job = Cronjob.objects.create(
            name="clear-write-job",
            schedule="0 9 * * *",
            function_type="command",
            function_name="update_timeline",
            message=build_cron_message({"limit": 10}, "command"),
        )
        write_cron_file(job)

        job.function_type = ""
        job.function_name = ""
        job.message = build_cron_message("run the thing", "")
        job.save()
        write_cron_file(job)

        job.refresh_from_disk()
        job.refresh_from_db()
        self.assertEqual(job.function_type, "")
        self.assertEqual(job.function_name, "")
        self.assertEqual(job.message.content_type, "TEXT")
        self.assertEqual(job.message.get(), "run the thing")

    def test_write_prefers_canonical_file_over_stale_manifest_dir(self):
        canonical = self._write("canonical-job", message="old")
        stale_dir = self._tmp / "stale"
        stale_dir.mkdir()
        stale = stale_dir / "canonical-job.md"
        stale.write_text(
            "---\nname: canonical-job\nschedule: 0 9 * * *\nmessage: stale\n---\n",
            encoding="utf-8",
        )
        job = Cronjob.objects.create(
            name="canonical-job",
            schedule="0 9 * * *",
            manifest_dir=stale_dir.as_posix(),
            message=build_cron_message("fresh", ""),
        )

        write_cron_file(job)

        self.assertIn("fresh", canonical.read_text(encoding="utf-8"))
        self.assertNotIn("fresh", stale.read_text(encoding="utf-8"))
        job.refresh_from_db()
        self.assertEqual(job.manifest_dir, canonical.parent.as_posix())

    def test_cron_file_path_uses_agentone_dir_without_workspace(self):
        from server.models.project import Project

        project = Project.objects.create(
            name="central-project",
            agentone_dir=(self._tmp / "central").as_posix(),
        )
        self.assertEqual(
            cron_file_path("job", project),
            self._tmp / "central" / "cronjobs" / "job.md",
        )

    def test_write_targets_existing_manifest_dir(self):
        workspace_dir = self._tmp / "workspace-cronjobs"
        workspace_dir.mkdir()
        existing = workspace_dir / "scoped-job.md"
        existing.write_text(
            "---\nname: scoped-job\nschedule: 0 9 * * *\n---\n",
            encoding="utf-8",
        )
        job = Cronjob.objects.create(
            name="scoped-job",
            schedule="0 9 * * *",
            manifest_dir=workspace_dir.as_posix(),
        )
        write_cron_file(job)
        job.refresh_from_db()
        self.assertEqual(job.manifest_dir, workspace_dir.as_posix())
        self.assertTrue((workspace_dir / "scoped-job.md").is_file())
        self.assertFalse((self._tmp / "cronjobs" / "scoped-job.md").exists())

    def test_function_type_without_name_raises(self):
        path = self._write(
            "invalid-job",
            function_type="command",
            function_name="",
            message='{"limit": 1}',
        )
        with self.assertRaises(ValueError):
            load_cron_manifest(path, install_repo=None)

    def test_refresh_from_disk_prefers_canonical_file(self):
        canonical = self._write(
            "shadowed-job",
            function_type="command",
            function_name="canonical_fn",
            message='{"limit": 1}',
        )
        stale_dir = self._tmp / "stale"
        stale_dir.mkdir()
        (stale_dir / "shadowed-job.md").write_text(
            "---\n"
            "name: shadowed-job\n"
            "schedule: 0 9 * * *\n"
            "function_type: command\n"
            "function_name: stale_fn\n"
            "message: '{\"limit\": 99}'\n"
            "---\n",
            encoding="utf-8",
        )
        job = load_cron_manifest(canonical, install_repo=None)
        job.manifest_dir = stale_dir.as_posix()
        job.save(update_fields=["manifest_dir"])

        job.refresh_from_disk()

        job.refresh_from_db()
        self.assertEqual(job.manifest_dir, canonical.parent.as_posix())
        self.assertEqual(job.function_name, "canonical_fn")
        self.assertEqual(job.message.get(), {"limit": 1})

    def test_removing_function_fields_from_markdown_clears_db(self):
        path = self._write(
            "markdown-job",
            function_type="task",
            function_name="health_check",
            message='{"task": "run"}',
        )
        job = load_cron_manifest(path, install_repo=None)
        self.assertEqual(job.function_type, "task")

        path.write_text(
            "---\n"
            "name: markdown-job\n"
            "schedule: 0 9 * * *\n"
            "message: send a normal message\n"
            "---\n",
            encoding="utf-8",
        )
        job = load_cron_manifest(path, install_repo=None)
        job.refresh_from_db()
        self.assertEqual(job.function_type, "")
        self.assertEqual(job.function_name, "")
        self.assertEqual(job.message.get(), "send a normal message")
