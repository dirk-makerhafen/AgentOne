from __future__ import annotations
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
}


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


def _config_path() -> Path:
    return Path.home() / ".agentone" / CONFIG_FILENAME


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
        return True

    def _save(self):
        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)

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
