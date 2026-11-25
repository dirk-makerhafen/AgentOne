from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from server.models.settings import SettingsModel


class ForceDeleteSettingsTest(TestCase):
    """Settings snapshots are immutable and must not be force-deleted."""

    def test_settings_delete_is_refused(self):
        settings = SettingsModel.objects.create()
        with self.assertRaisesMessage(CommandError, "Refusing to delete SettingsModel"):
            call_command("force_delete", "SettingsModel", str(settings.pk))
        self.assertTrue(SettingsModel.objects.filter(pk=settings.pk).exists())
