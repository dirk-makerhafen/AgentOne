"""
Battery / power-state guards for running local AI on macOS laptops.

Local model inference (Ollama, MLX, etc.) runs on the same machine.  On a
laptop the system normally sleeps after a few idle minutes — which interrupts
generation — while a blanket ``caffeinate`` would drain the battery.  This
module provides the sensor data and the low-battery *pause* gate, both driven
by the user preferences (``~/.agentone/config.yaml`` → ``preferences``):

* :func:`battery_gate_blocked` — says *pause* the local queue while on battery
  below ``pause_local_ai_below_battery_pct``.  Consumed by ``call_llm``.
* :func:`power_status` / :func:`caffeinate_allowed` / :func:`power_state_summary`
  — sensor readings and UI display state.

The keep-awake *sleep guard* (spawning a single ``caffeinate`` while local
models are active) is owned by the 60-second recovery scheduler via
:mod:`runtime.sleep_guard` — per-worker state here would be unreliable under
Celery prefork.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from types import SimpleNamespace

from runtime.settings.settings import (
    get_min_battery_pct_for_caffeinate,
    get_pause_local_ai_below_battery_pct,
    get_prevent_sleep_when_local_ai,
    get_sleep_guard_release_delay_minutes,
)

#: Power-state cache TTL — battery/AC rarely change faster than this, and it
#: avoids spawning ``pmset`` on every LLM call.
_POWER_CACHE: dict = {"t": 0.0, "data": None}
_POWER_CACHE_TTL: float = 15.0


@dataclass(frozen=True)
class PowerStatus:
    """Snapshot of the laptop's power state.

    ``on_ac`` is ``True``/``False`` on macOS, ``None`` when unknown (non-macOS
    or ``pmset`` failure).  ``battery_percent`` is ``None`` when unknown.
    """

    on_ac: bool | None = None
    battery_percent: int | None = None

    @property
    def known(self) -> bool:
        return self.on_ac is not None


def _read_power_status() -> PowerStatus:
    """Read ``pmset -g batt`` and parse the power source and charge percent."""
    if sys.platform != "darwin":
        return PowerStatus()
    try:
        proc = subprocess.run(
            ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5
        )
    except Exception:
        return PowerStatus()
    output = proc.stdout or ""
    on_ac: bool | None = None
    match = re.search(r"drawing from '([^']+)'", output)
    if match:
        on_ac = "AC" in match.group(1)
    battery_percent: int | None = None
    match = re.search(r"(\d+)%", output)
    if match:
        battery_percent = int(match.group(1))
    return PowerStatus(on_ac=on_ac, battery_percent=battery_percent)


def power_status() -> PowerStatus:
    """Return the current power state, cached briefly."""
    now = time.time()
    if _POWER_CACHE["data"] is not None and (now - _POWER_CACHE["t"]) < _POWER_CACHE_TTL:
        return _POWER_CACHE["data"]
    status = _read_power_status()
    _POWER_CACHE["t"] = now
    _POWER_CACHE["data"] = status
    return status


def invalidate_power_cache() -> None:
    """Force the next ``power_status()`` call to re-read the system."""
    _POWER_CACHE["data"] = None


def battery_gate_blocked(aimodel) -> tuple[bool, str]:
    """Whether a local-LLM call should be paused for lack of battery.

    Returns ``(blocked, reason)``.  Only local models (``is_local_model``)
    are ever paused; remote calls, AC power, and unknown power state never
    block.
    """
    if aimodel is None or not getattr(aimodel, "is_local_model", False):
        return False, ""
    status = power_status()
    if not status.known or status.on_ac or status.battery_percent is None:
        return False, ""
    threshold = get_pause_local_ai_below_battery_pct()
    if status.battery_percent < threshold:
        return True, (
            f"local AI paused: battery {status.battery_percent}% below "
            f"{threshold}%; plug in or wait for charge"
        )
    return False, ""


def caffeinate_allowed() -> bool:
    """Whether ``caffeinate`` may keep the system awake right now."""
    if sys.platform != "darwin":
        return False
    status = power_status()
    if status.on_ac:
        return True
    if status.battery_percent is None:
        return False
    return status.battery_percent >= get_min_battery_pct_for_caffeinate()


#: Sentinel used by :func:`power_state_summary` to probe the local-model gate.
_LOCAL_MODEL_STUB = SimpleNamespace(is_local_model=True)


def power_state_summary() -> dict:
    """Compact power/sleep state for UI display.

    Returns a JSON-serialisable dict with the current power source, battery
    charge, sleep-guard status (whether a managed ``caffeinate`` is actually
    running), and whether the low-battery pause gate would block a local
    model call right now.
    """
    status = power_status()
    if status.on_ac is True:
        source = "AC"
    elif status.on_ac is False:
        source = "Battery"
    else:
        source = "Unknown" if sys.platform == "darwin" else "Unavailable"

    blocked, reason = battery_gate_blocked(_LOCAL_MODEL_STUB)

    guard_active = False
    try:
        from runtime.sleep_guard import guard_is_active
        guard_active = guard_is_active()
    except Exception:
        pass

    if sys.platform != "darwin":
        sleep_state = "unavailable"
    elif not get_prevent_sleep_when_local_ai():
        sleep_state = "disabled"
    elif guard_active:
        sleep_state = "active"
    elif caffeinate_allowed():
        sleep_state = "ready"
    else:
        sleep_state = "battery_low"

    return {
        "battery_percent": status.battery_percent,
        "source": source,
        "sleep_state": sleep_state,
        "guard_active": guard_active,
        "paused": blocked,
        "pause_reason": reason,
        "min_caffeinate_pct": get_min_battery_pct_for_caffeinate(),
        "pause_local_pct": get_pause_local_ai_below_battery_pct(),
        "grace_minutes": get_sleep_guard_release_delay_minutes(),
    }
