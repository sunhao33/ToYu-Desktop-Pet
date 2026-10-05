# 架构设计

本文说明 ToYu 的分层结构、线程模型与智能体运行时设计。
面向想读懂代码或二次开发的人。

---

## 一、总体分层

```
┌──────────────────────────────────────────────────────────────┐
│  ui/                       界面层（全部在主线程）              │
│    main_window.py          主窗口：宠物 / 功能 / 工具 / AI 四页  │
│    flow_window.py          心流模式（独立顶层窗口，不持有数据）   │
│    mini_timer.py           悬浮计时小窗                        │
│    widgets/                进度环 · 报告渲染 · 专注时间轴        │
└────────────────────────────┬─────────────────────────────────┘
                             │ Qt 信号（跨线程唯一安全通道）
┌────────────────────────────▼─────────────────────────────────┐
│  pet_engine/agent/         智能体运行时                        │
│    loop.py                 多轮主循环 + 三条刹车                │
│    runtime.py              线程安全工具执行桥                   │
│    tools.py                工具注册表                          │
│    protocol.py             工具调用契约（JSON Schema）          │
│    context.py              上下文注入（6 优先级块）             │
│    memory_store.py         长期记忆存储（20 受控槽位）          │
│    memory_extract.py       记忆抽取 + 置信度重估                │
│    slots.py                受控槽位表                          │
└────────────────────────────┬─────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│  pet_engine/               宠物内核与业务                       │
│    pet_window.py           渲染 + 主循环（QTimer 60fps）        │
│    pet_physics.py          重力 / 落地 / 边缘碰撞               │
│    pet_state_machine.py    状态机（IDLE/WALKING/DRAGGED/...）   │
│    pet_ai.py               AI 传输层（子线程 HTTP + 信号回传）   │
│    report.py               学习工作报告                         │
│    goal.py                 每日目标                             │
│    focus_log.py            专注记录                             │
│    pet_companion.py        心情 / 好感度 / 番茄联动              │
└──────────────────────────────────────────────────────────────┘
```

**依赖方向单向向下**：界面依赖智能体，智能体依赖内核；
内核**不反向依赖界面**（`report.py`、`goal.py`、`focus_log.py`
完全不含 Qt 依赖，可以单独测试与复用）。

---

## 二、线程模型（最容易踩坑的地方）

### 为什么 Agent 主循环必须在子线程

工具执行需要**回主线程**操作 Qt（读写控件、弹气泡）。
如果 Agent 主循环自己占着主线程，等工具回主线程就等于等自己 → **死锁**。

所以：

```
主线程                          子线程
  │                               │
  │  start()                      │
  ├──────────────────────────────►│  loop.run()
  │                               │    ├─ 模型请求（HTTP，阻塞）
  │                               │    ├─ 决定调用工具
  │  QTimer 轮询队列              │    │
  │◄──── 工具请求入队 ────────────┤    │
  ├─ 执行工具（碰 Qt）             │    │
  │──── 结果入队 ────────────────►│    │
  │                               │    └─ 观察结果，继续下一轮
  │◄──── pyqtSignal(finished) ────┘
```

### 跨线程通知只能用信号

| 方式 | 结果 |
|---|---|
| `pyqtSignal.emit()` | ✅ 队列投递到接收者所在线程，安全 |
| 直接调用回调 | ❌ 在调用者线程执行；写 Qt 控件会静默出错 |
| `QTimer.singleShot`（子线程调用） | ❌ **静默失效**，回调永不触发（实测） |

`pet_ai.py` 的 `AIAgentWorker`、`AIChatWorker` 都是 QObject + 信号；
`ui/main_window.py` 的 `ReportAISignal` 是同一模式。

**踩坑记录**：早期版本把 `on_trace` 裸回调交给 AgentLoop，
子线程里直接 `QLabel.setText()` —— Qt 不警告、不报错、静默成功，
但偶发状态栏错乱。现已改为信号转发。

---

## 三、智能体运行时

### 3.1 主循环与三条刹车（`loop.py`）

```
for round in range(MAX_ROUNDS=5):
    if now > deadline:            # 总超时 90s
        break
    resp = model.chat(messages)   # 单次请求超时 20s
    if not resp.tool_calls:
        return resp.text          # 没有工具调用 = 结束
    for call in resp.tool_calls:
        ok, result = runtime.execute(call)   # 排队到主线程
        messages.append(tool_result)
        if not ok:
            failures += 1
            if failures >= MAX_CONSECUTIVE_FAILURES=2:
                return 让模型总结现状
return 轮数用尽，让模型总结现状
```

**关键点**：轮数/超时用尽时**不是直接报错**，而是再让模型总结一句，
避免用户看到生硬的失败。

### 3.2 工具执行桥（`runtime.py`）

