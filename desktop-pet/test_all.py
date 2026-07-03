import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from ui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
w = MainWindow()

# Check favorites
fav = w.settings.favorites
print(f'Favorites: {len(fav)}')
for f in fav:
    name = f.get('name', '?')
    path = f.get('path', '?')[-40:]
    print(f'  {name} -> {path}')

# Check pet path
pp = w.settings.pet_image_path
print(f'Pet path: ...{pp[-40:]}')

# Start pet
w._on_start_pet()
time.sleep(1)
pet = w._pet
print(f'Pet: {pet.size().width()}x{pet.size().height()}')
print(f'Mood: {pet.companion._mood.name}')
print(f'Affection: {pet.affection.level} / {pet.affection.display_text}')
print(f'Main window: {w.size().width()}x{w.size().height()}')

# Test particles
center = pet.geometry().center()
pet._effects.add_hearts(center.x(), center.y() - 30, count=3)
print(f'Particles after hearts: {len(pet._effects.particles)}')

# Check all 3 pages
for name, btn in w._page_btns.items():
    btn.click()
    idx = w._page_stack.currentIndex()
    print(f'Tab [{name}] -> page {idx}')

print('\nALL TESTS PASSED')
