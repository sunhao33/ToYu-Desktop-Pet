"""记忆存储 —— 一条记忆 = 一个槽位的最新值。

存储位置：%APPDATA%\\ToYu\\memory\\memories.json

设计要点：
  * **同槽位覆盖**：同一个 slot 只保留最新一条（active），旧值转存进
    history 供追溯。否则用户改主意后会出现两条互相矛盾的记忆。
  * **原子写入**：临时文件 + os.replace，避免崩溃时写出半个文件。
  * **过期自动清理**：事实类记忆带 TTL，过期即标记 inactive 而不是删除
    （保留可追溯性，但不再参与召回）。
  * **上限保护**：最多保留 MAX_RECORDS 条，超出按"低置信 + 老"淘汰，
    防止长期使用后文件无限膨胀。
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime

from pet_engine.agent.memory_contract import MemoryRecord

DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                        "ToYu", "memory")
MEMORY_FILE = os.path.join(DATA_DIR, "memories.json")

MAX_RECORDS = 300          # 活跃记忆上限
MAX_HISTORY = 500          # 被覆盖/删除的历史保留条数


class MemoryStore:
    """记忆库：读取、写入、遗忘、维护。"""

    def __init__(self, path: str | None = None):
        self._path = path or MEMORY_FILE
        self._records: list[MemoryRecord] = []
        self._history: list[dict] = []
        self._load()

    # ── 读写 ────────────────────────────────────────────────
    def _load(self):
        self._records = []
        self._history = []
        try:
            if not os.path.exists(self._path):
                return
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return
            for item in data.get("records", []):
                if isinstance(item, dict):
                    try:
                        self._records.append(MemoryRecord.from_dict(item))
                    except Exception:  # noqa: BLE001 — 单条坏数据不该丢整个库
                        continue
            self._history = [h for h in data.get("history", [])
                             if isinstance(h, dict)]
        except Exception as exc:  # noqa: BLE001
            print("[Memory] 读取失败，按空库处理: %s" % exc)
            self._records = []
            self._history = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            payload = {
                "version": 1,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "records": [r.to_dict() for r in self._records],
                "history": self._history[-MAX_HISTORY:],
            }
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self._path)
        except Exception as exc:  # noqa: BLE001
            print("[Memory] 保存失败: %s" % exc)

    # ── 查询 ────────────────────────────────────────────────
    def all(self, include_inactive: bool = False) -> list[MemoryRecord]:
        if include_inactive:
            return list(self._records)
        return [r for r in self._records if r.active and not r.is_expired()]

    def get(self, slot_id: str) -> MemoryRecord | None:
        """取活跃记忆。

        过期记录不算活跃 —— 这一点必须与 all() 一致，否则已过期的记忆
        仍然会被 upsert 命中并"复活"（改个值就又活了），
        等于 TTL 形同虚设。
        """
        for record in self._records:
            if record.slot_id == slot_id and record.active:
                if record.is_expired():
                    record.active = False
                    self._save()
                    return None
                return record
        return None

    def count(self) -> int:
        return len(self.all())

    # ── 写入 ────────────────────────────────────────────────
    def upsert(self, record: MemoryRecord) -> str:
        """写入或更新一条记忆。返回 'added' / 'updated' / 'rejected'。"""
        if record is None:
            return "rejected"

        existing = self.get(record.slot_id)
        if existing is None:
            self._records.append(record)
            self._enforce_limit()
            self._save()
            return "added"

        # 同槽位：只有新记录的置信度不低于旧的才覆盖，
        # 否则保留旧的 —— 避免一次模糊表达把明确偏好冲掉
        if record.confidence + 1e-9 < existing.confidence:
            return "rejected"

        # 值完全相同：只刷新时间与命中数，不写历史噪音
        if existing.value == record.value:
            existing.updated_at = record.updated_at
            existing.evidence = record.evidence
            existing.confidence = max(existing.confidence, record.confidence)
            self._save()
            return "updated"

        existing.active = False
        self._history.append({
            "memory_id": existing.memory_id,
            "slot_id": existing.slot_id,
            "value": existing.value,
            "confidence": existing.confidence,
            "evidence": existing.evidence,
            "replaced_at": record.created_at,
            "reason": "superseded",
        })
        # 刷新已存在记录的字段（保持 memory_id 稳定，便于追溯同一槽位的历史）
        existing.value = record.value
        existing.value_type = record.value_type
        existing.confidence = record.confidence
        existing.evidence = record.evidence
        existing.source_text = record.source_text
        existing.updated_at = record.updated_at
        existing.expires_at = record.expires_at
        existing.active = True
        self._save()
        return "updated"

    def upsert_many(self, records: list[MemoryRecord]) -> dict:
        out = {"added": 0, "updated": 0, "rejected": 0}
        for record in records or []:
            result = self.upsert(record)
            out[result] = out.get(result, 0) + 1
        return out

    def touch(self, slot_id: str):
        """标记一次命中（用于排序与统计）。"""
        record = self.get(slot_id)
        if record is not None:
            record.hits += 1
            self._save()

    # ── 遗忘 ────────────────────────────────────────────────
    def forget(self, slot_id: str, reason: str = "user_deleted") -> bool:
        record = self.get(slot_id)
        if record is None:
            return False
        record.active = False
        self._history.append({
            "memory_id": record.memory_id,
            "slot_id": record.slot_id,
            "value": record.value,
            "confidence": record.confidence,
            "evidence": record.evidence,
            "replaced_at": datetime.now().isoformat(timespec="seconds"),
            "reason": reason,
        })
        self._save()
        return True

    def forget_all(self) -> int:
        count = 0
        for record in list(self._records):
            if record.active:
                record.active = False
                count += 1
        if count:
            self._history.append({
                "slot_id": "*",
                "reason": "user_cleared_all",
                "count": count,
                "replaced_at": datetime.now().isoformat(timespec="seconds"),
            })
            self._save()
        return count

    def purge_expired(self) -> int:
        """把过期记忆标记为 inactive（保留记录，不再召回）。"""
        count = 0
        for record in self._records:
            if record.active and record.is_expired():
                record.active = False
                count += 1
        if count:
            self._save()
        return count

    # ── 维护 ────────────────────────────────────────────────
    def _enforce_limit(self):
        active = [r for r in self._records if r.active]
        if len(active) <= MAX_RECORDS:
            return
        # 淘汰顺序：低置信优先，其次旧的
        active.sort(key=lambda r: (r.confidence, r.updated_at))
        for record in active[:len(active) - MAX_RECORDS]:
            record.active = False
            self._history.append({
                "memory_id": record.memory_id,
                "slot_id": record.slot_id,
                "value": record.value,
                "reason": "evicted_low_confidence",
                "replaced_at": datetime.now().isoformat(timespec="seconds"),
            })

    def backup(self) -> str:
        """导出备份（一键清空前自动调用）。"""
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = "%s.backup_%s.json" % (self._path, stamp)
            if os.path.exists(self._path):
                shutil.copy2(self._path, dest)
            return dest
        except Exception as exc:  # noqa: BLE001
            print("[Memory] 备份失败: %s" % exc)
            return ""

    def summary(self) -> dict:
        active = self.all()
        by_kind: dict[str, int] = {}
        for record in active:
            by_kind[record.kind] = by_kind.get(record.kind, 0) + 1
        return {
            "active": len(active),
            "inactive": len([r for r in self._records if not r.active]),
            "history": len(self._history),
            "by_kind": by_kind,
        }
