#!/usr/bin/env python3
"""从 templates/role/ 生成新角色或新技能，并登记到 marketplace.json。

用法：
  python3 scripts/scaffold.py role <角色名> -d "<一句话定位>" [--skill <技能名> ...] [--readonly] [--color blue]
  python3 scripts/scaffold.py skill <角色名> <技能名> -d "<什么时候用这个技能>"

只依赖 Python 3 标准库。生成后记得把文件里的 TODO 填完，再运行 scripts/validate.py。
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "role"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RESERVED_PREFIXES = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")
COLORS = ("red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan")
READONLY_TOOLS = "tools: Read, Grep, Glob, Bash, WebSearch, WebFetch, Skill\n"


def die(msg):
    sys.exit(f"✗ {msg}")


def check_name(name, kind):
    if not NAME_RE.match(name):
        die(f"{kind}名 '{name}' 只能用小写字母、数字和连字符，例如 data-analyst")
    if name.startswith(RESERVED_PREFIXES):
        die(f"{kind}名不能以 {', '.join(RESERVED_PREFIXES)} 开头")


def render(text, **values):
    for key, value in values.items():
        text = text.replace(f"__{key.upper()}__", value)
    return text


def yaml_str(text):
    """description 里可能有冒号等 YAML 特殊字符，统一用 JSON 风格的双引号字符串（也是合法 YAML）。"""
    return json.dumps(text, ensure_ascii=False)


def write_new(path, content):
    if path.exists():
        die(f"{path.relative_to(ROOT)} 已存在")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  + {path.relative_to(ROOT)}")


def add_skill(role, skill, description):
    check_name(skill, "技能")
    role_dir = ROOT / "roles" / role
    if not role_dir.is_dir():
        die(f"角色 '{role}' 不存在")
    for other in (ROOT / "roles").glob(f"*/skills/{skill}"):
        die(f"技能名 '{skill}' 已被 {other.relative_to(ROOT)} 使用")
    template = (TEMPLATE / "skills" / "__SKILL__" / "SKILL.md").read_text(encoding="utf-8")
    write_new(role_dir / "skills" / skill / "SKILL.md",
              render(template, skill=skill, description=yaml_str(description)))

    agent = role_dir / "agents" / f"{role}.md"
    if not agent.is_file():
        return
    text = agent.read_text(encoding="utf-8")
    end = text.find("\n---", 4)
    head, body = text[:end], text[end:]
    entry = f"  - {role}:{skill}"
    if entry in head:
        return
    if re.search(r"^skills:\s*$", head, re.M):
        lines = head.split("\n")
        i = next(n for n, line in enumerate(lines) if re.match(r"^skills:\s*$", line))
        while i + 1 < len(lines) and lines[i + 1].startswith("  - "):
            i += 1
        lines.insert(i + 1, entry)
        head = "\n".join(lines)
    else:
        head += f"\nskills:\n{entry}"
    agent.write_text(head + body, encoding="utf-8")
    print(f"  ~ {agent.relative_to(ROOT)}（skills 列表加入 {role}:{skill}）")


def cmd_role(args):
    role = args.role
    check_name(role, "角色")
    if args.color not in COLORS:
        die(f"color 只能是 {', '.join(COLORS)}")
    if (ROOT / "roles" / role).exists():
        die(f"roles/{role} 已存在")
    market = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    if any(p["name"] == role for p in market["plugins"]):
        die(f"marketplace.json 里已有 '{role}'")

    manifest = json.loads((TEMPLATE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    manifest["name"] = role
    manifest["description"] = args.description
    write_new(ROOT / "roles" / role / ".claude-plugin" / "plugin.json",
              json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    template = (TEMPLATE / "agents" / "__ROLE__.md").read_text(encoding="utf-8")
    write_new(ROOT / "roles" / role / "agents" / f"{role}.md",
              render(template, role=role, description=yaml_str(args.description),
                     tools=READONLY_TOOLS if args.readonly else "", color=args.color))

    for skill in args.skill:
        add_skill(role, skill, f"TODO：{skill} 做什么、什么时候用、用户会怎么说")

    market["plugins"].append({
        "name": role,
        "source": f"./roles/{role}",
        "description": args.description,
        "category": "role",
    })
    MARKETPLACE.write_text(json.dumps(market, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  ~ .claude-plugin/marketplace.json（登记 {role}）")
    print(f"\n下一步：填完 roles/{role}/ 里的 TODO，然后运行 python3 scripts/validate.py")


def cmd_skill(args):
    add_skill(args.role, args.skill, args.description)
    print(f"\n下一步：填完 roles/{args.role}/skills/{args.skill}/SKILL.md 里的 TODO，然后运行 python3 scripts/validate.py")


def main():
    parser = argparse.ArgumentParser(description="生成新角色或新技能")
    sub = parser.add_subparsers(dest="command", required=True)

    p_role = sub.add_parser("role", help="新建角色")
    p_role.add_argument("role")
    p_role.add_argument("-d", "--description", required=True, help="一句话定位：它是谁、什么时候交给它")
    p_role.add_argument("--skill", action="append", default=[], help="同时创建的技能名，可重复")
    p_role.add_argument("--readonly", action="store_true", help="只读角色：不给 Write/Edit 工具")
    p_role.add_argument("--color", default="cyan", help="界面上的颜色")
    p_role.set_defaults(func=cmd_role)

    p_skill = sub.add_parser("skill", help="给已有角色新增技能")
    p_skill.add_argument("role")
    p_skill.add_argument("skill")
    p_skill.add_argument("-d", "--description", required=True, help="什么时候用这个技能")
    p_skill.set_defaults(func=cmd_skill)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
