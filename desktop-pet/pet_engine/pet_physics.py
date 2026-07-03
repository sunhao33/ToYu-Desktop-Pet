"""Simple physics for desktop pet — gravity, velocity, screen-edge collision.

Coordinate system: all positions are window top-left (Qt convention).
Physics works in logical pixels — DPI scaling is handled by Qt.

The ground level is calculated so the sprite's visible feet rest on the
taskbar's top edge (or screen bottom if no taskbar). This uses the
sprite_bottom_offset from visible-bounds detection to align precisely.
"""

from PyQt6.QtCore import QRect


# ── Constants ────────────────────────────────────────────────


class PetPhysics:
    """Frame-based physics with gravity, terminal velocity, and edge bouncing.

    Constants (per-frame values assuming ~60fps):
      GRAVITY          = 0.5  px/frame² — gentle fall acceleration
      TERMINAL_VELOCITY = 15.0 px/frame  — max fall speed
      BOUNCE_DAMPING   = 0.4            — energy retained on wall/ceiling bounce
      FRICTION         = 0.95           — horizontal velocity multiplier when grounded
    """

    GRAVITY = 0.5
    TERMINAL_VELOCITY = 15.0
    BOUNCE_DAMPING = 0.4
    FRICTION = 0.95

    def __init__(self, screen_geometry: QRect, pet_size: tuple,
                 taskbar_height: int = 0, sprite_bottom_offset: int = 0):
        self.screen = screen_geometry
        self.pet_width, self.pet_height = pet_size
        self.vx = 0.0
        self.vy = 0.0
        self.grounded = True
        self._taskbar_height = taskbar_height
        self._sprite_bottom_offset = sprite_bottom_offset
        self._ground_y = self._calc_ground_y()

    def _calc_ground_y(self):
        """Calculate ground Y for window top-left.
        
        We want the sprite's feet to be at the taskbar top edge.
        Sprite feet = window_top + sprite_bottom_in_window
        Window top = ground_y
        Sprite feet = ground_y + (window_height - sprite_bottom_offset)
        
        We want: sprite_feet = screen_bottom - taskbar_height
        So: ground_y = screen_bottom - taskbar_height - window_height + sprite_bottom_offset
        """
        return (
            self.screen.y()
            + self.screen.height()
            - self._taskbar_height
            - self.pet_height
            + self._sprite_bottom_offset
        )

    def update_screen(self, screen_geometry: QRect, taskbar_height: int = None):
        self.screen = screen_geometry
        if taskbar_height is not None:
            self._taskbar_height = taskbar_height
        self._ground_y = self._calc_ground_y()

    def update_pet_size(self, pet_size: tuple, sprite_bottom_offset: int = None):
        self.pet_width, self.pet_height = pet_size
        if sprite_bottom_offset is not None:
            self._sprite_bottom_offset = sprite_bottom_offset
        self._ground_y = self._calc_ground_y()

    def apply_gravity(self):
        if not self.grounded:
            self.vy = min(self.vy + self.GRAVITY, self.TERMINAL_VELOCITY)

    def step(self, x: float, y: float) -> tuple:
        """Advance physics one frame. Returns (new_x, new_y).

        Order: apply gravity → integrate velocity → resolve collisions.

        Collision resolution per edge:
          Left/Right: clamp position, reflect + dampen horizontal velocity
          Ceiling:    clamp position, reflect + dampen vertical velocity
          Ground:     clamp position, zero vertical velocity, set grounded flag
        """
        self.apply_gravity()

        new_x = x + self.vx
        new_y = y + self.vy

        # ── Screen bounds ──
        min_x = self.screen.x()
        max_x = self.screen.x() + self.screen.width() - self.pet_width
        min_y = self.screen.y()
        ground_y = self._ground_y

        # ── Left/right collision ──
        if new_x < min_x:
            new_x = min_x
            self.vx = abs(self.vx) * self.BOUNCE_DAMPING
        elif new_x > max_x:
            new_x = max_x
            self.vx = -abs(self.vx) * self.BOUNCE_DAMPING

        # ── Ceiling collision ──
        if new_y < min_y:
            new_y = min_y
            self.vy = abs(self.vy) * self.BOUNCE_DAMPING

        # ── Ground collision ──
        if new_y >= ground_y:
            new_y = ground_y
            self.vy = 0
            self.grounded = True
        else:
            # Only unground when moving downward (vy > 0)
            self.grounded = False if self.vy > 0 else self.grounded

        # ── Horizontal friction ──
        if self.grounded:
            self.vx *= self.FRICTION
            # Dead zone: stop micro-drift when nearly stationary
            if abs(self.vx) < 0.1:
                self.vx = 0

        return new_x, new_y

    def set_walk_velocity(self, vx: float):
        self.vx = vx
        self.vy = 0

    def set_fall_velocity(self, vy: float = 0):
        self.grounded = False
        self.vy = vy

    def set_jump_velocity(self, vy: float = -12):
        """Set upward velocity for jumping."""
        self.grounded = False
        self.vy = vy

    def stop(self):
        self.vx = 0
        self.vy = 0
