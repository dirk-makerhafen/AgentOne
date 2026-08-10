from __future__ import annotations
import time
from pathlib import Path
import yaml
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observable import Observable


CONFIG_FILENAME = "config.yaml"
DEFAULT_CONFIG_FILE = Path(__file__).parent / "default_config.yaml"

DEFAULT_CONFIG = {
    "appearance": {
        "theme": "system",
        "skin": "default",
        "font_size": "default",
        "workspace_panel_open": False,
    },
    "preferences": {
        "default_model": "",
        "send_key": "ctrl+enter",
        "prevent_sleep_when_local_ai": True,
        "min_battery_pct_for_caffeinate": 30,
        "pause_local_ai_below_battery_pct": 15,
        "sleep_guard_release_delay_minutes": 5,
    },
}

#: Short-lived cache so hot paths (e.g. ``Session.aimodel``) do not re-read the
#: config file on every access. Invalidated whenever ``UserSettings`` saves.
_CONFIG_CACHE: dict = {"t": 0.0, "data": None}
_CONFIG_CACHE_TTL: float = 30.0


def _load_defaults() -> dict:
    try:
        if DEFAULT_CONFIG_FILE.exists():
            with open(DEFAULT_CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                return loaded
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)

VALID_THEMES = {"light", "dark", "system"}
VALID_SKINS = {
    "default", "ares", "mono", "slate",
    "poseidon", "sisyphus", "charizard", "sienna",
}
VALID_FONT_SIZES = {"small", "default", "large"}
VALID_SEND_KEYS = {"enter", "ctrl+enter"}


def _config_path() -> Path:
    return Path.home() / ".agentone" / CONFIG_FILENAME


def _read_config_file() -> dict:
    path = _config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                return loaded if isinstance(loaded, dict) else {}
        except Exception:
            pass
    return {}


def get_config() -> dict:
    """Return the merged ``config.yaml`` contents (cached briefly)."""
    now = time.time()
    if _CONFIG_CACHE["data"] is not None and (now - _CONFIG_CACHE["t"]) < _CONFIG_CACHE_TTL:
        return _CONFIG_CACHE["data"]
    data = _read_config_file()
    _CONFIG_CACHE["t"] = now
    _CONFIG_CACHE["data"] = data
    return data


def invalidate_config_cache() -> None:
    _CONFIG_CACHE["data"] = None


def get_default_model_name() -> str:
    """Return the user-configured default model name, or ``""``."""
    return str(get_config().get("preferences", {}).get("default_model") or "").strip()


def get_send_key() -> str:
    """Return the configured send-key mode (default: ``"ctrl+enter"``)."""
    value = get_config().get("preferences", {}).get("send_key") or "ctrl+enter"
    return value if value in VALID_SEND_KEYS else "ctrl+enter"


def get_prevent_sleep_when_local_ai() -> bool:
    """Whether ``caffeinate`` may keep the system awake during local calls."""
    return bool(
        get_config().get("preferences", {}).get("prevent_sleep_when_local_ai", True)
    )


def _get_battery_pct_setting(key: str, default: int) -> int:
    value = get_config().get("preferences", {}).get(key, default)
    return value if isinstance(value, int) and 0 <= value <= 100 else default


def get_min_battery_pct_for_caffeinate() -> int:
    """Minimum battery percent (on battery power) that permits caffeinate."""
    return _get_battery_pct_setting("min_battery_pct_for_caffeinate", 30)


def get_pause_local_ai_below_battery_pct() -> int:
    """Below this battery percent (on battery power) local calls are paused."""
    return _get_battery_pct_setting("pause_local_ai_below_battery_pct", 15)


def get_sleep_guard_release_delay_minutes() -> int:
    """Grace period (minutes) before caffeinate is released after the last call."""
    value = get_config().get("preferences", {}).get(
        "sleep_guard_release_delay_minutes", 5
    )
    return value if isinstance(value, int) and 0 <= value <= 120 else 5


