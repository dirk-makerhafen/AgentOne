"""Tests for the power/battery guards (runtime/power.py).

Uses SimpleTestCase (no DB); all functions are pure or subprocess-based.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from runtime.power import (
    PowerStatus,
    _read_power_status,
    battery_gate_blocked,
    caffeinate_allowed,
    invalidate_power_cache,
    power_state_summary,
    power_status,
)

AC_OUTPUT = (
    "Now drawing from 'AC Power'\n"
    " -InternalBattery-0 (id=1234567)\t100%; charged; 0:00 remaining present: true\n"
)
BATTERY_OUTPUT = (
    "Now drawing from 'Battery Power'\n"
    " -InternalBattery-0 (id=1234567)\t93%; discharging; 4:41 remaining present: true\n"
)


class ReadPowerStatusTest(SimpleTestCase):
    @mock.patch("runtime.power.sys.platform", "darwin")
    @mock.patch("runtime.power.subprocess.run", return_value=SimpleNamespace(stdout=AC_OUTPUT))
    def test_parses_ac_power(self, *_):
        status = _read_power_status()
        self.assertTrue(status.on_ac)
        self.assertEqual(status.battery_percent, 100)

    @mock.patch("runtime.power.sys.platform", "darwin")
    @mock.patch("runtime.power.subprocess.run", return_value=SimpleNamespace(stdout=BATTERY_OUTPUT))
    def test_parses_battery_power(self, *_):
        status = _read_power_status()
        self.assertFalse(status.on_ac)
        self.assertEqual(status.battery_percent, 93)

    @mock.patch("runtime.power.sys.platform", "darwin")
    @mock.patch("runtime.power.subprocess.run", side_effect=RuntimeError("no pmset"))
    def test_pmset_failure_is_unknown(self, *_):
        status = _read_power_status()
        self.assertIsNone(status.on_ac)
        self.assertIsNone(status.battery_percent)

    @mock.patch("runtime.power.sys.platform", "linux")
    def test_non_darwin_is_unknown(self, *_):
        self.assertFalse(_read_power_status().known)


class PowerStatusCacheTest(SimpleTestCase):
    def test_power_status_caches_readings(self):
        status = PowerStatus(on_ac=True, battery_percent=100)
        with mock.patch("runtime.power._read_power_status", side_effect=[status, status]) as reader:
            invalidate_power_cache()
            self.assertEqual(power_status(), status)
            power_status()
            reader.assert_called_once_with()  # second read served from cache
            invalidate_power_cache()
            power_status()
            self.assertEqual(reader.call_count, 2)


class BatteryGateTest(SimpleTestCase):
    def make_model(self, local=True):
        return SimpleNamespace(is_local_model=local)

    def test_remote_models_never_blocked(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=False, battery_percent=5)):
            blocked, _ = battery_gate_blocked(self.make_model(local=False))
        self.assertFalse(blocked)

    def test_ac_power_never_blocks(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=True, battery_percent=5)):
            blocked, _ = battery_gate_blocked(self.make_model())
        self.assertFalse(blocked)

    def test_unknown_power_never_blocks(self):
        with mock.patch("runtime.power.power_status", return_value=PowerStatus()):
            blocked, _ = battery_gate_blocked(self.make_model())
        self.assertFalse(blocked)

    def test_sufficient_battery_not_blocked(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=False, battery_percent=60)):
            blocked, _ = battery_gate_blocked(self.make_model())
        self.assertFalse(blocked)

    def test_low_battery_blocks_local(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=False, battery_percent=10)):
            with mock.patch("runtime.power.get_pause_local_ai_below_battery_pct", return_value=15):
                blocked, reason = battery_gate_blocked(self.make_model())
        self.assertTrue(blocked)
        self.assertIn("10%", reason)


class CaffeinateAllowedTest(SimpleTestCase):
    @mock.patch("runtime.power.sys.platform", "darwin")
    def test_ac_power_allowed_even_when_low(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=True, battery_percent=5)):
            self.assertTrue(caffeinate_allowed())

    @mock.patch("runtime.power.sys.platform", "darwin")
    def test_battery_above_threshold_allowed(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=False, battery_percent=50)):
            with mock.patch("runtime.power.get_min_battery_pct_for_caffeinate", return_value=30):
                self.assertTrue(caffeinate_allowed())

    @mock.patch("runtime.power.sys.platform", "darwin")
    def test_battery_below_threshold_not_allowed(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=False, battery_percent=20)):
            with mock.patch("runtime.power.get_min_battery_pct_for_caffeinate", return_value=30):
                self.assertFalse(caffeinate_allowed())

    @mock.patch("runtime.power.sys.platform", "linux")
    def test_non_darwin_never_allowed(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=True, battery_percent=100)):
            self.assertFalse(caffeinate_allowed())


class PowerStateSummaryTest(SimpleTestCase):
    """UI-facing summary produced by power_state_summary()."""

    def base_settings(self):
        return [
            mock.patch("runtime.power.get_prevent_sleep_when_local_ai", return_value=True),
            mock.patch("runtime.power.get_min_battery_pct_for_caffeinate", return_value=30),
            mock.patch("runtime.power.get_pause_local_ai_below_battery_pct", return_value=15),
            mock.patch("runtime.power.get_sleep_guard_release_delay_minutes", return_value=5),
            mock.patch("runtime.sleep_guard.guard_is_active", return_value=False),
        ]

    @mock.patch("runtime.power.sys.platform", "darwin")
    def test_low_battery_reports_paused_and_off(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=False, battery_percent=10)):
            with self._enter(self.base_settings()):
                summary = power_state_summary()
        self.assertEqual(summary["source"], "Battery")
        self.assertEqual(summary["battery_percent"], 10)
        self.assertEqual(summary["sleep_state"], "battery_low")
        self.assertTrue(summary["paused"])

    @mock.patch("runtime.power.sys.platform", "darwin")
    def test_ac_reports_ready_and_not_paused(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=True, battery_percent=100)):
            with self._enter(self.base_settings()):
                summary = power_state_summary()
        self.assertEqual(summary["source"], "AC")
        self.assertEqual(summary["sleep_state"], "ready")
        self.assertFalse(summary["paused"])

    @mock.patch("runtime.power.sys.platform", "darwin")
    def test_healthy_battery_reports_ready(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=False, battery_percent=60)):
            with self._enter(self.base_settings()):
                summary = power_state_summary()
        self.assertEqual(summary["sleep_state"], "ready")
        self.assertFalse(summary["paused"])

    @mock.patch("runtime.power.sys.platform", "darwin")
    def test_preference_disabled_reports_disabled(self):
        settings = [
            mock.patch("runtime.power.get_prevent_sleep_when_local_ai", return_value=False),
        ] + self.base_settings()[1:]
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=True, battery_percent=100)):
            with self._enter(settings):
                summary = power_state_summary()
        self.assertEqual(summary["sleep_state"], "disabled")
        self.assertFalse(summary["paused"])

    @mock.patch("runtime.power.sys.platform", "linux")
    def test_non_darwin_unavailable(self):
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=None, battery_percent=None)):
            with self._enter(self.base_settings()):
                summary = power_state_summary()
        self.assertEqual(summary["source"], "Unavailable")
        self.assertEqual(summary["sleep_state"], "unavailable")
        self.assertFalse(summary["paused"])

    @mock.patch("runtime.power.sys.platform", "darwin")
    def test_guard_active_reported_in_summary(self):
        """guard_is_active() feeds the 'guard_active' key and 'active' state."""
        settings = list(self.base_settings()[:4]) + [
            mock.patch("runtime.sleep_guard.guard_is_active", return_value=True),
        ]
        with mock.patch("runtime.power.power_status",
                        return_value=PowerStatus(on_ac=True, battery_percent=100)):
            with self._enter(settings):
                summary = power_state_summary()
        self.assertEqual(summary["sleep_state"], "active")
        self.assertTrue(summary["guard_active"])

    def _enter(self, mocks):
        from contextlib import ExitStack
        stack = ExitStack()
        for m in mocks:
            stack.enter_context(m)
        return stack