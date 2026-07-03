"""Proactive behavior system — makes the pet initiate interactions.

The pet greets you on startup, reminds you to rest, reacts to weather,
and periodically checks in to keep you company.
"""

import json
import os
import random
import threading
import time
import urllib.request
from datetime import datetime
from typing import Optional, Callable

WEATHER_REACTIONS = {
    "sunny": [
        "今天天气真好！☀️",
        "阳光明媚～适合出门走走",
        "（眯眼享受阳光）",
        "好天气好心情！",
    ],
    "cloudy": [
        "今天多云，有点闷",
        "（望望天空）好像要变天了",
        "阴天...有点困",
    ],
    "rainy": [
        "下雨了...🌧️",
        "记得带伞哦！",
        "（听着雨声发呆）",
        "雨天适合窝在家里～",
    ],
    "snowy": [
        "下雪了！❄️",
        "好冷...（缩成一团）",
        "注意保暖哦！",
        "（搓手手）",
    ],
    "windy": [
        "风好大...🌬️",
        "（被风吹得摇摇晃晃）",
        "小心别着凉～",
    ],
    "foggy": [
        "雾蒙蒙的...",
        "（努力看清前方）",
        "出行注意安全哦！",
    ],
    "hot": [
        "好热...🥵",
        "记得多喝水！",
        "（吐舌头散热）",
        "开空调了吗？",
    ],
    "cold": [
        "好冷...❄️",
        "（缩成一团）",
        "多穿点衣服！",
        "需要一杯热可可...",
    ],
}

TIME_GREETINGS = {
    "morning": [
        "早安！新的一天开始了～",
        "早上好！今天也要加油！",
        "（伸懒腰）早～睡得好吗？",
        "元气满满的一天！✨",
        "早！今天有什么计划吗？",
    ],
    "noon": [
        "中午了，吃饭了吗？🍚",
        "该吃午饭啦！",
        "（摸摸肚子）饿了...",
        "午休一下吧～",
    ],
    "afternoon": [
        "下午好！精神怎么样？",
        "下午茶时间～☕",
        "（打个小哈欠）下午有点困",
        "继续加油！",
    ],
    "evening": [
        "傍晚了～",
        "今天辛苦了！",
        "（看着夕阳）好美...",
        "晚饭吃什么呢？",
    ],
    "night": [
        "夜深了...该休息了吧？🌙",
        "早点睡哦～",
        "（打哈欠）困了...",
        "明天还要早起呢",
        "晚安...做个好梦～",
    ],
    "late_night": [
        "怎么还不睡...💤",
        "（担心地看着你）",
        "身体最重要！快去休息",
        "我先打个盹...",
    ],
}

CHECKIN_MESSAGES = [
    "（偷偷看你一眼）",
    "还在忙吗？",
    "记得活动一下～",
    "（安静地陪着你）",
    "需要帮忙吗？",
    "（伸个懒腰）",
    "喝口水吧～",
    "你看起来很专注！",
]

class WeatherInfo:
    """Simple weather data."""
    def __init__(self, condition: str = "", temp: int = 0, description: str = ""):
        self.condition = condition  # sunny/cloudy/rainy/snowy/windy/foggy/hot/cold
        self.temp = temp
        self.description = description

    @property
    def is_valid(self):
        return bool(self.condition)

