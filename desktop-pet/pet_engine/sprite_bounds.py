"""Detect actual visible bounds of a pet sprite (ignoring transparent pixels)."""

from PyQt6.QtGui import QPixmap, QImage


# ── Visible Bounds Detection ─────────────────────────────────


def get_visible_bounds(pixmap: QPixmap) -> tuple:
    """Scan pet pixmap and return (top, bottom, left, right) of actual visible pixels.
    
    Returns offsets relative to the pixmap edges:
    - top: distance from top edge to first visible row
    - bottom: distance from bottom edge to last visible row  
    - left: distance from left edge to first visible column
    - right: distance from right edge to last visible column
    
    Returns (0, 0, 0, 0) if pixmap is null or fully transparent.
    """
    if pixmap.isNull():
        return (0, 0, 0, 0)
    
    img = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    
    if w == 0 or h == 0:
        return (0, 0, 0, 0)
    
    # Scan for first/last visible row
    top_visible = h
    bottom_visible = -1
    
    for y in range(h):
        row_has_pixel = False
        ptr = img.constScan(y)
        # Scan this row for any non-transparent pixel
        for x in range(w):
            pixel = img.pixelColor(x, y)
            if pixel.alpha() > 20:  # threshold: ignore near-transparent
                row_has_pixel = True
                break
        if row_has_pixel:
            if y < top_visible:
                top_visible = y
            if y > bottom_visible:
                bottom_visible = y
    
    if bottom_visible < 0:
        return (0, 0, 0, 0)
    
    # Scan for first/last visible column
    left_visible = w
    right_visible = -1
    
    for x in range(w):
        col_has_pixel = False
        for y in range(top_visible, bottom_visible + 1):
            pixel = img.pixelColor(x, y)
            if pixel.alpha() > 20:
                col_has_pixel = True
                break
        if col_has_pixel:
            if x < left_visible:
                left_visible = x
            if x > right_visible:
                right_visible = x
    
    if right_visible < 0:
        return (0, 0, 0, 0)
    
    return (
        top_visible,           # pixels from top edge to first visible row
        h - 1 - bottom_visible, # pixels from bottom edge to last visible row
        left_visible,           # pixels from left edge to first visible col
        w - 1 - right_visible   # pixels from right edge to last visible col
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


# Shared layout constants for the pet window
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
