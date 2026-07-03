import sys
import os
import traceback

try:
    sys.path.insert(0, r'C:\Users\34338\Desktop\003\desktop-pet')
    os.chdir(r'C:\Users\34338\Desktop\003\desktop-pet')
    
    import ctypes
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ToYu.DesktopPet")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon("resources/toyu_icon.ico"))
    
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    print("MainWindow shown OK")
    
    # Run for a few seconds then exit
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(3000, app.quit)
    sys.exit(app.exec())
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
