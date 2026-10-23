#!/usr/bin/env bash
# 从阿里 OpenCodeReview（ocr，Apache-2.0）导出内置评审规则到 reviewer 技能里。
# 只在想更新规则时手动跑；用的电脑需要先 npm i -g @alibaba-group/open-code-review。
set -euo pipefail
OUT="$(cd "$(dirname "$0")/.." && pwd)/roles/reviewer/skills/review-checklist/ocr-rules"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cd "$TMP" && git init -q
mkdir -p "$OUT"
VER=$(ocr --version | head -1)
# 文件名 = 规则组，后面是用来探测该组的示例扩展名
while read -r name ext; do
  {
    echo "<!-- 来源：$VER 内置规则（Apache-2.0，见仓库 THIRD_PARTY_NOTICES.md），由 scripts/sync-ocr-rules.sh 导出，勿手改 -->"
    echo "<!-- 适用：$(ocr rules check "a.$ext" | sed -n 's/^Pattern: //p') -->"
    echo
    ocr rules check "a.$ext" | sed '1,/^────/d'
  } > "$OUT/$name.md"
  echo "  $name.md"
done <<'LIST'
java java
go go
ts-js ts
python py
kotlin kt
rust rs
c c
cpp cpp
swift swift
php php
yaml yaml
default sh
LIST
echo "已导出到 $OUT"
