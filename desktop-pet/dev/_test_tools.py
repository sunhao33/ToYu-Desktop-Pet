"""Temporary verification for the desktop tools module (headless)."""

import json
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from ui.settings_manager import SettingsManager  # noqa: E402
from ui.tools import hub as hub_mod  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


# ── clipboard history ───────────────────────────────────────
s = SettingsManager()
s.clipboard_history = []
s.clipboard_enabled = True
clip = hub_mod.ClipboardHistory(s)

check("poll stores first item", clip.poll("hello world") and len(clip.history) == 1)
check("same text is ignored", not clip.poll("hello world"))
check("whitespace-only ignored", not clip.poll("   ") and len(clip.history) == 1)
check("second item goes to front", clip.poll("second") and clip.history[0]["text"] == "second")
check("duplicate bubbles to front", clip.poll("hello world") and clip.history[0]["text"] == "hello world")
check("history keeps 2 unique items", len(clip.history) == 2, str(len(clip.history)))
check("persisted through settings", SettingsManager().clipboard_history[0]["text"] == "hello world")

for i in range(120):
    clip.poll("bulk-%d" % i)
check("capped at MAX_HISTORY", len(clip.history) == hub_mod.MAX_HISTORY, str(len(clip.history)))
check("newest first after bulk", clip.history[0]["text"] == "bulk-119")

clip.set_enabled(False)
before = len(clip.history)
clip.poll("ignored while disabled")
check("disabled stops recording", len(clip.history) == before)
clip.set_enabled(True)

clip.clear()
check("clear empties history", clip.history == [])

# ── eye care ────────────────────────────────────────────────
events = []
s2 = SettingsManager()
s2.eye_care_deadline = 0.0
eye = hub_mod.EyeCareReminder(
    s2,
    on_rest=lambda minutes, count: events.append(("rest", minutes, count)),
    on_resume=lambda: events.append(("resume",)),
)
eye.work_minutes = 1
eye.rest_minutes = 1
eye.set_enabled(True)
eye._deadline = 0
eye.check_tick()
check("rest fires once", events == [("rest", 1, 1)], str(events))
check("resting flag", eye.resting is True)
eye._deadline = 0
eye.check_tick()
check("resume fires after rest", events == [("rest", 1, 1), ("resume",)], str(events))
check("work interval counted", eye.finished_work_intervals == 1)
check("deadline saved", s2.eye_care_deadline > 0)

eye.set_enabled(False)
eye.check_tick()
check("disabled never fires", len(events) == 2)
check("status text when off", eye.status_text() == "护眼提醒已关闭", eye.status_text())
eye.set_enabled(True)
check("status text shows countdown", "下次休息" in eye.status_text(), eye.status_text())

# ── data dir is writable and outside the bundle ─────────────
data_dir = hub_mod.get_data_dir()
check("data dir exists", os.path.isdir(data_dir), data_dir)
probe = os.path.join(data_dir, "_probe.json")
with open(probe, "w", encoding="utf-8") as fh:
    json.dump({"ok": True}, fh)
check("data dir writable", os.path.exists(probe))
os.remove(probe)

# ── hub end to end, driven through the real Qt clipboard ────
notices = []
h = hub_mod.DesktopToolsHub(s2, notify=lambda kind, t, b: notices.append((kind, t, b)))
seen = []
h.set_listeners(clipboard_cb=lambda hist: seen.append(len(hist)))
h.start()
QApplication.clipboard().setText("clipboard-e2e-1")
for _ in range(3):
    h._tick()
check("hub recorded real clipboard text", any(e["text"] == "clipboard-e2e-1" for e in h.clipboard.history))
check("hub notified listeners", seen and seen[-1] >= 1, str(seen))
check("hub running", h.running)
check("summary fields", set(h.summary()) == {"clipboard_enabled", "clipboard_count", "eye_care_enabled", "eye_care_status"})
h.flush()
h.stop()
check("hub stopped", not h.running)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    if status == "FAIL":
        fails += 1
    print("%-4s %-38s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
