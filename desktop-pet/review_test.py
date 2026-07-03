import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from ui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
app = QApplication(sys.argv)
w = MainWindow()

print("=== MAIN WINDOW ===")
print(f"Size: {w.size().width()}x{w.size().height()}")
print(f"Title: {w.windowTitle()}")
print(f"Min: {w.minimumSize().width()}x{w.minimumSize().height()}")

print("\n=== PAGE STACK ===")
print(f"Pages: {w._page_stack.count()}")
for i in range(w._page_stack.count()):
    widget = w._page_stack.widget(i)
    print(f"  Page {i}: {widget.__class__.__name__}")

print("\n=== TAB BUTTONS ===")
for name, btn in w._page_btns.items():
    print(f"  [{name}] checked={btn.isChecked()}")

print("\n=== FAVORITES POLLUTION ===")
fav = w.settings.favorites
temp_count = sum(1 for f in fav if '_MEI' in f.get('path', ''))
print(f"Total favorites: {len(fav)}")
print(f"Temp paths (PyInstaller leftovers): {temp_count}")
real_count = len(fav) - temp_count
print(f"Real paths: {real_count}")

print("\n=== BEAD CREATIONS ===")
beads = w.settings.bead_creations
print(f"Total: {len(beads)}")
for b in beads:
    print(f"  {b.get('name','?')} -> {b.get('path','?')[-50:]}")

print("\n=== PET IMAGE PATH ===")
pet_path = w.settings.pet_image_path
print(f"Path: {pet_path}")
if pet_path:
    print(f"Exists: {os.path.exists(pet_path)}")
    # Check if path has repeated _pet suffix
    basename = os.path.basename(pet_path)
    if '_pet' in basename:
        count = basename.count('_pet')
        print(f"WARNING: '_pet' suffix repeated {count} times in filename!")

print("\n=== LABELS (visible) ===")
labels = w.findChildren(QLabel)
for l in labels:
    t = l.text()
    if t and l.isVisible():
        print(f"  [{t[:60]}]")

print("\n=== VISIBLE BUTTONS ===")
for b in w.findChildren(QPushButton):
    if b.isVisible():
        print(f"  [{b.text()}] enabled={b.isEnabled()}")

print("\n=== START PET ===")
w._on_start_pet()
import time
time.sleep(1)
pet = w._pet
print(f"Pet: {pet.size().width()}x{pet.size().height()}")
print(f"Pet pos: {pet.pos()}")
print(f"Mood: {pet.companion._mood.name}")
# Check pet attributes
for attr in ['_walk_speed', '_idle_timer', '_physics']:
    if hasattr(pet, attr):
        val = getattr(pet, attr)
        if callable(val):
            print(f"{attr}: {val()}")
        else:
            print(f"{attr}: {val}")
    else:
        print(f"{attr}: MISSING")

print("\n=== BUBBLE ===")
bubble = pet._function_bubble
print(f"Bubble class: {bubble.__class__.__name__}")
print(f"Bubble visible: {bubble.isVisible()}")

print("\n=== COMPANION BUBBLE ===")
cbubble = pet._companion_bubble
print(f"Class: {cbubble.__class__.__name__}")
print(f"Visible: {cbubble.isVisible()}")

print("\n=== HOUSE ===")
house = w._house
print(f"House: {house.size().width()}x{house.size().height()}")
print(f"House pos: {house.pos()}")
print(f"Pet inside: {house._pet_inside if hasattr(house, '_pet_inside') else 'N/A'}")

print("\n=== EFFECTS ===")
effects = pet._effects
print(f"Class: {effects.__class__.__name__}")
print(f"Particles: {len(effects.particles)}")

print("\n=== SETTINGS ===")
s = w.settings
print(f"Dark mode: {s.dark_mode}")
print(f"Scale: {s.animation_scale}")
print(f"Pomodoro: {s.pomodoro_enabled}, interval={s.pomodoro_interval}")
print(f"Time awareness: {s.time_awareness_enabled}")
print(f"House: {s.house_enabled}")
print(f"Affection: {s.affection_level}")

print("\n=== TODO DATA ===")
todo_path = os.path.expanduser("~/.desktop_pet/todos.json")
if os.path.exists(todo_path):
    with open(todo_path, 'r', encoding='utf-8') as f:
        todos = json.load(f)
    done = sum(1 for t in todos if t.get('done'))
    print(f"Total: {len(todos)}, Done: {done}, Open: {len(todos)-done}")

print("\n=== SCREEN ===")
screen = app.primaryScreen().availableGeometry()
print(f"Available: {screen.width()}x{screen.height()}")

print("\nDONE")
