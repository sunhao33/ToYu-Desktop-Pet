import os, zipfile, shutil, time

VERSION = "0.61"
BASE = r"C:\Users\34338\Desktop\003"
PET_DIR = os.path.join(BASE, "desktop-pet")
DIST_DIR = os.path.join(PET_DIR, "dist")
ZIP_PATH = os.path.join(BASE, f"YoTu{VERSION}.zip")

# ── Changelog data ──────────────────────────────────────────
# 每次打包时更新这里，格式：版本号 → 变更详情
CHANGELOG = """
============================================================
  ToYu 桌面宠物 — 更新日志
============================================================

v0.60 (2026-06-09)
───────────────────
【好感度系统重写】
  - 旧系统：每次点击+1，喂食+15，无冷却限制，狂点就能满
  - 新系统：可持续增长，每日上限15点，8种互动类型独立冷却
  - 每日软上限8点（超过后收益减半），硬上限15点
  - 4小时不互动才开始衰减，最低保留5点
  - 里程碑系统：10/20/35/55/75/90/100 触发庆祝动画
  - 满好感需要7-10天持续互动

【互动类型限制】
  - 点击：15秒冷却，+1，每日4次
  - 拖拽：60秒冷却，+1，每日2次
  - 喂食：15分钟冷却，+3，每日3次
  - 聊天：2分钟冷却，+2，每日5次
  - 番茄钟：+2，每日4次
  - 完成任务：+2，每日5次
  - 每日首次：+3，每日1次
  - 陪伴：30分钟冷却，+1，每日2次

【拖拽交互】
  - 拖拽宠物移动现在会触发 drag 交互类型
  - 与普通点击分开计算冷却

【里程碑庆祝】
  - 达到里程碑触发 trigger_celebrate() 动画
  - 弹出特殊气泡显示里程碑名称和描述
  - 里程碑奖励额外+5点

v0.59 (2026-06-09)
───────────────────
【AccessoryBrain 行为联动系统】
  - 完全重写 accessory_brain.py
  - 天气反应：下雨自动撑伞45s+雨滴粒子，下雪飘雪+疲劳，高温冰淇淋宠物走过去吃掉
  - 无聊系统：10分钟没互动触发，随机帽子跳舞/墨镜耍酷/魔杖庆祝
  - 心情联动：高好感皇冠庆祝+星星，低好感伤心+汗滴
  - 时间感知：早安sparkle、晚安sleep、傍晚音符
  - 微行为：每2分钟40%概率触发环境粒子

【新增方法】
  - trigger_snow_mood() — 雪花粒子+疲劳动画
  - closeEvent 清理 brain 定时器

v0.58 (2026-06-09)
───────────────────
【启动崩溃修复】
  - 从 zip 恢复 pet_window.py 后缺少 start_accessory_brain 方法
  - 补回该方法（QTimer 驱动的定时检查循环）
  - 添加 get_taskbar_info 导入
  - 物理引擎尺寸覆盖 bug 修复

v0.57 (2026-06-08)
───────────────────
【表达系统三层架构】
  - Layer 1：浮动粒子（音符/闪光/雨滴/雪花+已有红心/星星/Zzz/火焰/汗滴）
  - Layer 2：整体动画（跳舞/疲劳/瞌睡/庆祝）
  - Layer 3：独立精灵配件（帽子/雨伞/冰淇淋/皇冠/墨镜/蝴蝶结/魔杖）
  - 精灵可见区域检测（像素扫描）
  - 配件质量优化（更高分辨率像素画）

v0.56 (2026-06-08)
───────────────────
【屏幕时间统计】
  - 后台检测前台窗口
  - 全屏应用自动暂停
  - 今日 vs 昨日对比
  - 应用排行 Top10
  - 中文时长格式
  - psutil 依赖修复

v0.55 (2026-06-08)
───────────────────
【统计图表优化】
  - 图表随窗口自动缩放（_ScaledLabel）
  - DPI 300 高清渲染
  - 现代配色方案
  - 修复 bar() 非法参数崩溃

v0.54 (2026-06-08)
───────────────────
【统计分析图表】
  - 环形图（任务时间分布）+ 柱状图（7天活动量）并排
  - 完成任务实时刷新图表

v0.53 (2026-06-08)
───────────────────
【日期任务历史】
  - 日历点击查看已完成任务
  - 卡片样式与待办一致
  - 显示任务耗时
  - 修复 QScrollArea 重复导入崩溃
  - 修复 deleteLater 竞态崩溃

v0.52 (2026-06-08)
───────────────────
【计时弹窗 UI】
  - 四角黑边修复（WA_TranslucentBackground）
  - 计时字体加粗（500）
  - 按钮颜色：暂停淡黄、完成淡绿、结束淡红

v0.51 (2026-06-08)
───────────────────
【计时弹窗配色】
  - 统一为 ToYu 暖土豆色系
  - 替换橙色为金色 #C49A3C

v0.50 (2026-06-08)
───────────────────
- 移除打地鼠小游戏（暂时）

v0.49 (2026-06-07)
───────────────────
- 修复 AI 设置保存崩溃
- 改为更新现有 AICompanion 实例（保留对话历史）
- 加 try-except 防崩溃

v0.48 (2026-06-07)
───────────────────
【AI 伴侣增强】
  - 聊天记录持久化（ai_chat_history.json，保留200条）
  - 聊天窗口显示完整对话历史
  - 好感度+时间段联动 AI
  - 主动行为系统（开机问候、天气感知、定期check-in、深夜提醒）
  - 天气缓存
  - 聊天窗口深色底修复

v0.47 (2026-06-07)
───────────────────
【AI 伴侣系统】
  - 双击宠物打开聊天
  - 支持 DeepSeek 等 OpenAI 兼容 API
  - 5种性格预设
  - AI 设置独立标签页
  - CompanionBubble 自动调整大小
  - 气泡尾巴加宽、定位优化

v0.46 (2026-06-07)
───────────────────
- 气泡彻底修复
- CompanionBubble/PomodoroNotificationBubble 改为独立顶层窗口
- 计算精灵图片实际顶部位置贴合宠物
- Tool 窗口无 DWM 阴影
- 点击外部关闭

v0.45 (2026-06-07)
───────────────────
- 深色模式文字修复
- 任务栏图标修复（AppUserModelID）
- 气泡重写（CompanionBubble 用 QPainter 画气泡尾巴）
- PetFunctionBubble 用 Tool 窗口去阴影
- 好感度同步修复（.value → .level）

v0.44 (2026-06-07)
───────────────────
- 深色模式全面修复
- 添加 _c() 颜色辅助方法
- 30+ 处 inline 样式改为动态取色
- DropZone 深色模式支持
- 切换模式时所有 inline 样式自动刷新

============================================================
""".strip()

