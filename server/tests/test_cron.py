"""Tests for the cron component: model, query interface, and execution helpers."""
from __future__ import annotations

from datetime import timedelta

from croniter import croniter
from django.test import TestCase
from django.utils import timezone

from server.models.cron import Cronjob
from server.models.content import GenericContent
from runtime.cron.crons import Cronjobs
from runtime.cron.execute import compute_next_run


class CronjobModelTest(TestCase):
    """Test the Cronjob model fields, defaults, and constraints."""

    def test_defaults(self):
        job = Cronjob.objects.create(
            name="test-job",
            schedule="0 9 * * *",
        )
        self.assertEqual(job.name, "test-job")
        self.assertEqual(job.schedule, "0 9 * * *")
        self.assertTrue(job.is_active)
        self.assertEqual(job.session_mode, "new")
        self.assertEqual(job.session_name, "")
        self.assertEqual(job.function_type, "")
        self.assertEqual(job.function_name, "")
        self.assertIsNone(job.last_run_at)
        self.assertIsNone(job.next_run_at)
        self.assertEqual(job.last_status, "")
        self.assertEqual(job.total_runs, 0)
        self.assertIsNone(job.message)

    def test_is_active_can_be_disabled(self):
        job = Cronjob.objects.create(
            name="paused-job", schedule="0 0 * * *", is_active=False
        )
        self.assertFalse(job.is_active)

    def test_session_mode_choices(self):
        job = Cronjob.objects.create(
            name="existing-session-job", schedule="* * * * *",
            session_mode="existing", session_name="my-session",
        )
        self.assertEqual(job.session_mode, "existing")
        self.assertEqual(job.session_name, "my-session")

    def test_function_fields(self):
        job = Cronjob.objects.create(
            name="func-job", schedule="*/5 * * * *",
            function_type="task", function_name="ingest_user_message",
        )
        self.assertEqual(job.function_type, "task")
        self.assertEqual(job.function_name, "ingest_user_message")

    def test_message_link(self):
        msg = GenericContent.objects.create(
            content="hello from cron", content_type="TEXT",
        )
        job = Cronjob.objects.create(
            name="msg-job", schedule="0 0 * * *", message=msg,
        )
        self.assertEqual(job.message.content, "hello from cron")

    def test_total_runs_increment(self):
        from django.db.models import F
        job = Cronjob.objects.create(name="counter", schedule="* * * * *")
        for _ in range(3):
            Cronjob.objects.filter(pk=job.pk).update(total_runs=F("total_runs") + 1)
        job.refresh_from_db()
        self.assertEqual(job.total_runs, 3)

    def test_description_defaults_to_empty(self):
        job = Cronjob.objects.create(name="desc-test", schedule="0 0 * * *")
        self.assertEqual(job.description, "")


