---
name: ocr
description: 全量扫描的快捷命令（对应阿里 OpenCodeReview 的 ocr scan，但不需要装 ocr）：不看改动，把指定范围的代码整体按分语言规则扫一遍，分批并行，出一份报告。支持 -model 选模型、补充扫描范围、--exclude 排除、--preview 只看清单、--resume 续扫。用户输入 /reviewer:ocr 时使用。
argument-hint: "[范围...] [-model deepseek|deepseek-flash|sonnet|opus|haiku] [--exclude 模式] [--preview] [--resume 目录]"
disable-model-invocation: true
---

# 全量扫描

参数：$ARGUMENTS

由主会话执行，**只出报告、不改代码**。要修复的，扫完后用户另说。

## 1. 解析参数

| 参数 | 含义 | 不写时 |
|---|---|---|
| 范围 | 一个或多个目录、文件，空格或逗号分隔 | 整个仓库 |
| `-model <名字>` | `deepseek`（ccds 默认模型）、`deepseek-flash`（ccds `--model 'deepseek-flash[1M]'`，更快）、`sonnet` / `opus` / `haiku` / `fable`（Claude 子代理） | `deepseek` |
| `--exclude <模式>` | 追加排除的 glob，逗号分隔 | 只用下面的默认排除 |
| `--preview` | 只列出要扫的文件和分批，不扫 | 列清单后直接开扫 |
| `--resume <目录>` | 接着上次的扫描做，只补跑没有结果文件的批次 | 新开一次扫描 |

默认用 DeepSeek：全量扫描量大，用 Claude 很快吃掉额度。本机没有 `ccds-run`（`command -v ccds-run`）时，告诉用户并改用 `sonnet`。

## 2. 列文件

在仓库根目录，用 `git ls-files -- <范围>` 取文件（只扫进了版本管理的文件），然后去掉：

- 默认排除：依赖锁文件（`*.lock`、`package-lock.json`、`pnpm-lock.yaml`、`go.sum`）、自动生成的代码（路径含 `generated`、`gen/`、`*.pb.go`、`*_pb2.py`、`*.min.js`）、`vendor/`、`node_modules/`、`dist/`、`build/`、`testdata/`、`fixtures/`、二进制和图片、超过 2000 行的单文件（单列出来，提示用户单独指定）
- 用户 `--exclude` 的模式

## 3. 分批

- 先按语言（扩展名对应 `review-checklist` 第 0 节的规则文件），同语言内按目录分；每批不超过 15 个文件或 3000 行，超了就拆。
- 扫描目录：`/tmp/review-scan/<仓库名>-<月日-时分>/`，写一份 `plan.md`：每批编号、语言、规则文件、文件列表。
- 告诉用户：一共多少文件、分几批、用什么模型、排除了什么、报告会写到哪。`--preview` 到这里结束。
- 超过 300 个文件时，先停下来问用户要不要缩小范围（说清预计批数），再开扫。

## 4. 并行扫

每批一个任务，同时最多 4 个，跑完一个补一个。每批的提示（或 brief）写清：

- 只读，不改任何文件
- 要扫的文件列表（相对仓库根目录的路径）
- 评审规则：`review-checklist/SKILL.md` 第 1~8 节和「我积累的常见坑」，加上该批语言的 `review-checklist/ocr-rules/<语言>.md`。给绝对路径让它自己读：路径在本技能目录的上一级下（加载本技能时显示的 Base directory 就是本技能目录）
- 看的是整个文件的现状，不是改动；只报有把握的真问题，没把握的不报
- 范围限死：只读这批文件、规则文件，以及为确认问题必须看的本仓库内调用方；不运行被扫的脚本，不研究仓库外的程序（命令行工具、依赖包的源码或二进制）。确认不了就写「疑似」并说明还缺什么，不要为了确认去深挖。原因：实测 worker 会为确认一条外部工具的行为把步数全耗光，一条结果都交不出
- 结果放在最后一条消息里返回（worker 只读，不写文件），每条一行：`严重程度（🔴/🟡/⚪）| 文件:行 | 问题 | 在什么情况下出错 | 建议改法`；没发现问题写「无」

派法：

- DeepSeek：按 `team:ds-dispatch` 写 brief，`ccds-run start --readonly --max-turns 25 --id scan-<编号>-<时分> --name "扫描 第<编号>批 <语言>" --cwd <仓库根> --brief ...`（`deepseek-flash` 加 `--model 'deepseek-flash[1M]'`），`run_in_background: true`。进度在 ccds 面板上。
- Claude：Agent 工具派 `reviewer:reviewer`，`model` 填用户指定的值。

每批返回后，由你把结果写进 `<扫描目录>/batch-<编号>.md`（DeepSeek 的在 `/tmp/ccds-runs/<ID>.state.json` 的 `result` 里）。

`--resume`：读该目录的 `plan.md`，只派没有 `batch-<编号>.md` 的批次。

## 5. 出报告

全部批次完成后，合并写成 `<扫描目录>/report.md`：

1. 开头的摘要（按 `team:doc` 的摘要要求，5 行以内）：扫了多少文件、多少问题、最该先修的 3 条
2. 🔴 阻塞、🟡 建议、⚪ 细节三节，同一问题在多处出现的合并成一条并列出所有位置
3. 没扫的文件（被排除的、超长的）及原因
4. 用的模型和规则版本

在聊天里只给摘要和报告路径。DeepSeek 的结论属于「worker 的汇报」：🔴 条目你要亲自打开代码核一遍再写进报告，核不实的删掉，并在报告末尾记一句删了几条。
