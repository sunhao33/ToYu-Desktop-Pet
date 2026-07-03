"""Pet companion system - makes the pet a real work companion.

The pet has moods, reacts to user actions, and visually reflects its state.
Every interaction matters. The pet is not a decoration - it's a partner.
"""

import random
import time
from enum import Enum

class PetMood(Enum):
    """Pet's current emotional state."""
    HAPPY = "happy"          # 开心 - 高好感度，用户互动频繁
    FOCUSED = "focused"      # 专注 - 番茄钟工作中
    TIRED = "tired"          # 疲惫 - 工作太久
    PLAYFUL = "playful"      # 贪玩 - 休息时间
    LONELY = "lonely"        # 孤独 - 好久没互动
    SLEEPY = "sleepy"        # 困倦 - 深夜
    EXCITED = "excited"      # 兴奋 - 完成任务/喂食
    CURIOUS = "curious"      # 好奇 - 用户在忙
    SAD = "sad"              # 伤心 - 好感度低
    PROUD = "proud"          # 自豪 - 帮助了用户
    EATING = "eating"        # 吃东西中
    DRAGGED = "dragged"      # 被拖拽

class WorkState(Enum):
    """What the user is currently doing."""
    IDLE = "idle"            # 空闲
    WORKING = "working"      # 工作中（番茄钟）
    BREAK = "break"          # 休息中
    AWAY = "away"            # 离开

