"""Phased soak: add one subsystem at a time to find what grows memory."""

import gc
import os
import sys
import time
from datetime import datetime

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LOG_DIR = r"C:\Users\asus\Desktop\Huabei\_work"
LOG_PATH = os.path.join(LOG_DIR, "phased_%s.log" % datetime.now().strftime("%m%d_%H%M%S"))

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


def snapshot():
    gc.collect()
    return {
        "rss": PROC.memory_info().rss / 1024 / 1024,
        "objs": len(gc.get_objects()),
        "gc0": gc.get_count()[0],
        "widgets": len(app.allWidgets()),
        "threads": PROC.num_threads(),
    }


mw = MainWindow()
mw.show()
app.processEvents()
mw._on_start_pet()
app.processEvents()
pet = mw._pet
log("pet started: %s" % (pet is not None))

# 每个阶段跑 PHASE_SEC 秒，阶段之间对比 RSS 斜率
PHASE_SEC = 75
PHASES = [
    ("A 仅游戏循环", lambda: pet._game_tick()),
    ("B + 交互与好感", lambda: (pet._game_tick(), pet.on_user_interaction("pet")) if _ % 3 == 0 else pet._game_tick()),
    ("C + 提示气泡刷新", lambda: (pet._game_tick(), pet._update_companion()) if _ % 17 == 0 else pet._game_tick()),
    ("D + 粒子与表情", lambda: (pet._game_tick(), pet.trigger_sparkle_burst()) if _ % 43 == 0 else pet._game_tick()),
    ("E + 配件与气泡窗口", lambda: (pet._game_tick(), pet._try_random_accessory(), pet._show_companion_bubble("阶段测试")) if _ % 53 == 0 else pet._game_tick()),
    ("F + 桌面工具轮询", lambda: (pet._game_tick(), mw._tools_hub._tick(), mw._refresh_desktop_tools()) if _ % 61 == 0 else pet._game_tick()),
]

CYCLE = {"i": 0, "_": 0}


def driver():
    _ = CYCLE["i"]
    CYCLE["_"] = _
    try:
        CYCLE["fn"]()
    except Exception:
        pass
    CYCLE["i"] += 1


timer = QTimer()
timer.timeout.connect(driver)
timer.start(16)

STATE = {"phase": 0, "samples": [], "start": None}


def measure(tag):
    snap = snapshot()
    STATE["samples"].append((tag, snap))
    log("  %-22s rss=%7.1f MB  objs=%7d  gc0=%6d  widgets=%4d  threads=%2d"
        % (tag, snap["rss"], snap["objs"], snap["gc0"], snap["widgets"], snap["threads"]))
    return snap


def next_phase():
    if STATE["phase"] > 0:
        measure("阶段 %s 结束" % PHASES[STATE["phase"] - 1][0][:1])
    if STATE["phase"] >= len(PHASES):
        timer.stop()
        log("---- 汇总（每阶段 75 秒的 RSS 增长）----")
        for i in range(1, len(STATE["samples"]), 2):
            start = STATE["samples"][i - 1][1]["rss"]
            end = STATE["samples"][i][1]["rss"]
            name = STATE["samples"][i][0]
            log("  %-24s %+6.1f MB  (%.2f MB/min)" % (name, end - start, (end - start) / (PHASE_SEC / 60)))
        log("log: %s" % LOG_PATH)
        QTimer.singleShot(200, app.quit)
        return

    name, fn = PHASES[STATE["phase"]]
    CYCLE["fn"] = fn
    STATE["phase"] += 1
    log("阶段 %s 开始" % name)
    measure("阶段 %s 开始" % name[:1])
    QTimer.singleShot(PHASE_SEC * 1000, next_phase)


log("phased soak start, log %s" % LOG_PATH)
QTimer.singleShot(1000, next_phase)
app.exec()
log("done")
