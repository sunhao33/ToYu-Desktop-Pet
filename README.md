# ToYu — 桌面土豆宠物 🥔

基于 PyQt6 的 Windows 桌面伴侣，一个会走路、会互动、会聊天的小土豆。

## 特性

- **桌面宠物** — 悬浮在桌面上的透明窗口，60fps 流畅动画
- **物理引擎** — 重力、落地、屏幕边缘碰撞
- **好感度系统** — 8 种互动类型，每日上限，里程碑庆祝
- **AI 对话** — 支持 DeepSeek/OpenAI 等接口，5 种性格预设
- **时间感知** — 早晚改变行为（夜晚变暗变慢，清晨活跃）
- **配件系统** — 帽子、雨伞、墨镜、皇冠等 7 种配件
- **粒子特效** — 爱心、星星、音符、雪花、雨滴
- **番茄钟** — 定时休息提醒
- **待办列表** — 完成任务 + 好感度
- **拼豆编辑器** — 51 色调色板，手绘像素宠物
- **小房子** — 宠物可进出，拖拽到门上即回家
- **天气感知** — 下雨自动撑伞，高温吃冰淇淋

## 运行

```bash
cd desktop-pet
pip install -r requirements.txt
python main.py
```

## 结构

```
desktop-pet/
├── main.py              入口
├── pet_engine/          核心引擎
│   ├── pet_window.py    主窗口（渲染、交互、游戏循环）
│   ├── pet_state_machine.py   状态机
│   ├── pet_animation.py       动画系统
│   ├── pet_physics.py         物理引擎
│   ├── pet_affection.py       好感度系统
│   ├── pet_bubble.py          气泡窗口
│   ├── pet_food.py            喂食系统
│   ├── pet_house.py           小房子
│   ├── pet_companion.py       陪伴系统
│   ├── pet_proactive.py       主动行为
│   ├── pet_effects.py         粒子特效
│   ├── pet_accessories.py     配件层
│   ├── accessory_brain.py     配件AI
│   └── pet_ai.py             AI对话
├── ui/                  控制面板
│   ├── main_window.py   主窗口（4标签页）
│   ├── bead_editor.py   拼豆编辑器
│   ├── settings_manager.py    设置持久化
│   └── ...
├── image_processor/     图片处理（去底/抠图）
└── resources/           图片、音效
```

## 交互

| 操作 | 效果 |
|------|------|
| 右键宠物 | 功能菜单（喂食、回家、隐藏） |
| 双击宠物 | AI 聊天 |
| 拖拽宠物 | 移动 / 丢进房子 / 摇晃触发眩晕 |
| 滚轮 | 缩放 |
| 拖放文件到宠物 | 删除到回收站 |

## 技术栈

- **Python 3.14** + **PyQt6**
- **Pillow** 图像处理
- **rembg** + **onnxruntime** AI 抠图
- **PyInstaller** 打包为 exe

## 许可

本软件仅供个人学习、研究和非商业用途使用。

- **允许** — 下载、使用、学习本项目代码
- **禁止** — 修改、分发、再发布本项目或其衍生作品
- **禁止** — 将本项目或其任何部分用于商业目的

保留所有权利。如需商业授权，请联系作者。
