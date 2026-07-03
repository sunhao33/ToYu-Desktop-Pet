"""Programmatic animation system for single-image desktop pet."""

import math
import time
import random
from enum import Enum

class AnimationType(Enum):
    IDLE = "idle"
    WALK = "walk"
    FALL = "fall"
    SIT = "sit"
    INTERACT = "interact"
    HOP = "hop"
    NONE = "none"
    DANCE = "dance"
    TIRED = "tired"
    SLEEP = "sleep"
    CELEBRATE = "celebrate"
    BOUNCE_LAND = "bounce_land"   # squash-stretch on landing after drag
    LEAN = "lean"                 # tilt toward mouse cursor (proximity)
    DIZZY = "dizzy"               # wobble after rapid shake

class AnimationState:
    def __init__(self):
        self.start_time = time.time()
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.rotation = 0.0
        self.offset_y = 0.0
        self.offset_x = 0.0

    def reset(self):
        self.start_time = time.time()
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.rotation = 0.0
        self.offset_y = 0.0
        self.offset_x = 0.0

class PetAnimation:
    def __init__(self, sprite_is_sheet=False, sheet_frames=1, sheet_columns=1):
        self.current_type = AnimationType.IDLE
        self.state = AnimationState()
        self._sprite_is_sheet = sprite_is_sheet
        self._sheet_frames = sheet_frames
        self._sheet_columns = sheet_columns
        self._current_frame = 0
        self._frame_timer = 0.0

        self._blink_timer = 0.0
        self._blink_interval = random.uniform(3.0, 7.0)
        self._blinking = False
        self._blink_start = 0.0
        self._wiggle_phase = random.uniform(0, 2 * math.pi)
        self._idle_time = 0.0  # total time spent idle

    def set_animation(self, anim_type: AnimationType):
        if self.current_type != anim_type:
            self.current_type = anim_type
            self.state.reset()
            if anim_type == AnimationType.IDLE:
                self._idle_time = 0.0
                self._schedule_next_blink()
            elif anim_type == AnimationType.HOP:
                self.state.start_time = time.time()

    def _schedule_next_blink(self):
        self._blink_timer = 0.0
        self._blink_interval = random.uniform(3.0, 7.0)
        self._blinking = False

    def update(self, dt: float, velocity_x: float = 0):
        """Update animation transforms. Returns self."""
        elapsed = time.time() - self.state.start_time
        s = self.state

        if self.current_type == AnimationType.IDLE:
            self._idle_time += dt

            breath_speed = 1.8 if self._idle_time < 30 else 1.0  # slower when sleepy
            breath_amplitude = 0.03 if self._idle_time < 30 else 0.02
            breath = math.sin(elapsed * breath_speed) * breath_amplitude
            s.scale_x = 1.0 + breath
            s.scale_y = 1.0 + breath
            s.rotation = math.sin(elapsed * 1.2 + self._wiggle_phase) * 1.0
            s.offset_y = math.sin(elapsed * breath_speed) * 1.5
            s.offset_x = 0

            self._blink_timer += dt
            if not self._blinking and self._blink_timer >= self._blink_interval:
                self._blinking = True
                self._blink_start = elapsed
                self._blink_timer = 0.0
                self._blink_interval = random.uniform(3.0, 7.0)

            if self._blinking:
                blink_elapsed = elapsed - self._blink_start
                blink_duration = 0.15
                if blink_elapsed < blink_duration:
                    t = blink_elapsed / blink_duration
                    squint = math.sin(t * math.pi) * 0.6
                    s.scale_y = s.scale_y * (1.0 - squint)
                    s.scale_x = s.scale_x * (1.0 + squint * 0.3)
                else:
                    self._blinking = False

            wiggle_interval = 15.0
            wiggle_elapsed = elapsed % wiggle_interval
            if wiggle_elapsed < 0.5:
                t = wiggle_elapsed / 0.5
                s.rotation += math.sin(t * math.pi * 4) * 4 * (1 - t)
                s.offset_x = math.sin(t * math.pi * 3) * 3 * (1 - t)

            if self._idle_time > 30:
                droop = min((self._idle_time - 30) / 10.0, 1.0) * 0.04
                s.scale_y -= droop
                s.offset_y += droop * 60

        elif self.current_type == AnimationType.WALK:
            direction = 1 if velocity_x >= 0 else -1
            speed = abs(velocity_x)
            bob = abs(math.sin(elapsed * 8.0)) * 3 * min(speed / 2.0, 1.0)
            s.rotation = direction * math.sin(elapsed * 8.0) * 5 * min(speed / 2.0, 1.0)
            s.scale_x = 1.0
            s.scale_y = 1.0 - bob * 0.02
            s.offset_y = bob
            s.offset_x = 0

        elif self.current_type == AnimationType.FALL:
            s.rotation = math.sin(elapsed * 3.0) * 8
            s.scale_x = 1.0 + math.sin(elapsed * 6.0) * 0.03
            s.scale_y = 1.0 - math.sin(elapsed * 6.0) * 0.05
            s.offset_y = 0
            s.offset_x = 0

        elif self.current_type == AnimationType.SIT:
            progress = min(elapsed / 0.3, 1.0)
            s.scale_x = 1.0 + progress * 0.08
            s.scale_y = 1.0 - progress * 0.12
            s.offset_y = progress * 8
            s.rotation = 0
            s.offset_x = 0

        elif self.current_type == AnimationType.INTERACT:
            duration = 0.3
            progress = min(elapsed / duration, 1.0)

            if progress < 0.5:
                t = progress * 2
                scale = 1.0 + t * 0.15
            else:
                t = (progress - 0.5) * 2
                overshoot = math.sin(t * math.pi) * 0.03 * (1 - t)
                scale = 1.15 - t * 0.15 + overshoot

            s.scale_x = scale
            s.scale_y = scale
            s.rotation = math.sin(elapsed * 20) * 3 * (1 - progress)
            s.offset_y = -math.sin(progress * math.pi) * 5
            s.offset_x = 0

            if progress >= 1.0:
                self.current_type = AnimationType.IDLE
                self.state.reset()
                self._schedule_next_blink()

        elif self.current_type == AnimationType.HOP:
            duration = 0.5
            progress = min(elapsed / duration, 1.0)

            if progress < 0.3:
                t = progress / 0.3
                s.scale_x = 1.0 + t * 0.1
                s.scale_y = 1.0 - t * 0.15
                s.offset_y = t * 5
            elif progress < 0.6:
                t = (progress - 0.3) / 0.3
                s.scale_x = 1.1 - t * 0.05
                s.scale_y = 0.85 + t * 0.15
                s.offset_y = 5 - t * 25
            else:
                t = (progress - 0.6) / 0.4
                landing = math.sin((1 - t) * math.pi) * 0.05
                s.scale_x = 1.05 + landing
                s.scale_y = 1.0 - landing
                s.offset_y = -20 * (1 - t) * (1 - t)

            s.rotation = math.sin(elapsed * 12) * 3 * (1 - progress)

            if progress >= 1.0:
                self.current_type = AnimationType.IDLE
                self.state.reset()
                self._schedule_next_blink()

        elif self.current_type == AnimationType.NONE:
            s.scale_x = 1.0
            s.scale_y = 1.0
            s.rotation = 0
            s.offset_y = 0
            s.offset_x = 0

        elif self.current_type == AnimationType.DANCE:
            s.offset_y = abs(math.sin(elapsed * 6.0)) * -15
            s.offset_x = math.sin(elapsed * 3.0) * 8
            s.rotation = math.sin(elapsed * 4.0) * 12
            bounce = math.sin(elapsed * 6.0) * 0.08
            s.scale_x = 1.0 + bounce
            s.scale_y = 1.0 - bounce * 0.5

        elif self.current_type == AnimationType.TIRED:
            s.rotation = math.sin(elapsed * 0.8) * 15
            s.offset_x = math.sin(elapsed * 0.5) * 5
            droop = min(elapsed / 5.0, 1.0) * 0.06
            s.scale_y = 1.0 - droop
            s.scale_x = 1.0 + droop * 0.3
            s.offset_y = droop * 40

        elif self.current_type == AnimationType.SLEEP:
            s.offset_y = min(elapsed * 0.5, 10)
            breath = math.sin(elapsed * 0.8) * 0.02
            s.scale_x = 1.0 + breath
            s.scale_y = 1.0 + breath
            s.rotation = math.sin(elapsed * 0.3) * 3
            s.offset_x = 0

        elif self.current_type == AnimationType.CELEBRATE:
            s.offset_y = abs(math.sin(elapsed * 10.0)) * -20
            s.rotation = math.sin(elapsed * 8.0) * 15
            pop = math.sin(elapsed * 10.0) * 0.1
            s.scale_x = 1.0 + pop
            s.scale_y = 1.0 - pop
            s.offset_x = math.sin(elapsed * 5.0) * 5

        elif self.current_type == AnimationType.BOUNCE_LAND:
            duration = 0.6
            progress = min(elapsed / duration, 1.0)
            if progress < 0.12:
                t = progress / 0.12
                s.scale_x = 1.0 + t * 0.35
                s.scale_y = 1.0 - t * 0.4
                s.offset_y = t * 18
            elif progress < 0.35:
                t = (progress - 0.12) / 0.23
                s.scale_x = 1.35 - t * 0.4
                s.scale_y = 0.6 + t * 0.55
                s.offset_y = 18 - t * 35
            elif progress < 0.6:
                t = (progress - 0.35) / 0.25
                bounce = math.sin(t * math.pi) * 0.08
                s.scale_x = 0.95 + bounce + t * 0.05
                s.scale_y = 1.15 - bounce - t * 0.15
                s.offset_y = -17 * (1 - t)
            elif progress < 0.8:
                t = (progress - 0.6) / 0.2
                s.scale_x = 1.0 + (1 - t) * 0.02
                s.scale_y = 1.0 - (1 - t) * 0.02
                s.offset_y = 0
            else:
                s.scale_x = 1.0
                s.scale_y = 1.0
                s.offset_y = 0
            s.rotation = math.sin(elapsed * 18) * 6 * (1 - progress)
            s.offset_x = 0
            if progress >= 1.0:
                self.current_type = AnimationType.IDLE
                self.state.reset()
                self._schedule_next_blink()

        elif self.current_type == AnimationType.LEAN:
            direction = getattr(self, '_lean_dir', 0)
            strength = getattr(self, '_lean_strength', 0.0)
            target_rot = direction * 8.0 * strength
            target_offset_x = direction * 4.0 * strength
            s.rotation += (target_rot - s.rotation) * 0.1
            s.offset_x += (target_offset_x - s.offset_x) * 0.1
            s.offset_y = math.sin(elapsed * 2.0) * 2.0 * strength
            pulse = math.sin(elapsed * 2.5) * 0.015 * strength
            s.scale_x = 1.0 + pulse
            s.scale_y = 1.0 - pulse * 0.5

        elif self.current_type == AnimationType.DIZZY:
            wobble_speed = max(3.0, 10.0 - elapsed * 2.0)
            wobble_amp = max(0.5, 8.0 - elapsed * 3.0)
            s.rotation = math.sin(elapsed * wobble_speed) * wobble_amp
            s.offset_x = math.sin(elapsed * wobble_speed * 0.7) * wobble_amp * 0.5
            pulse = math.sin(elapsed * 6.0) * 0.03
            s.scale_x = 1.0 + pulse
            s.scale_y = 1.0 - pulse
            s.offset_y = 0
            if elapsed > 2.0:
                self.current_type = AnimationType.IDLE
                self.state.reset()
                self._schedule_next_blink()

        if self._sprite_is_sheet:
            self._frame_timer += dt
            if self._frame_timer >= 0.1:
                self._frame_timer = 0
                self._current_frame = (self._current_frame + 1) % self._sheet_frames

        return self

    @property
    def sprite_frame(self):
        return self._current_frame if self._sprite_is_sheet else 0

    @property
    def sprite_column(self):
        return self._current_frame % self._sheet_columns

    @property
    def sprite_row(self):
        return self._current_frame // self._sheet_columns

    @property
    def interact_finished(self):
        return self.current_type == AnimationType.IDLE

    @property
    def sit_finished(self):
        elapsed = time.time() - self.state.start_time
        return elapsed >= 0.3

    @property
    def hop_finished(self):
        return self.current_type == AnimationType.IDLE

    def set_lean_params(self, direction: int, strength: float):
        """Set lean direction (-1 left, +1 right, 0 center) and strength (0-1)."""
        self._lean_dir = direction
        self._lean_strength = max(0.0, min(1.0, strength))
