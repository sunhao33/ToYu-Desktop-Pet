import sys, os, traceback
sys.path.insert(0, r'C:\Users\34338\Desktop\003\desktop-pet')
os.chdir(r'C:\Users\34338\Desktop\003\desktop-pet')

try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    from ui.settings_manager import SettingsManager
    from pet_engine.pet_window import PetWindow
    
    settings = SettingsManager()
    
    # Simulate _on_start_pet flow
    pet = PetWindow(settings)
    print("1. PetWindow created")
    
    pet.start_accessory_brain(settings)
    print("2. Accessory brain started")
    
    pet.set_pet_image(settings.pet_image_path or "")
    print("3. Pet image set")
    
    pet.set_scale(1.0)
    print("4. Scale set")
    
    pet.show()
    print("5. Pet shown")
    
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(3000, app.quit)
    sys.exit(app.exec())
except Exception as e:
    print(f"CRASH: {e}")
    traceback.print_exc()
