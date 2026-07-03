import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from ui.todo_widget import TodoWidget
tw = TodoWidget()
attrs = [a for a in dir(tw) if 'input' in a.lower() or 'add' in a.lower() or 'line' in a.lower()]
print('TodoWidget input attrs:', attrs)

from ui.timer_widget import TimerWidget
tw2 = TimerWidget()
attrs2 = [a for a in dir(tw2) if 'set' in a.lower() or 'time' in a.lower() or 'hour' in a.lower() or 'min' in a.lower()]
print('TimerWidget time attrs:', attrs2)

from ui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
mw = MainWindow()
feed_attrs = [a for a in dir(mw) if 'feed' in a.lower()]
print('MainWindow feed attrs:', feed_attrs)