class UserSettings(Observable):
    def __init__(self):
        super().__init__()
        self._data = _load_defaults()
        self._load()

    def _load(self):
        path = _config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                    self._merge(loaded)
            except Exception:
                pass

    def _merge(self, loaded: dict):
        for section, values in self._data.items():
            if section in loaded and isinstance(loaded[section], dict):
                for key, default in values.items():
                    val = loaded[section].get(key, default)
                    if self._valid(section, key, val):
                        self._data.setdefault(section, {})[key] = val

    @staticmethod
    def _valid(section: str, key: str, val) -> bool:
        if section == "appearance":
            if key == "theme":
                return val in VALID_THEMES
            if key == "skin":
                return val in VALID_SKINS
            if key == "font_size":
                return val in VALID_FONT_SIZES
            if key == "workspace_panel_open":
                return isinstance(val, bool)
        if section == "preferences":
            if key == "default_model":
                return isinstance(val, str)
            if key == "send_key":
                return val in VALID_SEND_KEYS
            if key == "prevent_sleep_when_local_ai":
                return isinstance(val, bool)
            if key in (
                "min_battery_pct_for_caffeinate",
                "pause_local_ai_below_battery_pct",
                "sleep_guard_release_delay_minutes",
            ):
                return isinstance(val, int) and 0 <= val <= 100
        return True

    def _save(self):
        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)
        invalidate_config_cache()

    def get(self, section: str, key: str):
        return self._data.get(section, {}).get(key)

    def set(self, section: str, key: str, value):
        if not self._valid(section, key, value):
            return
        self._data.setdefault(section, {})[key] = value
        self._save()
        self.notify_observers()

    @property
    def theme(self) -> str:
        return self.get("appearance", "theme")

    @theme.setter
    def theme(self, value: str):
        self.set("appearance", "theme", value)

    @property
    def skin(self) -> str:
        return self.get("appearance", "skin")

    @skin.setter
    def skin(self, value: str):
        self.set("appearance", "skin", value)

    @property
    def font_size(self) -> str:
        return self.get("appearance", "font_size")

    @font_size.setter
    def font_size(self, value: str):
        self.set("appearance", "font_size", value)

    @property
    def workspace_panel_open(self) -> bool:
        return self.get("appearance", "workspace_panel_open")

    @workspace_panel_open.setter
    def workspace_panel_open(self, value: bool):
        self.set("appearance", "workspace_panel_open", value)

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    @property
    def default_model(self) -> str:
        return self.get("preferences", "default_model") or ""

    @default_model.setter
    def default_model(self, value: str):
        self.set("preferences", "default_model", value)

    @property
    def send_key(self) -> str:
        return self.get("preferences", "send_key") or "ctrl+enter"

    @send_key.setter
    def send_key(self, value: str):
        self.set("preferences", "send_key", value)

    @property
    def prevent_sleep_when_local_ai(self) -> bool:
        return get_prevent_sleep_when_local_ai()

    @prevent_sleep_when_local_ai.setter
    def prevent_sleep_when_local_ai(self, value: bool):
        self.set("preferences", "prevent_sleep_when_local_ai", bool(value))

    @property
    def min_battery_pct_for_caffeinate(self) -> int:
        return get_min_battery_pct_for_caffeinate()

    @min_battery_pct_for_caffeinate.setter
    def min_battery_pct_for_caffeinate(self, value: int):
        self.set("preferences", "min_battery_pct_for_caffeinate", int(value))

    @property
    def pause_local_ai_below_battery_pct(self) -> int:
        return get_pause_local_ai_below_battery_pct()

    @pause_local_ai_below_battery_pct.setter
    def pause_local_ai_below_battery_pct(self, value: int):
        self.set("preferences", "pause_local_ai_below_battery_pct", int(value))

    @property
    def sleep_guard_release_delay_minutes(self) -> int:
        return get_sleep_guard_release_delay_minutes()

    @sleep_guard_release_delay_minutes.setter
    def sleep_guard_release_delay_minutes(self, value: int):
        self.set("preferences", "sleep_guard_release_delay_minutes", int(value))
