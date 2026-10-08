#!/usr/bin/env python3
"""校验 claude-team 仓库结构，保证在任何一台电脑上都能正常安装。

检查项：
  - .claude-plugin/marketplace.json 与 roles/ 下的目录一一对应
  - 每个角色都有 .claude-plugin/plugin.json，name 与目录名一致；普通角色依赖 team
  - agents/*.md、skills/*/SKILL.md 有 frontmatter，name 合法且与文件/目录名一致
  - agent 的 skills: 列表引用的技能真实存在、来自自己或已声明的依赖，且包含 team:house-rules
    （Claude Code 遇到不存在的技能会静默跳过，所以要在这里拦住）
  - 全仓库 agent 名、skill 名唯一（省略前缀调用时不会撞名）
  - 没有残留模板占位符（TODO：等）；同一插件里各 agent 的 description 不重复
  - team 核心里的 agent 必须显式声明 tools，且不能有写文件或派生子代理的工具（防止辩证裁决递归、误改文件）
  - 敏感词：仓库是公开的，用本机词表（不入库）检查所有文件，见 README“敏感词检查”

只依赖 Python 3 标准库。用法：python3 scripts/validate.py
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = "team"
CORE_SKILL = f"{CORE}:house-rules"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RESERVED_PREFIXES = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")
MAX_DESCRIPTION = 1024
TEMPLATE_MARKERS = ("TODO：", "TODO:", "**TODO**", "TODO 角色中文名", "TODO 技能标题")
CORE_FORBIDDEN_TOOLS = {"Agent", "Task", "Write", "Edit", "MultiEdit", "NotebookEdit"}
SENSITIVE_FILE = Path(os.environ.get("CLAUDE_TEAM_SENSITIVE_WORDS", ROOT / ".sensitive-words.txt"))

errors = []


def err(msg):
    errors.append(msg)


def rel(path):
    return path.relative_to(ROOT).as_posix()


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        err(f"{rel(path)}: 文件不存在")
    except json.JSONDecodeError as e:
        err(f"{rel(path)}: JSON 格式错误: {e}")
    return None


def frontmatter(path):
    """解析 frontmatter 的顶层字段：标量、多行字符串、`- item` 列表、`[a, b]` 行内列表。
    够本仓库用即可，不依赖 PyYAML。"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        err(f"{rel(path)}: 缺少 YAML frontmatter（文件需以 --- 开头）")
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        err(f"{rel(path)}: frontmatter 没有结束的 ---")
        return {}
    if not text[end + 4:].strip():
        err(f"{rel(path)}: frontmatter 之后没有正文")

    fields, key = {}, None
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            elif value in ("|", ">", "|-", ">-"):
                value = ""
            else:
                value = value.strip("'\"")
            fields[key] = value
            continue
        if key is None or not line.startswith((" ", "\t")) or not line.strip():
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and (fields[key] == "" or isinstance(fields[key], list)):
            fields[key] = (fields[key] or []) + [item.group(1).strip().strip("'\"")]
        elif isinstance(fields[key], str):
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def check_placeholders(path):
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if any(m in line for m in TEMPLATE_MARKERS):
            err(f"{rel(path)}:{n}: 还有模板占位符没填（{line.strip()[:40]}）")