class CronjobsQueryTest(TestCase):
    """Test the Cronjobs query interface."""

    def setUp(self):
        self.cronjobs = Cronjobs()

    def test_root_returns_all(self):
        Cronjob.objects.create(name="a", schedule="0 0 * * *")
        Cronjob.objects.create(name="b", schedule="0 0 * * *")
        self.assertEqual(self.cronjobs.root().count(), 2)

    def test_active_filters_by_is_active(self):
        Cronjob.objects.create(name="a", schedule="0 0 * * *", is_active=True)
        Cronjob.objects.create(name="b", schedule="0 0 * * *", is_active=False)
        self.assertEqual(self.cronjobs.active().count(), 1)
        self.assertEqual(self.cronjobs.active().first().name, "a")

    def test_due_returns_jobs_past_next_run(self):
        past = timezone.now() - timedelta(hours=1)
        future = timezone.now() + timedelta(hours=1)
        Cronjob.objects.create(
            name="past-due", schedule="0 0 * * *",
            is_active=True, next_run_at=past,
        )
        Cronjob.objects.create(
            name="future", schedule="0 0 * * *",
            is_active=True, next_run_at=future,
        )
        due = self.cronjobs.due()
        self.assertEqual(due.count(), 1)
        self.assertEqual(due.first().name, "past-due")

    def test_due_excludes_inactive(self):
        past = timezone.now() - timedelta(hours=1)
        Cronjob.objects.create(
            name="inactive-due", schedule="0 0 * * *",
            is_active=False, next_run_at=past,
        )
        self.assertEqual(self.cronjobs.due().count(), 0)

    def test_due_returns_none_when_no_jobs(self):
        self.assertEqual(self.cronjobs.due().count(), 0)

    def test_create_creates_message_content(self):
        job = self.cronjobs.create(
            name="create-test",
            schedule="0 9 * * *",
            agent_id=None,
            message_content="test message",
        )
        self.assertIsNotNone(job.message)
        self.assertEqual(job.message.content, "test message")
        self.assertEqual(job.message.content_type, "TEXT")

    def test_create_computes_next_run_at(self):
        job = self.cronjobs.create(
            name="next-run-test",
            schedule="0 9 * * *",
            agent_id=None,
        )
        self.assertIsNotNone(job.next_run_at)
        local = timezone.localtime(job.next_run_at)
        self.assertEqual(local.hour, 9)
        self.assertEqual(local.minute, 0)

    def test_create_empty_message_creates_no_content(self):
        job = self.cronjobs.create(
            name="no-msg", schedule="0 0 * * *", agent_id=None,
        )
        self.assertIsNone(job.message)

    def test_update_modifies_fields(self):
        job = Cronjob.objects.create(name="orig", schedule="0 0 * * *")
        updated = self.cronjobs.update(job, name="updated", schedule="*/5 * * * *")
        self.assertEqual(updated.name, "updated")
        self.assertEqual(updated.schedule, "*/5 * * * *")

    def test_delete_removes_job(self):
        job = Cronjob.objects.create(name="del-me", schedule="0 0 * * *")
        pk = job.pk
        self.cronjobs.delete(job)
        self.assertFalse(Cronjob.objects.filter(pk=pk).exists())

    def test_create_sets_all_custom_fields(self):
        job = self.cronjobs.create(
            name="full", schedule="30 6 * * 1-5", agent_id=None,
            description="my desc", session_mode="existing",
            session_name="my-session", message_content="hello",
            function_type="tool", function_name="shell",
        )
        self.assertEqual(job.description, "my desc")
        self.assertEqual(job.session_mode, "existing")
        self.assertEqual(job.session_name, "my-session")
        self.assertEqual(job.function_type, "tool")
        self.assertEqual(job.function_name, "shell")


class CronExecuteTest(TestCase):
    """Test the execution helper functions."""

    def test_compute_next_run_standard_cron(self):
        result = compute_next_run("0 9 * * *")
        self.assertIsNotNone(result)
        local = timezone.localtime(result)
        self.assertEqual(local.hour, 9)
        self.assertEqual(local.minute, 0)

    def test_compute_next_run_daily_shorthand(self):
        result = compute_next_run("@daily")
        self.assertIsNotNone(result)
        local = timezone.localtime(result)
        self.assertEqual(local.hour, 0)
        self.assertEqual(local.minute, 0)

    def test_compute_next_run_hourly(self):
        result = compute_next_run("@hourly")
        self.assertIsNotNone(result)
        local = timezone.localtime(result)
        self.assertEqual(local.minute, 0)

    def test_compute_next_run_weekly(self):
        result = compute_next_run("@weekly")
        self.assertIsNotNone(result)
        # Weekly runs on Sunday at 00:00
        self.assertEqual(timezone.localtime(result).weekday(), 6)

    def test_compute_next_run_invalid_expression(self):
        result = compute_next_run("not-a-cron")
        self.assertIsNone(result)

    def test_compute_next_run_every_n_minutes(self):
        result = compute_next_run("every 30m")
        self.assertIsNotNone(result)

    def test_compute_next_run_every_n_hours(self):
        result = compute_next_run("every 2h")
        self.assertIsNotNone(result)

    def test_next_run_is_in_the_future(self):
        result = compute_next_run("*/5 * * * *")
        self.assertIsNotNone(result)
        now = timezone.now()
        self.assertGreater(result, now - timedelta(seconds=10))

    def test_compute_next_run_empty_string(self):
        result = compute_next_run("")
        self.assertIsNone(result)
