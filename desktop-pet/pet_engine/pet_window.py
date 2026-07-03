"""Transparent desktop pet window with rendering and game loop."""

import os
import time
import math
import ctypes
from ctypes import wintypes
from datetime import datetime
from enum import Enum as _Enum
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QRect, QSize
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QTransform, QMouseEvent, QCursor, QColor
)
from PyQt6.QtWidgets import QMainWindow, QApplication, QToolTip

from .pet_physics import PetPhysics
from .taskbar import get_taskbar_info
from .pet_state_machine import PetStateMachine, PetState, InteractionMode
from .pet_animation import PetAnimation, AnimationType
from .pet_affection import AffectionSystem
from .pet_bubble import PetFunctionBubble, PomodoroNotificationBubble, ChatBubble
from .pet_food import FoodItemWindow, FloatingText
from .pet_ai import AICompanion, AIConfig
from image_processor.processor import get_default_pet_path, _resource_path
from pet_engine.sprite_bounds import get_visible_bounds, get_content_ratio

class TimePeriod(_Enum):
    NIGHT = "night"
    MORNING = "morning"
    DAY = "day"
    EVENING = "evening"

class PetWindow(QMainWindow):
    FRAME_RATE = 60  # fps
    FRAME_DT = 1.0 / FRAME_RATE

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

        self._init_core()
        self._init_interaction_state()
        self._init_timers()
        self._init_companion_systems()
        self._init_bubble_callbacks()

        self._init_ui()
        self._load_pet_image()
        self._restore_position()

        self._last_tick = time.time()
        self._game_timer = QTimer(self)
        self._game_timer.timeout.connect(self._game_tick)
        self._game_timer.start(int(1000 / self.FRAME_RATE))

        self.state_machine.set_time_period(self._current_time_period)

    def _init_core(self):
        """Initialize pixmap, physics, state machine, animation, and affection."""
        self._pet_pixmap = None
        self._pet_image_path = ""
        self._drag_offset = QPoint()
        self._position = QPoint(400, 300)
        self._scale = self.settings.animation_scale

        self._taskbar_info = get_taskbar_info()
        self._sprite_bottom_offset = 0
        self.physics = PetPhysics(
            QApplication.primaryScreen().geometry(),
            (128, 128),
            taskbar_height=self._taskbar_info['height'] if self._taskbar_info else 0
        )
        self.state_machine = PetStateMachine(self.settings)
        self.animation = PetAnimation()
        self.affection = AffectionSystem(self.settings)
        self.affection.set_milestone_callback(self._on_milestone_reached)
        self._anim_type_map = {
            PetState.IDLE: AnimationType.IDLE,
            PetState.WALKING: AnimationType.WALK,
            PetState.FALLING: AnimationType.FALL,
            PetState.SITTING: AnimationType.SIT,
            PetState.INTERACTING: AnimationType.INTERACT,
            PetState.HOPPING: AnimationType.HOP,
            PetState.DRAGGED: AnimationType.NONE,
        }

    def _init_interaction_state(self):
        """Initialize drag/shake/lean/landing state flags."""
        self._expression_active = False
        self._expression_end_timer = QTimer(self)
        self._expression_end_timer.setSingleShot(True)
        self._expression_end_timer.timeout.connect(self._end_expression)
        self._drag_positions = []
        self._shake_detected = False
        self._pending_bounce_land = False
        self._mouse_in_proximity = False
        self._lean_active = False
        self.setMouseTracking(True)
        self._was_grounded_last_tick = True

    def _init_timers(self):
        """Initialize all periodic timers."""
        self._pomodoro_timer = QTimer(self)
        self._pomodoro_timer.timeout.connect(self._check_pomodoro)
        self._pomodoro_timer.start(1000)

        self._decay_timer = QTimer(self)
        self._decay_timer.timeout.connect(self.affection.tick_decay)
        self._decay_timer.start(30000)

        self.affection.add(itype='first_daily')

        self._feed_cooldown_end = max(0, self.settings.feed_last_used + 30 - time.time())
        self._feed_cooldown_timer = QTimer(self)
        self._feed_cooldown_timer.timeout.connect(self._tick_feed_cooldown)

        self._time_awareness_enabled = self.settings.time_awareness_enabled
        self._current_time_period = self._get_time_period()
        self._time_check_timer = QTimer(self)
        self._time_check_timer.timeout.connect(self._on_time_check)
        self._time_check_timer.start(60000)

        self._auto_home_timeout_ms = self.settings.auto_home_timeout * 60 * 1000
        self._auto_home_timer = QTimer(self)
        self._auto_home_timer.timeout.connect(self._on_auto_home)
        if self._auto_home_timeout_ms > 0:
            self._auto_home_timer.start(int(self._auto_home_timeout_ms))
        self._last_interaction_time = time.time()

    def _init_companion_systems(self):
        """Initialize companion, AI, proactive, effects, and accessory subsystems."""
        from pet_engine.pet_companion import CompanionSystem
        self.companion = CompanionSystem(self.settings)
        self._companion_update_timer = QTimer(self)
        self._companion_update_timer.timeout.connect(self._update_companion)
        self._companion_update_timer.start(30000)
        self._last_companion_message_time = 0
        self._companion_bubble = None

        self._ai_config = AIConfig()
        self._ai_config.load()
        self._ai = AICompanion(self._ai_config)
        self._chat_bubble = ChatBubble(self)
        self._chat_bubble.message_sent.connect(self._on_ai_message)

        from pet_engine.pet_proactive import ProactiveSystem
        self._proactive = ProactiveSystem(self._ai)
        self._proactive.set_message_callback(self._show_companion_bubble)
        self._proactive._load_weather_cache()

        from pet_engine.pet_effects import ParticleSystem
        self._effects = ParticleSystem()

        from pet_engine.pet_accessories import AccessoryLayer, Anchor
        self._accessory_layer = AccessoryLayer()
        self._AccessoryAnchor = Anchor
        self._sprite_content_ratio = {'top': 0.15, 'bottom': 0.05, 'left': 0.1, 'right': 0.1}

    def _init_bubble_callbacks(self):
        """Initialize bubble callback dict (populated by main_window)."""
        self._bubble = None
        self._bubble_callbacks = {
            "show_hide": None, "change": None, "exit": None, "show_main_window": None,
        }
        self._house = None

    def _init_ui(self):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAutoFillBackground(False)
        self.setAcceptDrops(True)
        self.resize(150, 150)

        self._disable_ime()

    def _disable_ime(self):
        """Use Win32 API to disable IME on this window."""
        try:
            import ctypes
            hwnd = int(self.winId())
            # ImmAssociateContext(hWnd, hContext=NULL) disables IME
            ctypes.windll.imm32.ImmAssociateContext(hwnd, 0)
        except Exception:
            pass

    def set_bubble_callbacks(self, show_hide_cb=None, change_cb=None, exit_cb=None, show_main_window_cb=None):
        self._bubble_callbacks = {
            "show_hide": show_hide_cb,
            "change": change_cb,
            "exit": exit_cb,
            "show_main_window": show_main_window_cb,
        }

    def set_house(self, house_window):
        self._house = house_window

    def move_to(self, x, y):
        """Teleport pet to a specific screen position (used by house)."""
        self._position = QPoint(int(x), int(y))
        self.move(self._position)
        self.physics.stop()
        self.state_machine.transition_to(PetState.IDLE)
        self._clamp_to_screen()

    @staticmethod
    def _get_time_period():
        hour = datetime.now().hour
        if 22 <= hour or hour < 6:
            return TimePeriod.NIGHT
        elif 6 <= hour < 10:
            return TimePeriod.MORNING
        elif 10 <= hour < 18:
            return TimePeriod.DAY
        else:
            return TimePeriod.EVENING

    def set_time_awareness(self, enabled):
        self._time_awareness_enabled = enabled
        self.settings.time_awareness_enabled = enabled
        if enabled:
            self._on_time_check()
        else:
            self._current_time_period = TimePeriod.DAY
            self.state_machine.set_time_period(TimePeriod.DAY)
            if self._house:
                self._house.set_night_glow(False)

    def _on_time_check(self):
        if not self._time_awareness_enabled:
            return
        period = self._get_time_period()
        if period != self._current_time_period:
            self._current_time_period = period
            self.state_machine.set_time_period(period)
            if self._house:
                self._house.set_night_glow(period == TimePeriod.NIGHT)

    def _tick_feed_cooldown(self):
        remaining = max(0, int(self._feed_cooldown_end - time.time()))
        if self._bubble:
            self._bubble.set_feed_cooldown(remaining)
        if remaining <= 0:
            self._feed_cooldown_timer.stop()

    def _on_feed_pet(self):
        now = time.time()
        if now < self._feed_cooldown_end:
            return
        state = self.state_machine.current_state
        if state in (PetState.DRAGGED, PetState.FALLING):
            return

        food = FoodItemWindow()
        food.food_moved.connect(self._on_food_moved)
        food.spawn_near(self)

        self._feed_cooldown_end = now + 30
        self.settings.feed_last_used = now
        self._feed_cooldown_timer.start(1000)

        if self._bubble:
            self._bubble.set_feed_cooldown(30)

        self._current_food = food
        self._food_tracking_timer = QTimer(self)
        self._food_tracking_timer.timeout.connect(self._track_food)
        self._food_tracking_timer.start(50)  # Track every 50ms

    def _on_food_moved(self, pos):
        """Called when food is dragged to a new position."""
        pass  # Food position is tracked via _track_food

    def _track_food(self):
        """Track food position and make pet chase it.

        Simple pursuit AI: walk toward food horizontally, jump if food is above,
        or fall if food is below. When close enough, eat it.
        """
        if not hasattr(self, '_current_food') or not self._current_food:
            if hasattr(self, '_food_tracking_timer'):
                self._food_tracking_timer.stop()
            return

        food = self._current_food
        if not food.isVisible() or food._is_consumed:
            self._food_tracking_timer.stop()
            self._current_food = None
            return

        food_pos = food.pos()
        food_cx = food_pos.x() + food.width() // 2
        food_cy = food_pos.y() + food.height() // 2

        pet_cx = self.x() + self.width() // 2
        pet_cy = self.y() + self.height() // 2

        dx = food_cx - pet_cx
        dy = food_cy - pet_cy
        dist = (dx * dx + dy * dy) ** 0.5

        if dist < 40:
            self._complete_feed(food)
            self._food_tracking_timer.stop()
            self._current_food = None
            return

        if self.physics.grounded:
            direction = 1 if dx > 0 else -1
            walk_speed = self.settings.walking_speed_max * 1.2

            if dy < -50:
                self.physics.set_jump_velocity(-12)
                self.state_machine.transition_to(PetState.HOPPING)
            elif dy > 50:
                self.physics.set_fall_velocity(2)
                self.state_machine.transition_to(PetState.FALLING)
            else:
                self.state_machine._walk_direction = direction
                self.state_machine._walk_duration = 0.5
                self.state_machine.transition_to(PetState.WALKING)
                self.physics.set_walk_velocity(walk_speed * direction)

    def _complete_feed(self, food):
        if food._is_consumed:
            return
        food._is_consumed = True
        food.consume()
        self.affection.add(itype='feed')
        self._update_affection_tooltip()
        ft = FloatingText()
        ft.show_near(self)
        center = self.geometry().center()
        self._effects.add_hearts(center.x(), center.y() - 30, count=6)
        message = self.companion.on_interaction("feed")
        self._show_companion_bubble(message)
        self.state_machine.transition_to(PetState.IDLE)
        self._reset_auto_home_timer()

    def trigger_dance(self, duration=5.0):
        """Pet dances — bounce + sway + music notes."""
        self._expression_active = True
        self.animation.set_animation(AnimationType.DANCE)
        center = self.geometry().center()
        self._effects.add_music_notes(center.x(), center.y() - 30, count=5)
        self._expression_end_timer.start(int(duration * 1000))

    def trigger_tired(self, duration=6.0):
        """Pet looks tired — slow sway + sweat."""
        self._expression_active = True
        self.animation.set_animation(AnimationType.TIRED)
        center = self.geometry().center()
        self._effects.add_sweat(center.x(), center.y() - 30, count=3)
        self._expression_end_timer.start(int(duration * 1000))

    def trigger_sleep(self, duration=8.0):
        """Pet falls asleep — slow sink + Zzz."""
        self._expression_active = True
        self.animation.set_animation(AnimationType.SLEEP)
        center = self.geometry().center()
        self._effects.add_zzz(center.x() + 30, center.y() - 40, count=4)
        self._expression_end_timer.start(int(duration * 1000))

    def trigger_celebrate(self, duration=4.0):
        """Pet celebrates — fast bounce + sparkles + stars."""
        self._expression_active = True
        self.animation.set_animation(AnimationType.CELEBRATE)
        center = self.geometry().center()
        self._effects.add_sparkles(center.x(), center.y() - 30, count=10)
        self._effects.add_stars(center.x(), center.y() - 50, count=6)
        self._expression_end_timer.start(int(duration * 1000))

    def trigger_rain_mood(self, duration=6.0):
        """Pet in rain — gentle sway + rain drops."""
        self._expression_active = True
        self.animation.set_animation(AnimationType.TIRED)
        center = self.geometry().center()
        self._effects.add_rain(center.x(), center.y() - 30, count=8)
        self._expression_end_timer.start(int(duration * 1000))

    def trigger_sparkle_burst(self):
        """Quick sparkle burst — no animation change."""
        center = self.geometry().center()
        self._effects.add_sparkles(center.x(), center.y() - 30, count=6)

    def trigger_snow_mood(self, duration=5.0):
        """Pet in snow — gentle sink + snow particles."""
        self._expression_active = True
        self.animation.set_animation(AnimationType.TIRED)
        center = self.geometry().center()
        self._effects.add_snow(center.x(), center.y() - 20, count=10)
        self._expression_end_timer.start(int(duration * 1000))

    _ACCESSORY_REGISTRY = {
        "hat":      (_resource_path('resources/acc_hat.png'),      "TOP",        0.8, -5,  False, True),
        "umbrella": (_resource_path('resources/acc_umbrella.png'),  "TOP",        0.7, -10, True,  False),
        "icecream": (_resource_path('resources/acc_icecream.png'),  "HAND_RIGHT", 0.6, 0,   False, False),
        "bow":      (_resource_path('resources/acc_bow.png'),       "TOP_RIGHT",  0.5, -3,  False, False),
        "crown":    (_resource_path('resources/acc_crown.png'),     "TOP",        0.7, -8,  False, False),
        "glasses":  (_resource_path('resources/acc_glasses.png'),   "CENTER",     0.6, -5,  False, False),
        "wand":     (_resource_path('resources/acc_wand.png'),      "HAND_RIGHT", 0.7, -10, True,  True),
    }

    def _add_accessory_by_name(self, name, duration=0):
        """Generic accessory adder driven by _ACCESSORY_REGISTRY."""
        if name not in self._ACCESSORY_REGISTRY:
            return
        resource_path, anchor_name, scale, offset_y, bobbing, needs_cr = self._ACCESSORY_REGISTRY[name]
        g = self.geometry()
        self._accessory_layer.update_geometry(g.x(), g.y(), g.width(), g.height())
        if needs_cr:
            self._accessory_layer.set_content_ratio(self._sprite_content_ratio)
        anchor = getattr(self._AccessoryAnchor, anchor_name)
        self._accessory_layer.add_accessory(
            resource_path,
            anchor=anchor,
            scale=scale, offset_y=offset_y, bobbing=bobbing, duration=duration)

    def add_hat(self, duration=0):      self._add_accessory_by_name("hat", duration)
    def add_umbrella(self, duration=0): self._add_accessory_by_name("umbrella", duration)
    def add_icecream(self, duration=0): self._add_accessory_by_name("icecream", duration)
    def add_bow(self, duration=0):      self._add_accessory_by_name("bow", duration)
    def add_crown(self, duration=0):    self._add_accessory_by_name("crown", duration)
    def add_glasses(self, duration=0):  self._add_accessory_by_name("glasses", duration)
    def add_wand(self, duration=0):     self._add_accessory_by_name("wand", duration)

    def clear_accessories(self):
        """Remove all accessories."""
        self._accessory_layer.clear_all()

    def _end_expression(self):
        """Return to idle after expression animation."""
        self._expression_active = False
        if self.animation.current_type in (
            AnimationType.DANCE, AnimationType.TIRED,
            AnimationType.SLEEP, AnimationType.CELEBRATE,
            AnimationType.BOUNCE_LAND, AnimationType.DIZZY
        ):
            if self._mouse_in_proximity and not self.state_machine.is_dragged:
                self._lean_active = True
                self.animation.set_animation(AnimationType.LEAN)
            else:
                self.animation.set_animation(AnimationType.IDLE)

    def _reset_auto_home_timer(self):
        """Reset the auto-go-home timer on any interaction."""
        self._last_interaction_time = time.time()
        if self._auto_home_timeout_ms > 0 and self._auto_home_timer.isActive():
            self._auto_home_timer.start(int(self._auto_home_timeout_ms))

    def _on_auto_home(self):
        """Called when no interaction for the set duration. Pet goes home."""
        # Don't go home if already inside house
        if self._house and self._house._pet_inside:
            return
        # Don't go home if being dragged
        if self._is_dragging:
            return
        self._show_companion_bubble("我先回去休息啦~")
        QTimer.singleShot(2000, self._do_auto_home)

    def _do_auto_home(self):
        """Actually go home after the message."""
        if self._house and not self._house._pet_inside:
            self._go_home()

    def _update_sprite_bounds(self):
        """Cache visible content bounds of current pet sprite."""
        if self._pet_pixmap and not self._pet_pixmap.isNull():
            self._sprite_content_ratio = get_content_ratio(self._pet_pixmap)
        else:
            self._sprite_content_ratio = {'top': 0.15, 'bottom': 0.05, 'left': 0.1, 'right': 0.1}

    def _load_pet_image(self, path=None):
        if path:
            self._pet_image_path = path
        elif self.settings.pet_image_path:
            self._pet_image_path = self.settings.pet_image_path
        else:
            self._pet_image_path = get_default_pet_path()

        try:
            pix = QPixmap(self._pet_image_path)
            if pix.isNull():
                pix = QPixmap(get_default_pet_path())
                self._pet_image_path = get_default_pet_path()
            self._pet_pixmap = pix
            self._update_window_size()  # also updates physics with window size + sprite offset
        except Exception:
            self._pet_pixmap = QPixmap(get_default_pet_path())
            self._pet_image_path = get_default_pet_path()
            self._update_sprite_bounds()
            self._update_window_size()

    def _update_window_size(self):
        if self._pet_pixmap:
            padding = 60
            w = int(self._pet_pixmap.width() * self._scale * 1.6) + padding
            h = int(self._pet_pixmap.height() * self._scale * 1.6) + padding
            self.resize(w, h)
            margin = 10
            avail_h = h - margin * 2
            sprite_cy_in_window = margin + avail_h // 2
            sprite_h = int(self._pet_pixmap.height() * self._scale)
            sprite_bottom_in_window = sprite_cy_in_window + sprite_h // 2
            self._sprite_bottom_offset = h - sprite_bottom_in_window
            self.physics.update_pet_size(
                (w, h),
                sprite_bottom_offset=self._sprite_bottom_offset
            )

    def _restore_position(self):
        saved = self.settings.pet_position
        if saved is not None:
            self._position = saved
        else:
            screen = QApplication.primaryScreen().geometry()
            taskbar_h = self._taskbar_info['height'] if self._taskbar_info else 0
            self._position = QPoint(
                screen.x() + screen.width() // 2,
                screen.y() + screen.height() - taskbar_h - self.height() + self._sprite_bottom_offset,
            )
        self.move(self._position)
        self._clamp_to_screen()

    def _clamp_to_screen(self):
        screen = QApplication.primaryScreen().geometry()
        taskbar_h = self._taskbar_info['height'] if self._taskbar_info else 0
        geo = self.geometry()
        x = max(screen.x(), min(geo.x(), screen.x() + screen.width() - geo.width()))
        max_y = screen.y() + screen.height() - taskbar_h - geo.height() + self._sprite_bottom_offset
        y = max(screen.y(), min(geo.y(), max_y))
        if x != geo.x() or y != geo.y():
            self._position = QPoint(x, y)
            self.move(self._position)

    def set_pet_image(self, image_path):
        self._load_pet_image(image_path)
        self.settings.pet_image_path = image_path

    def set_scale(self, scale):
        old = self._scale
        clamped = max(0.5, min(2.0, scale))
        if clamped != scale:
            if scale > 2.0:
                QToolTip.showText(self.mapToGlobal(QPoint(20, -10)),
                                  "我已经变得够大啦！")
            elif scale < 0.5:
                QToolTip.showText(self.mapToGlobal(QPoint(20, -10)),
                                  "再变小可就看不见我咯～")
        if clamped == old:
            return
        self._scale = clamped
        self.settings.animation_scale = clamped
        self._update_window_size()  # also updates physics
        self._clamp_to_screen()
        self.update()

    def _game_tick(self):
        """Main update loop — runs at FRAME_RATE (60fps).

        Order: landing detection → state machine → follow-mouse AI
        → animation mapping → walking speed (with time awareness modifier)
        → physics step → animation update → lean update → repaint.
        """
        now = time.time()
        dt = now - self._last_tick
        self._last_tick = now

        # Cap dt: if app was backgrounded, don't let physics spiral
        if dt > 0.1:
            dt = self.FRAME_DT

        current_pos = QPoint(self.x(), self.y())
        grounded = self.physics.grounded

        if grounded and not self._was_grounded_last_tick and not self.state_machine.is_dragged:
            if not self._expression_active:
                fall_speed = abs(self.physics.vy)
                if fall_speed > 2.0 or self._pending_bounce_land:
                    self.animation.set_animation(AnimationType.BOUNCE_LAND)
                    self._expression_active = True
                    self._pending_bounce_land = False
                    self._expression_end_timer.start(700)
        if grounded and self._pending_bounce_land and not self.state_machine.is_dragged:
            if not self._expression_active:
                self.animation.set_animation(AnimationType.BOUNCE_LAND)
                self._expression_active = True
                self._pending_bounce_land = False
                self._expression_end_timer.start(700)
        self._was_grounded_last_tick = grounded

        cmd = self.state_machine.update(dt, grounded)
        state = cmd["state"]

        if (self.state_machine.interaction_mode == InteractionMode.FOLLOW
                and state == PetState.IDLE
                and grounded
                and not self.state_machine.is_dragged):
            cursor = QCursor.pos()
            pet_cx = self.x() + self.width() // 2
            pet_cy = self.y() + self.height() // 2
            dx = cursor.x() - pet_cx
            dy = cursor.y() - pet_cy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 60:
                direction = 1 if dx > 0 else -1
                walk_speed = self.settings.walking_speed_max * 0.8
                self.state_machine._walk_direction = direction
                self.state_machine._walk_duration = 1.5
                self.state_machine.transition_to(PetState.WALKING)
                state = PetState.WALKING
                cmd = {"state": PetState.WALKING,
                       "walk_speed": walk_speed,
                       "walk_direction": direction}

        if not self._expression_active:
            anim_type = self._anim_type_map.get(state, AnimationType.IDLE)
            self.animation.set_animation(anim_type)

        if state == PetState.WALKING:
            walk_speed = cmd.get("walk_speed", 0)
            walk_dir = cmd.get("walk_direction", 0)
            if self._time_awareness_enabled:
                period = self._current_time_period
                if period == TimePeriod.NIGHT:
                    walk_speed *= 0.5
                elif period == TimePeriod.MORNING:
                    walk_speed *= 1.3
                elif period == TimePeriod.EVENING:
                    walk_speed *= 0.8
            self.physics.set_walk_velocity(walk_speed * walk_dir)

        if not self.state_machine.is_dragged:
            new_x, new_y = self.physics.step(
                float(current_pos.x()), float(current_pos.y())
            )
            self._position = QPoint(int(new_x), int(new_y))
            self.move(self._position)
            if self._companion_bubble and self._companion_bubble._is_showing:
                self._companion_bubble.update_position()
            self._chat_bubble.update_position()

        self.animation.update(dt, self.physics.vx)

        self._update_lean()

        if state == PetState.SITTING and self.animation.sit_finished:
            self.state_machine.transition_to(PetState.IDLE)

        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self.affection.add(itype='click')
            self._update_affection_tooltip()
            self._show_function_bubble(event.globalPosition().toPoint())
            self._reset_auto_home_timer()
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.affection.add(itype='click')
            self._update_affection_tooltip()
            self._drag_offset = event.pos()
            self.state_machine.on_mouse_press()
            self.physics.stop()
            self._reset_auto_home_timer()
            self._drag_positions = [(time.time(), event.globalPosition().toPoint().x())]
            self._shake_detected = False
            if self._lean_active:
                self._lean_active = False
                self.animation.set_animation(AnimationType.NONE)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.state_machine.is_dragged:
            global_pos = event.globalPosition().toPoint()
            new_pos = global_pos - self._drag_offset
            self._position = new_pos
            self.move(new_pos)
            if self._companion_bubble and self._companion_bubble._is_showing:
                self._companion_bubble.update_position()
            self._chat_bubble.update_position()
            now = time.time()
            self._drag_positions.append((now, global_pos.x()))
            cutoff = now - 0.5
            self._drag_positions = [(t, x) for t, x in self._drag_positions if t > cutoff]
            if len(self._drag_positions) >= 4:
                self._detect_shake()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state_machine.is_dragged:
                self.affection.add(itype='drag')

                if self._shake_detected:
                    self.animation.set_animation(AnimationType.DIZZY)
                    self._expression_active = True
                    center = self.geometry().center()
                    self._effects.add_stars(center.x(), center.y() - 30, count=6)
                    self._expression_end_timer.start(2200)
                    self._shake_detected = False
                else:
                    self._pending_bounce_land = True

            self._update_affection_tooltip()
            self._drag_positions = []

            if self._house and self._house.isVisible():
                sprite_cx = self.x() + self.width() // 2
                sprite_bottom = self.y() + self.height() // 2 + int(self._pet_pixmap.height() * self._scale) // 2
                sprite_pt = QPoint(sprite_cx, sprite_bottom)
                if self._house.is_door_overlap(sprite_pt):
                    self.hide()
                    self._house.set_pet_inside(True)
                    self.state_machine.transition_to(PetState.IDLE)
                    return

            grounded = (
                self._position.y()
                >= self.physics.screen.height() - self.physics.pet_height - 5
            )
            self.state_machine.on_mouse_release(grounded)
            if not grounded:
                self.physics.set_fall_velocity()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_scale(self._scale + 0.1)
        else:
            self.set_scale(self._scale - 0.1)
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Double-click: open AI chat if enabled, otherwise add affection."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._ai.is_available():
                self._chat_bubble.load_history(self._ai.get_history())
                self._chat_bubble.toggle()
                event.accept()
            else:
                self.affection.add(itype='click')
                self._update_affection_tooltip()
                self.state_machine.on_mouse_click()

    def contextMenuEvent(self, event):
        # Already handled in mousePressEvent; prevent double-fire
        event.accept()

    def _detect_shake(self):
        """Detect rapid left-right shaking during drag.

        Tracks the last 0.5s of drag positions (sampled by mouseMoveEvent)
        and counts direction reversals. 3+ reversals = shake detected,
        which triggers a dizzy animation on release.
        """
        if len(self._drag_positions) < 4:
            return
        reversals = 0
        prev_dx = 0
        for i in range(1, len(self._drag_positions)):
            dx = self._drag_positions[i][1] - self._drag_positions[i - 1][1]
            if prev_dx != 0 and dx != 0:
                if (dx > 0) != (prev_dx > 0):
                    reversals += 1
            prev_dx = dx
        if reversals >= 3:
            self._shake_detected = True

    def enterEvent(self, event):
        """Mouse entered pet area — start lean animation."""
        if not self.state_machine.is_dragged and not self._expression_active:
            self._mouse_in_proximity = True
            self._lean_active = True
            self.animation.set_animation(AnimationType.LEAN)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse left pet area — stop lean animation."""
        self._mouse_in_proximity = False
        if self._lean_active and not self._expression_active:
            self._lean_active = False
            self.animation.set_animation(AnimationType.IDLE)
        super().leaveEvent(event)

    def _update_lean(self):
        """Make pet lean toward the cursor when mouse is nearby.

        Lean strength scales with cursor distance from pet center,
        saturating at 150px. Suppressed during drag, expression, and walking.
        """
        if not self._lean_active or self.state_machine.is_dragged or self._expression_active:
            return
        if self.state_machine.current_state == PetState.WALKING:
            return
        cursor = QCursor.pos()
        pet_cx = self.x() + self.width() // 2
        dx = cursor.x() - pet_cx
        dist = abs(dx)
        strength = min(dist / 150.0, 1.0)  # max lean at 150px distance
        direction = 1 if dx > 0 else (-1 if dx < 0 else 0)
        self.animation.set_lean_params(direction, strength)

    def _show_function_bubble(self, global_pos):
        if self._bubble is None:
            self._bubble = PetFunctionBubble(mode="pet")
            self._bubble.zoom_in.connect(lambda: self.set_scale(self._scale + 0.1))
            self._bubble.zoom_out.connect(lambda: self.set_scale(self._scale - 0.1))
            cb_change = self._bubble_callbacks.get("change")
            if cb_change:
                self._bubble.change_pet.connect(cb_change)
            cb_show = self._bubble_callbacks.get("show_hide")
            if cb_show:
                self._bubble.toggle_visibility.connect(cb_show)
            else:
                self._bubble.toggle_visibility.connect(self.toggle_visibility)
            cb_exit = self._bubble_callbacks.get("exit")
            if cb_exit:
                self._bubble.exit_app.connect(cb_exit)
            self._bubble.go_home.connect(self._go_home)
            self._bubble.pomodoro_toggle.connect(self._toggle_pomodoro)
            self._bubble.feed_pet.connect(self._on_feed_pet)
            cb_main = self._bubble_callbacks.get("show_main_window")
            if cb_main:
                self._bubble.pomodoro_settings.connect(cb_main)

        self._bubble.set_pomodoro_active(self.settings.pomodoro_enabled)
        self._bubble.set_affection(self.affection.level)
        self._bubble.set_visibility_text(self.isVisible())
        period = self._current_time_period if self._time_awareness_enabled else None
        self._bubble.set_mood(period, self.affection.level)
        remaining = max(0, int(self._feed_cooldown_end - time.time()))
        self._bubble.set_feed_cooldown(remaining)
        if remaining > 0 and not self._feed_cooldown_timer.isActive():
            self._feed_cooldown_timer.start(1000)
        self._bubble.show_at(global_pos)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path and os.path.isfile(path):
                    self._delete_to_recycle_bin(path)

    def _delete_to_recycle_bin(self, file_path):
        try:
            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", ctypes.c_uint),
                    ("pFrom", ctypes.c_wchar_p),
                    ("pTo", ctypes.c_wchar_p),
                    ("fFlags", ctypes.c_ushort),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", ctypes.c_wchar_p),
                ]

            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x40
            FOF_NOCONFIRMATION = 0x10
            FOF_SILENT = 0x04
            FOF_NOERRORUI = 0x0400

            pFrom = file_path + "\0\0"
            shf = SHFILEOPSTRUCTW()
            shf.hwnd = int(self.winId())
            shf.wFunc = FO_DELETE
            shf.pFrom = pFrom
            shf.pTo = None
            shf.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
            shf.fAnyOperationsAborted = 0

            result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(shf))

            if result == 0 and not shf.fAnyOperationsAborted:
                self.state_machine.on_mouse_click()
                self.affection.add(itype='task_done')
                self._update_affection_tooltip()
                QToolTip.showText(
                    self.mapToGlobal(QPoint(20, -10)),
                    f"已删除到回收站 (+5好感)\n{os.path.basename(file_path)}"
                )
            else:
                raise OSError(f"SHFileOperationW returned {result}")
        except Exception as e:
            QToolTip.showText(
                self.mapToGlobal(QPoint(20, -10)),
                f"删除失败: {os.path.basename(file_path)}\n{str(e)[:80]}"
            )

    def _check_pomodoro(self):
        if not self.settings.pomodoro_enabled:
            return
        interval_seconds = self.settings.pomodoro_interval * 60
        if interval_seconds <= 0:
            return
        last = self.settings.pomodoro_last_fired
        now = time.time()
        if now - last >= interval_seconds:
            self._fire_pomodoro()

    def _fire_pomodoro(self):
        self.settings.pomodoro_last_fired = time.time()
        self.affection.add(itype='pomodoro')
        self._update_affection_tooltip()
        message = self.companion.on_pomodoro_end()
        notification = PomodoroNotificationBubble(
            self,
            title="⏰ 时间到！",
            subtitle=message
        )
        notification.show_near(self)
        self.state_machine.on_mouse_click()
        self._show_companion_bubble(message)
        self._reset_auto_home_timer()

    def _go_home(self):
        """Pet goes into the house."""
        self._show_go_home_popup()
        if self._house:
            self._house.set_pet_inside(True)
            self.hide()
        if self._bubble:
            self._bubble.hide()

    def _show_go_home_popup(self):
        """Show contextual popup when pet goes home."""
        go_home_config = {
            'time_pools': [
                (5, 9,  ["早安~回去补个觉", "天亮了，先回去休息~", "早安，回去准备早餐~"]),
                (9, 12, ["上午回去休息一下~", "先回去喝杯水~", "回去整理一下~"]),
                (12, 14,["午休时间~回去睡一会", "午饭时间~", "回去吃点东西~"]),
                (14, 18,["下午回去歇歇~", "先回去喝杯茶~", "回去休息一下~"]),
                (18, 21,["晚饭时间~先回去啦", "天黑了，回去休息~", "晚上回去放松一下~"]),
                (21, 5, ["晚安~回去睡觉啦", "夜深了，回去休息~", "今天辛苦啦，回去睡个好觉~"]),
            ],
            'weather_pools': {
                '雨': ["下雨了，回家躲雨~", "雨天回去听雨声~"],
                '雪': ["好冷，回家暖暖~", "下雪了，回去喝热可可~"],
                '热': ["太热了，回去吹空调~", "太阳好大，回去避暑~"],
                '晴': ["太热了，回去吹空调~", "太阳好大，回去避暑~"],
            },
            'affection_pools': [
                (80, ["好舍不得你~明天见！", "晚安，梦里见~💖", "今天也好开心！"]),
                (50, ["明天见~", "回去啦，想你~", "今天很开心！"]),
                (20, ["我先回去了~", "回去休息啦", "拜拜~"]),
                (0,  ["我先回去了。", "嗯，回去了。", "走了。"]),
            ],
            'extra_parts': [self._get_today_summary],
            'final_effect': self.trigger_sleep,
            'affection_effects': {},
        }
        self._compose_context_bubble(go_home_config)

    def _show_come_out_popup(self):
        """Show contextual popup when pet comes out of house."""
        come_out_config = {
            'time_pools': [
                (5, 9,  ["早安！新的一天~", "早上好！睡得好吗？", "早安~精神满满！"]),
                (9, 12, ["上午好！", "出来啦~", "今天也要加油！"]),
                (12, 14,["午安~", "下午好！", "午休结束！"]),
                (14, 18,["下午好~", "出来活动活动~", "下午茶时间？"]),
                (18, 21,["晚上好~", "天黑啦，出来逛逛~", "晚饭后散步？"]),
                (21, 5, ["夜猫子上线~", "晚上好~", "今晚月色真美~"]),
            ],
            'weather_pools': {
                '晴': ["今天天气真好！", "阳光明媚~适合出门！", "晴天！心情好好~"],
                '阴': ["多云，适合出门~", "阴天，凉快~", "天气不错~"],
                '雨': ["下雨了，小心地滑~", "雨天出门记得带伞~", "雨声好好听~"],
                '雪': ["下雪啦！好美~", "雪天出门注意保暖~", "白色世界~"],
                '热': ["好热啊~注意防晒", "高温预警！少出门~", "热化了~"],
                '冷': ["好冷~多穿点", "注意保暖哦~", "冷飕飕~"],
            },
            'affection_pools': [
                (80, ["好想你！💖", "终于见到你了~", "出来找你玩！"]),
                (50, ["出来啦~", "又见面了！", "想你了~"]),
                (20, ["出来了~", "嗯。", "你好~"]),
                (0,  ["...", "嗯。", "出来了。"]),
            ],
            'affection_effects': {
                80: lambda: self._effects.add_hearts(
                    self.geometry().center().x(), self.geometry().center().y() - 30, count=4),
                0: lambda: self._effects.add_sweat(
                    self.geometry().center().x(), self.geometry().center().y() - 30, count=2),
            },
            'extra_parts': [self._try_random_accessory],
            'sparkle_threshold': 60,
        }
        self._compose_context_bubble(come_out_config)

    def _compose_context_bubble(self, config):
        """Build and show a contextual popup from declarative config.

        config keys:
            time_pools: list of (start_hour, end_hour, [messages]) — last one is default
            weather_pools: dict weather_key -> [messages]
            affection_pools: list of (min_level, [messages]) — last one is default
            affection_effects: dict level -> callable (optional side effects)
            extra_parts: list of callables returning str (optional)
            final_effect: optional callable to run after bubble
            sparkle_threshold: if set, trigger sparkle burst when affection >= threshold
        """
        import random
        hour = time.localtime().tm_hour
        lv = self.affection.level

        time_msg = ""
        for start, end, pool in config['time_pools']:
            if (start <= hour < end) or (start > end and (hour >= start or hour < end)):
                time_msg = random.choice(pool)
                break

        weather_msg = ""
        try:
            weather = self._proactive.get_weather_status()
            pools = config.get('weather_pools', {})
            for keyword, pool in pools.items():
                if keyword in weather:
                    weather_msg = random.choice(pool)
                    break
        except Exception:
            pass

        affection_msg = ""
        affection_pools = config.get('affection_pools', [])
        effects = config.get('affection_effects', {})
        for min_lv, pool in affection_pools:
            if lv >= min_lv:
                affection_msg = random.choice(pool)
                if min_lv in effects:
                    effects[min_lv]()
                break

        parts = [time_msg]
        if weather_msg:
            parts.append(weather_msg)
        for getter in config.get('extra_parts', []):
            extra = getter()
            if extra:
                parts.append(extra)
        parts.append(affection_msg)
        self._show_companion_bubble("\n".join(parts))

        if 'final_effect' in config:
            config['final_effect']()
        threshold = config.get('sparkle_threshold')
        if threshold is not None and lv >= threshold:
            self.trigger_sparkle_burst()

    def _get_today_summary(self):
        """Get a brief summary of today's activities."""
        import json
        try:
            history_file = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
            if not os.path.exists(history_file):
                return ""
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            today = time.strftime("%Y-%m-%d")
            today_tasks = history.get(today, [])
            count = len(today_tasks)
            if count == 0:
                return ""
            total_seconds = sum(t.get('duration', 0) for t in today_tasks)
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            if hours > 0:
                time_str = f"{hours}小时{minutes}分钟"
            elif minutes > 0:
                time_str = f"{minutes}分钟"
            else:
                time_str = ""
            parts = [f"今天完成了{count}个任务 🎉"]
            if time_str:
                parts.append(f"一起学习了{time_str} ⏰")
            return "\n".join(parts)
        except Exception:
            return ""

    def _try_random_accessory(self):
        """Try to equip a random accessory. Returns description or None."""
        import random
        if not hasattr(self, '_accessory_layer') or not self._accessory_layer:
            return None
        try:
            accessories = [
                ("acc_hat", "戴了顶帽子~🎩"),
                ("acc_glasses", "戴上墨镜耍酷~🕶️"),
                ("acc_crown", "戴上小皇冠~👑"),
                ("acc_bow", "系了个蝴蝶结~🎀"),
            ]
            if random.random() < 0.4:
                choice = random.choice(accessories)
                if hasattr(self, '_accessory_brain') and self._accessory_brain:
                    acc_id = choice[0]
                    from .pet_accessories import Accessory, Anchor
                    acc = Accessory(
                        acc_id=acc_id,
                        anchor=Anchor.TOP,
                        scale=1.0,
                        offset=(0, -5),
                        duration=60,
                    )
                    self._accessory_layer.add_accessory(acc)
                return choice[1]
        except Exception:
            pass
        return None

    def _toggle_pomodoro(self):
        self.settings.pomodoro_enabled = not self.settings.pomodoro_enabled
        if self.settings.pomodoro_enabled:
            self.settings.pomodoro_last_fired = time.time()
            message = self.companion.on_pomodoro_start(self.settings.pomodoro_interval)
            self._show_companion_bubble(message)
        else:
            self.companion._work_state = self.companion._work_state.IDLE
        if self._bubble:
            self._bubble.set_pomodoro_active(self.settings.pomodoro_enabled)

    def _update_companion(self):
        """Update companion mood and show messages."""
        try:
            self.companion.update()
            now = time.time()

            if not self._proactive._greeted:
                self._proactive.on_startup()
            self._proactive.update()

            if self.companion._mood.name == "SLEEPY" and random.random() < 0.3:
                center = self.geometry().center()
                self._effects.add_zzz(center.x() + 30, center.y() - 40, count=2)

            if now - self._last_companion_message_time > random.randint(180, 360):
                message = self.companion.get_mood_message()
                if self.state_machine._state in (PetState.IDLE, PetState.SITTING):
                    if not self._bubble or not self._bubble.isVisible():
                        self._show_companion_bubble(message)
                        self._last_companion_message_time = now

            mood_emoji = self.companion.get_mood_emoji()
            status = self.companion.get_status_text()
            affection_text = self.affection.display_text
            weather = self._proactive.get_weather_status()
            self.setToolTip(f"{mood_emoji} ToYu · {status}\n{affection_text}\n天气: {weather}")
        except Exception:
            pass  # Don't crash on companion errors

    def _show_companion_bubble(self, message):
        """Show a speech bubble attached to pet."""
        if not message or not self.isVisible():
            return
        try:
            if not self._companion_bubble:
                from pet_engine.pet_bubble import CompanionBubble
                self._companion_bubble = CompanionBubble(self)
            self._companion_bubble.show_message(message, self)
        except Exception:
            self._companion_bubble = None  # Reset on error

    def _on_milestone_reached(self, title, emoji, desc):
        """Called when a new milestone is reached."""
        self.trigger_celebrate()
        msg = f"{emoji} {title}！\n{desc}"
        try:
            self._show_companion_bubble(msg)
        except Exception:
            pass

    def _on_ai_message(self, user_text: str):
        """Handle user chat message — send to AI and show response."""
        self.affection.add(itype='chat')
        self._update_affection_tooltip()

        time_map = {
            TimePeriod.MORNING: "早上", TimePeriod.DAY: "白天",
            TimePeriod.EVENING: "傍晚", TimePeriod.NIGHT: "深夜"
        }
        self._ai.inject_context(
            affection_level=self.affection.level,
            time_period=time_map.get(self._current_time_period, "白天"),
        )

        def on_response(ai_text: str):
            self._chat_bubble.clear_status()
            self._chat_bubble.show_response(ai_text)
            self._show_companion_bubble(ai_text)

        def on_error(err: str):
            self._chat_bubble.show_status(err)

        self._ai.chat(user_text, on_response=on_response, on_error=on_error)

    def on_user_interaction(self, interaction_type="pet"):
        """Called when user interacts with pet."""
        message = self.companion.on_interaction(interaction_type)
        self._show_companion_bubble(message)
        return message

    def on_task_complete(self):
        """Called when a todo task is completed."""
        self.affection.add(itype='task_done')
        self._update_affection_tooltip()
        message = self.companion.on_task_complete()
        self._show_companion_bubble(message)
        center = self.geometry().center()
        self._effects.add_stars(center.x(), center.y() - 30, count=8)
        self._reset_auto_home_timer()

    def _update_affection_tooltip(self):
        self.setToolTip(f"ToYu  {self.affection.display_text}")

    def moveEvent(self, event):
        super().moveEvent(event)
        self._update_overlay_positions()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay_positions()

    def _update_overlay_positions(self):
        g = self.geometry()
        if hasattr(self, '_accessory_layer') and self._accessory_layer and self._accessory_layer.isVisible():
            self._accessory_layer.update_geometry(
                g.x(), g.y(), g.width(), g.height())

    def start_accessory_brain(self, settings_manager):
        """Start the accessory intelligence system."""
        try:
            from pet_engine.accessory_brain import AccessoryBrain
            self._accessory_brain = AccessoryBrain(self, settings_manager)
            self._accessory_brain.start()
            print("[PetWindow] Accessory brain started")
        except Exception as e:
            print(f"[PetWindow] Failed to start accessory brain: {e}")

    def paintEvent(self, event):
        """Render the pet sprite with animation transforms.

        Transform order (QTransform applies right-to-left):
        1. Center the pixmap at origin
        2. Scale (with animation squash/stretch)
        3. Rotate
        4. Translate to window center + animation offset

        Night period: painter opacity reduced to 65% for a sleepy look.
        """
        if not self._pet_pixmap:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        anim = self.animation.state
        center_x = self.width() / 2
        center_y = self.height() / 2
        pix = self._pet_pixmap
        sw = pix.width() * self._scale
        sh = pix.height() * self._scale

        transform = QTransform()
        transform.translate(center_x + anim.offset_x, center_y + anim.offset_y)
        transform.rotate(anim.rotation)
        transform.scale(anim.scale_x * self._scale, anim.scale_y * self._scale)
        transform.translate(-sw / 2, -sh / 2)

        if self._time_awareness_enabled and self._current_time_period == TimePeriod.NIGHT:
            painter.setOpacity(0.65)

        painter.setTransform(transform)
        painter.drawPixmap(0, 0, int(sw), int(sh), pix)

        if self._time_awareness_enabled and self._current_time_period == TimePeriod.NIGHT:
            painter.setOpacity(1.0)

        painter.end()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
            if self._bubble:
                self._bubble.set_visibility_text(False)
        else:
            self.show()
            if self._bubble:
                self._bubble.set_visibility_text(True)

    def keyPressEvent(self, event):
        """Debug keys for testing expressions (disabled by default).
        Enable by setting _debug_keys = True on the pet window instance."""
        if not getattr(self, '_debug_keys', False):
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_1:
            self.trigger_dance(5.0)
        elif key == Qt.Key.Key_2:
            self.trigger_tired(6.0)
        elif key == Qt.Key.Key_3:
            self.trigger_sleep(8.0)
        elif key == Qt.Key.Key_4:
            self.trigger_celebrate(4.0)
        elif key == Qt.Key.Key_5:
            self.trigger_rain_mood(6.0)
        elif key == Qt.Key.Key_6:
            self.trigger_sparkle_burst()
        elif key == Qt.Key.Key_D:
            self._start_demo()
        elif key == Qt.Key.Key_7:
            self.add_hat()
        elif key == Qt.Key.Key_8:
            self.add_umbrella()
        elif key == Qt.Key.Key_9:
            self.add_icecream()
        elif key == Qt.Key.Key_0:
            self.clear_accessories()
        else:
            super().keyPressEvent(event)

    def _start_demo(self):
        """Cycle through all expressions for demo (press D)."""
        demos = [
            (0,    lambda: self._show_companion_bubble("\U0001F3B5 跳舞时间！")),
            (0.5,  lambda: self.trigger_dance(4.5)),
            (6,    lambda: self._show_companion_bubble("\U0001F634 好累啊...")),
            (6.5,  lambda: self.trigger_tired(5.0)),
            (12.5, lambda: self._show_companion_bubble("\U0001F4A4 打瞌睡了...")),
            (13,   lambda: self.trigger_sleep(7.0)),
            (21,   lambda: self._show_companion_bubble("\U0001F389 庆祝！")),
            (21.5, lambda: self.trigger_celebrate(3.5)),
            (26,   lambda: self._show_companion_bubble("\u2602\uFE0F 下雨天...")),
            (26.5, lambda: self.trigger_rain_mood(5.0)),
            (32.5, lambda: self._show_companion_bubble("\u2728 闪闪发光！")),
            (33,   lambda: self.trigger_sparkle_burst()),
            (36,   lambda: self._show_companion_bubble("\U0001F451 配件时间！")),
            (36.5, lambda: self.add_hat()),
            (40,   lambda: self.add_umbrella()),
            (44,   lambda: self.add_icecream()),
            (48,   lambda: self._show_companion_bubble("\u2728 演示完毕！")),
            (48.5, lambda: self.clear_accessories()),
        ]
        for delay, fn in demos:
            QTimer.singleShot(int(delay * 1000), fn)

    def closeEvent(self, event):
        self.settings.pet_position = self._position
        self._game_timer.stop()
        self._pomodoro_timer.stop()
        self._decay_timer.stop()
        self._feed_cooldown_timer.stop()
        self._time_check_timer.stop()
        self._expression_end_timer.stop()
        self._companion_update_timer.stop()
        if hasattr(self, '_accessory_brain') and self._accessory_brain:
            self._accessory_brain.stop()
        if self._chat_bubble:
            self._chat_bubble.close()
        if self._companion_bubble:
            self._companion_bubble.close()
        if self._bubble:
            self._bubble.close()
        if hasattr(self, '_effects') and self._effects:
            self._effects.close()
        if hasattr(self, '_accessory_layer') and self._accessory_layer:
            self._accessory_layer.close()
        self._auto_home_timer.stop()
        if hasattr(self, '_food_tracking_timer'):
            self._food_tracking_timer.stop()
        super().closeEvent(event)
