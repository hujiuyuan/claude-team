---
name: new-role
description: 在 claude-team 仓库里新建一个角色（agent 提示词 + 专属 skill），或给已有角色新增 skill。用户说“新建角色”“加一个 xx 角色”“把这类工作交给一个专门的角色”“给 xx 角色加个技能”时使用。
argument-hint: <角色名或一句话描述>
---

# 新建角色 / 新增技能

需求：$ARGUMENTS

## 0. 定位仓库

按顺序找 claude-team 仓库的本地克隆：

1. 环境变量 `CLAUDE_TEAM_HOME`
2. `~/claude-team`
3. 都没有：问我放在哪，然后 `git clone https://github.com/hujiuyuan/claude-team.git <路径>`

进入仓库后先 `git pull --ff-only`，不要在旧版本上改。仓库根目录的 `CLAUDE.md` 有约定，先读。

## 1. 访谈（一次问完，每项给出你建议的默认值）

如果当前对话里已经有足够信息，直接起草，不要重复问。

- **名字**：英文小写加短横线，如 `data-analyst`；不能以 `claude-`、`anthropic-` 开头，不能和已有角色重名。
- **定位**：一句话说清它是谁、什么时候该交给它。
- **职责与边界**：负责什么，明确不负责什么。
- **典型任务**：两三个真实例子。
- **我的习惯**：我在这类工作上的偏好、标准、模板、检查清单、常用命令、禁忌。越具体越好。
- **工具权限**：只读（Read, Grep, Glob）、可改文件（+ Write, Edit）、可执行命令（+ Bash）、可联网（+ WebSearch, WebFetch）。
- **技能**：哪些可重复的流程、模板、清单值得做成独立 skill。

## 2. 生成骨架

```bash
# 新角色（--readonly 表示不给写文件工具；--skill 可重复）
python3 scripts/scaffold.py role <角色名> -d "<一句话定位>" --skill <技能名>
# 给已有角色加技能
python3 scripts/scaffold.py skill <角色名> <技能名> -d "<什么时候用这个技能>"
```

脚本会从 `templates/role/` 生成文件，登记到 `.claude-plugin/marketplace.json`，并把技能写进 agent 的 `skills:` 列表。

## 3. 填写内容

- `roles/<角色名>/agents/<角色名>.md`：角色提示词，把模板里的 TODO 全部替换掉。
- `roles/<角色名>/skills/<技能名>/SKILL.md`：每个技能的具体步骤、模板、清单。

怎么写好提示词和技能，见 [authoring-guide.md](authoring-guide.md)。写完把草稿给我过目。

## 4. 校验与提交

```bash
python3 scripts/validate.py
claude plugin validate .              # 有 claude 命令时
git add -A roles/<角色名> .claude-plugin/marketplace.json
git commit -m "feat(roles): add <角色名>"
```

push 前先问我。

## 5. 告诉我怎么启用

- 本机：`claude plugin install <角色名>@claude-team`，在已打开的会话里执行 `/reload-plugins`。
- 其他电脑（push 之后）：`scripts/setup.sh <角色名>`，或 `claude plugin marketplace update claude-team && claude plugin install <角色名>@claude-team`。
- 用 `~/.claude/settings.json` 的 `enabledPlugins` 管理角色的电脑：把 `"<角色名>@claude-team": true` 加进去。
