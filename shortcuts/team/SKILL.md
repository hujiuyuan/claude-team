---
name: team
description: /team 快捷命令：把任务交给角色团队，等同 /team:kickoff。用户输入 /team <任务> 时使用。
argument-hint: <任务描述>
disable-model-invocation: true
---

用 Skill 工具调用 `team:kickoff`，参数原样传：$ARGUMENTS

没装 team 插件（找不到 `team:kickoff`）时，告诉用户先在 claude-team 仓库里运行 `scripts/setup.sh`。
