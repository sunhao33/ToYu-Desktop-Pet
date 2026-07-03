"""Application settings persisted via QSettings."""

from PyQt6.QtCore import QSettings, QPoint


# ── Settings Manager ─────────────────────────────────────────


class SettingsManager:
    def __init__(self):
        self._settings = QSettings("DesktopPet", "DesktopPet")

    @property
    def pet_image_path(self):
        return self._settings.value("pet/image_path", "")

    @pet_image_path.setter
    def pet_image_path(self, value):
        self._settings.setValue("pet/image_path", value)

    @property
    def pet_position(self):
        val = self._settings.value("pet/position")
        if val is None:
            return None
        return QPoint(val)

    @pet_position.setter
    def pet_position(self, point):
        self._settings.setValue("pet/position", point)

    @property
    def walking_speed_min(self):
        return float(self._settings.value("behavior/walking_speed_min", 1.0))

    @walking_speed_min.setter
    def walking_speed_min(self, value):
        self._settings.setValue("behavior/walking_speed_min", float(value))

    @property
    def walking_speed_max(self):
        return float(self._settings.value("behavior/walking_speed_max", 3.0))

    @walking_speed_max.setter
    def walking_speed_max(self, value):
        self._settings.setValue("behavior/walking_speed_max", float(value))

    @property
    def idle_time_min(self):
        return int(self._settings.value("behavior/idle_time_min", 3000))

    @property
    def idle_time_max(self):
        return int(self._settings.value("behavior/idle_time_max", 15000))

    @property
    def animation_scale(self):
        return float(self._settings.value("display/animation_scale", 1.0))

    @animation_scale.setter
    def animation_scale(self, value):
        self._settings.setValue("display/animation_scale", value)

    @property
    def always_on_top(self):
        val = self._settings.value("display/always_on_top", True)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @always_on_top.setter
    def always_on_top(self, value):
        self._settings.setValue("display/always_on_top", value)

    @property
    def auto_start(self):
        val = self._settings.value("behavior/auto_start", False)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @auto_start.setter
    def auto_start(self, value):
        self._settings.setValue("behavior/auto_start", value)

    @property
    def favorites(self):
        import json
        val = self._settings.value("pet/favorites")
        if not val:
            return []
        try:
            data = json.loads(val)
        except Exception:
            return []
        # Migrate old format (list of strings) → new format (list of dicts)
        if data and isinstance(data[0], str):
            data = [{"path": p, "name": self._path_to_name(p)} for p in data]
        return data

    @favorites.setter
    def favorites(self, items):
        import json
        self._settings.setValue("pet/favorites", json.dumps(items))

    @staticmethod
    def _path_to_name(path):
        import os
        basename = os.path.basename(path)
        # Strip known suffixes
        for suf in ("_pet.png", ".png", "_processed", "_bead"):
            basename = basename.replace(suf, "")
        return basename or "未命名"

    @property
    def interaction_mode(self):
        return self._settings.value("behavior/interaction_mode", "free")

    @interaction_mode.setter
    def interaction_mode(self, value):
        self._settings.setValue("behavior/interaction_mode", value)

    @property
    def bead_creations(self):
        import json
        val = self._settings.value("pet/bead_creations")
        if not val:
            return []
        try:
            return json.loads(val)
        except Exception:
            return []

    @bead_creations.setter
    def bead_creations(self, creations):
        import json
        self._settings.setValue("pet/bead_creations", json.dumps(creations))

    @property
    def pomodoro_enabled(self):
        val = self._settings.value("pomodoro/enabled", False)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @pomodoro_enabled.setter
    def pomodoro_enabled(self, value):
        self._settings.setValue("pomodoro/enabled", value)

    @property
    def pomodoro_interval(self):
        return int(self._settings.value("pomodoro/interval", 25))

    @pomodoro_interval.setter
    def pomodoro_interval(self, value):
        self._settings.setValue("pomodoro/interval", int(value))

    @property
    def pomodoro_last_fired(self):
        return float(self._settings.value("pomodoro/last_fired", 0.0))

    @pomodoro_last_fired.setter
    def pomodoro_last_fired(self, value):
        self._settings.setValue("pomodoro/last_fired", float(value))

    @property
    def affection_level(self):
        return int(self._settings.value("pet/affection_level", 0))

    @affection_level.setter
    def affection_level(self, value):
        self._settings.setValue("pet/affection_level", int(value))

    @property
    def affection_last_decay(self):
        return float(self._settings.value("pet/affection_last_decay", 0.0))

    @affection_last_decay.setter
    def affection_last_decay(self, value):
        self._settings.setValue("pet/affection_last_decay", float(value))

    @property
    def feed_last_used(self):
        return float(self._settings.value("pet/feed_last_used", 0.0))

    @feed_last_used.setter
    def feed_last_used(self, value):
        self._settings.setValue("pet/feed_last_used", float(value))

    @property
    def time_awareness_enabled(self):
        val = self._settings.value("behavior/time_awareness", True)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @time_awareness_enabled.setter
    def time_awareness_enabled(self, value):
        self._settings.setValue("behavior/time_awareness", value)

    @property
    def house_enabled(self):
        val = self._settings.value("house/enabled", False)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @house_enabled.setter
    def house_enabled(self, value):
        self._settings.setValue("house/enabled", value)

    @property
    def house_position(self):
        val = self._settings.value("house/position")
        if val is None:
            return None
        from PyQt6.QtCore import QPoint
        return QPoint(val)

    @house_position.setter
    def house_position(self, point):
        self._settings.setValue("house/position", point)

    @property
    def auto_home_timeout(self):
        """Auto-go-home timeout in minutes. 0 = disabled."""
        return int(self._settings.value("pet/auto_home_timeout", 0))

    @auto_home_timeout.setter
    def auto_home_timeout(self, value):
        self._settings.setValue("pet/auto_home_timeout", int(value))
