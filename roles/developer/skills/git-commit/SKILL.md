---
name: git-commit
description: 我的 git 提交规范：拆分提交、Conventional Commits 格式、提交前检查。需要提交代码、写提交信息、整理提交历史时使用。
---

# 提交规范

仓库自己有提交规范（CONTRIBUTING、commitlint 配置、历史提交风格）时，以仓库为准；没有时按下面的来。

## 提交前

1. `git status` 和 `git diff` 看清楚要提交什么；只 `git add` 本次相关的文件，不用 `git add .` 一把梭。
2. 检查暂存区里没有密钥、`.env`、本机路径、大文件、调试代码。
3. 相关的测试、lint 已经通过。

## 一次提交一件事

- 一个提交只做一件逻辑上完整的事；重构和功能改动分开提交。
- 每个提交都应该能单独构建通过。

## 提交信息格式

```
<type>(<scope>): <subject>

<body：为什么改、怎么改的要点；简单改动可省略>
```

- `type`：feat / fix / refactor / perf / test / docs / build / ci / chore
- `scope`：受影响的模块，可省略
- `subject`：祈使句，说明做了什么，不超过 72 个字符，结尾不加句号
- 语言：跟随仓库历史提交的语言；新仓库默认英文

示例：

```
fix(auth): refresh token before expiry instead of after 401

Requests that raced with token expiry failed once and were retried,
doubling load on the auth service during peak hours.
```

## 禁止

- 不用 `--no-verify` 跳过钩子；钩子失败就修复问题。
- 不 amend 或 rebase 已经推送的提交，除非我明确要求。
- 不 force push 到共享分支。
