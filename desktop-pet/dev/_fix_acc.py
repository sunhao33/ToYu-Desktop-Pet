import os, sys

path = r'C:\Users\34338\Desktop\003\desktop-pet\pet_engine\pet_window.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# After physics init, calculate sprite_bottom_offset immediately
old_after_physics = """        self._sprite_bottom_offset = 0  # will be calculated after first render
        self.physics = PetPhysics(
            full_screen,
            (self.width(), self.height()),
            taskbar_height=taskbar['height'] if taskbar else 0,
            sprite_bottom_offset=0
        )"""

new_after_physics = """        # Calculate sprite bottom offset: distance from sprite feet to window bottom
        margin = 10
        avail_h = self.height() - margin * 2
        sprite_cy_in_window = margin + avail_h // 2
        sprite_h = int(self._pet_pixmap.height() * self._scale) if self._pet_pixmap else 75
        sprite_bottom_in_window = sprite_cy_in_window + sprite_h // 2
        self._sprite_bottom_offset = self.height() - sprite_bottom_in_window
        
        self.physics = PetPhysics(
            full_screen,
            (self.width(), self.height()),
            taskbar_height=taskbar['height'] if taskbar else 0,
            sprite_bottom_offset=self._sprite_bottom_offset
        )"""

content = content.replace(old_after_physics, new_after_physics)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK - sprite offset calculated at init')
