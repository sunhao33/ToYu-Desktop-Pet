import sys
sys.stdout.reconfigure(encoding='utf-8')
from PyQt6.QtWidgets import QApplication, QScrollArea
from PyQt6.QtCore import QTimer
sys.path.insert(0, '.')
from ui.main_window import MainWindow

app = QApplication(sys.argv)
w = MainWindow()
w.resize(720, 900)
w.show()

def scroll_and_shot():
    for child in w.findChildren(QScrollArea):
        vbar = child.verticalScrollBar()
        vbar.setValue(vbar.maximum())
    QTimer.singleShot(300, shot)

def shot():
    screen = app.primaryScreen()
    p = screen.grabWindow(w.winId())
    p.save('auto_home_test.png')
    print('Done')
    app.quit()

QTimer.singleShot(500, scroll_and_shot)
app.exec()
