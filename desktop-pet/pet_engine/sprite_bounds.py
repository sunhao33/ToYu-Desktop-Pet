"""Detect actual visible bounds of a pet sprite (ignoring transparent pixels)."""

import numpy as np
from PyQt6.QtGui import QPixmap, QImage

def _alpha_mask(pixmap: QPixmap):
    """Return the alpha channel as an owned 2D uint8 array, or None if unusable.

    注意：必须在这里就把数据拷出来。numpy 若直接引用 QImage 的缓冲区，
    那个 QImage 是临时对象，函数返回后随时可能被回收 —— 之后访问就是野指针
    （表现为偶发 access violation，图越大越容易崩）。
    """
    if pixmap.isNull():
        return None

    img = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    if w == 0 or h == 0:
        return None

    ptr = img.constBits()
    if hasattr(ptr, "setsize"):
        ptr.setsize(img.sizeInBytes())
    # ARGB32 在小端机器上字节序为 B,G,R,A；每行按 bytesPerLine 对齐，需按行切片
    buf = np.frombuffer(ptr, dtype=np.uint8)
    padded = buf.reshape(h, img.bytesPerLine())[:, : w * 4].reshape(h, w, 4)
    return np.ascontiguousarray(padded[:, :, 3])


def get_visible_bounds(pixmap: QPixmap) -> tuple:
    """Scan pet pixmap and return (top, bottom, left, right) of actual visible pixels.

    Returns offsets relative to the pixmap edges:
    - top: distance from top edge to first visible row
    - bottom: distance from bottom edge to last visible row
    - left: distance from left edge to first visible column
    - right: distance from right edge to last visible column

    Returns (0, 0, 0, 0) if pixmap is null or fully transparent.
    """
    alpha = _alpha_mask(pixmap)
    if alpha is None:
        return (0, 0, 0, 0)

    h, w = alpha.shape
    visible = alpha > 20  # threshold: ignore near-transparent
    rows = np.flatnonzero(visible.any(axis=1))
    if rows.size == 0:
        return (0, 0, 0, 0)
    cols = np.flatnonzero(visible.any(axis=0))
    if cols.size == 0:
        return (0, 0, 0, 0)

    top_visible = int(rows[0])
    bottom_visible = int(rows[-1])
    left_visible = int(cols[0])
    right_visible = int(cols[-1])

    return (
        top_visible,            # pixels from top edge to first visible row
        h - 1 - bottom_visible,  # pixels from bottom edge to last visible row
        left_visible,           # pixels from left edge to first visible col
        w - 1 - right_visible,  # pixels from right edge to last visible col
    )

def get_content_rect(pixmap: QPixmap) -> tuple:
    """Return (x, y, width, height) of the actual visible content area."""
    if pixmap.isNull():
        return (0, 0, 0, 0)
    
    w, h = pixmap.width(), pixmap.height()
    top, bottom, left, right = get_visible_bounds(pixmap)
    
    cx = left
    cy = top
    cw = w - left - right
    ch = h - top - bottom
    
    return (cx, cy, cw, ch)

def get_content_ratio(pixmap: QPixmap) -> dict:
    """Return visible content as ratios (0.0-1.0) relative to full pixmap.
    
    Useful for positioning accessories relative to actual content.
    Example: {'top': 0.15, 'bottom': 0.05, 'left': 0.1, 'right': 0.1}
    means content starts 15% from top, 5% from bottom, etc.
    """
    if pixmap.isNull():
        return {'top': 0.0, 'bottom': 0.0, 'left': 0.0, 'right': 0.0}
    
    w, h = pixmap.width(), pixmap.height()
    top, bottom, left, right = get_visible_bounds(pixmap)
    
    return {
        'top': top / h if h > 0 else 0.0,
        'bottom': bottom / h if h > 0 else 0.0,
        'left': left / w if w > 0 else 0.0,
        'right': right / w if w > 0 else 0.0,
    }

_PET_PADDING = 60
_PET_SCALE_FACTOR = 1.6

def get_sprite_frame_size(pet_geometry):
    """Return the sprite pixel dimensions and position from pet window geometry.

    The pet sprite is centered in the window with PET_PADDING total padding,
    scaled by PET_SCALE_FACTOR. This is used by bubble positioning to align
    speech bubbles with the pet's head.

    Returns dict with keys: sprite_h, sprite_top, sprite_w, sprite_left
    """
    geo = pet_geometry
    sprite_h = (geo.height() - _PET_PADDING) / _PET_SCALE_FACTOR
    sprite_w = (geo.width() - _PET_PADDING) / _PET_SCALE_FACTOR
    sprite_top = geo.y() + (geo.height() - sprite_h) / 2
    sprite_left = geo.x() + (geo.width() - sprite_w) / 2
    return {
        'sprite_h': sprite_h,
        'sprite_top': sprite_top,
        'sprite_w': sprite_w,
        'sprite_left': sprite_left,
    }
