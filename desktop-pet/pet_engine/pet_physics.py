"""Simple physics for desktop pet — gravity, velocity, screen-edge collision.

Coordinate system: all positions are window top-left (Qt convention).
Physics works in logical pixels — DPI scaling is handled by Qt.

The ground level is calculated so the sprite's visible feet rest on the
taskbar's top edge (or screen bottom if no taskbar). This uses the
sprite_bottom_offset from visible-bounds detection to align precisely.
"""

from PyQt6.QtCore import QRect

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
                 taskbar_height: int = 0, sprite_bottom_offset: int = 0,
                 sprite_left_offset: int = 0, sprite_right_offset: int = 0):
        self.screen = screen_geometry
        self.pet_width, self.pet_height = pet_size
        self.vx = 0.0
        self.vy = 0.0
        self.grounded = True
        self._taskbar_height = taskbar_height
        self._sprite_bottom_offset = sprite_bottom_offset
        # 窗口两侧的空白（像素）。窗口比可见的宠物宽 —— sprite 是居中画在
        # 窗口里的，实测窗口 220px 宽、sprite 可见范围只有 160px，两侧各
        # 30px。原来水平边界按**窗口**算，于是宠物走到屏幕边时视觉上永远
        # 差这 30px 就停住，看着像"没走到边"。
        self._sprite_left_offset = sprite_left_offset
        self._sprite_right_offset = sprite_right_offset
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

    def update_sprite_horizontal_offsets(self, left: int = None, right: int = None):
        """更新窗口两侧的空白量（换宠物图或改缩放后都要重算）。"""
        if left is not None:
            self._sprite_left_offset = left
        if right is not None:
            self._sprite_right_offset = right

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

        # 水平边界按**可见 sprite** 算，不是按窗口算。
        # 窗口左右各有 sprite_left/right_offset 的空白，扣掉之后宠物的
        # 可见边缘才真的能贴到屏幕边（实测原来是差 30px 停住）。
        # 注意 offset 不能超过窗口宽的一半，否则 min_x > max_x 会让宠物
        # 卡在错误位置，所以先夹一下。
        half_w = self.pet_width / 2.0
        left_off = max(0, min(self._sprite_left_offset, half_w))
        right_off = max(0, min(self._sprite_right_offset, half_w))
        min_x = self.screen.x() - left_off
        max_x = (self.screen.x() + self.screen.width()
                 - self.pet_width + right_off)
        if max_x < min_x:               # 极窄屏兜底，避免反向区间
            min_x = max_x = self.screen.x()
        min_y = self.screen.y()
        ground_y = self._ground_y

        if new_x < min_x:
            new_x = min_x
            self.vx = abs(self.vx) * self.BOUNCE_DAMPING
        elif new_x > max_x:
            new_x = max_x
            self.vx = -abs(self.vx) * self.BOUNCE_DAMPING

        if new_y < min_y:
            new_y = min_y
            self.vy = abs(self.vy) * self.BOUNCE_DAMPING

        if new_y >= ground_y:
            new_y = ground_y
            self.vy = 0
            self.grounded = True
        else:
            # Only unground when moving downward (vy > 0)
            self.grounded = False if self.vy > 0 else self.grounded

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
