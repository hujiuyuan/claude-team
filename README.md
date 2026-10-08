# claude-team

我的 Claude 角色团队。每个**角色**由两部分组成：一段**提示词**（agent，规定它是谁、怎么工作、有哪些习惯）和它专属的**技能**（skills，可复用的流程、模板和清单）。每个角色打包成一个 Claude Code 插件，这个仓库本身就是插件市场（marketplace）。换一台电脑，一条命令装好，同一套习惯到处可用。

```
你 ──任务──▶ Claude（队长）──分派──▶ architect / developer / reviewer / writer …
                                        │
                     每个角色 = 提示词 + 预加载的技能 + 全员通用习惯（team:house-rules）
```

## 角色一览

| 角色 | 什么时候交给它 | 技能 | 权限 |
|---|---|---|---|
| **team**（核心，必装） | 全员通用习惯、遇到问题先辩证再问我、组队分派、新建角色、沉淀习惯 | `house-rules` `deliberate` `kickoff` `new-role` `learn` | — |
| **architect** 架构师 | 需求澄清、方案设计、技术选型、任务拆解；PRD 需求分析规划（X-NN） | `design-doc` `task-breakdown` `xnn-review` | 只读 |
| **developer** 开发 | 实现功能、修 bug、写测试、提交 | `implement` `git-commit` | 全部 |
| **reviewer** 评审 | 合并前审查改动的正确性、安全性、可维护性 | `review-checklist` | 只读 |
| **writer** 写作 | 技术文档、README、周报和工作汇报 | `tech-doc` `weekly-report` | 读写文件 |

所有角色都会预加载 `team:house-rules`（全员通用习惯），所以“用中文交流”“遇到问题先辩证再问我”“破坏性操作先问我”这类习惯只需要写一次。

team 里还有两个只读 agent：`team:judge`（裁判）和 `team:debater`（辩手）。它们只在辩证裁决里由主会话调用，不是可以直接分派的角色。

## 在新电脑上安装

