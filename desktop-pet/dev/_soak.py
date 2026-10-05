"""Soak test: keep the pet fully exercised for a long time and watch for leaks/crashes.

Runs headless (offscreen) so it can churn for tens of minutes while printing a
memory / thread / timer / object-count timeline.

Usage:  python _soak.py [minutes]
Log:    <workspace>/_work/soak_<stamp>.log
"""

import os
import sys
import time
import traceback
from datetime import datetime

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
LOG_DIR = r"C:\Users\asus\Desktop\Huabei\_work"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "soak_%s.log" % datetime.now().strftime("%m%d_%H%M%S"))

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import psutil  # noqa: E402

# 同时装上产品里的崩溃防护，这样即使槽函数抛异常也不会中断浸泡（并会记进 errors.log）
import main as toyu_main  # noqa: E402

toyu_main._install_crash_guard()

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

LOG = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
PROC = psutil.Process()
ERROR_LOG = toyu_main.LOG_PATH


def error_log_size():
    try:
        return os.path.getsize(ERROR_LOG)
    except OSError:
        return 0


def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg)
    print(line)
    LOG.write(line + "\n")


STATE = {"errors": 0, "start": time.time()}


def rss_mb():
    return PROC.memory_info().rss / 1024 / 1024


def thread_count():
    return PROC.num_threads()


def object_census():
    import gc
    from PyQt6.QtCore import QObject, QTimer as QT

    gc.collect()
    timers = 0
    for obj in app.allWidgets():
        timers += len(obj.findChildren(QT))
    return {
        "widgets": len(app.allWidgets()),
        "top_level": len([w for w in app.topLevelWidgets() if w.isVisible()]),
        "timers_in_widgets": timers,
        "qobjects": len(app.findChildren(QObject)),
        "pyobjs": len(gc.get_objects()),
    }


# ── 启动宠物 ────────────────────────────────────────────────
mw = MainWindow()
mw.show()
app.processEvents()

pet = None
try:
    mw._on_start_pet()
    app.processEvents()
    pet = mw._pet
    log("pet started: %s" % (pet is not None))
except Exception:
    log("pet start FAILED:\n" + traceback.format_exc())

mw._init_tools_hub()
mw._tools_hub.start()

if pet is not None:
    try:
        pet.start_accessory_brain(mw.settings)
        log("accessory brain started")
    except Exception:
        log("accessory brain FAILED:\n" + traceback.format_exc())

baseline = {
    "rss": rss_mb(),
    "threads": thread_count(),
    "objects": object_census(),
}
log("baseline: rss=%.1f MB threads=%d %s" % (baseline["rss"], baseline["threads"], baseline["objects"]))

# ── 制造负载 ────────────────────────────────────────────────
CYCLE = {"i": 0}


def exercise():
    """Drive everything a user would touch, on repeat."""
    if pet is None:
        return
    i = CYCLE["i"]
    CYCLE["i"] += 1
    try:
        pet._game_tick()

        if i % 3 == 0:
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
        if i % 43 == 0:
            pet.trigger_tired(1.0)
        if i % 47 == 0:
            pet.trigger_celebrate(1.0)
        if i % 53 == 0:
            pet._show_companion_bubble("浸泡测试中～ 第 %d 次" % i)
        if i % 59 == 0:
            mw._tools_hub._tick()
        if i % 61 == 0:
            mw._refresh_desktop_tools()
        if i % 67 == 0:
            mw._pulse_status()
        if i % 71 == 0:
            pet._game_tick()
            pet.toggle_visibility()
            pet.toggle_visibility()
    except Exception:
        STATE["errors"] += 1
        log("EXERCISE ERROR #%d:\n%s" % (STATE["errors"], traceback.format_exc()))


driver = QTimer()
driver.timeout.connect(exercise)
driver.start(16)  # 每秒约 60 次调度

report = QTimer()
SAMPLES = []


def do_report():
    elapsed = (time.time() - STATE["start"]) / 60
    cur = {"t": elapsed, "rss": rss_mb(), "threads": thread_count(), **object_census()}
    SAMPLES.append(cur)
    log("t=%5.2f min  rss=%7.1f MB (+%6.1f)  threads=%2d  widgets=%4d  pyobjs=%6d  qobjects=%5d  errors=%d  errlog=%d"
        % (cur["t"], cur["rss"], cur["rss"] - baseline["rss"], cur["threads"],
           cur["widgets"], cur["pyobjs"], cur["qobjects"], STATE["errors"], error_log_size()))


report.timeout.connect(do_report)
report.start(60 * 1000)


def finish():
    driver.stop()
    report.stop()
    log("---- final report ----")
    if SAMPLES:
        first, last = SAMPLES[0], SAMPLES[-1]
        span = max(last["t"] - first["t"], 1e-6)
        log("rss: %.1f -> %.1f MB  (%.2f MB/min)"
            % (first["rss"], last["rss"], (last["rss"] - first["rss"]) / span))
        log("threads: %d -> %d" % (first["threads"], last["threads"]))
        log("widgets: %d -> %d" % (first["widgets"], last["widgets"]))
        log("qobjects: %d -> %d" % (first["qobjects"], last["qobjects"]))
        growth = [s["rss"] for s in SAMPLES]
        if len(growth) > 6:
            head = sum(growth[:3]) / 3
            tail = sum(growth[-3:]) / 3
            log("late-stage growth: %.2f MB per sample (head %.1f -> tail %.1f)"
                % ((tail - head) / max(len(SAMPLES) - 3, 1), head, tail))
    log("exercise errors total: %d" % STATE["errors"])
    log("done, log at %s" % LOG_PATH)
    if pet:
        try:
            pet.close()
        except Exception:
            pass
    QTimer.singleShot(300, app.quit)


QTimer.singleShot(int(MINUTES * 60 * 1000), finish)

log("soak started, %.1f minutes, log %s" % (MINUTES, LOG_PATH))
app.exec()
