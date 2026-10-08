---
name: weekly-report
description: 写周报或阶段工作汇报：从 git 提交记录和我提供的要点收集素材，按“完成 / 进行中 / 风险与求助 / 下周计划”成文。用户说“写周报”“整理这周做了什么”“写个工作汇报”时使用。
argument-hint: [时间范围，默认本周] [仓库路径...]
---

# 周报

参数：$ARGUMENTS

## 1. 收集素材

能自己查清的不问我。必须问的合并起来，最多问两次：查提交之前一次（邮箱、时区、git 以外的工作），列出 Claude 的提交之后一次（归属）。

### 1.1 仓库

我指定的仓库，没指定就是当前仓库。每个仓库先执行 `git fetch --all --tags`。不要加 `--prune`：已经合并并删除的 `claude/...` 分支上的提交，正是本周的工作。

### 1.2 我的邮箱

- 在仓库里执行 `git config user.email`。结果为空，或者是 `noreply@anthropic.com`，就不能用：后者是 Claude 自己的身份，Claude Code 云端会话里取到的就是它。
- 执行 `git shortlog -sne --branches --remotes --tags`，找出可能也是我的邮箱：和我同名的其他邮箱，以及 `*@users.noreply.github.com`（在 GitHub 网页上合并 PR、编辑文件时，提交用的是这个邮箱）。
- 拿不准的问我。最后得到“我的邮箱”列表。

### 1.3 时间范围

- 参数里没给就是本周一 00:00 到现在。“本周一”和 00:00 都按**我所在的时区**算。
- 时区偏移：在我自己的电脑上用 `date +%z`（PowerShell 用 `Get-Date -Format zzz`）。Claude Code 云端会话的机器是 UTC，不能用它的时区，改为从我本人最近的提交推断：`git log -F --branches --remotes --author="<me@corp.com>" -n 20 --format=%ad --date=format:%z`。推断不出就问我。

### 1.4 查提交

下面的 `me@corp.com`、`me.home@gmail.com`、日期和 `+0800` 都是示例，换成实际值：我的每个邮箱写一个 `--author`，**邮箱两边的尖括号要保留**。

```bash
git log -F --branches --remotes --tags --no-merges --source \
  --since="2026-10-05 00:00 +0800" \
  --author="<me@corp.com>" --author="<me.home@gmail.com>" --author="<noreply@anthropic.com>" \
  --date=format:"%Y-%m-%d %H:%M" --pretty="%h | 写于 %ad | 提交于 %cd | %an | %S | %s"
```

我给了结束日期时，再加 `--until="<结束日期的次日> 00:00 +0800"`。

- **`-F` 和尖括号**：`--author` 默认按正则做子串匹配，`me@corp.com` 会匹配到同事的 `jaime@corp.com`。`-F` 按字面匹配，尖括号保证匹配完整的邮箱。
- **多个 `--author`** 是“或”的关系：我本人的各个邮箱，加上 Claude Code 云端会话代我做的提交（作者是 `Claude <noreply@anthropic.com>`）。
- **`--branches --remotes --tags`**：本地和远端的所有分支以及 tag。云端会话的提交常在还没合并的 `claude/...` 分支上，只查当前分支会漏。不用 `--all`，它会把 stash、git notes 产生的提交也带进来。
- **`--since` 带上 `00:00` 和时区偏移**：只写日期时，git 按当前时刻算起点；不写偏移时，按运行这台机器的时区算。云端会话是 UTC，会漏掉我周一早上的提交。
- **“写于”早于开始日期的行**：`--since` 按提交时间筛选，这些是以前写好、本周才 rebase、cherry-pick 或合并进来的。默认不算本周新完成的工作，拿不准就问我。
- **`%S`** 是找到这条提交的分支，下一步用它判断 Claude 的提交来自谁的会话。

### 1.5 Claude 提交的归属

别人用 Claude Code 云端会话做的提交，作者同样是 `Claude <noreply@anthropic.com>`，而且那个人可能一条自己署名的提交都没有。所以不能凭“这段时间有没有别的作者”来判断。

- **个人仓库**：`git shortlog -sne --branches --remotes --tags`（不限时间，含合并提交）里，除了 Claude 只有我的邮箱，那么 Claude 的提交都算我的。
- **其他情况**：按分支（`%S`）把 Claude 的提交分组列给我确认。能用 `gh` 时，先执行 `gh pr list --author @me --state all --search "updated:>=2026-10-05" --json headRefName`（日期换成开始日期），在这些分支上的提交预先标成“我的”，其余的问我。

### 1.6 问我补充

会议、评审、沟通协调、线上问题处理等 git 里看不到的工作，和 1.2、1.3 里拿不准的事一起，在查提交之前问。

## 2. 归并

- 把零散提交按“事情”归并，一件事一条，不逐条罗列提交。
- 同一个改动可能出现好几次：cherry-pick 或 rebase 的副本，或者 squash 合并生成的新提交加上原分支上的提交。按标题和内容去重，不重复计。
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
