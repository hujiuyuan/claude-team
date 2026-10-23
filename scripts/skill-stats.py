"""每周统计 skill / agent / slash 命令 / MCP 的使用量与返工信号。
用法: python3 -I scripts/skill-stats.py [天数=7]   每周复跑，看各 skill / agent / 插件的调用量和返工信号
返工信号: 某组件被调用后, 同一会话接下来 3 条用户真人消息里出现纠正词或中断。
"""
import json, os, re, sys, glob, time
from collections import defaultdict

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7
since = time.time() - DAYS * 86400
ROOT = os.path.expanduser("~/.claude/projects")
FIX = re.compile(r"不对|错了|重来|重新|返工|不是这样|不是我要|还是不行|没用|搞错|改回|撤回|别这样|不要这样|你没|漏了|又错|wrong|redo|revert|undo|not what", re.I)
INTR = "[Request interrupted"
WINDOW = 3

stats = defaultdict(lambda: {"calls": 0, "sessions": set(), "rework": 0, "errors": 0, "samples": []})

def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""

for path in glob.glob(f"{ROOT}/**/*.jsonl", recursive=True):
    if os.path.getmtime(path) < since:
        continue
    sub = "/subagents/" in path
    pending = []  # [key, remaining_user_msgs, flagged]
    tool_ids = {}
    with open(path, errors="ignore") as fh:
        for line in fh:
            if '"attachment"' in line[:200] and '"prompt_snapshot"' in line[:400]:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            msg = e.get("message") or {}
            role = msg.get("role")
            content = msg.get("content")
            keys = []
            if role == "assistant" and isinstance(content, list):
                for c in content:
                    if c.get("type") != "tool_use":
                        continue
                    n, inp = c.get("name", ""), c.get("input") or {}
                    if n == "Skill":
                        k = "skill:" + str(inp.get("skill"))
                    elif n in ("Agent", "Task"):
                        k = "agent:" + str(inp.get("subagent_type") or "general-purpose")
                    elif n.startswith("mcp__"):
                        k = "mcp:" + n.split("__")[1]
                    else:
                        continue
                    keys.append(k)
                    tool_ids[c.get("id")] = k
            elif role == "user":
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error") and c.get("tool_use_id") in tool_ids:
                            stats[tool_ids[c["tool_use_id"]]]["errors"] += 1
                t = text_of(content)
                m = re.search(r"<command-name>/?([^<]+)</command-name>", t)
                if m:
                    keys.append("slash:" + m.group(1).strip())
                human = t and not t.startswith(("<", "This session is being continued", "Another Claude session")) and not any(isinstance(c, dict) and c.get("type") == "tool_result" for c in (content if isinstance(content, list) else []))
                if (human or INTR in t) and not sub:
                    bad = INTR in t or bool(FIX.search(t[:500]))
                    for p in pending:
                        if bad and not p[2]:
                            p[2] = True
                            stats[p[0]]["rework"] += 1
                            if len(stats[p[0]]["samples"]) < 3:
                                stats[p[0]]["samples"].append(t[:80].replace("\n", " "))
                        p[1] -= 1
                    pending = [p for p in pending if p[1] > 0]
            for k in keys:
                s = stats[k]
                s["calls"] += 1
                s["sessions"].add(path)
                if not sub:
                    pending.append([k, WINDOW, False])

rows = sorted(stats.items(), key=lambda kv: -kv[1]["calls"])
print(f"近 {DAYS} 天 | 组件 | 调用 | 会话 | 返工 | 返工率 | 报错")
for k, s in rows:
    rate = s["rework"] / s["calls"] if s["calls"] else 0
    print(f"{k} | {s['calls']} | {len(s['sessions'])} | {s['rework']} | {rate:.0%} | {s['errors']}")
print("\n## 返工样本")
for k, s in rows:
    for x in s["samples"]:
        print(f"{k}: {x}")
