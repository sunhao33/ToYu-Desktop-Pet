import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from ui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
w = MainWindow()
w.show()
time.sleep(1)

# Tab 1: Pet
w._page_btns['宠物'].click()
app.processEvents()
time.sleep(0.5)
w.grab().save('tab1_pet.png')
print('Tab 1 saved')

# Tab 2: Features
w._page_btns['功能'].click()
app.processEvents()
time.sleep(0.5)
w.grab().save('tab2_features.png')
print('Tab 2 saved')

# Tab 3: Tools
w._page_btns['工具'].click()
app.processEvents()
time.sleep(0.5)
w.grab().save('tab3_tools.png')
print('Tab 3 saved')

print('DONE')