# ── Generate changelog.txt ──────────────────────────────────
changelog_path = os.path.join(PET_DIR, "changelog.txt")
with open(changelog_path, 'w', encoding='utf-8') as f:
    f.write(CHANGELOG)
print(f"Generated: changelog.txt ({len(CHANGELOG)} chars)")

# ── Build zip ───────────────────────────────────────────────
staging = os.path.join(BASE, "_staging")
if os.path.exists(staging):
    shutil.rmtree(staging)
os.makedirs(staging)

shutil.copy2(os.path.join(DIST_DIR, "ToYu.exe"), os.path.join(staging, "ToYu.exe"))
shutil.copy2(changelog_path, os.path.join(staging, "changelog.txt"))

src_dst = os.path.join(staging, "desktop-pet")
os.makedirs(src_dst, exist_ok=True)
EXCLUDE_DIRS = {"dist", "build", "__pycache__", ".git", ".claude", "_staging"}
EXCLUDE_EXTS = {".zip", ".pyc"}
SKIP_SCRIPTS = {'_add_acc.py', '_debug.py', '_debug2.py', '_debug3.py', '_debug4.py',
                '_debug5.py', '_fix_acc.py', '_gen_acc.py', '_recover.py',
                '_check_methods.py', '_test_run.py', '_test_crash.py', '_test_pet.py',
                '_package.py', 'test_demo.py'}

for item in os.listdir(PET_DIR):
    if item in EXCLUDE_DIRS or item in SKIP_SCRIPTS:
        continue
    if os.path.splitext(item)[1] in EXCLUDE_EXTS:
        continue
    src = os.path.join(PET_DIR, item)
    dst = os.path.join(src_dst, item)
    if os.path.isdir(src):
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*EXCLUDE_DIRS, "*.pyc", "*.zip"))
    else:
        print(f"Copying: {item}")
        shutil.copy2(src, dst)

with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(staging):
        for f in files:
            full = os.path.join(root, f)
            arcname = os.path.relpath(full, staging)
            zf.write(full, arcname)

shutil.rmtree(staging)

size_mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
print(f"\nCreated: {ZIP_PATH}")
print(f"Size: {size_mb:.1f} MB")
