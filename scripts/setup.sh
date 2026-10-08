#!/usr/bin/env bash
# 在这台电脑上安装 claude-team 的角色。可以重复执行：已装的会更新到最新。
#
#   scripts/setup.sh                    从 GitHub 安装全部角色
#   scripts/setup.sh developer writer   只装指定角色（team 核心总会装上）
#   scripts/setup.sh --dev              以本地克隆为来源：改了仓库文件，/reload-plugins 即生效
#
# 依赖：bash、Claude Code（claude 命令）。Windows 请看 README 里的 PowerShell 命令。
set -euo pipefail

REPO="hujiuyuan/claude-team"
MARKET="claude-team"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

dev=0
roles=()
for arg in "$@"; do
  case "$arg" in
    --dev) dev=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    -*) echo "未知参数：$arg" >&2; exit 1 ;;
    *) roles+=("$arg") ;;
  esac
done

command -v claude >/dev/null || { echo "找不到 claude 命令，请先安装 Claude Code" >&2; exit 1; }

if [ ${#roles[@]} -eq 0 ]; then
  for d in "$ROOT"/roles/*/; do roles+=("$(basename "$d")"); done
fi
for r in "${roles[@]}"; do
  [ -d "$ROOT/roles/$r" ] || { echo "没有这个角色：$r（可选：$(ls "$ROOT/roles" | tr '\n' ' ')）" >&2; exit 1; }
done

if [ "$dev" = 1 ]; then want="$ROOT"; else want="$REPO"; fi

# 已添加的 marketplace 来源和这次要的不一样（GitHub ↔ 本地克隆）时，先移除再重新添加
entry=$(claude plugin marketplace list --json </dev/null | tr -d '\n' | grep -o "{[^{}]*\"name\": *\"$MARKET\"[^{}]*}" || true)
if [ -n "$entry" ] && ! printf '%s' "$entry" | grep -qF "\"$want\""; then
  echo "→ marketplace 来源改为 $want，重新添加"
  claude plugin marketplace remove "$MARKET" </dev/null
  entry=""
fi
if [ -z "$entry" ]; then
  echo "→ 添加 marketplace：$want"
  claude plugin marketplace add "$want" </dev/null
else
  echo "→ 更新 marketplace：$MARKET"
  claude plugin marketplace update "$MARKET" </dev/null
fi

installed=()
for r in team "${roles[@]}"; do
  case " ${installed[*]-} " in *" $r "*) continue ;; esac
  echo "→ 安装 $r"
  claude plugin install "$r@$MARKET" </dev/null
  [ "$dev" = 1 ] || claude plugin update "$r@$MARKET" </dev/null
  installed+=("$r")
done

echo
echo "✓ 已安装：${installed[*]}"
echo "  新开的会话自动生效；已打开的会话里执行 /reload-plugins。"
