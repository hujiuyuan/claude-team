---
name: ds-dispatch
description: 用 ccds（DeepSeek 中转站驱动的 Claude Code，不占 Max 额度）派活：写自包含 brief、用 ccds-run 后台启动（进度实时显示在 ccds 任务面板）、收结果、验收 diff。用户说「用 ccds / 派给 DeepSeek / 交给 worker」时用；手上有边界清楚、能用命令验收的编码任务，想省官方额度或并行推进时也用。
---

# ds-dispatch：把活派给 ccds worker

分工：你（官方会话）拆任务、写 brief、验收；worker（ccds，DeepSeek 中转站驱动的 Claude Code）读代码、改代码、跑验收命令。
worker 的 token 走中转站；你读结果和 diff 的 token 仍算 Max 额度，所以先看摘要和 `git diff --stat`，再按需读细节。

启动一律用 `ccds-run`（claude-team 的 `bin/ccds-run`，`setup.sh` 链接到 `~/.local/bin`；`ccds-run -h` 看用法。`ccds` 本身和 DeepSeek 中转站配置不在仓库里，每台电脑要自己配好，`ccds --ccds-check` 检查），不要直接拼 `ccds -p`：它带好了安全限制（禁推代码、提交、删文件、套娃起 worker），并把进度边跑边写进 `/tmp/ccds-runs/<ID>.state.json`，用户在聊天旁边的「ccds 任务」面板（`ccds-panel` 插件，`/ccds` 打开）能实时看到、停止、让它接着做。

## 1. 判断派不派

- 派：按规格实现函数并补测试、跨文件机械重构、补测试、修原因已知的 bug、批量改写、只读调研（"列出所有调用 X 的地方并分类"）。
- 自己做：需要拍板的设计取舍、需求还模糊、涉及密钥/权限/线上数据、三分钟能改完的小改动、离不开当前对话上下文的活。

完成标准：每个要派的任务都写得出至少一条验收命令（只读任务则写得出明确的产出格式）。写不出，就自己做或先找用户澄清。

## 2. 派活前检查（每次）

```bash
ccds --ccds-check        # 退出码 78 = 用户还没配好：把输出原样转告用户，停止派活
git status --porcelain   # 改代码的任务要求为空，worker 的改动才能和用户自己的改动分开；不为空先问用户
jq '(.permissions.allow // []) | any(. == "Bash(*)")' ~/.claude/settings.json   # false = worker 默认跑不了命令，启动时要加 --allowed（见第 4 节）
```

同时改代码的 worker 不止一个时，每个用独立 worktree（第 5 节）。

## 3. 写 brief

brief 是 worker 能看到的全部信息：它没有这段对话，也没有你的记忆。用 Write 工具写到 `/tmp/ccds-runs/<ID>.brief.md`（`mkdir -p /tmp/ccds-runs`）；`<ID>` = 任务简称-时间，如 `auth-retry-0923-1530`。

```markdown
# 目标
<一句话：做完之后什么变了>

# 背景
<为什么做；worker 需要知道的项目约定和已定的设计。只写结论>

# 相关文件
- path/to/a.go —— 要改：<改什么>
- path/to/a_test.go —— 要新增测试：<覆盖哪些情况>
- path/to/c.go —— 只读参考：<看什么>

# 约束
- 只动上面标了"要改/要新增"的文件；范围外的改动先写进最终汇报，由派活方决定
- 改动留在工作区，由派活方审查后提交
- <接口签名保持不变 / 不引入新依赖 / ……>

# 验收（全部通过才算完成，你自己跑）
- `go test ./internal/auth/...`
- `golangci-lint run ./internal/auth/...`

<周报、工作汇报类任务加这一节：
# 归属
只算 <用户的 git 邮箱列表> 的提交；Claude 云端会话的提交按 PR 作者判断归属（规则见 team:doc 的 types/weekly.md 第 1.6 节，原样贴进来）。拿不准的单列出来，不要算进去。>

# 最终汇报（最后一条消息，按此格式）
1. 改了哪些文件，每个一句话
2. 每条验收命令及结果（贴输出最后几行）
3. 没做完的、拿不准的、需要派活方决定的
```

完成标准：一个没看过这段对话的工程师拿着它就能开工，并且知道什么时候算做完。

## 4. 启动

用 Bash 工具，`run_in_background: true`：

