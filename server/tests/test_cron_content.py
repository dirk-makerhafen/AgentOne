"""Cron message storage and content-addressing tests.

Cron job manifest files have been removed; cron jobs are DB-canonical.
"""
from __future__ import annotations

import json
from hashlib import sha256

from django.test import TestCase

from runtime.cron.content import build_cron_message
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


class CronDbBehaviorTest(TestCase):
    """DB-canonical cron behavior (manifest files removed)."""

    def test_refresh_from_disk_is_noop(self):
        job = Cronjob.objects.create(
            name="db-job",
            schedule="0 9 * * *",
            function_type="command",
            function_name="update_timeline",
            message=build_cron_message({"limit": 10}, "command"),
        )
        job.refresh_from_disk()
        job.refresh_from_db()
        self.assertEqual(job.function_type, "command")
        self.assertEqual(job.function_name, "update_timeline")
        self.assertEqual(job.message.get(), {"limit": 10})
