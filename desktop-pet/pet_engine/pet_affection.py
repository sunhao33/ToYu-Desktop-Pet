"""Affection system — sustainable, long-term bond building.

Design philosophy:
- 100 好感度需要持续数周甚至数月才能达到
- 每天有软上限，防止一天刷满
- 达到里程碑触发庆祝 + 奖励
"""

import json
import os
import random
import time

LEVEL_EMOJIS = [
    (0, "😊"),
    (15, "🙂"),
    (35, "😄"),
    (55, "😍"),
    (80, "🤩"),
    (100, "💖"),
]

MAX_AFFECTION = 100

DAILY_SOFT_CAP = 8
DAILY_HARD_CAP = 15  # absolute max per day regardless of source

INTERACTIONS = {
    'click':       {'cooldown': 15,   'points': 1, 'daily_max': 4},
    'drag':        {'cooldown': 60,   'points': 1, 'daily_max': 2},
    'feed':        {'cooldown': 900,  'points': 3, 'daily_max': 3},
    'chat':        {'cooldown': 120,  'points': 2, 'daily_max': 5},
    'pomodoro':    {'cooldown': 0,    'points': 2, 'daily_max': 4},
    'task_done':   {'cooldown': 0,    'points': 2, 'daily_max': 5},
    'first_daily': {'cooldown': 0,    'points': 3, 'daily_max': 1},
    'stay':        {'cooldown': 1800, 'points': 1, 'daily_max': 2},
    'milestone':   {'cooldown': 0,    'points': 5, 'daily_max': 1},
}

DECAY_INTERVAL = 7200    # lose 1 point every 2 hours
DECAY_GRACE = 14400      # no decay if interacted within 4 hours
DECAY_MIN = 5            # never decay below this level (hard-earned base)

MILESTONES = {
    10:  ("初见",    "🌱", "第一次建立联系"),
    20:  ("相识",    "🌿", "开始熟悉彼此"),
    35:  ("朋友",    "🌳", "成为朋友"),
    55:  ("好友",    "💛", "亲密的好友"),
    75:  ("挚友",    "💕", "无话不谈"),
    90:  ("知己",    "💖", "心灵相通"),
    100: ("灵魂伴侣", "💖", "永远的伙伴"),
}

DATA_DIR = os.path.join(os.path.expanduser("~"), ".desktop_pet")