前提：已安装 [Claude Code](https://code.claude.com/docs)。本仓库目前是公开的；如果改成私有，本机 git 要能访问 GitHub（`gh auth login` 或配置 SSH key）。

### 方式一：命令行（macOS / Linux / Windows 通用）

```bash
claude plugin marketplace add hujiuyuan/claude-team
claude plugin install developer@claude-team     # 装哪个角色就写哪个，team 核心会自动带上
claude plugin install reviewer@claude-team
```

一次装全部：

```bash
# macOS / Linux
for r in team architect developer reviewer writer; do claude plugin install "$r@claude-team"; done
```

```powershell
# Windows PowerShell
"team","architect","developer","reviewer","writer" | ForEach-Object { claude plugin install "$_@claude-team" }
```

如果已经 clone 了仓库，也可以直接运行 `scripts/setup.sh`（全部角色）或 `scripts/setup.sh developer writer`（指定角色）。脚本可以重复执行，已装的会更新到最新。

### 方式二：写进配置，启动时自动安装、自动更新

把下面的内容合并进 `~/.claude/settings.json`（Windows 是 `%USERPROFILE%\.claude\settings.json`），启动 Claude Code 时会自动拉取并安装，之后每次启动自动更新：

```json
{
  "extraKnownMarketplaces": {
    "claude-team": {
      "source": { "source": "github", "repo": "hujiuyuan/claude-team" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": {
    "team@claude-team": true,
    "architect@claude-team": true,
    "developer@claude-team": true,
    "reviewer@claude-team": true,
    "writer@claude-team": true
  }
}
```

> ⚠️ 用这种方式时 **`team@claude-team` 必须写上**。通过配置启用不会自动安装依赖，缺了 team，其他角色会因为依赖不满足而加载失败。

这份配置可以放进你自己的 dotfiles，新电脑同步完配置就有整个团队。不想在某台电脑上用某个角色，把它改成 `false` 即可。

### 方式三：编辑模式（经常调教角色的那台主力机）

```bash
git clone https://github.com/hujiuyuan/claude-team.git ~/claude-team
~/claude-team/scripts/setup.sh --dev
```

`--dev` 让插件直接从本地克隆读取：改了仓库里的文件，在会话里执行 `/reload-plugins` 就生效，不用重新安装。改满意了 `git push`，其他电脑更新后同步。

克隆放在别的位置时，设置环境变量 `CLAUDE_TEAM_HOME=<克隆路径>`，`/team:learn` 和 `/team:new-role` 会去那里改文件。

## 日常使用

| 想做的事 | 怎么说 |
|---|---|
| 让 Claude 自己挑角色 | 直接描述任务。Claude 根据每个角色的 description 自动分派，例如“评审一下我刚才的改动”会交给 reviewer。 |
| 点名某个角色 | “让 architect 先出个方案”，或 `@agent-reviewer:reviewer 看一下 src/auth` |
| 整个会话都由某个角色来做 | `claude --agent developer`（名字不冲突时可以省略前缀，否则写 `developer:developer`） |
| 多个角色协作完成一件事 | `/team:kickoff 给订单列表加导出 Excel 功能` |
| 需求分析规划：核对 PRD 遗漏、闭环、拆成可执行的子任务文档 | `/architect:xnn-review X-03 --prd <PRD 路径> --design <设计文档目录>`（见下文） |
| 让多个角色辩证分析一个问题 | 平时不用管：遇到问题会自动走辩证裁决；也可以手动 `/team:deliberate <问题>` |
| 直接用某个技能 | `/writer:weekly-report`、`/architect:design-doc 消息队列选型`、`/reviewer:review-checklist` |
| 把习惯教给角色 | `/team:learn`（见下一节） |
| 新增一个角色 | `/team:new-role 数据分析师`（见后文） |

### 遇到问题：先辩证，再问你

这是写在 `team:house-rules` 里的全员规则，由 `team:deliberate` 执行：

| 级别 | 什么情况 | 怎么处理 |
|---|---|---|
| L0 查证 | 能从 PRD、代码、文档、已有设计里查到 | 直接查，写明出处 |
| L1 辩证 | 其余所有需要判断的问题 | 2 名盲审分析员（`team:debater`）独立分析，再由裁判（`team:judge`）裁决；某题两人推荐不一致（按内容比较）或涉及业务取舍时，这道题的每个候选方案配一名代言人辩论 1 轮后再裁决 |
| L2 问你 | 安全底线、裁判判“需你拍板”、必需的输入读不到 | 阶段末一次问完，每个问题都带方案表、推荐、默认值和反悔代价，等你回复期间按默认值推进 |

分析和辩论的固定维度：PRD 是否体现 → 已有设计能否解决 → 有几种方案 → 各自优势 → 能否兼得 → 劣势和规避办法 → 会不会产生新问题 → 需求变更时的更新代价。

辩论原文、裁决和决策日志保存在本机 `~/.claude-team/runs/`，不进任何仓库，可以随时复盘。

### 需求分析规划（X-NN 设计评审）

在设计文档所在的仓库目录里启动 `claude`，然后运行：

```
/architect:xnn-review X-03 --prd <PRD 路径> --design <设计文档目录> --code <代码目录>
```

参数都可以省略，省略时会自动查找。流程是固定的：

1. **准备**：读 PRD、样板、代码，读不到的会标注降级。
2. **需求基线**：architect 给 PRD 条目编号，建立“PRD 条目 → X 文件 → YY”的追溯表。
3. **三视角盲审**：3 名审计员互相看不到对方的结论，分别检查：
   - **覆盖**：以 PRD 为准定位遗漏，判定是补 X-03 的功能点，还是新增一个 X 文件。
   - **闭环**：资源 × 操作矩阵、状态机、权限、审计等横切项。后端必须闭环，前端可以不提供，但要写理由。
   - **可执行性**：能不能拆成可以独立提交的 YY。
4. **交叉校验、裁判裁决**：有多个修法的条目进入辩论。
5. **写文档**：先写 X-03（完整生命周期），再拆成若干 X-03-YY（一个 YY = 一次独立提交，精确到每个动作），最后复审可执行性。
6. **交付**：只写文件，**不提交**。你抽检后明确说“提交”，再按那个仓库的规范提交并推送。

格式以目标仓库里已有的样板为准；没有样板时，用 `roles/architect/skills/xnn-review/` 下的通用骨架。

### 让角色以“队友”身份并行协作（实验功能）

Claude Code 的 [agent teams](https://code.claude.com/docs/en/agent-teams) 可以让多个角色作为独立的队友同时工作、互相发消息。建议只在需要时对单个会话开启，不要写进全局配置：

```bash
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude
```

然后用 `/team:kickoff` 或直接说“用 reviewer:reviewer 类型生成一个队友去评审 auth 模块”。需要注意：

- 队友不会预加载 `skills:` 里的技能。每个角色的提示词里已经写了“没有就先用 Skill 工具加载”，所以仍然能用上。
- 开启后，带 `name` 的子代理调用会变成生成队友，token 消耗明显更高。辩证裁决调用子代理时不传 `name`，不受影响。
- 一个会话只能有一个团队，不能嵌套。
- 只能在交互式会话里用（`claude -p` 不支持）。

## 沉淀习惯：让角色越用越像你

这个仓库最重要的用法是**持续把你的习惯写进去**：

1. 在任何一台电脑上，对话中纠正了 Claude 的做法，或者想到一条“以后都要这样”的规矩，执行 `/team:learn`，或者 `/team:learn 周报控制在一屏以内`。
2. Claude 提炼成可执行的规则，判断应该放在哪里：
   - 所有角色都适用 → `team:house-rules`
   - 某个角色特有 → 该角色提示词的「我的习惯」章节
   - 某个流程的步骤或清单 → 对应的技能
3. 你确认后，它写进仓库、校验、提交并 push。
4. 其他电脑：开了 autoUpdate 的下次启动自动更新；没开的重新运行 `scripts/setup.sh`，或执行 `claude plugin marketplace update claude-team` 再 `claude plugin update <角色>@claude-team`。

也可以直接编辑文件，每个角色提示词末尾都留了「我的习惯」章节。

## 新建角色

最省事的办法是在会话里说 `/team:new-role 数据分析师，帮我取数、做分析、出结论`。Claude 会问清楚职责、边界、你的习惯和需要的权限，然后生成文件、校验、提交。

手动操作：

```bash
# 生成骨架（--readonly：不给写文件工具；--skill 可以写多个）
python3 scripts/scaffold.py role data-analyst -d "数据分析师：取数、分析、出结论。只读。" --skill sql-query --readonly
# 给已有角色加技能（--no-preload：只由主会话调用的流程技能，不预加载进 agent）
python3 scripts/scaffold.py skill developer debug -d "排查线上问题的步骤：收集现象、缩小范围、验证假设"
# 一个角色由几个 agent 配合时，再加 agent
python3 scripts/scaffold.py agent <角色> <agent名> -d "什么时候交给它" --readonly
# 填完生成文件里的 TODO 后校验
python3 scripts/validate.py
```

写提示词和技能的要点见 [authoring-guide.md](roles/team/skills/new-role/authoring-guide.md)。

## 仓库结构

```
claude-team/
├── .claude-plugin/marketplace.json   # 插件市场清单：登记所有角色
├── roles/                            # 每个子目录是一个角色（一个插件）
│   ├── team/                         # 核心：通用习惯 + 辩证裁决 + 团队管理技能
│   │   ├── .claude-plugin/plugin.json
│   │   ├── agents/{judge,debater}.md       # 只读，仅辩证裁决使用
│   │   └── skills/{house-rules,deliberate,kickoff,new-role,learn}/SKILL.md
│   └── developer/                    # 普通角色的样子
│       ├── .claude-plugin/plugin.json      # 依赖 team
│       ├── agents/developer.md             # 角色提示词
│       └── skills/{implement,git-commit}/SKILL.md
├── templates/role/                   # 新角色模板（scaffold.py 使用）
└── scripts/
    ├── setup.sh                      # 在当前电脑安装或更新角色
    ├── scaffold.py                   # 生成新角色或新技能
    └── validate.py                   # 结构校验（CI 也会跑）
```

### 一个角色是怎么组成的

`roles/<角色>/agents/<角色>.md` 的 frontmatter：

```yaml
---
name: reviewer                  # 与文件名一致
description: 代码评审。……         # Claude 靠这句话决定什么时候交给它
tools: Read, Grep, Glob, Bash, Skill   # 最小够用；省略表示继承全部工具
model: inherit                  # 跟随会话模型
color: red                      # 界面上区分角色
skills:                         # 作为子代理启动时预加载的技能全文
  - team:house-rules
  - reviewer:review-checklist
---
（正文：身份、工作流程、输出格式、原则、边界、我的习惯）
```

技能怎么进到角色的上下文里：

- 作为子代理被调用时，`skills:` 里的技能（包括来自 team 插件的 `team:house-rules`）会完整预加载（已实测）。
- 用 `claude --agent <角色>` 让整个会话扮演角色时不会预加载，角色会按提示词里的说明自己用 Skill 工具加载（已实测）。作为 agent teams 队友时，官方文档说明同样不预加载，靠同一条说明兜底。

## 维护约定

- 改完运行 `python3 scripts/validate.py`；装了 Claude Code 的话再跑 `claude plugin validate .`。push 后 GitHub Actions 会自动跑同样的检查。
- **不写 `version` 字段**。不写时，插件版本取自 git 提交，每次 push 都算新版本，不用手动改版本号。`claude plugin validate` 会提示 “No version specified”，忽略即可。
- 角色名、技能名用小写字母和连字符，全仓库唯一；角色名不能以 `claude-`、`anthropic-` 开头（Claude Code 保留）。
- 插件里的 `CLAUDE.md` 不会被加载，所以全员通用的习惯放在 `team:house-rules` 技能里。
- team 里的 agent 必须只读，不能有 `Agent`、`Write`、`Edit`（防止辩证裁决递归、误改文件），validate.py 会检查。

### 敏感词检查

**本仓库是公开的**，角色和技能里只写通用规则，示例用虚构领域。为了兜底，`validate.py` 会用一份**只放在本机**的词表检查仓库里的所有文件：

```bash
# 在仓库根目录建词表（已在 .gitignore 里，不会入库）；一行一个词，# 开头是注释
printf '公司名\n内部项目代号\n' > .sensitive-words.txt
python3 scripts/validate.py
```

也可以用环境变量 `CLAUDE_TEAM_SENSITIVE_WORDS=<词表路径>` 指向别处。没有词表时跳过这项检查。

## 常见问题

**装好了但看不到角色？** 在会话里执行 `/plugin` 查看是否已启用，再执行 `/reload-plugins`。用方式二（配置文件）的，确认 `team@claude-team` 也写上了；第一次启动是后台拉取，没出现的话重启一次。

**本机 `~/.claude/agents/` 里也有一个叫 reviewer 的 agent？** 插件里的角色全名是 `reviewer:reviewer`，和本机的 `reviewer` 是两个 agent。`claude --agent reviewer` 这种省略前缀的写法可能选中本机那个，写全名就不会混淆。

**想让某台电脑只用部分角色？** 方式一只装需要的；方式二把不需要的设为 `false`。