class CompanionSystem:
    """Manages pet's companion behavior and reactions."""

    MOOD_MESSAGES = {
        PetMood.HAPPY: [
            "今天心情真好～",
            "有你陪我真开心！",
            "嘿嘿，好幸福～",
            "一起加油吧！",
            "（开心地晃悠）",
        ],
        PetMood.FOCUSED: [
            "嘘...专心工作中",
            "（认真脸）",
            "加油！还有 {remaining} 分钟",
            "我在旁边陪着你～",
            "（安静地坐在旁边）",
        ],
        PetMood.TIRED: [
            "好累啊...",
            "要不要休息一下？",
            "你已经工作很久了",
            "揉揉眼睛...",
            "（打哈欠）",
        ],
        PetMood.PLAYFUL: [
            "休息时间到！",
            "伸个懒腰～",
            "嘿嘿，偷个懒？",
            "要不要玩一会儿？",
            "（蹦蹦跳跳）",
        ],
        PetMood.LONELY: [
            "你去哪了...",
            "好久没理我了",
            "（默默等你回来）",
            "我想你了...",
            "（望向远方）",
        ],
        PetMood.SLEEPY: [
            "好困...zzZ",
            "晚安...",
            "（打哈欠）",
            "该睡觉了吧...",
            "（眼皮打架）",
        ],
        PetMood.EXCITED: [
            "太棒了！！",
            "耶！完成啦！",
            "好厉害！",
            "（开心转圈）",
            "（蹦跶蹦跶）",
        ],
        PetMood.CURIOUS: [
            "你在忙什么呀？",
            "（偷偷看你）",
            "需要帮忙吗？",
            "我在这儿哦～",
            "（歪头）",
        ],
        PetMood.SAD: [
            "（低头不说话）",
            "...",
            "你是不是忘记我了",
            "（小声叹气）",
            "（眼巴巴地看着你）",
        ],
        PetMood.PROUD: [
            "我帮你计时啦！",
            "做得好！",
            "你真棒！",
            "（骄傲脸）",
            "（挺起小胸脯）",
        ],
        PetMood.EATING: [
            "好好吃！",
            "（满足地嚼嚼）",
            "还要还要～",
            "（幸福脸）",
        ],
        PetMood.DRAGGED: [
            "哇！飞起来了！",
            "放我下来～",
            "（惊恐脸）",
            "晕了晕了...",
            "（手舞足蹈）",
        ],
    }

    EVENT_REACTIONS = {
        "feed": [
            "好好吃！谢谢～",
            "（满足地嚼嚼）",
            "好吃！还要！",
            "你对我真好～",
            "（幸福地冒泡泡）",
        ],
        "pet": [
            "（开心）",
            "嘿嘿～",
            "再摸摸～",
            "好舒服...",
            "（蹭蹭你的手）",
        ],
        "drag_start": [
            "哇！飞起来了！",
            "放我下来～",
            "（惊恐脸）",
            "晕了晕了...",
            "（手舞足蹈）",
        ],
        "drag_end": [
            "呼...安全着陆",
            "（松了口气）",
            "吓死我了...",
            "下次温柔点嘛",
        ],
        "task_done": [
            "又完成一个！",
            "效率真高！",
            "（鼓掌）",
            "太强了！",
            "（为你欢呼）",
        ],
        "task_add": [
            "新任务！记住了",
            "（认真记录）",
            "收到！",
            "（点点头）",
        ],
        "pomodoro_start": [
            "开始工作！我陪着你",
            "专注模式 ON",
            "加油！{interval} 分钟后休息",
            "（安静坐好）",
            "（握拳）一起加油！",
        ],
        "pomodoro_end": [
            "时间到！休息一下",
            "辛苦了！",
            "站起来活动活动～",
            "看看远处放松眼睛",
            "（伸懒腰）",
        ],
        "morning_greeting": [
            "早安！新的一天",
            "早上好～",
            "今天也要加油！",
            "（伸懒腰）早～",
            "元气满满的一天！",
        ],
        "night_greeting": [
            "晚安～",
            "该休息了",
            "明天见！",
            "（打哈欠）困了...",
            "做个好梦～",
        ],
        "long_work": [
            "你已经工作 {minutes} 分钟了",
            "要不要喝杯水？",
            "休息一下吧～",
            "（担心地看着你）",
            "眼睛累了吗？",
        ],
        "return": [
            "你回来啦！",
            "（开心蹦跶）",
            "想你了～",
            "欢迎回来！",
            "（扑过来）",
        ],
        "idle_chat": [
            "（偷偷看你）",
            "今天天气怎么样？",
            "（发呆中）",
            "你在想什么呀？",
            "（打个小哈欠）",
        ],
        "high_affection": [
            "最喜欢你了！",
            "（幸福脸）",
            "有你真好～",
            "（蹭蹭）",
        ],
        "low_affection": [
            "（委屈脸）",
            "你是不是不喜欢我了...",
            "（小声）理理我嘛...",
            "（眼巴巴）",
        ],
    }

    def __init__(self, settings):
        self.settings = settings
        self._mood = PetMood.HAPPY
        self._work_state = WorkState.IDLE
        self._last_interaction = time.time()
        self._last_mood_change = time.time()
        self._last_message_time = 0
        self._work_start_time = 0
        self._tasks_completed_today = 0
        self._pomodoro_remaining = 0
        self._consecutive_work_minutes = 0
        self._interaction_count = 0  # Track interaction frequency

    @property
    def mood(self):
        return self._mood

    @property
    def work_state(self):
        return self._work_state

    def update(self):
        """Called periodically to update mood based on context."""
        now = time.time()
        affection = self.settings.affection_level
        time_since_interact = now - self._last_interaction

        from datetime import datetime
        hour = datetime.now().hour

        new_mood = self._mood

        if 0 <= hour < 6:
            new_mood = PetMood.SLEEPY
        elif self._work_state == WorkState.WORKING:
            if self._consecutive_work_minutes > 45:
                new_mood = PetMood.TIRED
            else:
                new_mood = PetMood.FOCUSED
        elif self._work_state == WorkState.BREAK:
            new_mood = PetMood.PLAYFUL
        elif time_since_interact > 600:  # 10 minutes
            new_mood = PetMood.LONELY
        elif affection < 20:
            new_mood = PetMood.SAD
        elif affection > 80 and time_since_interact < 60:
            new_mood = PetMood.EXCITED
        elif affection > 60:
            new_mood = PetMood.HAPPY
        else:
            new_mood = PetMood.CURIOUS

        if new_mood != self._mood:
            self._mood = new_mood
            self._last_mood_change = now

    def on_interaction(self, interaction_type="pet"):
        """Called when user interacts with the pet."""
        self._last_interaction = time.time()
        self._interaction_count += 1

        reactions = self.EVENT_REACTIONS.get(interaction_type, ["..."])
        message = random.choice(reactions)

        message = self._format_message(message)

        return message

    def on_pomodoro_start(self, interval_minutes):
        """Called when pomodoro timer starts."""
        self._work_state = WorkState.WORKING
        self._work_start_time = time.time()
        self._pomodoro_remaining = interval_minutes
        self._consecutive_work_minutes = 0

        reactions = self.EVENT_REACTIONS["pomodoro_start"]
        message = random.choice(reactions)
        message = message.replace("{interval}", str(interval_minutes))
        return message

    def on_pomodoro_end(self):
        """Called when pomodoro timer ends."""
        self._work_state = WorkState.BREAK
        self._consecutive_work_minutes = 0

        reactions = self.EVENT_REACTIONS["pomodoro_end"]
        return random.choice(reactions)

    def on_pomodoro_tick(self, remaining_minutes):
        """Called every minute during pomodoro."""
        self._pomodoro_remaining = remaining_minutes
        self._consecutive_work_minutes += 1

        if self._consecutive_work_minutes > 0 and self._consecutive_work_minutes % 30 == 0:
            reactions = self.EVENT_REACTIONS["long_work"]
            message = random.choice(reactions)
            message = message.replace("{minutes}", str(self._consecutive_work_minutes))
            return message

        return None

    def on_task_complete(self):
        """Called when a todo task is completed."""
        self._tasks_completed_today += 1
        reactions = self.EVENT_REACTIONS["task_done"]
        return random.choice(reactions)

    def on_task_add(self):
        """Called when a new task is added."""
        reactions = self.EVENT_REACTIONS["task_add"]
        return random.choice(reactions)

    def on_break_end(self):
        """Called when break time is over."""
        self._work_state = WorkState.IDLE
        return "休息好了，继续加油！"

    def on_drag_start(self):
        """Called when pet is picked up."""
        self._mood = PetMood.DRAGGED
        reactions = self.EVENT_REACTIONS["drag_start"]
        return random.choice(reactions)

    def on_drag_end(self):
        """Called when pet is released."""
        reactions = self.EVENT_REACTIONS["drag_end"]
        return random.choice(reactions)

    def get_mood_message(self):
        """Get a message based on current mood."""
        messages = self.MOOD_MESSAGES.get(self._mood, ["..."])
        message = random.choice(messages)
        return self._format_message(message)

    def get_context_message(self):
        """Get a context-aware message based on current situation."""
        now = time.time()
        affection = self.settings.affection_level
        time_since_interact = now - self._last_interaction

        if affection > 80 and random.random() < 0.3:
            return random.choice(self.EVENT_REACTIONS["high_affection"])

        if affection < 20 and random.random() < 0.3:
            return random.choice(self.EVENT_REACTIONS["low_affection"])

        if time_since_interact > 300 and random.random() < 0.4:
            return random.choice(self.EVENT_REACTIONS["idle_chat"])

        return self.get_mood_message()

    def _format_message(self, message):
        """Format message with context variables."""
        if "{remaining}" in message:
            message = message.replace("{remaining}", str(self._pomodoro_remaining))
        return message

    def get_mood_emoji(self):
        """Get emoji representing current mood."""
        emoji_map = {
            PetMood.HAPPY: "😊",
            PetMood.FOCUSED: "🧐",
            PetMood.TIRED: "😫",
            PetMood.PLAYFUL: "😄",
            PetMood.LONELY: "🥺",
            PetMood.SLEEPY: "😴",
            PetMood.EXCITED: "🎉",
            PetMood.CURIOUS: "🤔",
            PetMood.SAD: "😢",
            PetMood.PROUD: "😤",
            PetMood.EATING: "😋",
            PetMood.DRAGGED: "😱",
        }
        return emoji_map.get(self._mood, "🥔")

    def get_status_text(self):
        """Get status text for display."""
        mood_text = {
            PetMood.HAPPY: "开心",
            PetMood.FOCUSED: "专注中",
            PetMood.TIRED: "疲惫",
            PetMood.PLAYFUL: "休息中",
            PetMood.LONELY: "等你回来",
            PetMood.SLEEPY: "困了",
            PetMood.EXCITED: "兴奋",
            PetMood.CURIOUS: "好奇",
            PetMood.SAD: "伤心",
            PetMood.PROUD: "自豪",
            PetMood.EATING: "吃东西",
            PetMood.DRAGGED: "被抓住了",
        }
        return mood_text.get(self._mood, "发呆")

    def get_work_duration(self):
        """Get how long user has been working in minutes."""
        if self._work_state == WorkState.WORKING and self._work_start_time > 0:
            return int((time.time() - self._work_start_time) / 60)
        return 0

    def get_daily_summary(self):
        """Get a summary of today's activity."""
        return {
            "tasks_completed": self._tasks_completed_today,
            "work_duration": self.get_work_duration(),
            "interactions": self._interaction_count,
            "mood": self._mood.value,
        }
