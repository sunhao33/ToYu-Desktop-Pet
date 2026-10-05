"""Memory leak hunter: tracemalloc snapshots + gc type census while exercising the app."""

import gc
import os
import sys
import time
import tracemalloc
from datetime import datetime

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG_DIR = r"C:\Users\asus\Desktop\Huabei\_work"
LOG_PATH = os.path.join(LOG_DIR, "leak_%s.log" % datetime.now().strftime("%m%d_%H%M%S"))

import psutil  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import main as toyu_main  # noqa: E402

toyu_main._install_crash_guard()

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

LOG = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
PROC = psutil.Process()


def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    LOG.write(line + "\n")


mw = MainWindow()
mw.show()
app.processEvents()
mw._on_start_pet()
app.processEvents()
mw._init_tools_hub()
mw._tools_hub.start()
pet = mw._pet
log("pet started: %s" % (pet is not None))

CYCLE = {"i": 0}


def exercise():
    """与 _soak.py 相同的负载，用于复现增长。"""
    i = CYCLE["i"]
    CYCLE["i"] += 1
    try:
        pet._game_tick()
        pet.on_user_interaction("pet")
        if i % 7 == 0:
            pet.affection.add(1, "click")
        if i % 11 == 0:
            pet.companion.update()
        if i % 13 == 0:
            pet._proactive.update()
        if i % 17 == 0:
            pet._on_time_check()
        if i % 19 == 0:
            pet._update_companion()
        if i % 23 == 0:
            pet._update_sprite_bounds()
        if i % 29 == 0:
            pet._check_pomodoro()
        if i % 31 == 0:
            pet._try_random_accessory()
        if i % 37 == 0:
            pet.trigger_sparkle_burst()
        if i % 41 == 0:
            pet.trigger_dance(1.0)
        if i % 47 == 0:
            pet.trigger_celebrate(1.0)
        if i % 53 == 0:
            pet._show_companion_bubble("泄漏定位中 %d" % i)
        if i % 59 == 0:
            mw._tools_hub._tick()
        if i % 61 == 0:
            mw._refresh_desktop_tools()
        if i % 67 == 0:
            mw._pulse_status()
        if i % 71 == 0:
            pet.toggle_visibility()
            pet.toggle_visibility()
    except Exception:
        pass


timer = QTimer()
timer.timeout.connect(exercise)
timer.start(16)

TYPE_BASELINE = {}


def type_census():
    counts = {}
    for obj in gc.get_objects():
        name = type(obj).__name__
        counts[name] = counts.get(name, 0) + 1
    return counts


def diff_types(before, after, top=15):
    delta = {k: after.get(k, 0) - before.get(k, 0) for k in set(before) | set(after)}
    return sorted(delta.items(), key=lambda kv: -kv[1])[:top]


STATE = {}


def phase_start():
    gc.collect()
    tracemalloc.start(25)
    STATE["snap1"] = tracemalloc.take_snapshot()
    STATE["types1"] = type_census()
    STATE["rss1"] = PROC.memory_info().rss / 1024 / 1024
    STATE["t1"] = time.time()
    log("采样开始 rss=%.1f MB pyobjs=%d" % (STATE["rss1"], len(gc.get_objects())))


def phase_end():
    STATE["snap2"] = tracemalloc.take_snapshot()
    STATE["types2"] = type_census()
    rss2 = PROC.memory_info().rss / 1024 / 1024
    minutes = (time.time() - STATE["t1"]) / 60
    log("采样结束 rss=%.1f MB pyobjs=%d  (%.1f 分钟, RSS %+.1f MB)"
        % (rss2, len(gc.get_objects()), minutes, rss2 - STATE["rss1"]))

    log("---- Python 对象增长 Top 15 ----")
    for name, delta in diff_types(STATE["types1"], STATE["types2"]):
        if delta > 0:
            log("  %+7d  %s" % (delta, name))

    log("---- tracemalloc 归属行 Top 12 ----")
    stats = STATE["snap2"].compare_to(STATE["snap1"], "lineno")
    for stat in stats[:12]:
        frame = stat.traceback[0]
        log("  %+9.1f KB  %s:%d  (%d blocks)"
            % (stat.size_diff / 1024, os.path.basename(frame.filename), frame.lineno,
               stat.count_diff))

    tracemalloc.stop()
    log("log: %s" % LOG_PATH)
    QTimer.singleShot(300, app.quit)


QTimer.singleShot(20 * 1000, phase_start)
QTimer.singleShot(20 * 1000 + 240 * 1000, phase_end)
log("leak hunter start, 采样 4 分钟, log %s" % LOG_PATH)
app.exec()
log("done")
