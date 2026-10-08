---
name: weekly-report
description: 写周报或阶段工作汇报：从 git 提交记录和我提供的要点收集素材，按“完成 / 进行中 / 风险与求助 / 下周计划”成文。用户说“写周报”“整理这周做了什么”“写个工作汇报”时使用。
argument-hint: [时间范围，默认本周] [仓库路径...]
---

# 周报

参数：$ARGUMENTS

## 1. 收集素材

能自己查清的不问我。必须问的合并起来，最多问两轮：第一轮在查提交之前（1.4），第二轮在查完提交之后（1.6）。

### 1.1 准备仓库

我指定的仓库，没指定就是当前仓库。在每个仓库里：

- `git remote` 没有输出（没有远端）：跳过这一节，直接用本地数据。
- `git rev-parse --is-shallow-repository` 输出 `true`：先执行 `git fetch --unshallow`。
- 对 `git remote` 列出的每个远端（下面用 `origin` 举例）：`git config --get-all remote.origin.fetch` 的输出里没有 `+refs/heads/*:refs/remotes/origin/*` 这一行（只拉单个分支的克隆就是这样），执行 `git remote set-branches --add origin '*'`。
- 最后执行 `git fetch --all --tags`。不要加 `--prune`，留着本机拉过的 `claude/...` 分支名，判断归属时有用。

### 1.2 我的邮箱

- `git config user.email` 的结果为空，或者是 `noreply@anthropic.com`，就不能用。后者是 Claude 自己的身份，Claude Code 云端会话里取到的就是它（`user.name` 也是 Claude）。
- 执行 `gh api user --jq '[.login, .id, .name] | @tsv'`。成功的话，我的 GitHub noreply 邮箱是 `<id>+<login>@users.noreply.github.com`，2017 年 7 月之前注册的老账号也可能是 `<login>@users.noreply.github.com`。我在 GitHub 开了邮箱隐私时，网页上合并 PR、编辑文件的提交用的就是它。
- 执行 `git shortlog -sne --branches --remotes --tags` 列出所有作者，找出可能是我的邮箱：上面的 noreply 邮箱，以及和我同名的作者（`name` 为空时用 `login` 比对）。
- 拿不准的放进第一轮问题。

### 1.3 时间范围

- 参数里没给就是本周一 00:00 到现在。“本周一”和 00:00 都按**我所在的时区**算。
- 时区偏移：在我自己的电脑上用 `date +%z`（PowerShell 用 `Get-Date -Format zzz`）。Claude Code 云端会话的机器是 UTC，不能用它的时区，要从我本人最近的提交推断：对每个候选邮箱执行 `git log -F --branches --remotes --tags --author="<me@corp.com>" -n 20 --format=%ad --date=format:%z`，取出现最多的偏移。
- 只有推断不出、或者各邮箱的结果不一致时，才放进第一轮问。

### 1.4 第一轮问题（查提交之前）

一次问完：

- 1.2、1.3 里拿不准的邮箱和时区。
- 会议、评审（包括帮别人评审、合并 PR）、沟通协调、线上问题处理等 git 里看不到的工作。
- 如果 shortlog 里有 Claude 的提交，而 `gh api user` 失败：问“这个仓库是不是只有你自己在用”。

### 1.5 查提交

```bash
git log -F --branches --remotes --tags --no-merges --source \
  --since="2026-10-05 00:00 +0800" \
  --author="<me@corp.com>" --author="<me.home@gmail.com>" --author="<noreply@anthropic.com>" \
  --date=format:"%Y-%m-%d %H:%M %z" --pretty="%h | 写于 %ad | 提交于 %cd | %an | %S | %s"
```