def check_sensitive():
    """仓库是公开的：用本机词表检查所有文件。词表本身属于内部信息，不入库。"""
    if not SENSITIVE_FILE.is_file():
        return 0
    words = [w.strip() for w in SENSITIVE_FILE.read_text(encoding="utf-8").splitlines()
             if w.strip() and not w.strip().startswith("#")]
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard"],
                             capture_output=True, text=True, check=True).stdout
        files = [ROOT / f for f in out.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        files = [p for p in ROOT.rglob("*") if ".git" not in p.parts]
    for f in files:
        if not f.is_file() or f.resolve() == SENSITIVE_FILE.resolve():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lower = text.lower()
        for w in words:
            if w.lower() in lower:
                line = lower[:lower.index(w.lower())].count("\n") + 1
                err(f"{rel(f)}:{line}: 含敏感词表里的词（公开仓库不能写内部信息）")
    return len(words)


def check_named(path, fields, expected, kind):
    name = fields.get("name", "")
    if not name:
        err(f"{rel(path)}: 缺少 name")
    elif not NAME_RE.match(name):
        err(f"{rel(path)}: name '{name}' 只能用小写字母、数字和连字符")
    elif name != expected:
        err(f"{rel(path)}: name '{name}' 应与{kind}名 '{expected}' 一致")
    desc = fields.get("description", "")
    if not desc:
        err(f"{rel(path)}: 缺少 description（Claude 靠它判断何时调用）")
    elif len(desc) > MAX_DESCRIPTION:
        err(f"{rel(path)}: description 超过 {MAX_DESCRIPTION} 字符")
    return name


def main():
    market = load_json(ROOT / ".claude-plugin" / "marketplace.json") or {}
    entries = {p.get("name"): p for p in market.get("plugins", [])}

    role_dirs = sorted(p for p in (ROOT / "roles").iterdir() if p.is_dir())
    role_names = {d.name for d in role_dirs}
    if CORE not in role_names:
        err(f"缺少核心角色 roles/{CORE}")
    for d in role_dirs:
        if d.name not in entries:
            err(f"{rel(d)}: 没有登记到 marketplace.json 的 plugins 里")
        if d.name.startswith(RESERVED_PREFIXES):
            err(f"{rel(d)}: 角色名不能以 {', '.join(RESERVED_PREFIXES)} 开头")
    for name, entry in entries.items():
        if name not in role_names:
            err(f"marketplace.json: 插件 '{name}' 在 roles/ 下没有对应目录")
        elif entry.get("source") != f"./roles/{name}":
            err(f"marketplace.json: 插件 '{name}' 的 source 应为 './roles/{name}'")

    # 先收集全部技能，再检查 agent 的引用
    skills = {}  # "角色:技能" -> frontmatter
    skill_owner = {}
    for d in role_dirs:
        skills_dir = d / "skills"
        for s in sorted(p for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []:
            skill_md = s / "SKILL.md"
            if not skill_md.is_file():
                err(f"{rel(s)}: 缺少 SKILL.md")
                continue
            fm = frontmatter(skill_md)
            for doc in sorted(s.rglob("*.md")):
                check_placeholders(doc)
            name = check_named(skill_md, fm, s.name, "目录")
            if name in skill_owner:
                err(f"skill 重名: '{name}' 同时出现在 {skill_owner[name]} 和 {d.name}")
            skill_owner[name] = d.name
            skills[f"{d.name}:{s.name}"] = fm

    agent_owner = {}
    for d in role_dirs:
        manifest = load_json(d / ".claude-plugin" / "plugin.json") or {}
        if manifest.get("name") != d.name:
            err(f"{rel(d)}/.claude-plugin/plugin.json: name 应为 '{d.name}'")
        if "version" in manifest or "version" in entries.get(d.name, {}):
            err(f"{rel(d)}: 不要写 version 字段（版本取自 git 提交，写了就得每次手动改）")
        deps = {dep if isinstance(dep, str) else dep.get("name") for dep in manifest.get("dependencies", [])}
        if d.name != CORE and CORE not in deps:
            err(f"{rel(d)}/.claude-plugin/plugin.json: dependencies 需要包含 '{CORE}'")

        agents = sorted((d / "agents").glob("*.md")) if (d / "agents").is_dir() else []
        if not agents and not (d / "skills").is_dir():
            err(f"{rel(d)}: 角色里既没有 agent 也没有 skill")
        descriptions = {}
        for a in agents:
            fm = frontmatter(a)
            check_placeholders(a)
            name = check_named(a, fm, a.stem, "文件")
            desc = fm.get("description", "")
            if desc and desc in descriptions:
                err(f"{rel(a)}: description 与 {descriptions[desc]} 相同，Claude 无法区分该派给谁")
            descriptions[desc] = a.name
            if d.name == CORE:
                tools = fm.get("tools", "")
                tools = set(tools) if isinstance(tools, list) else {x.strip() for x in tools.split(",") if x.strip()}
                if not tools:
                    err(f"{rel(a)}: team 里的 agent 必须显式声明 tools")
                elif tools & CORE_FORBIDDEN_TOOLS:
                    err(f"{rel(a)}: team 里的 agent 不能有 {', '.join(sorted(tools & CORE_FORBIDDEN_TOOLS))}")
            if name in agent_owner:
                err(f"agent 重名: '{name}' 同时出现在 {agent_owner[name]} 和 {d.name}")
            agent_owner[name] = d.name

            preload = fm.get("skills", [])
            if isinstance(preload, str):
                preload = [preload] if preload else []
            if CORE_SKILL not in preload:
                err(f"{rel(a)}: skills 列表需要包含 {CORE_SKILL}")
            for ref in preload:
                plugin, _, skill = ref.partition(":")
                if not skill:
                    err(f"{rel(a)}: skills 里的 '{ref}' 要写成 <插件>:<技能> 全名")
                elif ref not in skills:
                    err(f"{rel(a)}: skills 引用的 '{ref}' 不存在（运行时会被静默跳过）")
                elif plugin != d.name and plugin not in deps:
                    err(f"{rel(a)}: 引用了 '{ref}'，但 plugin.json 的 dependencies 没有 '{plugin}'")
                elif str(skills[ref].get("disable-model-invocation", "")).lower() == "true":
                    err(f"{rel(a)}: '{ref}' 设置了 disable-model-invocation，不能预加载")

    n_words = check_sensitive()

    if errors:
        print(f"✗ 发现 {len(errors)} 个问题：")
        for e in errors:
            print(f"  - {e}")
        return 1
    note = f"，敏感词 {n_words} 个" if n_words else "，未配置敏感词表"
    print(f"✓ {len(role_dirs)} 个角色，{len(agent_owner)} 个 agent，{len(skills)} 个 skill，全部通过{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
