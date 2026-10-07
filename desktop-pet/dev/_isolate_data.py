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

# 2.5) QSettings -> 临时 INI 文件
#
#     这是**之前漏掉的一处**，而且影响很大：QSettings("DesktopPet",
#      "DesktopPet") 默认写 Windows 注册表，而上面 HOME / APPDATA 的
#      重定向只影响文件路径，管不到注册表。于是每个跑测试的脚本都会
#      读写**用户的真实设置** —— 深色模式、每日动画缩放、宠物图片路径、
#      收藏夹、番茄钟开关全在里面。
#
#      实际踩过的坑：
#        · 截图脚本把 animation_scale 改成 1.6，用户下次启动宠物变大
#        · 默认深色模式的脚本循环跑，真实设置被反复切换
#        · 测试断言"初始深色为 False / 目标未设置"，一旦被污染就失败，
#          而且失败原因看起来像是代码 bug
#
#     为什么不用 QSettings.setDefaultFormat / setPath：
#     实测无效 —— 代码里显式写了 QSettings("DesktopPet", "DesktopPet")，
#     带参数的构造会走 NativeFormat，setDefaultFormat 管不到；
#     setPath 也只在未显式传组织名时生效。所以改成**拦截构造本身**：
#     把 QSettings(...) 换成指向临时目录的 INI 文件。
try:
    from PyQt6.QtCore import QSettings as _QS

    _REAL_QS_INIT = _QS.__init__
    _INI_PATH = os.path.join(_TMP, "settings.ini")

    def _isolated_init(self, *args, **kwargs):
        # 保留调用方传的组织名/应用名（代码里可能后面还会读），
        # 但把存储格式与位置强行换成临时 INI
        kwargs.pop("format", None)
        _REAL_QS_INIT(self, _INI_PATH, _QS.Format.IniFormat)

    _QS.__init__ = _isolated_init
except Exception as _exc:      # noqa: BLE001
    print("[isolate] QSettings 拦截失败（测试可能污染真实设置）:", _exc)

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
print("[isolate] QSettings 已重定向到", _INI_PATH)