- `me@corp.com`、`me.home@gmail.com`、日期和 `+0800` 是示例，换成实际值。我的每个邮箱写一个 `--author`，**邮箱两边的尖括号要保留**；`--author="<noreply@anthropic.com>"` 原样保留。
- 我给了结束日期时，再加 `--until="<结束日期的次日> 00:00 +0800"`。
- 用 PowerShell 执行时写成一行：`\` 续行只在 bash、zsh 里有效。

各参数为什么这样写：

- **`-F` 和尖括号**：`--author` 默认按正则做子串匹配，`me@corp.com` 会匹配到同事的 `jaime@corp.com`。`-F` 按字面匹配，尖括号保证匹配完整的邮箱。
- **多个 `--author`** 是“或”的关系：我本人的各个邮箱，加上 Claude Code 云端会话做的提交（作者是 `Claude <noreply@anthropic.com>`，归属在 1.6 确认）。
- **`--branches --remotes --tags`**：本地和远端的所有分支以及 tag。云端会话的提交常在还没合并的 `claude/...` 分支上，只查当前分支会漏。不用 `--all`，它会把 stash、git notes 产生的提交也带进来。
- **`--since` 带上 `00:00` 和时区偏移**：只写日期时，git 按当前时刻算起点；不写偏移时，按运行这台机器的时区算。云端会话是 UTC，会漏掉我周一早上的提交。
- **写于 / 提交于**：按每条提交自己的时区显示，看末尾的 `+0000`、`+0800`。云端会话的提交是 `+0000`，**先换算到我的时区再判断**。`--since` 按提交时间筛选；换算后“写于”仍早于开始时间的，是以前写好、本周才 rebase、cherry-pick 或合并进来的，默认不算本周新完成的工作，在第二轮里列出来让我纠正。
- **`%S`** 是遍历时第一个到达这条提交的分支或 tag，只能作参考：主干上的提交也可能显示成某个 tag 名，合并后删除了分支的提交会显示成 `main`。要确认一条提交在哪些分支上，用 `git branch -a --contains <提交哈希>`；输出为空，说明它只在 tag 上（通常是发布或热修复）。

### 1.6 Claude 提交的归属（第二轮问题）

别人用 Claude Code 云端会话做的提交，作者同样是 `Claude <noreply@anthropic.com>`。如果他的 PR 是我合并的，他的名字可能在仓库历史里一次都不出现。所以不能看作者列表判断，要逐条查：

- 对每条 Claude 提交执行 `gh api "repos/{owner}/{repo}/commits/<提交哈希>/pulls" --jq '.[] | [.number, .user.login, .head.ref, .base.ref] | @tsv'`。`{owner}/{repo}` 原样写，gh 会按当前仓库自动填入；分支删了也查得到。
  - 只返回一条 PR：作者是我的 login，算我的；是别人，不算；是机器人账号，问我。
  - 返回多条（提交还没进默认分支时，发布 PR 之类也会带上它）：以 head 分支是 `claude/...` 的那条为准；还是判断不出，问我。**不能因为其中任意一条的作者是我就算我的。**
  - 没有 PR，或者 `gh api` 报错（比如仓库不在 GitHub 上）：问我。
- 不要用 `gh pr list`：它走 GraphQL，Claude Code 云端会话里会返回 403。
- 我在第一轮说过仓库只有我自己在用的，Claude 的提交直接全算我的，不用查。

要问我的 Claude 提交按分支（`%S`）分组列出，连同 1.5 里默认不算的旧提交，作为第二轮一次问完。

## 2. 归并

- 把零散提交按“事情”归并，一件事一条，不逐条罗列提交。
- 同一个改动可能出现好几次：cherry-pick 或 rebase 的副本；squash 合并生成的新提交（标题通常是 PR 标题，带 `(#编号)`）加上原分支上的提交。按事情归并，不重复计。
- 每条写成结果，而不是过程：“完成订单导出功能，支持 10 万行以内 Excel 导出”，而不是“写了导出代码、改了 bug”。
- 能量化就量化：数量、耗时、性能指标、影响用户数。没有数据就不写数字。

## 3. 成文

```markdown
## 本周完成
- <事情>：<结果/影响>

## 进行中
- <事情>：进度 <x%或阶段>，预计 <日期> 完成

## 风险与需要的支持
- <风险或阻塞>：<影响>，需要 <谁> 提供 <什么>

## 下周计划
- <事情>：<目标>
```

没有内容的章节写“无”，不要删掉章节。篇幅控制在一屏以内。

## 4. 交付

把成稿给我。是否发送、发到哪里由我决定。