```bash
ccds-run start --id auth-retry-0923-1530 --name 登录重试上限 \
  --brief /tmp/ccds-runs/auth-retry-0923-1530.brief.md --cwd <仓库或 worktree 目录>
```

- `--name`：面板上显示的中文名，写成用户看得懂的一句话。
- `--timeout 3600`（秒，默认 1 小时，按预估时长的两倍调）、`--max-turns 60`（小任务 30，大任务 100）。
- `--model 'deepseek-flash[1M]'`：简单任务提速；带 `[1M]` 必须加引号。看图任务也用它。**从图片里找错别字的活别派**：DeepSeek 识图会把错别字顺手改对（2026-09-23 实测）。
- `--allowed "Bash(go test:*),Bash(golangci-lint:*)"`：全局没放行 `Bash(*)` 时，把验收命令放行，否则 worker 跑不了测试。
- `--bypass`：全部放行，只给一次性 worktree 里需要任意命令的任务。安全限制在 bypass 下照样生效。
- WebSearch 可以用，不占 Max 额度（2026-09-23 实测）。
- 跑完自动通知你；中途用户可能在面板上停止或让它接着做，收结果时以 state 文件为准。

## 5. 并行

- 只读任务（调研、审查）：同一目录直接并行。
- 改代码的任务：一个 worker 一个 worktree，`--cwd` 指向它：

```bash
WT="$(git rev-parse --show-toplevel)-auth-retry-0923-1530"
git worktree add -b "ccds/auth-retry-0923-1530" "$WT" HEAD
ccds-run start --id auth-retry-0923-1530 --name 登录重试上限 --brief /tmp/ccds-runs/auth-retry-0923-1530.brief.md --cwd "$WT"
```

- 每个 worker 一次 Bash 调用（`run_in_background: true`），ID 互不相同，一次性全部发出。同时跑先控制在 4 个以内；出现 429 / rate limit 就减少并发。
- Bash 的 shell 变量不跨调用保留，后面的命令把 ID、路径写成实际值。

## 6. 收结果

```bash
jq '{status, exitCode, turns, sessionId, models, denied, result, files}' /tmp/ccds-runs/<ID>.state.json
```

- `models` 全部以 `deepseek` 开头。出现 `claude-` 开头说明 worker 在烧 Max 额度：停止派活，告诉用户检查 `~/.claude/deepseek.settings.json`。
- `status`：`done` 才算跑完；`failed` 看 `result` 和 `/tmp/ccds-runs/<ID>.err`（步数用完就拆小或 resume）；`timeout`、`stopped` 是超时和被用户停掉。
- `denied` 非空：有操作被拦下，判断是否影响完成度。
- `.err` 里的 `[claude-code:unrecognized_model]` 是正常噪音。退出码 78 是 ccds 配置问题，把输出原样转告用户。

## 7. 验收

worker 的汇报是线索，结论以你亲自核对的为准。

1. 范围：`git status --porcelain` 和 `git diff --stat`，每个改动文件（含新文件）都在 brief 的范围内，或在汇报里说明了理由。
2. 内容：读 `git diff`，风险高的文件先读。
3. 亲自重跑 brief 里的每一条验收命令。
4. 把结论写回面板：`ccds-run note <ID> "验收通过：……"`，不通过加 `--bad`。一句大白话，用户在面板上直接看。
5. 接受：由你提交（worker 被禁止 commit）。worktree 的情况：在 worktree 里 `git add -A && git commit`，回主目录 `git merge ccds/<ID>`（或 cherry-pick），再 `git worktree remove "$WT"`。
6. 返工：把问题写成一段说明（具体到文件、期望行为、失败输出），接着同一个会话做，`run_in_background: true`：`ccds-run resume <ID> "<返工说明>" --foreground`。
7. 放弃：`ccds-run discard <ID>` 还原它改过的文件（派活前工作区是干净的，不会误伤用户的改动）；worktree 直接 `git worktree remove --force "$WT"` 并删分支。

完成标准：每条验收命令都由你亲自跑过且通过，每个改动文件都在范围内或有说明，结论已写回面板。

## 8. 交给用户接手

worker 的会话可以在终端里接着聊：`ccds --resume <sessionId>`。用 ccds 打开才会继续走中转站；用 `claude --resume` 打开会换成官方模型，吃 Max 额度。
