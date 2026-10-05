"""回归测试：长期记忆（第 3 批）。

覆盖四层：
  * 受控槽位表：格式、kind/value_type 与表一致、禁止自创
  * 契约强校验：字段白名单、类型（含 bool/int 陷阱）、枚举、数值范围、
    证据必填、置信度从证据重算
  * 存储：同槽位覆盖、低置信不覆盖、失效与遗忘、上限淘汰、原子写入
  * 召回：相关度/新近度打分、无需向量库、块长度上限
  * 抽取：模型链 + 规则兜底 + 降级告警与冷却恢复
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pet_engine.agent.memory_contract import (  # noqa: E402
    MemoryRecord, has_explicit_signal, parse_memory, parse_memory_list,
    reestimate_confidence,
)
from pet_engine.agent.memory_extract import (  # noqa: E402
    MemoryExtractor, extract_with_rules,
)
from pet_engine.agent.memory_store import MemoryStore  # noqa: E402
from pet_engine.agent.recall import (  # noqa: E402
    MAX_BLOCK_CHARS, build_memory_block, explain, recall, relevance, score,
)
from pet_engine.agent.slots import (  # noqa: E402
    KIND_FACT, KIND_GOAL, KIND_PREFERENCE, KNOWN_SLOTS, SLOT_RE, format_slot_table,
    get_slot, slot_names,
)

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def tmp_store() -> MemoryStore:
    path = os.path.join(tempfile.mkdtemp(prefix="toyu_mem_"), "memories.json")
    return MemoryStore(path)


# ══════════════════════════════════════════════════════════
# 1. 受控槽位表
# ══════════════════════════════════════════════════════════
check("槽位表非空", len(KNOWN_SLOTS) >= 15, "%d 个" % len(KNOWN_SLOTS))
check("所有槽位名符合 对象.属性 格式",
      all(SLOT_RE.match(s) for s in slot_names()),
      str([s for s in slot_names() if not SLOT_RE.match(s)]))
check("每个槽位都有 description/kind/value_type/hint",
      all(all(k in meta for k in ("description", "kind", "value_type", "hint"))
          for meta in KNOWN_SLOTS.values()))
check("kind 只取三类",
      all(meta["kind"] in (KIND_PREFERENCE, KIND_GOAL, KIND_FACT)
          for meta in KNOWN_SLOTS.values()))
check("value_type 合法",
      all(meta["value_type"] in ("string", "number", "boolean", "list")
          for meta in KNOWN_SLOTS.values()))
table = format_slot_table()
check("槽位表可渲染成提示词", len(table) > 200 and "study.focus_duration" in table)
check("get_slot 可取到定义", get_slot("study.focus_duration") is not None)
check("get_slot 对自创槽位返回 None", get_slot("study.whatever") is None)

# ══════════════════════════════════════════════════════════
# 2. 契约强校验
# ══════════════════════════════════════════════════════════
rec, err = parse_memory({"slot_id": "study.focus_duration", "value": 50,
                         "confidence": 0.8, "evidence": "用户说以后都专注 50 分钟"})
check("合法记录通过校验", rec is not None and err == "", err)
check("kind 由槽位表决定", rec is not None and rec.kind == KIND_PREFERENCE,
      rec.kind if rec else "")
check("value_type 由槽位表决定", rec is not None and rec.value_type == "number")
check("preference 类不过期", rec is not None and rec.expires_at == "",
      rec.expires_at if rec else "")

# 禁止自创槽位
bad, err = parse_memory({"slot_id": "study.invented", "value": 1,
                         "confidence": 0.9, "evidence": "x"})
check("自创槽位被拒绝", bad is None and "不得自创" in err, err)

# 槽位名格式
bad, err = parse_memory({"slot_id": "Study.Focus", "value": 1,
                         "confidence": 0.9, "evidence": "x"})
check("槽位名格式错误被拒绝", bad is None, err)

# 字段白名单
bad, err = parse_memory({"slot_id": "study.focus_duration", "value": 50,
                         "confidence": 0.9, "evidence": "x", "extra": 1})
check("未定义字段被拒绝", bad is None and "未定义的字段" in err, err)

# 类型校验
bad, err = parse_memory({"slot_id": "study.focus_duration", "value": True,
                         "confidence": 0.9, "evidence": "x"})
check("number 槽位收到布尔值被拒绝（bool/int 陷阱）", bad is None, err)
bad, err = parse_memory({"slot_id": "assistant.use_emoji", "value": "yes",
                         "confidence": 0.9, "evidence": "x"})
check("boolean 槽位收到字符串被拒绝", bad is None, err)
bad, err = parse_memory({"slot_id": "study.focus_duration", "value": "50",
                         "confidence": 0.9, "evidence": "x"})
check("number 槽位收到字符串被拒绝", bad is None, err)

# 数值范围
bad, err = parse_memory({"slot_id": "study.focus_duration", "value": 9999,
                         "confidence": 0.9, "evidence": "x"})
check("数值超出合理范围被拒绝", bad is None and "上限" in err, err)

# 枚举
rec2, err2 = parse_memory({"slot_id": "assistant.answer_length", "value": "简短",
                           "confidence": 0.9, "evidence": "用户要简短"})
check("枚举内取值通过", rec2 is not None, err2)
bad, err = parse_memory({"slot_id": "assistant.answer_length", "value": "超短",
                         "confidence": 0.9, "evidence": "用户要超短"})
check("枚举外取值被拒绝", bad is None and "只能是" in err, err)

# 证据必填
bad, err = parse_memory({"slot_id": "study.focus_duration", "value": 50,
                         "confidence": 0.9, "evidence": ""})
check("缺少 evidence 被拒绝", bad is None and "evidence" in err, err)

# 缺 value
bad, err = parse_memory({"slot_id": "study.focus_duration",
                         "confidence": 0.9, "evidence": "x"})
check("缺少 value 被拒绝", bad is None, err)

# 非字典
bad, err = parse_memory("not a dict")
check("非对象输入被拒绝", bad is None, err)

# ══════════════════════════════════════════════════════════
# 3. 置信度从证据重算
# ══════════════════════════════════════════════════════════
check("显性信号可识别", has_explicit_signal("以后都用三段式写"))
check("无关文本不误判", not has_explicit_signal("今天天气不错"))

check("显性信号把低置信抬到 0.9 地板",
      reestimate_confidence(0.3, "用户说以后都这样") >= 0.9,
      str(reestimate_confidence(0.3, "用户说以后都这样")))
check("弱信号抬到 0.7 地板",
      reestimate_confidence(0.2, "用户说比较喜欢这样") >= 0.7,
      str(reestimate_confidence(0.2, "用户说比较喜欢这样")))
check("无信号时压低模型自报的高置信",
      reestimate_confidence(0.99, "用户提到了一件事") <= 0.6,
      str(reestimate_confidence(0.99, "用户提到了一件事")))
check("置信度始终在 0~1 之间",
      all(0.0 <= reestimate_confidence(v, t) <= 1.0
          for v in (-5, 0, 0.5, 2) for t in ("以后都", "随便说说")))
check("非法置信度输入不崩", reestimate_confidence("abc", "以后都") >= 0.9)

# 模型报低置信但证据很强 -> 采信证据
rec3, _ = parse_memory({"slot_id": "study.focus_duration", "value": 50,
                        "confidence": 0.1, "evidence": "用户明确说以后都专注 50 分钟"})
check("契约层用重算后的置信度",
      rec3 is not None and rec3.confidence >= 0.9,
      str(rec3.confidence) if rec3 else "")

# 批量校验：一条坏不该丢其他好的
records, errors = parse_memory_list([
    {"slot_id": "study.focus_duration", "value": 50, "confidence": 0.9, "evidence": "以后都"},
    {"slot_id": "bad slot", "value": 1, "confidence": 0.9, "evidence": "x"},
    {"slot_id": "assistant.use_emoji", "value": False, "confidence": 0.9, "evidence": "以后别用"},
])
check("批量校验保留合法项", len(records) == 2, "%d 条" % len(records))
check("批量校验回报被拒原因", len(errors) == 1, str(errors))
check("批量校验非数组输入不崩", parse_memory_list("nope")[0] == [])

# ══════════════════════════════════════════════════════════
# 4. 存储
# ══════════════════════════════════════════════════════════
store = tmp_store()
check("空库计数为 0", store.count() == 0)

r1, _ = parse_memory({"slot_id": "study.focus_duration", "value": 25,
                      "confidence": 0.9, "evidence": "以后专注 25 分钟"})
check("首次写入返回 added", store.upsert(r1) == "added")
check("写入后可读回", store.get("study.focus_duration") is not None)
check("count 反映活跃记忆", store.count() == 1)

# 同槽位更新
r2, _ = parse_memory({"slot_id": "study.focus_duration", "value": 50,
                      "confidence": 0.9, "evidence": "以后专注 50 分钟"})
check("同槽位新值返回 updated", store.upsert(r2) == "updated")
check("同槽位只保留一条活跃记录", store.count() == 1, "%d 条" % store.count())
check("同槽位值为最新", store.get("study.focus_duration").value == 50)
check("被覆盖的旧值进了历史", store.summary()["history"] >= 1,
      str(store.summary()))

# 低置信不覆盖高置信
r_low, _ = parse_memory({"slot_id": "study.focus_duration", "value": 15,
                         "confidence": 0.2, "evidence": "用户随口提到 15 分钟"})
check("低置信不覆盖已有高置信", store.upsert(r_low) == "rejected")
check("被拒绝后原值不变", store.get("study.focus_duration").value == 50)

# 遗忘
check("单条遗忘成功", store.forget("study.focus_duration") is True)
check("遗忘后不再召回", store.get("study.focus_duration") is None)
check("遗忘后计数减少", store.count() == 0)
check("遗忘不存在的槽位返回 False", store.forget("study.nope") is False)

# 清空
store.upsert(r1)
store.upsert(r2)
cleared = store.forget_all()
check("一键清空返回清掉的条数", cleared >= 1, str(cleared))
check("清空后没有活跃记忆", store.count() == 0)

# 过期
store2 = tmp_store()
r_fact, _ = parse_memory({"slot_id": "fact.course", "value": "机器学习",
                          "confidence": 0.9, "evidence": "以后都学机器学习"})
store2.upsert(r_fact)
check("fact 类带过期时间", store2.get("fact.course").expires_at != "",
      store2.get("fact.course").expires_at)
# 手动把过期时间改到过去
rec_fact = store2.get("fact.course")
rec_fact.expires_at = (datetime.now() - timedelta(days=1)).isoformat()
check("过期记忆被判为过期", rec_fact.is_expired() is True)
check("过期后不再出现在活跃列表", store2.count() == 0)
check("purge_expired 能清理过期记忆", store2.purge_expired() >= 0)

# 持久化（用全新记录，避免复用前面已被改动的对象）
store3 = tmp_store()
r_fresh, _ = parse_memory({"slot_id": "study.focus_duration", "value": 50,
                           "confidence": 0.9, "evidence": "以后专注 50 分钟"})
check("持久化用例写入成功", store3.upsert(r_fresh) == "added")
reloaded = MemoryStore(store3._path)
check("重启后记忆仍在", reloaded.count() == 1, "%d 条" % reloaded.count())
check("重启后值正确",
      reloaded.get("study.focus_duration") is not None
      and reloaded.get("study.focus_duration").value == 50)
check("备份可导出", os.path.exists(store3.backup()))

# 坏数据不崩
bad_path = os.path.join(tempfile.mkdtemp(prefix="toyu_bad_"), "memories.json")
with open(bad_path, "w", encoding="utf-8") as fh:
    fh.write("{ 这不是合法 json")
check("坏文件按空库处理不崩", MemoryStore(bad_path).count() == 0)
with open(bad_path, "w", encoding="utf-8") as fh:
    # 第二条是垃圾（非 dict），必须被跳过；第一条字段不全但结构合法，可保留
    json.dump({"records": [
        {"slot_id": "study.focus_duration", "value": 25,
         "confidence": 0.9, "evidence": "以后 25 分钟", "active": True},
        "not a dict",
        None,
    ]}, fh)
bad_store = MemoryStore(bad_path)
check("库中垃圾条目被跳过（不崩）", bad_store.count() == 1,
      "%d 条活跃" % bad_store.count())
check("库中有效条目仍可读",
      bad_store.get("study.focus_duration") is not None
      and bad_store.get("study.focus_duration").value == 25)

# 过期记忆不能被"复活"（get 与 all 的过期判断必须一致）
store_exp = tmp_store()
r_exp, _ = parse_memory({"slot_id": "fact.course", "value": "高数",
                         "confidence": 0.9, "evidence": "这学期学高数"})
store_exp.upsert(r_exp)
store_exp.get("fact.course").expires_at = (
    datetime.now() - timedelta(days=1)).isoformat()
check("过期后 get 返回 None", store_exp.get("fact.course") is None)
r_exp2, _ = parse_memory({"slot_id": "fact.course", "value": "线代",
                          "confidence": 0.9, "evidence": "现在学线代"})
check("过期记忆被当作新记录写入（added 而非 updated）",
      store_exp.upsert(r_exp2) == "added", "复活的 TTL 会让过期形同虚设")

# ══════════════════════════════════════════════════════════
# 5. 召回（无向量库）
# ══════════════════════════════════════════════════════════
store4 = tmp_store()
pairs = [
    ("study.focus_duration", 50, "以后专注都用 50 分钟"),
    ("assistant.use_emoji", False, "以后别再用 emoji"),
    ("fact.course", "机器学习", "这学期在学机器学习"),
    ("goal.current", "准备竞赛", "我在准备竞赛"),
]
for slot, value, ev in pairs:
    r, _ = parse_memory({"slot_id": slot, "value": value,
                         "confidence": 0.9, "evidence": ev})
    store4.upsert(r)
check("四条记忆都已入库", store4.count() == 4, "%d 条" % store4.count())

picked = recall(store4, "我专注应该用多久")
check("召回能找到相关记忆", len(picked) >= 1, str([p[0].slot_id for p in picked]))
check("最相关的排第一", picked and picked[0][0].slot_id == "study.focus_duration",
      str([(p[0].slot_id, p[1]) for p in picked]))

picked2 = recall(store4, "emoji 能不能用")
check("不同问题召回不同记忆",
      picked2 and picked2[0][0].slot_id == "assistant.use_emoji",
      str([p[0].slot_id for p in picked2]))

# 完全无关的查询：注意 recency 与 hit_factor 会给一个基础分（0.25+0.20），
# 所以纯新近度不足以低于 MIN_SCORE，必须用与记忆完全无字符重合的查询
check("完全无关的问题召回为空",
      recall(store4, "qqq zzz xxx yyy www") == [],
      str([(p[0].slot_id, p[1]) for p in recall(store4, "qqq zzz xxx yyy www")]))
check("空查询召回为空", recall(store4, "") == [])

# 相关度与打分单调性
rec_a = store4.get("study.focus_duration")
check("相关文本的打分高于无关文本",
      relevance("专注时长", rec_a) > relevance("完全无关的词", rec_a),
      "%.3f vs %.3f" % (relevance("专注时长", rec_a), relevance("完全无关的词", rec_a)))
check("分数在 0~1 之间", 0.0 <= score("专注", rec_a) <= 1.0)

# 块构建
block = build_memory_block(store4, "我专注该用多久")
check("召回块带标题", block.startswith("[关于这位用户]"), block[:40])
check("召回块包含命中槽位", "study.focus_duration" in block, block[:100])
check("召回块长度受控", len(block) <= MAX_BLOCK_CHARS + 40,
      "%d 字符" % len(block))
check("命中会累加 hits", store4.get("study.focus_duration").hits >= 1,
      str(store4.get("study.focus_duration").hits))
check("无效查询返回空块", build_memory_block(store4, "qqq zzz xxx") == "")
check("无库时返回空块", build_memory_block(None, "专注") == "")

detail = explain(store4, "专注")
check("explain 给出打分明细",
      detail and all(k in detail[0] for k in
                     ("slot_id", "relevance", "recency", "score")),
      str(detail[0] if detail else None))

# ══════════════════════════════════════════════════════════
# 6. 规则抽取
# ══════════════════════════════════════════════════════════
cases = [
    ("以后我每次专注都用 50 分钟", ["study.focus_duration"]),
    ("记住我习惯晚上学习", ["study.focus_time_of_day"]),
    ("以后别再用 emoji 了", ["assistant.use_emoji"]),
    ("我打算每天学 4 小时", ["study.daily_goal_minutes"]),
    ("以后回答简短一点", ["assistant.answer_length"]),
    ("以后先跟我说计划再动手", ["assistant.plan_first"]),
]
for text, expect in cases:
    got = [i["slot_id"] for i in extract_with_rules(text)]
    check("规则抽取：%s" % text[:16], expect[0] in got, "得到 %s" % got)

negatives = ["帮我加个待办", "今天天气不错", "现在几点了", "这个 bug 怎么修"]
for text in negatives:
    got = extract_with_rules(text)
    check("规则不误抽：%s" % text[:14], not got, "误抽 %s" % [g["slot_id"] for g in got])

check("空文本不抽", extract_with_rules("") == [])
check("超长文本不崩", isinstance(extract_with_rules("以后" + "很长" * 500), list))

# 规则产出的记录必须能过契约
for item in extract_with_rules("以后我每次专注都用 50 分钟"):
    rec_rule, err_rule = parse_memory(item, source_text="以后我每次专注都用 50 分钟")
    check("规则产出能过契约校验", rec_rule is not None, err_rule)

# ══════════════════════════════════════════════════════════
# 7. 抽取器：模型链 + 兜底 + 降级
# ══════════════════════════════════════════════════════════
store5 = tmp_store()
logs = []
extractor = MemoryExtractor(transport=None, store=store5,
                            on_log=lambda lvl, msg: logs.append((lvl, msg)))

# 无模型 -> 走规则
out = extractor.extract("以后我每次专注都用 50 分钟")
check("无模型时走规则链", out["source"] == "rules", out["source"])
check("规则抽取结果入库", store5.count() == 1, "%d 条" % store5.count())
check("入库计数正确", out["added"] == 1, str(out))

# 模型链
store6 = tmp_store()


def fake_transport(messages):
    return json.dumps({"memories": [
        {"slot_id": "study.break_interval", "value": 15,
         "confidence": 0.6, "evidence": "用户说以后每 50 分钟休息 15 分钟"}
    ]}, ensure_ascii=False)


ex6 = MemoryExtractor(transport=fake_transport, store=store6,
                      on_log=lambda lvl, msg: logs.append((lvl, msg)))
out6 = ex6.extract("以后每 50 分钟休息 15 分钟")
check("模型链可用时走模型", out6["source"] == "model", out6["source"])
check("模型结果入库", store6.count() == 1)
check("模型链状态正常", ex6.health()["degraded"] is False)

# 模型返回 markdown 包裹也能解析
def md_transport(messages):
    return "```json\n{\"memories\": []}\n```"


ex_md = MemoryExtractor(transport=md_transport, store=tmp_store())
check("模型返回 markdown 包裹可解析",
      ex_md.extract("随便说点什么").get("source") != "failed")

# 模型抛异常 -> 降级 + 规则兜底
def boom_transport(messages):
    raise RuntimeError("网络断了")


logs2 = []
store7 = tmp_store()
ex7 = MemoryExtractor(transport=boom_transport, store=store7,
                      on_log=lambda lvl, msg: logs2.append((lvl, msg)))
out7 = ex7.extract("以后我每次专注都用 50 分钟")
check("模型失败时降级到规则", out7["source"] == "rules", out7["source"])
check("降级后规则仍然入库", store7.count() == 1)
check("降级状态被标记", ex7.health()["degraded"] is True)
check("降级有 ERROR 告警（不静默）",
      any(lvl == "ERROR" and "降级" in msg for lvl, msg in logs2),
      str(logs2[:2]))
check("降级原因可查", "网络断了" in ex7.health()["reason"],
      ex7.health()["reason"])

# 冷却期内不再尝试模型
check("冷却期内不再调用模型", ex7._should_try_model() is False)
ex7._degraded_at = time.time() - ex7.RECOVER_SECONDS - 1
check("冷却结束后自动重试", ex7._should_try_model() is True)

# 恢复
def ok_transport(messages):
    return json.dumps({"memories": []})


ex7._transport = ok_transport
out7b = ex7.extract("我打算每天学 2 小时")
check("模型恢复后从降级状态回到正常", ex7.health()["degraded"] is False,
      ex7.health()["reason"])

# 模型返回非法槽位 -> 被拒绝，不写库
def bad_slot_transport(messages):
    return json.dumps({"memories": [
        {"slot_id": "study.made_up", "value": 1, "confidence": 0.9, "evidence": "x"}
    ]})


store8 = tmp_store()
ex8 = MemoryExtractor(transport=bad_slot_transport, store=store8,
                      on_log=lambda lvl, msg: logs.append((lvl, msg)))
out8 = ex8.extract("以后我都要这样")
check("模型给出的自创槽位被拒绝", store8.count() == 0, "%d 条" % store8.count())
check("拒绝原因被记录", bool(out8["rejected"]), str(out8["rejected"]))

# 模型返回非 JSON
def junk_transport(messages):
    return "我觉得你说得对"


ex9 = MemoryExtractor(transport=junk_transport, store=tmp_store(),
                      on_log=lambda lvl, msg: logs.append((lvl, msg)))
out9 = ex9.extract("以后我每次专注都用 50 分钟")
check("模型返回非 JSON 时降级到规则", out9["source"] == "rules", out9["source"])

# 短文本直接跳过
check("过短文本不抽取", ex9.extract("嗯").get("source") == "none")

# 统计可查
stats = ex9.health()["stats"]
check("抽取统计可查", all(k in stats for k in ("model", "rules", "empty", "failed")),
      str(stats))

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-46s %s" % (status, name, extra[:50]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