```python
# 子线程侧
def execute(call):
    req = Request(call)
    queue.put(req)                 # 入队
    return req.done.wait(timeout)  # 等主线程执行完

# 主线程侧（QTimer 轮询）
def _drain():
    while not queue.empty():
        req = queue.get()
        try:
            req.result = handler(**req.args)
            req.ok = True
        finally:
            req.done.set()         # 必须放 finally，否则超时后子线程永久等待
```

### 3.3 工具契约（`protocol.py`）

工具参数在**执行前**做 JSON Schema 校验（类型 / 长度 / 取值范围）。
校验失败**不抛异常**，而是把失败原因作为工具结果回灌给模型，让它自己改参数重试。

### 3.4 上下文注入（`context.py`）

6 个块按优先级排序，超 token 预算就从最低优先级开始丢：

| 优先级 | 块 | 说明 |
|---|---|---|
| 1 | 待办 | 未完成任务 |
| 2 | 学习情况 | 今日有效学习时长、目标进度 |
| 3 | 日程 | 日历标注 |
| 4 | 宠物状态 | 心情、好感度 |
| 5 | 当前应用 | 前台窗口（可关闭） |
| 6 | 剪贴板 | 最近复制（可关闭） |

`TOKEN_BUDGET = 400`（换算 `CHAR_BUDGET = 480`）。

**提示注入防护**：窗口标题、剪贴板属于**外部可控文本**，
进入上下文前做标记（包在明确的引用块里），且不参与指令解析。

### 3.5 长期记忆（`memory_store.py` + `memory_extract.py`）

**20 个受控槽位**，每个槽位有固定的 `kind` 与 `value_type`。
写入前经过三层校验：

1. **结构校验** —— 字段、类型、取值范围
2. **槽位校验** —— 槽位必须在受控表内，且 kind/value_type 与表一致
3. **置信度重算** —— **不信模型自报的 confidence**

置信度重算规则：

| 证据形态 | 置信度 |
|---|---|
| 显性信号（「我叫…」「记住…」「我的目标是…」） | ≥ 0.90 |
| 弱信号（「可能」「大概」「有时候」） | ≥ 0.70 |
| 其它 | `min(模型自报, 0.60)` |

检索**不用向量库**：字符 2-gram 相似度 + 时间衰减，
阈值 `MIN_RELEVANCE = 0.08`、`MIN_SCORE = 0.18`。
理由见 README「设计决策」。

---

## 四、数据落盘

### 两套数据目录（历史遗留，已在文档中标注）

| 路径 | 内容 |
|---|---|
| `%APPDATA%\ToYu\` | 设置（QSettings）、AI 配置、记忆、报告导出、计时器 |
| `~\.desktop_pet\` | 待办、任务历史、屏幕会话、拼豆图片 |

### 写入纪律

**所有会覆盖的数据都要原子写**：写临时文件 → `os.replace()` 替换。
直接覆写时写到一半崩溃/断电会留下截断文件，下次读取即视为损坏。

已经在用的地方：拼豆图保存、屏幕会话保存、待办保存、记忆保存。

**读取纪律**：解析失败时**先备份再放弃**，绝不用空数据覆写非空文件。
（曾经踩过：一条记录带未知字段 → 整批构造失败 → 待办被清空写回。）

---

## 五、降级策略

```
记忆不可用        → 对话继续，只是没有长期记忆
上下文获取失败    → 跳过该块，模型少知道一点
报告 AI 分析失败  → 退回基础版报告（纯本机统计）
模型请求失败      → 明确提示错误，本机功能不受影响
未捕获异常        → 崩溃守卫写日志，程序继续运行
```

每一层都独立降级，**不会因为 AI 部分出问题就让桌宠不能用**。

---

## 六、性能取舍

| 位置 | 现状 | 说明 |
|---|---|---|
| 屏幕采样 | 子线程 + 60 秒落盘 | 有锁保护缓冲，读取端也持锁 |
| 图像处理 | 纯 Python 逐像素 | 大图较慢（2000×2000 约 0.7 秒），可向量化优化 |
| 记忆检索 | 2-gram 扫描 | 20 槽位规模下开销可忽略 |
| 宠物渲染 | 60fps QTimer | 单精灵绘制，开销很低 |

---

## 七、目录职责速查

| 想改什么 | 去哪 |
|---|---|
| 加一个 AI 工具 | `agent/tools.py` 注册 + `agent/protocol.py` 加 schema |
| 改上下文内容 | `agent/context.py` |
| 改记忆规则 | `agent/memory_extract.py`、`agent/slots.py` |
| 改报告口径 | `report.py` |
| 改界面 | `ui/main_window.py`（四页在同一文件） |
| 改宠物行为 | `pet_engine/pet_state_machine.py`、`pet_companion.py` |
| 改打包 | `ToYuDir.spec` + `dev/_package.py` |
