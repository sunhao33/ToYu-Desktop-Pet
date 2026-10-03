"""Package ToYu into ToYu_v<版本>.zip。

包内结构：
  根目录：      ToYu.exe + _internal/      ← onedir 版，双击即用（不会被杀软拦）
               changelog.txt
               README.txt                 ← 安装包使用说明（含杀软注意事项）
  onefile/      ToYu_单文件版.exe           ← 免安装单文件（部分杀软会拦解压，备用）
  desktop-pet/  完整源码

为什么主推 onedir：单文件 exe 每次启动都要把自己解压到 %TEMP%\_MEIxxxx，
火绒/Defender 的实时防护会偶发拦截这个解压目录，报
"Could not create temporary directory!" 而启动失败。onedir 版不解压，实测 8/8 稳定。

路径按脚本自身位置推导，换机器/换目录不用改；版本号从 changelog.txt 读取。
"""

import os
import re
import shutil
import zipfile

PET_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PET_DIR)
DIST_ONEFILE = os.path.join(PET_DIR, "dist", "ToYu.exe")
DIST_ONEDIR = os.path.join(PET_DIR, "dist_dir", "ToYu")
CHANGELOG_PATH = os.path.join(PET_DIR, "changelog.txt")
STAGING = os.path.join(PET_DIR, "_staging")

EXCLUDE_DIRS = {"dist", "dist_dir", "build", "build_dir", "build_debug", "__pycache__",
                ".git", ".claude", "_staging"}
EXCLUDE_EXTS = {".zip", ".pyc", ".log"}
SKIP_SCRIPTS = {
    "_package.py", "_test_tools.py", "_smoke_real.py", "_debug2.py",
    "_debug_launch.py", "_check_methods.py", "_fix_acc.py", "_path_matrix.py",
    "_reliability.py", "_stress_exe.py", "_test_crash.py", "_test_pet.py",
    "_test_run.py", "main_window.py.bak", "_ToYuDebug.spec",
    # 稳定性测试与截图工具（开发期使用，不进发布包）
    "_test_all.py", "_test_crash_guard.py", "_test_sprite_bounds.py",
    "_soak.py", "_soak_phased.py", "_shots_render.py",
}

README = r"""ToYu 桌面土豆宠物 — 使用说明
================================

【怎么启动】
双击本文件夹里的 ToYu.exe 即可，不需要安装。

【为什么有这么多文件】
ToYu.exe 旁边的 _internal 文件夹是程序运行库，请勿删除或改名，
它和 exe 必须放在同一个文件夹里。

【如果启动没反应 / 弹出 could not create temporary directory】
这是杀毒软件（火绒、360、Defender 等）拦截了程序启动造成的，不是程序本身的问题。
三种解决办法，任选一种：
  1. 把整个文件夹加入杀毒软件的「信任区 / 白名单」；
  2. 改用 onefile 文件夹里的 ToYu_单文件版.exe（已加入白名单时更省事）；
  3. 右键 ToYu.exe → 以管理员身份运行。
单文件版每次启动都要把自己解压到系统临时目录，被杀软扫描时更容易被拦，
所以正式演示建议用当前这个文件夹版。

【首次使用】
1. 启动后桌面上会出现小土豆宠物，屏幕上还会有一个控制面板；
2. 面板 → 宠物页：选择图片、显示/隐藏、收藏夹切换宠物；
3. 面板 → 工具页：待办、倒计时、剪贴板历史、护眼提醒；
4. 面板 → AI 页：填入 DeepSeek 或任意 OpenAI 兼容接口的 API Key 才能聊天；
5. 双击宠物打开聊天框；右键宠物打开功能气泡（喂食、回家、番茄钟等）。

【数据保存位置】
设置存在注册表 HKCU\\Software\\DesktopPet\\DesktopPet；
剪贴板历史、聊天记录等存在 %APPDATA%\\ToYu。

【版本】
本包版本见 changelog.txt 第一行。
"""


def read_version():
    with open(CHANGELOG_PATH, encoding="utf-8") as fh:
        for line in fh:
            # 支持 x.y 与 x.y.z（补丁号）
            match = re.match(r"\s*v(\d+\.\d+(?:\.\d+)*)", line)
            if match:
                return match.group(1)
    raise RuntimeError("changelog.txt 里找不到版本号")


def copy_tree(src, dst):
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns(*EXCLUDE_DIRS, "*.pyc", "*.zip", "*.log"),
    )


def main():
    version = read_version()
    zip_path = os.path.join(PROJECT_ROOT, f"ToYu_v{version}.zip")

    have_onedir = os.path.isdir(DIST_ONEDIR) and os.path.exists(os.path.join(DIST_ONEDIR, "ToYu.exe"))
    have_onefile = os.path.exists(DIST_ONEFILE)
    if not have_onedir and not have_onefile:
        raise SystemExit("缺少构建产物：先跑\n"
                         "  python -m PyInstaller ToYuDir.spec --noconfirm --distpath dist_dir --workpath build_dir\n"
                         "  python -m PyInstaller ToYu.spec --noconfirm")

    if os.path.exists(STAGING):
        shutil.rmtree(STAGING)
    os.makedirs(STAGING)

    shutil.copy2(CHANGELOG_PATH, os.path.join(STAGING, "changelog.txt"))
    with open(os.path.join(STAGING, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write(README)

    if have_onedir:
        app_dst = os.path.join(STAGING, "ToYu")
        os.makedirs(app_dst)
        for name in os.listdir(DIST_ONEDIR):
            src = os.path.join(DIST_ONEDIR, name)
            dst = os.path.join(app_dst, name)
            if os.path.isdir(src):
                copy_tree(src, dst)
            else:
                shutil.copy2(src, dst)

    if have_onefile:
        single = os.path.join(STAGING, "onefile")
        os.makedirs(single)
        shutil.copy2(DIST_ONEFILE, os.path.join(single, "ToYu_单文件版.exe"))

    src_root = os.path.join(STAGING, "desktop-pet")
    os.makedirs(src_root)
    for item in sorted(os.listdir(PET_DIR)):
        if item in EXCLUDE_DIRS or item in SKIP_SCRIPTS:
            continue
        if os.path.splitext(item)[1] in EXCLUDE_EXTS:
            continue
        src = os.path.join(PET_DIR, item)
        dst = os.path.join(src_root, item)
        if os.path.isdir(src):
            copy_tree(src, dst)
        else:
            shutil.copy2(src, dst)

    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(STAGING):
            for name in files:
                full = os.path.join(root, name)
                zf.write(full, os.path.relpath(full, STAGING))

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    shutil.rmtree(STAGING)

    print(f"版本: v{version}")
    print(f"输出: {zip_path}")
    print(f"大小: {os.path.getsize(zip_path) / 1024 / 1024:.1f} MB")
    print(f"条目: {len(names)} 个")
    print("根目录/一层:", sorted({n.split('/')[0] for n in names}))
    print("onedir 版:", "有" if have_onedir else "无",
          "| 单文件版:", "有" if have_onefile else "无")
    print("源码文件数:", len([n for n in names if n.startswith("desktop-pet/")]))


if __name__ == "__main__":
    main()