class ProactiveSystem:
    """Manages proactive pet behaviors — greetings, weather, check-ins."""

    WEATHER_CACHE_PATH = "weather_cache.json"

    def __init__(self, ai_companion=None):
        self._ai = ai_companion
        self._last_checkin = 0
        self._last_weather_fetch = 0
        self._weather = WeatherInfo()
        self._greeted = False
        self._night_reminded = False
        self._checkin_interval = 1800  # 30 minutes
        self._weather_interval = 3600  # 1 hour
        self._on_message: Optional[Callable[[str], None]] = None

    def set_message_callback(self, callback: Callable[[str], None]):
        """Set callback for sending messages to the pet bubble."""
        self._on_message = callback

    def on_startup(self):
        """Called when pet starts up — send greeting."""
        if self._greeted:
            return

        self._greeted = True
        now = datetime.now()
        hour = now.hour

        if 6 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 14:
            period = "noon"
        elif 14 <= hour < 18:
            period = "afternoon"
        elif 18 <= hour < 22:
            period = "evening"
        elif 22 <= hour or hour < 1:
            period = "night"
        else:
            period = "late_night"

        greeting = random.choice(TIME_GREETINGS[period])

        if self._ai and self._ai.is_available():
            self._ai.inject_context(extra="刚开机，请用一句话打招呼，简短可爱")
            def on_response(text):
                if self._on_message:
                    self._on_message(text)
            self._ai.chat("[系统] 用户刚打开电脑，请打招呼",
                         on_response=on_response,
                         on_error=lambda _: self._send(greeting))
        else:
            self._send(greeting)

    def update(self):
        """Called periodically (e.g., every minute) to check for proactive actions."""
        now = time.time()

        if now - self._last_checkin > self._checkin_interval:
            self._last_checkin = now
            self._do_checkin()

        if now - self._last_weather_fetch > self._weather_interval:
            self._last_weather_fetch = now
            self._fetch_weather_async()

        hour = datetime.now().hour
        if (hour == 23 or hour == 0) and not self._night_reminded:
            self._night_reminded = True
            self._send(random.choice(TIME_GREETINGS["night"]))
        elif hour != 23 and hour != 0:
            self._night_reminded = False

    def _do_checkin(self):
        """Send a periodic check-in message."""
        if random.random() > 0.3:
            return

        if self._weather.is_valid and random.random() < 0.4:
            msg = self._get_weather_message()
            if msg:
                self._send(msg)
                return

        self._send(random.choice(CHECKIN_MESSAGES))

    def _fetch_weather_async(self):
        """Fetch weather data in background thread."""
        def _fetch():
            try:
                self._weather = self._fetch_weather()
                if self._weather.is_valid:
                    self._save_weather_cache()
            except Exception:
                pass

        thread = threading.Thread(target=_fetch, daemon=True)
        thread.start()

    def _fetch_weather(self) -> WeatherInfo:
        """Fetch weather from wttr.in (free, no API key needed)."""
        try:
            url = "https://wttr.in/?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "ToYu/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            current = data.get("current_condition", [{}])[0]
            temp_c = int(current.get("temp_C", 20))
            weather_desc = current.get("lang_zh", [{}])[0].get("value", "")
            if not weather_desc:
                weather_desc = current.get("weatherDesc", [{}])[0].get("value", "")

            desc_lower = weather_desc.lower()
            if any(w in desc_lower for w in ["rain", "drizzle", "shower", "雨"]):
                condition = "rainy"
            elif any(w in desc_lower for w in ["snow", "sleet", "雪"]):
                condition = "snowy"
            elif any(w in desc_lower for w in ["fog", "mist", "haze", "雾"]):
                condition = "foggy"
            elif any(w in desc_lower for w in ["wind", "gust", "风"]):
                condition = "windy"
            elif any(w in desc_lower for w in ["cloud", "overcast", "阴", "多云"]):
                condition = "cloudy"
            elif any(w in desc_lower for w in ["sun", "clear", "晴"]):
                condition = "sunny"
            else:
                condition = "cloudy"

            if temp_c >= 35:
                condition = "hot"
            elif temp_c <= 0:
                condition = "cold"

            return WeatherInfo(condition, temp_c, weather_desc)

        except Exception:
            return WeatherInfo()

    def _save_weather_cache(self):
        """Cache weather data to disk."""
        try:
            data = {
                "condition": self._weather.condition,
                "temp": self._weather.temp,
                "description": self._weather.description,
                "timestamp": datetime.now().isoformat(),
            }
            with open(self.WEATHER_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _load_weather_cache(self):
        """Load cached weather data."""
        try:
            if os.path.exists(self.WEATHER_CACHE_PATH):
                with open(self.WEATHER_CACHE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._weather = WeatherInfo(
                    data.get("condition", ""),
                    data.get("temp", 0),
                    data.get("description", ""),
                )
        except Exception:
            pass

    def _get_weather_message(self) -> Optional[str]:
        """Get a weather-appropriate message."""
        if not self._weather.is_valid:
            return None
        messages = WEATHER_REACTIONS.get(self._weather.condition, [])
        if not messages:
            return None
        msg = random.choice(messages)
        if self._weather.temp:
            msg = f"{msg}（{self._weather.temp}°C）"
        return msg

    def get_weather_status(self) -> str:
        """Get current weather status for display."""
        if not self._weather.is_valid:
            return "未知"
        desc = self._weather.description or self._weather.condition
        return f"{desc} {self._weather.temp}°C" if self._weather.temp else desc

    def _send(self, message: str):
        """Send a message via the callback."""
        if self._on_message:
            self._on_message(message)

    def set_checkin_interval(self, seconds: int):
        """Set how often the pet checks in (default 30 min)."""
        self._checkin_interval = max(300, seconds)  # Min 5 minutes
