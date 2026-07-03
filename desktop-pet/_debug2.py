import sys
sys.path.insert(0, r'C:\Users\34338\Desktop\003\desktop-pet')
from PyQt6.QtWidgets import QApplication
from pet_engine.pet_window import PetWindow
from ui.settings_manager import SettingsManager

app = QApplication(sys.argv)
settings = SettingsManager()
pet = PetWindow(settings)

print(f'Window size: {pet.width()}x{pet.height()}')
print(f'Window pos: {pet.pos()}')
print(f'Physics ground_y: {pet.physics._ground_y}')
print(f'Physics screen: {pet.physics.screen}')
print(f'Taskbar info: {getattr(pet, "_taskbar_info", "N/A")}')
print(f'Sprite offset: {getattr(pet, "_sprite_bottom_offset", "N/A")}')

# Where would the window bottom be at ground?
win_bottom = pet.physics._ground_y + pet.height()
taskbar_top = pet.physics.screen.y() + pet.physics.screen.height() - pet.physics._taskbar_height
print(f'Window bottom at ground: {win_bottom}')
print(f'Taskbar top: {taskbar_top}')
print(f'Sprite feet at ground: {pet.physics._ground_y + pet.height() - getattr(pet, "_sprite_bottom_offset", 0)}')
