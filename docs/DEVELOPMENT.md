# 开发指南

面向要改 ToYu 代码的人。约定与踩坑记录都在这。

---

## 一、环境准备

```bash
git clone https://github.com/sunhao33/ToYu-Desktop-Pet.git
cd ToYu-Desktop-Pet/desktop-pet
pip install -r requirements.txt
python main.py
```

**版本**：Python 3.10+（开发环境 3.14）· Windows 10/11 64 位

> `rembg` 是**可选**依赖，只在 AI 抠图时懒加载。不装也能用，
> 只是没有「AI 智能抠图」这一项。

---

## 二、目录约定

```
desktop-pet/
├── main.py              入口。只有这一个可执行脚本留在顶层
├── pet_engine/          宠物内核 + 智能体运行时
├── ui/                  界面
├── image_processor/     图像处理
├── resources/           素材（图标、宠物、配件、房子）
└── dev/                 开发工具，全部在这
    ├── _test_all.py     全量回归入口
    ├── _test_*.py       各模块测试
    ├── _package.py      打包脚本
    ├── _probe_*.py      探针（临时排查用）
    └── _isolate_data.py 数据隔离（写测试/截图脚本时用）
```

**约定**：产品文件放顶层，开发工具一律进 `dev/`。
新增测试脚本命名 `_test_<模块>.py`，并在 `dev/_test_all.py` 的列表里注册。

---

## 三、测试

### 跑全量回归

```bash
python dev/_test_all.py          # 27 个测试文件，约 170 秒
```

### 跑单个

```bash
python dev/_test_agent_tools.py
```

每个测试脚本输出 `PASS/FAIL` 明细与 `N/M passed`，
退出码 0 表示全过。

### 写测试的注意事项

**① 一定要隔离数据目录**

测试脚本会读写真实用户目录（`%APPDATA%\ToYu`、`~\.desktop_pet`），
不隔离就会污染真实数据，导致别的测试莫名失败。**这个坑反复踩过多次。**

```python
import sys, os
sys.path.insert(0, r"...\desktop-pet")
import _isolate_data  # noqa: F401  必须放在导入业务模块之前
```

`_isolate_data.py` 会把两个数据目录重定向到临时目录。

**② 判断控件可见性用 `isHidden()`**

离屏平台下祖先控件没有前台化，`isVisible()` 恒为 False。
判断「这个控件是否被隐藏」要用 `isHidden()`。

**③ 离屏模式没有中文字体**

`QT_QPA_PLATFORM=offscreen` 下中文会渲染成方块。
**抓截图必须用真实窗口**（不设该环境变量），否则图没法用。

**④ 定时器槽里的未捕获异常会让 PyQt6 直接终止进程**

不是抛到上层，是 `qFatal`（退出码 `0xC0000409`）。
所以测试里注入异常要小心，别把测试进程自己干掉。

---

## 四、代码约定

### 零新增依赖

当前依赖只有 `requirements.txt` 里那些（PyQt6 / matplotlib / Pillow /
NumPy / psutil / pywin32 / openai）。**新增依赖需要充分理由** ——
安装包每大 10 MB，传播成本就上一个台阶。

### 注释写「为什么」

```python
# ✗ 别这样：把颜色设成金色
self.setStyleSheet("color: #C49A3C")

# ✓ 这样：冷底上金色偏暗，提亮后才能在暗色模式下达标（实测 6.9:1）
self.setStyleSheet("color: %s" % DARK_ACCENT)
```

踩过的坑要写进注释，否则下一个人（包括未来的你）会踩第二次。

### 颜色与主题

**不要在界面代码里写死颜色**。用 `main_window._c(key)` 取当前主题色：

| key | 用途 |
|---|---|
| `bg` / `card` | 背景 / 卡片底 |
| `text` / `text2` | 正文 / 次要文字 |
| `border` | 描边 |
| `accent` / `accent_h` | 强调色 / 悬停 |
| `success` / `danger` / `warn` | 语义色 |
| `hover_bg` / `press_bg` | 交互态 |
| `input_bg` / `tab_bg` | 输入框 / 标签底 |

深色模式的每项配色都按 **WCAG AA** 实测过（正文对比度 ≥4.5:1）。
改配色请重新量对比度，别凭观感调。

> 注意 `_global_stylesheet()` 是 `@staticmethod`（没有 `self`），
> 只能用模块级常量，不能调 `self._c()`。

### 跨线程

**永远不要**从子线程直接操作 Qt 控件，也不要用 `QTimer.singleShot`
从子线程投递回调（实测静默失效）。用 `pyqtSignal`。

详见 [ARCHITECTURE.md](ARCHITECTURE.md#二线程模型最容易踩坑的地方)。

### 数据落盘

覆盖写一律**临时文件 + `os.replace()`**。
读取失败**先备份再放弃**，不要用空数据覆写非空文件。

```python
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
os.replace(tmp, path)
```

---

## 五、打包发布

```bash
cd desktop-pet
python -m PyInstaller ToYuDir.spec --noconfirm --distpath dist_dir2 --workpath build_dir2
python dev/_package.py
```

产出 `ToYu_v<版本>.zip`（版本号从 `changelog.txt` 第一行读取）。

### 关键约束

| 约束 | 原因 |
|---|---|
| 必须用 **onedir**（`ToYuDir.spec`） | onefile 运行时解压到 `%TEMP%\_MEIxxxx`，会被杀毒软件拦截导致启动失败 |
| `base_library.zip` 不能进包 | 同上，会被杀毒软件清除后报「Failed to import encodings module」 |
| 打包后必须跑 `_package.py` | 它会排除开发脚本与运行时数据（含 API Key），并做交付前自检 |

`_package.py` 的自检会扫描包内是否含 `sk-` 开头的密钥、运行时数据、
开发脚本，命中即让构建失败。**别绕过它。**

---

## 六、更新日志

每次改完在 `desktop-pet/changelog.txt` 顶部加一条：

```
v0.81.0 (2026-10-06)
────────────────────
【本次改了什么】
  1) 具体改动 + 为什么这么改
  ...
```

**版本号由它决定**（`_package.py` 读第一行）。
忘了加条目就会打出旧版本号的包 —— 这个坑踩过一次。

---

## 七、常见问题排查

| 现象 | 排查方向 |
|---|---|
| 程序启动即报错窗口 | 包内是否有 `base_library.zip`；杀毒软件是否拦截 |
| 中文显示成方块 | 是否用了 `QT_QPA_PLATFORM=offscreen` |
| 子线程更新界面无反应 | 是否误用 `QTimer.singleShot`；应改 `pyqtSignal` |
| 测试莫名失败 | 真实数据目录是否被别的脚本污染（用 `_isolate_data`） |
| 深色模式下某处仍是浅色 | 该控件是否用了 `self._c()`；或需加入主题重刷 |
| 打包后版本号不对 | `changelog.txt` 第一行是否是新版本 |
| 定时器槽里异常导致退出 | 这是 PyQt6 的 `qFatal` 行为，需在槽内 try/except |

### 看运行日志

```
%APPDATA%\ToYu\errors.log        未捕获异常（崩溃守卫写入，超 512KB 轮转）
```

---

## 八、提交前检查清单

- [ ] `python dev/_test_all.py` 全过
- [ ] `changelog.txt` 加了本次条目
- [ ] 没有新增依赖（除非有充分理由）
- [ ] 没有写死颜色（用 `_c()`）
- [ ] 覆盖写用了临时文件 + `os.replace`
- [ ] 跨线程通信用了信号
- [ ] 没有把 API Key、运行时数据提交进仓库
