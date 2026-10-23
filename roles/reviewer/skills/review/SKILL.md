---
name: review
description: 普通评审的快捷命令：评审改动（默认当前分支相对主分支的改动 + 未提交改动），可补充范围（文件、目录、提交、分支、PR），加 --fix 审完直接改，加 -model 指定模型。用户输入 /reviewer:review 时使用。
argument-hint: "[范围] [--fix] [-model sonnet|opus|haiku|deepseek]"
disable-model-invocation: true
---

# 评审改动

参数：$ARGUMENTS

由主会话执行：解析参数 → 派评审 → 汇报。评审规则一律按 `reviewer:review-checklist`（含按语言的规则）。

## 1. 解析参数

| 参数 | 含义 | 不写时 |
|---|---|---|
| 范围 | 文件或目录路径、提交（`abc123`）、区间（`main..feat`）、分支名、PR 号（`#12` 或链接） | 当前分支相对主分支的改动（`git diff <base>...HEAD`）+ 未提交的改动 |
| `--fix` | 审完直接改：按 `review-checklist`「审完直接改」一节走 | 只出意见，不改 |
| `-model <名字>` | `sonnet` / `opus` / `haiku` / `fable`：派 reviewer 时用这个模型；`deepseek` / `deepseek-flash`：用 ccds 派只读评审（`deepseek-flash` 加 `--model 'deepseek-flash[1M]'`） | 当前会话的模型 |

范围是路径时，只评审这些路径上的改动；该路径没有改动时，告诉用户「这里没有改动，要全量扫描请用 `/reviewer:ocr <路径>`」，不要自作主张改成全量扫描。

## 2. 派评审

- Claude 模型：用 Agent 工具派 `reviewer:reviewer`（`model` 填用户指定的值，没指定就不填），提示词写清范围、取 diff 的命令、这次改动的目的（能从提交信息或对话里看出来的话）。
- DeepSeek：按 `ds-dispatch` 技能写 brief，用 `ccds-run start --readonly --model <对应模型> ...` 派出；brief 里要求按 `review-checklist` 的规则和输出格式评审，规则文件写绝对路径让 worker 自己读：本技能目录的上一级下的 `review-checklist/SKILL.md` 和 `review-checklist/ocr-rules/<语言>.md`（加载本技能时显示的 Base directory 就是本技能目录）。本机没有 `ccds-run` 时，告诉用户并改用默认模型。

## 3. 汇报

照 reviewer 的输出格式转给用户：第一行结论，再按 🔴 / 🟡 / ⚪ 分级。用了 `--fix` 的，按「审完直接改」的汇报要求写。
