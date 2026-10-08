---
name: learn
description: 把对话中暴露出的个人习惯、偏好、纠正意见沉淀进 claude-team 仓库（通用习惯、某个角色的提示词或技能），推送后所有电脑上的角色都会学会。用户说“记住这个习惯”“以后都这样做”“把这个教给 xx 角色”“沉淀一下”时使用。
argument-hint: [要记住的习惯；留空则从当前对话中提炼]
---

# 沉淀习惯

要沉淀的内容：$ARGUMENTS

## 1. 提炼

参数为空时，从当前对话里我的纠正、明确偏好、反复强调的点提炼。每条写成：

- **规则**：可执行的一句话（“做 X” / “不做 Y” / “X 时用 Y”），不写感想。
- **原因**：一句话，帮助角色在边界情况下判断。
- **范围**：通用 / 某个角色 / 某个流程。

只沉淀以后会反复用到的东西。一次性的事实（某个 bug 的细节、某次会议的结论）不要写进去。

## 2. 决定放哪

| 范围 | 写入位置 |
|---|---|
| 所有角色都适用 | `roles/team/skills/house-rules/SKILL.md` 对应章节 |
| 只属于某个角色 | `roles/<角色>/agents/<角色>.md` 的「我的习惯」章节 |
| 某个流程的步骤、模板、清单 | 对应技能的 `SKILL.md`；没有合适的技能就新建（见 `/team:new-role`） |
| 不属于任何现有角色的新领域 | 建议新建角色，问我是否要建 |

## 3. 给我确认

列出每条习惯、目标文件和拟写入的原文，等我确认。

- 和已有条目重复：合并改写，不新增。
- 和已有条目冲突：指出冲突，问我以哪个为准，旧的删掉。

我确认改动，即视为同意提交并 push 到 claude-team 仓库。

## 4. 写入、校验、同步

按顺序找仓库的本地克隆：环境变量 `CLAUDE_TEAM_HOME` → `~/claude-team` → 问我；都没有就 `git clone https://github.com/hujiuyuan/claude-team.git`。

```bash
cd <仓库>
git pull --ff-only
# 编辑文件
python3 scripts/validate.py
git add -A roles
git commit -m "chore(habits): <一句话摘要>"
git push
```

push 失败（例如远端有新提交）时先 `git pull --rebase` 再推；有冲突就停下来告诉我。

## 5. 让改动生效

- 本机：用 `scripts/setup.sh --dev` 装的（插件直接从本地克隆读取），执行 `/reload-plugins` 即可。
- 其他电脑：开启了 autoUpdate 的，下次启动自动更新；没开的重新运行 `scripts/setup.sh`，或执行 `claude plugin marketplace update claude-team` 后再 `claude plugin update <角色>@claude-team`。
