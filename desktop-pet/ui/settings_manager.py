"""Application settings persisted via QSettings."""

from PyQt6.QtCore import QSettings, QPoint

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

    # ── 桌面工具 ────────────────────────────────────────────
    @property
    def clipboard_enabled(self):
        val = self._settings.value("tools/clipboard_enabled", False)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @clipboard_enabled.setter
    def clipboard_enabled(self, value):
        self._settings.setValue("tools/clipboard_enabled", value)

    @property
    def clipboard_history(self):
        import json
        val = self._settings.value("tools/clipboard_history")
        if not val:
            return []
        try:
            data = json.loads(val)
        except Exception:
            return []
        return data if isinstance(data, list) else []

    @clipboard_history.setter
    def clipboard_history(self, items):
        import json
        self._settings.setValue("tools/clipboard_history", json.dumps(items))

    @property
    def eye_care_enabled(self):
        val = self._settings.value("tools/eye_care_enabled", False)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @eye_care_enabled.setter
    def eye_care_enabled(self, value):
        self._settings.setValue("tools/eye_care_enabled", value)

    @property
    def eye_care_work_minutes(self):
        return int(self._settings.value("tools/eye_care_work_minutes", 45))

    @eye_care_work_minutes.setter
    def eye_care_work_minutes(self, value):
        self._settings.setValue("tools/eye_care_work_minutes", int(value))

    @property
    def eye_care_rest_minutes(self):
        return int(self._settings.value("tools/eye_care_rest_minutes", 5))

    @eye_care_rest_minutes.setter
    def eye_care_rest_minutes(self, value):
        self._settings.setValue("tools/eye_care_rest_minutes", int(value))

    @property
    def eye_care_deadline(self):
        return float(self._settings.value("tools/eye_care_deadline", 0.0))

    @eye_care_deadline.setter
    def eye_care_deadline(self, value):
        self._settings.setValue("tools/eye_care_deadline", float(value))

    # ── 心流模式 ────────────────────────────────────────────
    @property
    def flow_mode_enabled(self):
        val = self._settings.value("flow/enabled", False)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @flow_mode_enabled.setter
    def flow_mode_enabled(self, value):
        self._settings.setValue("flow/enabled", value)

    # ── 悬浮计时小窗 ────────────────────────────────────────
    @property
    def mini_timer_enabled(self):
        val = self._settings.value("flow/mini_timer", True)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @mini_timer_enabled.setter
    def mini_timer_enabled(self, value):
        self._settings.setValue("flow/mini_timer", value)

    @property
    def mini_timer_pos(self):
        """小窗位置；没记录过返回 None，由窗口自己挑一个默认角落。"""
        val = self._settings.value("flow/mini_timer_pos", None)
        if isinstance(val, str) and "," in val:
            try:
                x, y = val.split(",")
                return int(x), int(y)
            except ValueError:
                return None
        return None

    @mini_timer_pos.setter
    def mini_timer_pos(self, value):
        if value is None:
            self._settings.remove("flow/mini_timer_pos")
        else:
            self._settings.setValue("flow/mini_timer_pos", "%d,%d" % (value[0], value[1]))

    # ── AI 上下文隐私开关 ───────────────────────────────────
    # 剪贴板内容与前台应用名属于隐私敏感信息，默认**不**提供给 AI
    @property
    def context_clipboard_enabled(self):
        return self._bool("context/clipboard_enabled", False)

    @context_clipboard_enabled.setter
    def context_clipboard_enabled(self, value):
        self._settings.setValue("context/clipboard_enabled", bool(value))

    @property
    def context_foreground_enabled(self):
        return self._bool("context/foreground_enabled", False)

    @context_foreground_enabled.setter
    def context_foreground_enabled(self, value):
        self._settings.setValue("context/foreground_enabled", bool(value))

    # ── 长期记忆开关 ────────────────────────────────────────
    @property
    def memory_enabled(self):
        return self._bool("memory/enabled", True)

    @memory_enabled.setter
    def memory_enabled(self, value):
        self._settings.setValue("memory/enabled", bool(value))

    # ── 打字机效果 ──────────────────────────────────────────
    @property
    def typing_enabled(self):
        return self._bool("ui/typing_enabled", True)

    @typing_enabled.setter
    def typing_enabled(self, value):
        self._settings.setValue("ui/typing_enabled", bool(value))

    def _bool(self, key, default=False):
        val = self._settings.value(key, default)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)
