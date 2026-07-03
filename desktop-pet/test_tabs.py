import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from ui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication, QFrame, QLabel
app = QApplication(sys.argv)
w = MainWindow()

# Check features page (page 1)
w._page_btns['功能'].click()
page1 = w._page_stack.widget(1)
cards1 = page1.findChildren(QFrame)
print("=== Features Page ===")
for c in cards1:
    labels = c.findChildren(QLabel)
    texts = [l.text()[:30] for l in labels if l.text()]
    if texts:
        print(f'  Card: {texts[0]}')

# Check tools page (page 2)
w._page_btns['工具'].click()
page2 = w._page_stack.widget(2)
cards2 = page2.findChildren(QFrame)
print("\n=== Tools Page ===")
for c in cards2:
    labels = c.findChildren(QLabel)
    texts = [l.text()[:30] for l in labels if l.text()]
    if texts:
        print(f'  Card: {texts[0]}')

print('\nOK')
