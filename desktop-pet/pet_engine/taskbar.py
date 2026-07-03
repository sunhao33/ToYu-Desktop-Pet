"""Detect taskbar position using Qt's built-in geometry (DPI-aware)."""

from PyQt6.QtWidgets import QApplication

def get_taskbar_info():
    """Get taskbar info using Qt's screen geometry (automatically DPI-aware).
    
    Returns dict with height, position ('bottom'/'top'/'left'/'right').
    """
    screen = QApplication.primaryScreen()
    if not screen:
        return None
    
    full = screen.geometry()
    avail = screen.availableGeometry()
    
    if avail.y() > full.y():
        return {
            'height': avail.y() - full.y(),
            'position': 'top',
            'top_edge': full.y(),
            'bottom_edge': avail.y(),
        }
    elif avail.y() + avail.height() < full.y() + full.height():
        taskbar_h = (full.y() + full.height()) - (avail.y() + avail.height())
        return {
            'height': taskbar_h,
            'position': 'bottom',
            'top_edge': avail.y() + avail.height(),
            'bottom_edge': full.y() + full.height(),
        }
    elif avail.x() > full.x():
        return {
            'height': avail.x() - full.x(),
            'position': 'left',
        }
    elif avail.x() + avail.width() < full.x() + full.width():
        taskbar_w = (full.x() + full.width()) - (avail.x() + avail.width())
        return {
            'height': taskbar_w,
            'position': 'right',
        }
    
    return None

def get_taskbar_height():
    """Return taskbar height in logical pixels, or 0."""
    info = get_taskbar_info()
    return info['height'] if info else 0
