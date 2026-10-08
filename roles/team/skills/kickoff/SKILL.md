---
name: kickoff
description: 把一个任务交给角色团队完成：分析任务类型，挑选角色（architect 架构 / developer 开发 / reviewer 评审 / writer 写作等），编排顺序，分派并汇总。用户说“组队”“让团队来做”“分派给角色”“kickoff”时使用。
argument-hint: <任务描述>
---

# 组队完成任务

任务：$ARGUMENTS

你是队长：负责拆分、分派、把关和汇总，具体工作交给角色去做。

## 1. 盘点可用角色

claude-team 的角色以 `<角色>:<角色>` 命名，例如 `developer:developer`、`reviewer:reviewer`。只使用当前确实可用的角色。缺少合适的角色时，用通用 agent 顶上，并在汇报里建议“新增 xx 角色（`/team:new-role`）”。

## 2. 选流水线

按任务类型选一个起点，再按实际情况增删：

| 任务类型 | 流水线 |
|---|---|
| 新功能 / 较大改动 | architect（方案 + 拆解）→ **我确认** → developer（实现）→ reviewer（评审）→ developer（修复阻塞问题）→ writer（文档，可选） |
| Bug 修复 | developer（复现 → 定位 → 修复 → 回归测试）→ reviewer |
| 小改动（单文件、几十行以内） | 不组队，直接做或交给 developer |
| 代码评审 | reviewer；改动大时按模块或关注点并行多个 reviewer |
| 文档 / 报告 / 周报 | writer →（可选）reviewer 核对技术事实 |
| 技术调研 / 选型 | architect；多个候选方向可并行调研，最后由你汇总对比 |

能一个角色做完就不组队。组队的收益是分工和互相校验，代价是时间和 token。

## 3. 选执行方式

- **Agent teams**（实验功能，`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 时可用）：适合多个角色需要长时间并行、互相沟通的任务。你作为队长创建团队，按角色的 agent 类型生成队友（例：“用 reviewer:reviewer 类型生成一个队友评审 auth 模块”），通过共享任务列表分派和跟进。队友不会自动预加载角色 skill，分派任务时提醒它先加载 `team:house-rules` 和角色自己的 skill。
- **子代理**（默认）：用 Agent 工具按流水线依次调用对应角色；互不依赖的步骤在同一轮里并行调用。

## 4. 交接要自包含

子代理看不到我们的对话。每次分派都写清楚：

- 目标和验收标准
- 相关文件路径；上一步的产出（方案、diff 摘要、评审意见）原文或文件路径
- 边界：不该做什么
- 期望的返回格式

## 5. 关卡

- architect 的方案出来后，先把方案摘要给我确认，再进入实现。我明确说过“直接做完”时可以跳过。
- reviewer 提出的 🔴 阻塞问题必须修完才能交付；🟡 建议列进汇报，由我决定。
- 任何角色要越过 house-rules 安全底线时，停下来问我。

## 6. 汇总

按 house-rules 的汇报格式汇总：每个角色做了什么、最终结果、验证情况、遗留问题。如果过程中我纠正了某个角色的做法，最后问一句是否要用 `/team:learn` 沉淀下来。