class AffectionSystem:
    def __init__(self, settings_manager):
        self._settings = settings_manager
        self._interaction_log = {}  # {type: last_timestamp}
        self._daily_points = {}     # {date_str: total_points}
        self._daily_by_type = {}    # {date_str: {type: count}}
        self._milestones_reached = set()
        self._milestone_callback = None  # set externally
        self._load_state()

    @property
    def level(self):
        return min(self._settings.affection_level, MAX_AFFECTION)

    def set_milestone_callback(self, cb):
        """Set callback for milestone events: cb(title, emoji, description)"""
        self._milestone_callback = cb

    def _today(self):
        return time.strftime("%Y-%m-%d")

    def _load_state(self):
        path = os.path.join(DATA_DIR, "affection_state.json")
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._daily_points = data.get('daily_points', {})
                self._daily_by_type = data.get('daily_by_type', {})
                self._milestones_reached = set(data.get('milestones', []))
                cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7*86400))
                self._daily_points = {k: v for k, v in self._daily_points.items() if k >= cutoff}
                self._daily_by_type = {k: v for k, v in self._daily_by_type.items() if k >= cutoff}
        except Exception:
            pass

    def _save_state(self):
        path = os.path.join(DATA_DIR, "affection_state.json")
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            data = {
                'daily_points': self._daily_points,
                'daily_by_type': self._daily_by_type,
                'milestones': list(self._milestones_reached),
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _get_daily_total(self) -> int:
        return self._daily_points.get(self._today(), 0)

    def _get_daily_type_count(self, itype: str) -> int:
        today = self._today()
        return self._daily_by_type.get(today, {}).get(itype, 0)

    def _inc_daily_type(self, itype: str):
        today = self._today()
        if today not in self._daily_by_type:
            self._daily_by_type[today] = {}
        self._daily_by_type[today][itype] = self._daily_by_type[today].get(itype, 0) + 1

    def can_interact(self, itype: str) -> bool:
        if itype not in INTERACTIONS:
            return False
        cfg = INTERACTIONS[itype]

        if self._get_daily_total() >= DAILY_HARD_CAP:
            return False

        if self._get_daily_type_count(itype) >= cfg['daily_max']:
            return False

        last = self._interaction_log.get(itype, 0)
        if cfg['cooldown'] > 0 and (time.time() - last) < cfg['cooldown']:
            return False

        return True

    def add(self, amount_unused=1, itype='click'):
        """Add affection through a typed interaction.

        Returns actual points added (0 if blocked).
        """
        if itype not in INTERACTIONS:
            return 0

        cfg = INTERACTIONS[itype]

        last = self._interaction_log.get(itype, 0)
        if cfg['cooldown'] > 0 and (time.time() - last) < cfg['cooldown']:
            return 0

        if self._get_daily_type_count(itype) >= cfg['daily_max']:
            return 0

        daily_total = self._get_daily_total()
        if daily_total >= DAILY_HARD_CAP:
            return 0

        self._interaction_log[itype] = time.time()

        base_points = cfg['points']
        if daily_total >= DAILY_SOFT_CAP:
            actual_points = max(1, base_points // 2)
        else:
            actual_points = base_points

        actual_points = min(actual_points, DAILY_HARD_CAP - daily_total)

        if actual_points <= 0:
            return 0

        new_lv = min(self.level + actual_points, MAX_AFFECTION)
        self._settings.affection_level = new_lv
        self._settings.affection_last_decay = time.time()

        today = self._today()
        self._daily_points[today] = self._daily_points.get(today, 0) + actual_points
        self._inc_daily_type(itype)

        self._check_milestones(self.level, new_lv)

        self._save_state()
        return actual_points

    def tick_decay(self):
        """Decay affection slowly. Only if grace period passed."""
        now = time.time()
        last = self._settings.affection_last_decay

        if last <= 0:
            self._settings.affection_last_decay = now
            return

        if (now - last) < DECAY_GRACE:
            return

        elapsed = now - last - DECAY_GRACE
        steps = int(elapsed / DECAY_INTERVAL)
        if steps > 0:
            new_lv = max(DECAY_MIN, self.level - steps)
            self._settings.affection_level = new_lv
            self._settings.affection_last_decay = now

    def _check_milestones(self, old_level, new_level):
        for threshold, (title, emoji, desc) in MILESTONES.items():
            if new_level >= threshold and old_level < threshold and threshold not in self._milestones_reached:
                self._milestones_reached.add(threshold)
                self.add(itype='milestone')
                if self._milestone_callback:
                    self._milestone_callback(title, emoji, desc)

    def get_milestone(self):
        current = None
        next_milestone = None
        for threshold in sorted(MILESTONES.keys()):
            if self.level >= threshold:
                current = (threshold, MILESTONES[threshold])
            elif next_milestone is None:
                next_milestone = (threshold, MILESTONES[threshold])
        return current, next_milestone

    def get_daily_stats(self) -> dict:
        today = self._today()
        by_type = self._daily_by_type.get(today, {})
        return {
            'total_points': self._daily_points.get(today, 0),
            'by_type': by_type,
            'remaining_clicks': max(0, INTERACTIONS['click']['daily_max'] - self._get_daily_type_count('click')),
            'remaining_feeds': max(0, INTERACTIONS['feed']['daily_max'] - self._get_daily_type_count('feed')),
            'soft_cap_remaining': max(0, DAILY_SOFT_CAP - self._get_daily_total()),
            'hard_cap_remaining': max(0, DAILY_HARD_CAP - self._get_daily_total()),
        }

    @property
    def emoji(self):
        lv = self.level
        for threshold, emoji in reversed(LEVEL_EMOJIS):
            if lv >= threshold:
                return emoji
        return "😊"

    @property
    def display_text(self):
        return f"{self.emoji} {self.level}"
