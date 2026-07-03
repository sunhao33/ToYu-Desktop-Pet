"""Accessory intelligence — natural behavior chains for a living pet."""

import time
import random
from PyQt6.QtCore import QTimer


class AccessoryBrain:
    """Behavior-driven accessory/expression system.

    Design principles:
    - Accessories have natural durations (umbrella ~45s, ice cream ~5s)
    - Behaviors chain: accessory + animation + particles + text
    - Each behavior has its own cooldown to prevent spam
    - Pet state-aware: won't interrupt active expressions
    - Random selection when multiple behaviors are possible
    """

    # Behavior cooldowns (seconds)
    COOLDOWN_WEATHER = 300      # 5 min between weather reactions
    COOLDOWN_BOREDOM = 480      # 8 min between boredom behaviors
    COOLDOWN_ICECREAM = 1800    # 30 min between ice cream treats
    COOLDOWN_MUSIC = 600        # 10 min between music reactions
    COOLDOWN_MOOD = 900         # 15 min between mood accessories
    COOLDOWN_MICRO = 120        # 2 min between micro-behaviors (particles etc)

    def __init__(self, pet_window, settings_manager):
        self.pet = pet_window
        self.settings = settings_manager
        self._enabled = True

        # Cooldown tracking (timestamp of last trigger)
        self._cooldowns = {
            'weather': 0, 'boredom': 0, 'icecream': 0,
            'music': 0, 'mood': 0, 'micro': 0,
            'morning_greet': 0, 'night_greet': 0,
        }

        # State
        self._current_weather_acc = None  # 'umbrella', 'snow', None
        self._boredom_count = 0           # escalates if ignored
        self._last_interaction_time = time.time()
        self._last_check_time = 0
        self._started = False

        # Main behavior loop — every 2 minutes
        self._timer = QTimer(self.pet)
        self._timer.timeout.connect(self._tick)

        # Track interaction for boredom detection
        if not getattr(pet_window, '_brain_handlers_wrapped', False):
            pet_window._brain_handlers_wrapped = True
            self._orig_mouse_press = pet_window.mousePressEvent
            self._orig_mouse_double = pet_window.mouseDoubleClickEvent
            pet_window.mousePressEvent = self._on_interact_wrap(self._orig_mouse_press)
            pet_window.mouseDoubleClickEvent = self._on_interact_wrap(self._orig_mouse_double)

    def _on_interact_wrap(self, original):
        def handler(event):
            self._last_interaction_time = time.time()
            self._boredom_count = 0
            if original:
                original(event)
        return handler

    def start(self):
        """Start the brain. First check after 8 seconds."""
        if self._started:
            return
        self._started = True
        self._schedule(8000, self._tick)
        self._timer.start(120_000)  # every 2 min

    def stop(self):
        self._timer.stop()
        self._started = False

    def _schedule(self, delay_ms, callback):
        """Schedule a callback that only fires if the brain is still active."""
        def _guarded():
            if not self._started or not self._enabled:
                return
            callback()
        QTimer.singleShot(delay_ms, _guarded)

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if not enabled:
            self._timer.stop()
        else:
            self._timer.start(120_000)
            self._tick()

    def _can(self, name: str, cooldown: float) -> bool:
        """Check if a behavior is off cooldown."""
        return (time.time() - self._cooldowns[name]) >= cooldown

    def _did(self, name: str):
        """Mark a behavior as triggered now."""
        self._cooldowns[name] = time.time()

    def _busy(self) -> bool:
        """Is the pet currently in an expression?"""
        return self.pet._expression_active

    def _tick(self):
        """Main behavior evaluation — runs every 2 min."""
        if not self._enabled:
            return
        try:
            now = time.localtime()
            hour = now.tm_hour

            # Priority: weather > time-of-day > boredom > mood > micro
            if self._try_weather():
                return
            if self._try_time_of_day(hour):
                return
            if self._try_boredom():
                return
            if self._try_mood():
                return
            self._try_micro(hour)

        except Exception as e:
            print(f"[AccessoryBrain] Error: {e}")

    # ── Weather ──────────────────────────────────────────────

    def _get_weather(self):
        try:
            proactive = getattr(self.pet, '_proactive', None)
            if proactive and hasattr(proactive, '_weather'):
                w = proactive._weather
                if w and w.is_valid:
                    return w
        except Exception:
            pass
        return None

    def _try_weather(self) -> bool:
        """React to weather: rain → umbrella, snow → snow particles, hot → ice cream."""
        if not self._can('weather', self.COOLDOWN_WEATHER):
            return False

        weather = self._get_weather()
        if not weather:
            return False

        condition = (weather.condition or '').lower()
        desc = (weather.description or '').lower()
        combined = condition + ' ' + desc

        is_rainy = any(w in combined for w in ['雨', 'rain', 'drizzle', 'shower', 'thunder'])
        is_snowy = any(w in combined for w in ['雪', 'snow', 'sleet'])
        is_hot = False
        try:
            temp = getattr(weather, 'temperature', None)
            if temp is not None:
                is_hot = float(temp) >= 32
        except (ValueError, TypeError):
            pass

        if is_rainy and self._current_weather_acc != 'umbrella':
            self._do_rain()
            return True
        elif is_snowy and self._current_weather_acc != 'snow':
            self._do_snow()
            return True
        elif is_hot and self._can('icecream', self.COOLDOWN_ICECREAM):
            self._do_hot_icecream()
            return True

        # Clear weather → remove umbrella if present
        if not is_rainy and not is_snowy and self._current_weather_acc:
            self.pet.clear_accessories()
            self._current_weather_acc = None

        return False

    def _do_rain(self):
        """Rain behavior: umbrella + rain particles + gentle sway."""
        if self._busy():
            return
        self._did('weather')
        self._current_weather_acc = 'umbrella'

        # Remove old accessories, add umbrella
        self.pet.clear_accessories()
        self.pet.add_umbrella(duration=45)  # auto-fade after 45s

        # Rain particles + tired animation
        self.pet.trigger_rain_mood(6.0)

        # Text bubble
        self._say(random.choice([
            "下雨了，撑伞~☂️",
            "雨滴答答的...",
            "别淋湿了哦~",
        ]))

        # After umbrella fades, clear state
        self._schedule(46_000, lambda: self._clear_weather_acc('umbrella'))

    def _do_snow(self):
        """Snow behavior: snow particles + sleepy expression."""
        if self._busy():
            return
        self._did('weather')
        self._current_weather_acc = 'snow'

        self.pet.trigger_snow_mood(5.0)

        self._say(random.choice([
            "下雪啦~❄️",
            "好冷好冷...",
            "想窝在被子里~",
        ]))

        self._schedule(300_000, lambda: self._clear_weather_acc('snow'))

    def _do_hot_icecream(self):
        """Hot weather: ice cream appears nearby, pet 'eats' it."""
        if self._busy():
            return
        self._did('icecream')
        self._did('weather')

        # Add ice cream at HAND_RIGHT
        self.pet.clear_accessories()
        self.pet.add_icecream(duration=0)

        # Sparkle burst (excitement)
        center = self.pet.geometry().center()
        self.pet._effects.add_sparkles(center.x(), center.y() - 20, count=4)

        self._say(random.choice([
            "好热呀~吃个冰淇淋🍦",
            "热化了...来根冰棍！",
            "夏天的快乐~🍦",
        ]))

        # Pet "eats" it — fade after 5s, then celebrate
        self._schedule(5000, self._eat_icecream)

    def _eat_icecream(self):
        """Pet finishes eating ice cream."""
        self.pet.clear_accessories()
        if not self._busy():
            self.pet.trigger_celebrate(3.0)
            self._say(random.choice([
                "好好吃~😋",
                "满足！",
                "嗝~",
            ]))

    def _clear_weather_acc(self, which):
        """Clear weather accessory state if it matches."""
        if self._current_weather_acc == which:
            self._current_weather_acc = None
            self.pet.clear_accessories()

    # ── Time of Day ──────────────────────────────────────────

    def _try_time_of_day(self, hour: int) -> bool:
        """Time-based behaviors: morning sparkle, night sleep."""
        # Morning greeting (6-9, once per session)
        if 6 <= hour < 9 and self._can('morning_greet', 7200):
            if self._busy():
                return False
            self._did('morning_greet')
            self.pet.trigger_sparkle_burst()
            self._say(random.choice([
                "早安~☀️",
                "新的一天开始啦！",
                "早~今天也要加油哦",
            ]))
            return True

        # Night sleep (23-6)
        if (hour >= 23 or hour < 6) and self._can('night_greet', 3600):
            if self._busy():
                return False
            self._did('night_greet')
            self.pet.trigger_sleep(8.0)
            self._say(random.choice([
                "该睡觉了...💤",
                "晚安~",
                "zzZ...",
            ]))
            return True

        # Evening wind-down (20-22)
        if 20 <= hour < 22 and self._can('micro', self.COOLDOWN_MICRO):
            if self._busy():
                return False
            center = self.pet.geometry().center()
            self.pet._effects.add_music_notes(center.x(), center.y() - 30, count=3)
            self._did('micro')
            return True

        return False

    # ── Boredom ──────────────────────────────────────────────

    def _try_boredom(self) -> bool:
        """If pet hasn't been interacted with for a while, do something fun."""
        if not self._can('boredom', self.COOLDOWN_BOREDOM):
            return False
        if self._busy():
            return False

        idle_time = time.time() - self._last_interaction_time
        if idle_time < 600:  # needs 10+ min of no interaction
            return False

        self._did('boredom')
        self._boredom_count += 1

        # Escalating boredom behaviors
        behaviors = [
            self._bored_dance_with_hat,
            self._bored_cool_glasses,
            self._bored_wand_sparkle,
            self._bored_just_dance,
        ]
        # Pick one, weighted by boredom level
        weights = [3, 3, 2, 1] if self._boredom_count <= 2 else [1, 1, 2, 3]
        behavior = random.choices(behaviors, weights=weights, k=1)[0]
        behavior()
        return True

    def _bored_dance_with_hat(self):
        """Bored: put on hat, dance, remove hat."""
        self.pet.clear_accessories()
        self.pet.add_hat(duration=7)
        self.pet.trigger_dance(6.0)
        self._say(random.choice([
            "戴上小帽子~跳个舞💃",
            "无聊了，自娱自乐~",
            "啦啦啦~🎩",
        ]))
        # Hat auto-fades via duration=7

    def _bored_cool_glasses(self):
        """Bored: put on sunglasses, do a cool pose, remove."""
        self.pet.clear_accessories()
        self.pet.add_glasses(duration=8)
        # Cool sway + sparkles
        self.pet.trigger_dance(5.0)
        center = self.pet.geometry().center()
        self.pet._effects.add_sparkles(center.x(), center.y() - 20, count=4)
        self._say(random.choice([
            "😎 cool~",
            "墨镜一带，谁都不爱",
            "今日份的帅气✓",
        ]))

    def _bored_wand_sparkle(self):
        """Bored: grab wand, sparkle, put away."""
        self.pet.clear_accessories()
        self.pet.add_wand(duration=6)
        self.pet.trigger_celebrate(4.0)
        self._say(random.choice([
            "✨ 魔法时间~",
            "biu~biu~✨",
            "看我的魔法棒！",
        ]))

    def _bored_just_dance(self):
        """Bored: just dance with music notes."""
        self.pet.trigger_dance(5.0)
        center = self.pet.geometry().center()
        self.pet._effects.add_music_notes(center.x(), center.y() - 30, count=5)
        self._say(random.choice([
            "♪~♪~♪",
            "哼首歌吧~🎵",
            "跳舞！跳舞！",
        ]))

    # ── Mood / Favorability ──────────────────────────────────

    def _try_mood(self) -> bool:
        """Based on favorability, do mood-appropriate accessories."""
        if not self._can('mood', self.COOLDOWN_MOOD):
            return False
        if self._busy():
            return False

        try:
            favorability = 50
            if hasattr(self.pet, '_ai_companion') and self.pet._ai_companion:
                favorability = getattr(self.pet._ai_companion, 'favorability', 50)

            if favorability >= 80:
                self._did('mood')
                self.pet.clear_accessories()
                self.pet.add_crown(duration=10)
                self.pet.trigger_celebrate(4.0)
                center = self.pet.geometry().center()
                self.pet._effects.add_stars(center.x(), center.y() - 40, count=6)
                self._say(random.choice([
                    "👑 心情超好！",
                    "我是最幸福的宠物~",
                    "✨ 好开心~",
                ]))
                return True

            elif favorability < 30:
                self._did('mood')
                self.pet.trigger_tired(6.0)
                self._say(random.choice([
                    "有点难过...",
                    "💧 呜...",
                    "想被关注...",
                ]))
                return True

        except Exception:
            pass
        return False

    # ── Micro-behaviors (ambient particles) ──────────────────

    def _try_micro(self, hour: int):
        """Small ambient effects — particles, tiny reactions."""
        if not self._can('micro', self.COOLDOWN_MICRO):
            return
        if self._busy():
            return

        # 40% chance to do something ambient
        if random.random() > 0.4:
            return

        center = self.pet.geometry().center()
        choices = []

        # Time-appropriate particles
        if 6 <= hour < 12:
            choices.append(('sparkles', lambda: self.pet._effects.add_sparkles(center.x(), center.y() - 20, count=3)))
        if 12 <= hour < 18:
            choices.append(('stars', lambda: self.pet._effects.add_stars(center.x(), center.y() - 30, count=3)))
        if 18 <= hour < 23:
            choices.append(('music', lambda: self.pet._effects.add_music_notes(center.x(), center.y() - 25, count=2)))
        if hour >= 23 or hour < 6:
            choices.append(('zzz', lambda: self.pet._effects.add_zzz(center.x() + 20, center.y() - 35, count=2)))

        # Always available
        choices.append(('heart', lambda: self.pet._effects.add_hearts(center.x(), center.y() - 30, count=2)))

        if choices:
            name, action = random.choice(choices)
            action()
            self._did('micro')

    # ── Utility ──────────────────────────────────────────────

    def _say(self, message: str):
        """Show a text bubble from the pet."""
        try:
            if hasattr(self.pet, '_show_companion_bubble'):
                self.pet._show_companion_bubble(message)
        except Exception as e:
            print(f"[AccessoryBrain] say error: {e}")
