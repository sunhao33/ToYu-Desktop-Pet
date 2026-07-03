"""State machine for desktop pet behaviors.

State flow (autonomous, FREE mode only):
  IDLE ──timer──→ WALKING ──duration──→ IDLE
    │                 │
    │                 └── (hop_probability) ──→ HOPPING ──0.5s──→ IDLE
    └── (random action timer)

User-driven transitions:
  click ──→ INTERACTING ──0.4s──→ IDLE
  drag  ──→ DRAGGED ──release──→ IDLE (grounded) / FALLING (air)
  FALLING ──land──→ SITTING ──1s──→ IDLE

Time-of-day modifiers scale idle times and hop probability.
"""

import random
import time
from enum import Enum, auto


# ── Enums ────────────────────────────────────────────────────

class PetState(Enum):
    IDLE = auto()
    WALKING = auto()
    FALLING = auto()
    DRAGGED = auto()
    SITTING = auto()
    INTERACTING = auto()
    HOPPING = auto()


class InteractionMode(Enum):
    FREE = "free"
    FOLLOW = "follow"
    STAY = "stay"


class PetStateMachine:
    def __init__(self, settings):
        self.current_state = PetState.IDLE
        self.previous_state = PetState.IDLE
        self.settings = settings
        self._time_multiplier = 1.0
        self._hop_probability = 0.3
        self._idle_timer = 0.0
        self._walk_timer = 0.0
        self._hop_timer = 0.0
        self._next_action_time = self._random_idle_time()
        self._walk_duration = self._random_walk_duration()
        self._walk_direction = 1
        self._idle_start = time.time()
        self._interact_timer = 0.0
        self.interaction_mode = InteractionMode.FREE

    def set_time_period(self, period):
        """Adjust idle time and hop probability based on time of day.

        Night (2x idle): sleepy, rarely hops (5%)
        Morning (0.5x idle): energetic, hops often (50%)
        Evening (1.3x idle): winding down, moderate hops (20%)
        Afternoon (1x idle): default, moderate hops (30%)
        """
        period_val = period.value if hasattr(period, 'value') else str(period)
        if period_val == "night":
            self._time_multiplier = 2.0
            self._hop_probability = 0.05
        elif period_val == "morning":
            self._time_multiplier = 0.5
            self._hop_probability = 0.5
        elif period_val == "evening":
            self._time_multiplier = 1.3
            self._hop_probability = 0.2
        else:
            self._time_multiplier = 1.0
            self._hop_probability = 0.3

    def set_mode(self, mode: InteractionMode):
        self.interaction_mode = mode
        if mode == InteractionMode.STAY:
            self._next_action_time = float('inf')
        elif self.current_state == PetState.IDLE:
            self._next_action_time = time.time() + self._random_idle_time()

    def _random_idle_time(self):
        return random.uniform(
            self.settings.idle_time_min / 1000.0,
            self.settings.idle_time_max / 1000.0,
        ) * self._time_multiplier

    def _random_walk_duration(self):
        return random.uniform(2.0, 6.0)

    def _random_walk_speed(self):
        return random.uniform(
            self.settings.walking_speed_min,
            self.settings.walking_speed_max,
        )

    def transition_to(self, new_state: PetState):
        if new_state != self.current_state:
            self.previous_state = self.current_state
            self.current_state = new_state
            if new_state == PetState.IDLE:
                self._idle_start = time.time()
                if self.interaction_mode == InteractionMode.FREE:
                    self._next_action_time = time.time() + self._random_idle_time()
                else:
                    self._next_action_time = float('inf')
            elif new_state == PetState.WALKING:
                self._walk_timer = 0
                self._walk_duration = self._random_walk_duration()
                self._walk_direction = random.choice([-1, 1])
            elif new_state == PetState.HOPPING:
                self._hop_timer = 0

    def update(self, dt: float, grounded: bool) -> dict:
        """Tick the state machine every frame.

        Returns a command dict with keys:
          state: PetState — current state for animation
          walk_speed, walk_direction — movement params (0 when idle)

        Transition timings:
          INTERACTING → 0.4s → IDLE
          HOPPING     → 0.5s → IDLE
          FALLING     → land  → SITTING → 1.0s → IDLE
          WALKING     → 2-6s  → IDLE
        """
        state = self.current_state

        # Don't auto-transition from DRAGGED
        if state == PetState.DRAGGED:
            return {"state": state, "walk_speed": 0, "walk_direction": 0}

        # INTERACTING → IDLE after animation completes (~0.4s)
        if state == PetState.INTERACTING:
            self._interact_timer += dt
            if self._interact_timer >= 0.4:
                self._interact_timer = 0.0
                self.transition_to(PetState.IDLE)
                return {"state": PetState.IDLE, "walk_speed": 0, "walk_direction": 0}
            return {"state": state, "walk_speed": 0, "walk_direction": 0}

        # HOPPING → IDLE after hop animation completes
        if state == PetState.HOPPING:
            self._hop_timer += dt
            if self._hop_timer >= 0.5:
                self.transition_to(PetState.IDLE)
                return {"state": PetState.IDLE, "walk_speed": 0, "walk_direction": 0}
            return {"state": state, "walk_speed": 0, "walk_direction": 0}

        # FALLING → SITTING when grounded
        if state == PetState.FALLING:
            if grounded:
                self.transition_to(PetState.SITTING)
                return {"state": PetState.SITTING, "walk_speed": 0, "walk_direction": 0}
            return {"state": state, "walk_speed": 0, "walk_direction": 0}

        # SITTING → IDLE after brief pause
        if state == PetState.SITTING:
            if time.time() - self._idle_timer > 1.0:
                self.transition_to(PetState.IDLE)
                return {"state": PetState.IDLE, "walk_speed": 0, "walk_direction": 0}
            return {"state": state, "walk_speed": 0, "walk_direction": 0}

        # IDLE → random action when timer fires (FREE mode only)
        if state == PetState.IDLE:
            if self.interaction_mode == InteractionMode.FREE and time.time() >= self._next_action_time:
                if grounded and random.random() < self._hop_probability:
                    self.transition_to(PetState.HOPPING)
                    return {"state": PetState.HOPPING, "walk_speed": 0, "walk_direction": 0}
                else:
                    self.transition_to(PetState.WALKING)
                    return {
                        "state": PetState.WALKING,
                        "walk_speed": self._random_walk_speed(),
                        "walk_direction": self._walk_direction,
                    }
            return {"state": state, "walk_speed": 0, "walk_direction": 0}

        # WALKING → IDLE when duration expires
        if state == PetState.WALKING:
            self._walk_timer += dt
            if self._walk_timer >= self._walk_duration:
                self._idle_timer = time.time()
                self.transition_to(PetState.IDLE)
                return {"state": PetState.IDLE, "walk_speed": 0, "walk_direction": 0}
            return {
                "state": state,
                "walk_speed": self._random_walk_speed(),
                "walk_direction": self._walk_direction,
            }

        return {"state": state, "walk_speed": 0, "walk_direction": 0}

    def on_mouse_press(self):
        self.transition_to(PetState.DRAGGED)

    def on_mouse_release(self, grounded: bool):
        if grounded:
            self.transition_to(PetState.IDLE)
        else:
            self.transition_to(PetState.FALLING)

    def on_mouse_click(self):
        if self.current_state not in (PetState.DRAGGED, PetState.FALLING, PetState.SITTING):
            self.transition_to(PetState.INTERACTING)
            self._interact_timer = 0.0

    @property
    def is_dragged(self):
        return self.current_state == PetState.DRAGGED
