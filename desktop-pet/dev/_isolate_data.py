"""把数据目录指向临时目录，避免测试/截图脚本污染真实用户数据。

用法（在 import 业务模块**之前**）：
    import _isolate_data  # noqa: F401

背景：这个项目的数据分散在三处 ——
    ~/.desktop_pet/（待办、任务历史、屏幕会话、图片）
    %APPDATA%\\ToYu/（设置、计时、专注日志、报告）
    Windows 注册表 HKCU\\Software\\DesktopPet（QSettings）
脚本如果不隔离就会往真实文件里写测试数据，导致后续测试
（依赖"待办条数""学习时长"这类断言）莫名失败 —— 已经踩过多次。
"""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="toyu_isolated_")

# 1) ~/.desktop_pet -> 临时目录
os.environ["HOME"] = _TMP              # 部分代码用 expanduser("~")
_real_expanduser = os.path.expanduser


def _expanduser(path):
    # matplotlib 等库会传 Path 而不是 str，统一转字符串再判断，
    # 返回类型与传入类型保持一致
    is_path = hasattr(path, "__fspath__") and not isinstance(path, str)
    s = os.fspath(path)
    if s == "~":
        out = _TMP
    elif s.startswith("~" + os.sep) or s.startswith("~/"):
        out = os.path.join(_TMP, s[2:])
    else:
        out = _real_expanduser(s)
    return type(path)(out) if is_path else out


os.path.expanduser = _expanduser

# 2) %APPDATA%\\ToYu -> 临时目录（代码里既有 os.environ 读取，
#    也有硬编码的 Roaming 拼接，所以两处都要覆盖）
os.environ["APPDATA"] = _TMP

# 3) 已导入的模块里若有模块级路径常量，尝试重定向
for mod_name in ("ui.screen_time_tracker", "ui.todo_widget",
                 "pet_engine.focus_log", "pet_engine.report"):
    try:
        mod = __import__(mod_name, fromlist=["_"])
    except Exception:      # noqa: BLE001
        continue
    for attr in ("DATA_DIR", "HISTORY_FILE", "LOG_FILE", "REPORT_DIR",
                 "APP_DIR", "FLOW_TIMER_FILE"):
        if hasattr(mod, attr):
            old = getattr(mod, attr)
            if isinstance(old, str) and ("ToYu" in old or ".desktop_pet" in old):
                new = os.path.join(_TMP, os.path.basename(old))
                setattr(mod, attr, new)

print("[isolate] 数据目录已重定向到", _TMP)
