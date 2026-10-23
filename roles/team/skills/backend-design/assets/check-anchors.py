#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
锚点对账脚本 —— 拷进项目 tools/ 下用。

只做跨项目通用的存在性检查，不做语言特定的深度解析
（枚举值域比对、路由比对这类交给项目自己已有的工具，本脚本不重造）。

查十二件事：
   1. 文档里反引号包的文件路径 / 文件名，在不在
   2. 文档里反引号包的类名、方法名，源码里 grep 得到吗
   3. 设计文档与执行手册的任务编号集合是否相等
   4. 未决台账编号 ↔ 代码接缝注释，两边对不对得上
   5. 执行手册里有没有代码块（命令行除外）——有就是越界
   6. 文档里写的 §X.Y 有没有对应标题
   7. 出入参字段表：第一列是不是代码里的真名、类型有没有写成「A 或 B」
   8. 文档里的 `表.列` 在迁移脚本里有没有
   9. 驼峰标识符长度有没有超上限
  10. 文档给出的方法签名跟仓库真实签名一不一致
  11. 每个任务的「要读的小节」清单取没取到传递闭包
  12. 术语表：收了的用得上吗、回指指得到吗、「不是什么」那列空没空

两种阶段：
  设计期（默认）  ——「找不到的标识符」只提醒不失败，因为设计本来就在描述还没建的东西
  完工后 --strict ——「找不到的标识符」算失败，用来验收「设计里写的都真的落地了」

用法：
  # 设计期自检（多仓库就给多个 --src）
  python3 check-anchors.py --src app-server --src app-web \
      --design docs/xx-设计.md --manual docs/xx-执行手册.md --ledger docs/xx-未决台账.md

  # 完工验收
  python3 check-anchors.py --src . --design d.md --manual m.md --strict

  # 任务编号 / 台账编号用别的格式：正则要收窄到各自前缀
  python3 check-anchors.py --src . --manual m.md --task-pattern '\bT-[0-9]{2}\b'

注意：任务编号、台账编号、需求条目编号都是「前缀-序号」同格式，正则分不出语义。
默认的 \b[A-Z]{1,4}-\d{1,3}\b 会把三者一起收进来 —— 要么收窄到本类前缀，
要么看输出里的「前缀分布」，混进外来前缀时一眼能看见。

退出码：全过 0，有失败 1，参数错 2。
"""

import argparse
import os
import re
import sys

# ---------------------------------------------------------------- 配置

# 读进内存供 grep 的源码后缀
SRC_EXT = {
    ".java", ".kt", ".scala", ".groovy",
    ".py", ".go", ".rs", ".rb", ".php",
    ".ts", ".tsx", ".js", ".jsx", ".vue",
    ".sql", ".xml", ".yml", ".yaml", ".properties", ".json",
}
# 认得出的文件后缀（反引号内容带这些后缀才当路径检查，避免 Foo.bar 被当成文件）
FILE_EXT = SRC_EXT | {
    ".md", ".html", ".htm", ".css", ".scss", ".txt", ".csv",
    ".sh", ".conf", ".toml", ".ini", ".gradle", ".lock", ".env",
}
SKIP_DIR = {
    ".git", "node_modules", "target", "build", "dist", "out",
    ".idea", ".vscode", "__pycache__", ".venv", "venv", ".next", ".turbo",
}

# 反引号内容当"标识符"检查的条件：大驼峰，且大小写都有，不含下划线
# —— 这样 V78 / TRD / TRADE_CFG_TENANT / NEXT_PUBLIC_API_BASE_URL 都不会被误判成类名
RE_IDENT = re.compile(r"^[A-Z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)*(?:\(\))?$")
RE_HAS_LOWER = re.compile(r"[a-z]")
RE_FENCE = re.compile(r"^```([\w+-]*)", re.M)
# 执行手册里允许的围栏：命令行、纯文本、依赖批次图。
# 不允许 java / sql / ts 这类——接口签名、字段表、DDL 只能写在设计文档里。
MANUAL_OK_LANGS = {"bash", "sh", "shell", "console", "zsh", "text", "diff", "mermaid", ""}

RESET, RED, GREEN, YELLOW, DIM = "\033[0m", "\033[31m", "\033[32m", "\033[33m", "\033[2m"


def color(s, c):
    return c + s + RESET if sys.stdout.isatty() else s


# ---------------------------------------------------------------- 工具

def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def load_sources(roots):
    """把所有源码根读进内存。返回 (拼接文本, 相对路径集合, 文件名集合)。"""
    blobs, paths, names = [], set(), set()
    for root in roots:
        root = os.path.abspath(root)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                paths.add(os.path.relpath(full, root).replace(os.sep, "/"))
                names.add(fn)
                if os.path.splitext(fn)[1].lower() in SRC_EXT:
                    try:
                        blobs.append(read(full))
                    except OSError:
                        pass
    return "\n".join(blobs), paths, names


def backticks(text):
    """抽出所有单反引号内容，跳过围栏代码块内部。"""
    out, in_fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.extend(re.findall(r"`([^`\n]+)`", line))
    return out


def is_filelike(tok):
    ext = os.path.splitext(tok)[1].lower()
    return ext in FILE_EXT and not tok.endswith("/")


def prefixes(ids):
    """把编号集合按前缀分组计数，形如 'A(11) MBR(1)'。

    三类编号（任务 / 台账 / 需求条目）都是「前缀-序号」同格式，正则分不出语义。
    把前缀分布打出来，混进外来前缀时人一眼能看见——不依赖谁记得传窄正则。
    """
    bucket = {}
    for i in ids:
        p = i.rsplit("-", 1)[0] if "-" in i else i
        bucket[p] = bucket.get(p, 0) + 1
    return " ".join("%s(%d)" % (p, n) for p, n in sorted(bucket.items()))


def is_identlike(tok):
    return (not is_filelike(tok)
            and RE_IDENT.match(tok) is not None
            and RE_HAS_LOWER.search(tok) is not None
            and len(tok) >= 4)


class Report:
    def __init__(self):
        self.fail = 0

    def ok(self, msg):
        print(color("  ✔ ", GREEN) + msg)

    def bad(self, title, items, fatal=True):
        if fatal:
            self.fail += 1
        head = color("  ✘ " + title, RED) if fatal else color("  ! " + title, YELLOW)
        print(head)
        for i in items[:30]:
            print("      " + i)
        if len(items) > 30:
            print(color("      … 另有 %d 条未列出" % (len(items) - 30), DIM))

    def skip(self, msg):
        print(color("  – " + msg, DIM))


# ---------------------------------------------------------------- 十二项检查

def check_paths(docs, paths, names, rep, strict):
    """1. 反引号里的文件路径 / 文件名，在不在。"""
    missing, checked = [], 0
    for label, text in docs:
        for tok in sorted(set(backticks(text))):
            if not is_filelike(tok) or "*" in tok:  # 通配写法不检
                continue
            checked += 1
            probe = tok.lstrip("./")
            if probe in paths or os.path.basename(probe) in names:
                continue
            if any(p.endswith("/" + probe) for p in paths):
                continue
            missing.append("%s：`%s`" % (label, tok))
    if not checked:
        rep.skip("路径锚点：文档里没有可检的路径")
    elif missing and strict:
        rep.bad("路径锚点：%d/%d 个找不到——完工验收不允许" % (len(missing), checked),
                missing, fatal=True)
    elif missing:
        rep.bad("路径锚点：%d/%d 个还不存在。逐条确认是「本次要新建的」还是「路径写错了 / 跨仓库没加进 --src」"
                % (len(missing), checked), missing, fatal=False)
    else:
        rep.ok("路径锚点：%d 个全部存在" % checked)


def check_idents(docs, blob, rep, strict):
    """2. 反引号里的类名 / 方法名，源码里有没有。"""
    missing, checked = [], 0
    for label, text in docs:
        for tok in sorted(set(backticks(text))):
            if not is_identlike(tok):
                continue
            checked += 1
            parts = [p for p in tok.rstrip("()").split(".") if p]
            if all(p in blob for p in parts):
                continue
            missing.append("%s：`%s`" % (label, tok))
    if not checked:
        rep.skip("标识符锚点：文档里没有可检的标识符")
    elif missing:
        if strict:
            rep.bad("标识符锚点：%d/%d 个在源码里找不到——完工验收不允许"
                    % (len(missing), checked), missing, fatal=True)
        else:
            rep.bad("标识符锚点：%d/%d 个源码里还没有。逐条确认是「本次要新建的」还是「名字写错了」"
                    % (len(missing), checked), missing, fatal=False)
    else:
        rep.ok("标识符锚点：%d 个全部在源码里找得到" % checked)


def check_task_ids(design, manual, pattern, rep, strict):
    """3. 设计文档与执行手册的任务编号集合是否相等。"""
    if not (design and manual):
        rep.skip("任务编号：缺设计文档或执行手册，跳过（S 档只有手册一份，本项免）")
        return
    rx = re.compile(pattern)
    a, b = set(rx.findall(design[1])), set(rx.findall(manual[1]))
    if not a and not b:
        msg = ("任务编号：两份文档里一条编号都没匹配到（正则 %s）。"
               "多半是前缀没配对——用 --task-pattern 指定项目实际在用的格式" % pattern)
        rep.bad(msg, ["设计文档 + 执行手册均无匹配"], fatal=bool(strict))
        return
    # 只比「两份文档都在成规模使用的前缀」。单份文档里零星出现的 X-N（需求条目编号
    # A-40、外部任务号 MEM-05、甚至 AES-256 这种算法名）不是本条线的任务编号，
    # 拿它们报红只会让人开始无视这个检查。
    def pfx(t):
        return t.rsplit("-", 1)[0]
    from collections import Counter
    ca, cb = Counter(pfx(t) for t in a), Counter(pfx(t) for t in b)
    live = {p for p in set(ca) & set(cb) if ca[p] >= 3 and cb[p] >= 3}
    if live:
        dropped = sorted((a | b) - {t for t in a | b if pfx(t) in live})
        a = {t for t in a if pfx(t) in live}
        b = {t for t in b if pfx(t) in live}
    else:
        dropped = []
    only_a, only_b = sorted(a - b), sorted(b - a)
    hint = ("　　前缀分布：设计文档 %s ｜ 执行手册 %s"
            "（多出来的前缀多半是需求条目编号被 --task-pattern 误收了）"
            % (prefixes(a) or "无", prefixes(b) or "无"))
    if only_a or only_b:
        items = []
        if only_a:
            items.append("只在设计文档里：" + ", ".join(only_a))
        if only_b:
            items.append("只在执行手册里：" + ", ".join(only_b))
        items.append(hint.strip())
        rep.bad("任务编号：两份文档的编号集合不相等", items)
    else:
        extra = ("；已跳过非本线编号 %d 个：%s" % (len(dropped), ", ".join(dropped[:8]))) if dropped else ""
        rep.ok("任务编号：两份文档编号集合相等（%d 个）· 前缀 %s%s" % (len(a), prefixes(a), extra))


def check_ledger(ledger, blob, pattern, rep, strict):
    """4. 台账编号 ↔ 代码接缝，两边互相对得上。"""
    if not ledger:
        rep.skip("台账对账：没给未决台账，跳过")
        return
    rx = re.compile(pattern)
    ids = set(rx.findall(ledger[1]))
    if not ids:
        msg = ("台账对账：给了 --ledger 却一条编号都没匹配到（正则 %s）。"
               "多半是前缀没配对——用 --ledger-pattern 指定项目实际在用的格式" % pattern)
        # 完工验收时「匹配到零条」几乎必然是配错了，不能当跳过放行
        if strict:
            rep.bad(msg, ["台账文件：" + ledger[0]], fatal=True)
        else:
            rep.bad(msg, ["台账文件：" + ledger[0]], fatal=False)
        return
    orphan = sorted(i for i in ids if i not in blob)
    dangling = sorted(i for i in set(rx.findall(blob)) if i not in ids)
    items = []
    if orphan:
        items.append("台账有、代码里没接缝：" + ", ".join(orphan))
    if dangling:
        items.append("代码里引了、台账里没有：" + ", ".join(dangling))
    if items and not strict and not dangling:
        rep.bad("台账对账：%d 条台账项在代码里还没有接缝。逐条确认是「本次要新建的接缝」还是「编号写错了」"
                % len(orphan), items, fatal=False)
    elif items:
        items.append("前缀分布：%s（多出来的前缀多半是别类编号被 --ledger-pattern 误收了）"
                     % prefixes(ids))
        rep.bad("台账对账：候补项与代码接缝对不上", items)
    else:
        rep.ok("台账对账：%d 条与代码接缝双向对得上 · 前缀 %s" % (len(ids), prefixes(ids)))


RE_SECREF = re.compile(r"§\s*(\d+(?:\.\d+)*)")
RE_HEADING = re.compile(r"^#{2,6}\s+(\d+(?:\.\d+)*)\s", re.M)
RE_TABLEROW = re.compile(r"^\|(.+)\|\s*$", re.M)
CJK = re.compile(r"[\u4e00-\u9fff]")


def check_section_refs(design, rep):
    """6. 文档里写的 §X.Y 必须真的有那一节。指向不存在的小节比不指还糟。"""
    if not design:
        rep.skip("小节指向：没给设计文档，跳过")
        return
    text = design[1]
    have = set(RE_HEADING.findall(text))
    # 章级标题（## 4. 设计）也算，补进去
    have |= set(m.group(1) for m in re.finditer(r"^#{2,6}\s+(\d+)\.", text, re.M))
    # 只判「指向本文自己」的 §编号。同一行里先出现别的文档名（xxx.md / 反引号包的文件名）
    # 时，那个 § 指的是外部文档的小节，本脚本管不着，跳过。
    want = set()
    for ln in text.split("\n"):
        for m in RE_SECREF.finditer(ln):
            before = ln[:m.start()]
            if re.search(r"[\w-]+\.md|ddl-conventions|adr/|架构仓库|库表设计约定", before):
                continue
            want.add(m.group(1))
    missing = sorted(w for w in want if w not in have)
    if missing:
        rep.bad("小节指向：%d 个 §编号在本文里没有对应标题——**指向不存在的小节比不指还糟**"
                % len(missing), ["§" + m for m in missing])
    else:
        rep.ok("小节指向：全部 §编号都有对应标题")


def check_field_tables(design, rep):
    """7. 出入参字段表：第一列必须是代码里真实的名字；类型不许写「A 或 B」。"""
    if not design:
        rep.skip("字段表：没给设计文档，跳过")
        return
    text = design[1]
    lines = text.split("\n")
    cjk_first, or_type = [], []
    in_field_table = False
    for i, ln in enumerate(lines):
        m = RE_TABLEROW.match(ln)
        if not m:
            in_field_table = False
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if not cells:
            continue
        head = cells[0].strip("* `")
        # 表头：第一列叫「字段」或「JSON 键名」之类，且有「类型」列 → 认定为字段表
        if head in ("字段", "字段名", "JSON 键名", "键名", "列", "列名") and any("类型" in c for c in cells):
            in_field_table = True
            type_idx = next(i2 for i2, c in enumerate(cells) if "类型" in c)
            continue
        if not in_field_table:
            continue
        if set(cells[0]) <= set("-: "):   # 分隔行
            continue
        first = cells[0].strip("* `")
        if first and CJK.search(first) and "`" not in cells[0]:
            cjk_first.append("第 %d 行：%s" % (i + 1, cells[0][:40]))
        if type_idx < len(cells) and re.search(r"\S\s*或\s*\S", cells[type_idx]):
            or_type.append("第 %d 行：%s" % (i + 1, cells[type_idx][:40]))
    if cjk_first:
        rep.bad("字段表第一列是中文：%d 处。**第一列必须是代码里真实的名字**（JSON 键名 / Java 字段名），"
                "中文只能放「含义」列——对面做穷尽校验时键名对不上会整单作废，且失败是静默的"
                % len(cjk_first), cjk_first[:12])
    else:
        rep.ok("字段表第一列：都是代码里的真实名字")
    if or_type:
        rep.bad("字段类型写成「A 或 B」：%d 处。强类型语言里一个字段不能是两种类型，"
                "写代码的人只能自己发明形状。真有互斥形态就用封闭类型（sealed）交给编译器"
                % len(or_type), or_type[:12])
    else:
        rep.ok("字段类型：无「A 或 B」式二选一")


def check_table_columns(docs, roots, rep):
    """8. 文档里引用的 `表名.列名` 必须在迁移脚本里真的存在。"""
    mig = []
    for r in roots:
        for dp, _, fns in os.walk(r):
            if "migration" not in dp:
                continue
            for fn in fns:
                if fn.endswith(".sql"):
                    mig.append(os.path.join(dp, fn))
    if not mig:
        rep.skip("库表列：没找到迁移脚本目录，跳过")
        return
    sql = "\n".join(read(p) for p in mig)
    bad = []
    seen = set()
    for label, text in docs:
        for tok in backticks(text):
            m = re.fullmatch(r"([a-z][a-z0-9_]{2,})\.([a-z][a-z0-9_]{2,})", tok)
            if not m or tok in seen:
                continue
            seen.add(tok)
            tbl, col = m.group(1), m.group(2)
            if not re.search(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?%s\b" % re.escape(tbl), sql, re.I):
                continue          # 不是真表名（权限键 fin.rcp、包路径 dao.impl 之类），不判
            if not re.search(r"^\s*%s\s" % re.escape(col), sql, re.M) and \
               not re.search(r"COLUMN\s+%s\.%s\b" % (re.escape(tbl), re.escape(col)), sql):
                bad.append("%s：`%s`" % (label, tok))
    if bad:
        rep.bad("库表列：%d 个 `表.列` 在迁移脚本里找不到。逐条确认是「本次要新建的列」"
                "还是「列名写错了」——写错的话写到那一步才会发现" % len(bad), sorted(set(bad))[:15], fatal=False)
    else:
        rep.ok("库表列：文档引用的列在迁移脚本里都有")


RE_JAVAISH = re.compile(r"^[a-z][A-Za-z0-9]*$")


def check_name_length(docs, rep, limit=30):
    """9. 文档里给出的 Java 标识符不许超过命名长度上限（很多仓库有这条硬规则）。

    只判驼峰的方法/变量名（表名列名是 snake_case，且通常不受这条限制）。
    """
    bad = []
    for label, text in docs:
        for tok in sorted(set(backticks(text))):
            name = tok.split("(")[0].split(".")[-1]
            if RE_JAVAISH.match(name) and len(name) > limit and any(c.isupper() for c in name):
                bad.append("%s：`%s`（%d 字符）" % (label, name, len(name)))
    if bad:
        rep.bad("命名长度：%d 个驼峰标识符超过 %d 字符。仓库通常有「类/方法/变量名不得超过 N 字符」"
                "的硬规则——文档自己给出的名字违反它，照抄就过不了检查"
                % (len(bad), limit), sorted(set(bad))[:12], fatal=False)
    else:
        rep.ok("命名长度：文档给出的驼峰标识符都不超过 %d 字符" % limit)


RE_DECL = re.compile(
    r"\b(?:public\s+|private\s+|protected\s+|static\s+|final\s+|default\s+|abstract\s+)*"
    r"([A-Za-z_][\w.<>\[\], ?]*?)\s+"          # 返回类型
    r"([a-z][A-Za-z0-9_]*)\s*"                  # 方法名
    r"\(([^)]*)\)")                             # 参数表


def _types_of(params):
    """从参数表里抽出类型序列，忽略参数名与泛型内部的逗号。"""
    out, depth, cur = [], 0, ""
    for ch in params:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    types = []
    for p in out:
        p = re.sub(r"@\w+(\([^)]*\))?", "", p).strip()
        if not p:
            continue
        toks = p.split()
        types.append(re.sub(r"\s+", "", toks[0] if len(toks) == 1 else " ".join(toks[:-1])))
    return types


def _strip_fences(text):
    """摘掉 fenced code block。签名走样只查「正文内联的方法引用」，不查代码块。

    代码块里是「新定义」（新建接口/类/方法的完整声明，如 `public interface EffectAction {...}`），
    不是「对已有方法的描述」；而签名走样这一项要抓的是后者——「类和方法都存在，只有描述错了」。
    不摘的话，新接口里 `apply`/`register` 这类通用方法名会撞上仓库里无关的同名方法，报假红。
    """
    return re.sub(r"```[^\n]*\n.*?```", "", text, flags=re.S)


def check_signature_drift(docs, roots, rep):
    """10. 文档里给出的方法签名，要跟仓库里真实的那一个一致。

    这一项补的是前面几项的盲区：类和方法**存在**（第 2 项过），但文档对它的
    **描述**（返回类型 / 参数类型）是错的——照着写调用代码会编译不过，而且
    看的人会以为是自己写错了。

    只扫**正文内联**的方法引用（表格、段落里的 `X.y(...)`），**跳过 fenced code block**——
    代码块里是新定义接口，仓库里根本没有那个类，不该拿去跟同名方法比。
    """
    src = {}
    for r in roots:
        for dp, _, fns in os.walk(r):
            if os.sep + "test" + os.sep in dp:
                continue
            for fn in fns:
                if fn.endswith(".java"):
                    for m in RE_DECL.finditer(read(os.path.join(dp, fn))):
                        ret, name, params = m.group(1).strip(), m.group(2), m.group(3)
                        if ret in ("return", "new", "if", "for", "while", "catch", "switch"):
                            continue
                        src.setdefault(name, []).append(
                            (ret, tuple(_types_of(params)), os.path.relpath(os.path.join(dp, fn), r)))
    bad = []
    seen = set()
    for label, text in docs:
        for m in RE_DECL.finditer(_strip_fences(text)):
            ret, name, params = m.group(1).strip(), m.group(2), m.group(3)
            if name not in src or (label, name) in seen:
                continue
            real = src[name]
            if len({(r0, t0) for r0, t0, _ in real}) != 1:
                continue                       # 同名多签名（重载），不判
            seen.add((label, name))
            rret, rtypes, rfile = real[0]
            dtypes = tuple(_types_of(params))
            if len(dtypes) != len(rtypes):
                bad.append("%s：`%s` 文档 %d 个参数 / 真实 %d 个（%s）"
                           % (label, name, len(dtypes), len(rtypes), rfile))
            elif dtypes != rtypes:
                bad.append("%s：`%s` 参数类型 文档 (%s) / 真实 (%s)（%s）"
                           % (label, name, ", ".join(dtypes), ", ".join(rtypes), rfile))
            elif ret.split()[-1] != rret.split()[-1]:
                bad.append("%s：`%s` 返回类型 文档 %s / 真实 %s（%s）"
                           % (label, name, ret, rret, rfile))
    if bad:
        rep.bad("签名走样：%d 个方法，文档写的跟仓库里真实的那一个对不上。"
                "⚠️ 这是最危险的一类——类和方法都存在（前面的检查全过），"
                "只有你的描述是错的，别人照着写调用代码会编译不过、还以为是自己错了"
                % len(bad), sorted(set(bad))[:15])
    else:
        rep.ok("签名走样：文档给出的方法签名与仓库真实签名一致")


RE_TASKSEC = re.compile(r"^###\s+([A-Z]{2,4}-\d{1,3})\s", re.M)
RE_READLIST = re.compile(r"本任务要读的设计文档小节[^\n]*")


def _design_sections(text):
    """把设计文档切成 {编号: 该节正文} —— 正文到下一个同级或更高级标题为止。"""
    hits = [(m.start(), len(m.group(1)), m.group(2))
            for m in re.finditer(r"^(#{2,6})\s+(\d+(?:\.\d+)*)[ .．]", text, re.M)]
    out = {}
    for i, (pos, lvl, num) in enumerate(hits):
        end = len(text)
        for pos2, lvl2, _ in hits[i + 1:]:
            if lvl2 <= lvl:
                end = pos2
                break
        out[num] = text[pos:end]
    return out


def check_readlist_closure(design, manual, rep):
    """11. 任务书给的「要读哪几节」清单，必须取传递闭包。

    清单里的某一节如果又把人指向另一节，那一节也得在清单里——否则按派活规则
    他读不到，等于指了个空。真实盲测栽在这上面：清单里的速查节写着
    「完整字段表在 §X，那一节必须读」，而 §X 不在清单里。

    另一个来源也要收进清单：任务书「2 前置」清单之外的正文（第 3/4/6/7 段）
    里出现的「见 §X / 见设计文档 §X」读指引指针——任务书指到哪，干活人就被
    指引去读哪。真实盲测栽过：正文三次写「三条调用规矩见设计文档 §4.3.0」，
    而 §4.3.0 不在清单里。
    """
    if not (design and manual):
        rep.skip("清单闭包：缺设计文档或执行手册，跳过")
        return
    secs = _design_sections(design[1])
    text = manual[1]
    tasks = [(m.group(1), m.start()) for m in RE_TASKSEC.finditer(text)]
    bad = []
    for i, (tid, pos) in enumerate(tasks):
        end = tasks[i + 1][1] if i + 1 < len(tasks) else len(text)
        body = text[pos:end]
        m = RE_READLIST.search(body)
        if not m:
            continue
        listed = set(re.findall(r"§\s*(\d+(?:\.\d+)*)", m.group(0)))
        # 任务书整节正文里的「读指引」指针也进清单。「（设计文档 §3.5）」这种
        # 括号出处标注不算——那是标出处，不是「去读」。
        listed |= set(re.findall(
            r"(?:见|详见|参见|去读)\s*(?:设计文档\s*)?§\s*(\d+(?:\.\d+)*)", body))
        if not listed:
            continue
        for num in sorted(listed):
            body_sec = secs.get(num, "")
            # 只认「强指针」：那句话本身在说「你必须去读那一节 / 完整的东西在那一节」。
            # 「详细理由见 §X」「两处互指」这类补充指针不算——那是给想深究的人看的，
            # 不读也能把代码写对。全算的话一个任务能牵出十几节，清单就没意义了。
            for ln in body_sec.split("\n"):
                if not re.search(r"必须读|必读|完整字段表|完整清单|完整列清单|逐字照|一并读|全在", ln):
                    continue
                for tgt in set(re.findall(r"§\s*(\d+(?:\.\d+)*)", ln)):
                    if tgt in listed or tgt == num or tgt.startswith(num + "."):
                        continue
                    bad.append("%s：清单里的 §%s 明说「%s」要去 §%s，**但 §%s 不在清单里**"
                               % (tid, num, ln.strip()[:28], tgt, tgt))
    if bad:
        rep.bad("清单闭包：%d 处「清单内的节指向清单外的节」。按派活规则他读不到那一节，"
                "**等于指了个空**——把目标小节一并列进清单" % len(bad), sorted(set(bad))[:15])
    else:
        rep.ok("清单闭包：每个任务的小节清单都取到了传递闭包")


RE_GLOSS_SEC = re.compile(r"^##\s+\d+\s*[.、·]?\s*术语表\s*$(.*?)(?=^##\s|\Z)", re.M | re.S)
RE_GLOSS_BACKREF = re.compile(r"术语表\s*[「『\u201c]([^」』\u201d\n]{1,12})[」』\u201d]")
RE_BOLD = re.compile(r"\*\*([^*\n]{1,20})\*\*")
RE_PURE_CJK = re.compile(r"^[\u4e00-\u9fff]{2,6}$")
# 虚词与谓词字。候选提醒里凡是含这些字的一律滤掉——「一次写对」「任何情况下」这类是
# 强调语气不是术语。实测：不滤时一份 2000 行文档出 1033 个候选，滤后 194 个。
GLOSS_STOP = set("不是要都别也就只才该会能可让把被给从到在有没无未各每同另再又先后"
                 "但而且或和与及的了吗呢很更最之所以如果因为")


def _gloss_head(cell):
    """术语表第一列 → 主词。「行级安全（RLS）」→「行级安全」，「适配器 / SPI」→「适配器」。"""
    w = cell.strip().strip("* `")
    w = re.sub(r"[（(].*?[)）]", "", w)
    w = re.split(r"[/／]", w)[0]
    w = re.sub(r"\s+[A-Za-z_][A-Za-z0-9_]*$", "", w)
    return w.strip().strip("* `")


def check_glossary(design, rep):
    """12. 术语表对账：收了的要用得上、指得到，且「不是什么」那列不许空。

    分四段：前三段判失败（精确、零误报），第四段只提醒。
      ① 词条注水——收了但正文一次都没用到
      ② 回指断链——正文写「术语表「X」」而 X 不在表里
      ③ 第四列「不是什么」空着——writing-shapes.md 说它是唯一能防住「以为自己懂了」的一列，
        空了术语表就退化成两列词典
      ④ 未收候选——正文加粗的名词短语里没被收录的，只报条数与样本

    ④ 不判失败是有意的：实测精度只有三成（真术语与「删掉」「结论」这类噪声混着），
    判失败会让脚本永远红，然后被整个关掉。收不收由人过目决定。

    没有术语表小节就跳过，不报红——design-doc.md 写明 `M` 档可略去术语表、`S` 档不出设计文档。
    """
    if not design:
        rep.skip("术语表：没给设计文档，跳过")
        return
    text = design[1]
    m = RE_GLOSS_SEC.search(text)
    if not m:
        rep.skip("术语表：本文没有术语表小节（`M` 档可略、`S` 档不出本文档），跳过")
        return

    sec = m.group(1)
    body = text[:m.start(1)] + text[m.end(1):]
    rows = [ln for ln in sec.split("\n") if ln.lstrip().startswith("|")]
    if len(rows) < 3:
        rep.bad("术语表：小节在，但没有数据行", ["术语表是空表"])
        return

    header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    data = [r for r in rows[2:] if not set(r.strip().strip("| ")) <= set("-: |")]

    terms, aliases, no_col4 = [], set(), []
    for r in data:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        head = _gloss_head(cells[0])
        if not head:
            continue
        terms.append(head)
        aliases.add(head)
        aliases.add(cells[0].strip("* `"))
        if len(cells) < 4 or not cells[3] or cells[3] in ("-", "—", "/", "无"):
            no_col4.append(head)

    # ③ 第四列
    has_col4 = len(header) >= 4 and "不是" in header[3]
    if not has_col4:
        rep.bad("术语表缺「不是什么」列：现在是 %d 列。**这是唯一能防住「以为自己懂了」的一列**——"
                "少了它，术语表退化成两列词典，读的人拿自己的旧理解往上套，不会发现套错了"
                % len(header), ["表头：" + " | ".join(header)])
    elif no_col4:
        rep.bad("术语表「不是什么」列空着：%d 条。**这列最值钱**——写不出「不是什么」，"
                "通常说明这条词自己也没想清楚该跟谁划清界限" % len(no_col4), no_col4[:12])
    else:
        rep.ok("术语表「不是什么」列：%d 条全部写了" % len(terms))

    # ① 词条注水
    unused = [w for w in terms if body.count(w) == 0]
    if unused:
        rep.bad("术语表收了但正文没用到：%d 条。词条是为读正文服务的，正文不出现的词属于凑数，"
                "删掉或者去正文补上用它的地方" % len(unused), unused[:12])
    else:
        rep.ok("术语表词条：%d 条全部在正文里用到" % len(terms))

    # ② 回指断链
    dangling = sorted({x for x in RE_GLOSS_BACKREF.findall(text) if x not in aliases})
    if dangling:
        rep.bad("回指断链：%d 处写了「术语表「X」」但表里没有 X——**指向不存在的词条比不指还糟**，"
                "读的人会去翻，翻不到就只能自己猜" % len(dangling),
                ["术语表「%s」" % d for d in dangling])
    else:
        rep.ok("术语表回指：全部指得到")

    # ④ 未收候选（只提醒）
    plain = _strip_fences(body)
    cand = {t for t in (x.strip() for x in RE_BOLD.findall(plain))
            if RE_PURE_CJK.match(t) and not (set(t) & GLOSS_STOP)}
    # 候选是已收词条的一截就不报（收了「幂等键」，「幂等」不算漏）。
    # 反过来不成立：候选比词条长时（收了「租户」，出现「租户段」）可能是另一个词，照报。
    missing = [c for c in cand
               if c not in aliases and not any(c in a and c != a for a in aliases)]
    # 按正文出现次数降序——被反复用的更可能是真术语。按字典序排会把只出现一次的
    # 强调短语顶到最前面，人看第一眼全是噪声，这一项就废了。
    missing.sort(key=lambda w: (-body.count(w), w))
    if missing:
        rep.bad("术语表未收候选：正文加粗的名词里有 %d 个不在术语表。**不算失败**，"
                "人工过一遍决定收不收——判据见 writing-shapes.md 收词三类"
                % len(missing),
                ["%s（正文 %d 次）" % (w, body.count(w)) for w in missing[:12]],
                fatal=False)
    else:
        rep.ok("术语表未收候选：无")


def check_manual_fences(manual, rep):
    """5. 执行手册里不许出现代码块（命令行除外）。"""
    if not manual:
        rep.skip("手册越界：没给执行手册，跳过")
        return
    bad = [lang for lang in RE_FENCE.findall(manual[1]) if lang.lower() not in MANUAL_OK_LANGS]
    if bad:
        rep.bad("手册越界：出现 %d 个非命令行代码块（接口签名、字段表、DDL 只能写在设计文档里）"
                % len(bad), sorted(set("```" + b for b in bad)))
    else:
        rep.ok("手册越界：无非命令行代码块")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="设计文档 / 执行手册 / 未决台账 的锚点对账")
    ap.add_argument("--src", action="append", default=None,
                    help="仓库根目录，可给多次（跨仓库引用时把相关仓库都加上）。默认当前目录")
    ap.add_argument("--design", help="设计文档路径")
    ap.add_argument("--manual", help="执行手册路径")
    ap.add_argument("--ledger", help="未决台账路径")
    ap.add_argument("--name-limit", type=int, default=30,
                    help="驼峰标识符长度上限，默认 30（对齐多数仓库的命名硬规则）")
    ap.add_argument("--strict", action="store_true",
                    help="完工验收模式：源码里找不到的标识符算失败")
    ap.add_argument("--task-pattern", default=r"\b[A-Z]{1,4}-\d{1,3}\b",
                    help=r"任务编号正则，默认 \b[A-Z]{1,4}-\d{1,3}\b")
    ap.add_argument("--ledger-pattern", default=r"\bD-\d{1,3}\b",
                    help=r"台账编号正则，默认 \bD-\d{1,3}\b")
    args = ap.parse_args()

    if not (args.design or args.manual or args.ledger):
        ap.error("至少给一份文档：--design / --manual / --ledger")
    roots = args.src or ["."]
    for r in roots:
        if not os.path.isdir(r):
            print(color("不是目录：" + r, RED))
            sys.exit(2)

    def load(p, label):
        if not p:
            return None
        if not os.path.isfile(p):
            print(color("找不到文件：" + p, RED))
            sys.exit(2)
        return (label, read(p))

    design = load(args.design, "设计文档")
    manual = load(args.manual, "执行手册")
    ledger = load(args.ledger, "未决台账")
    docs = [d for d in (design, manual, ledger) if d]

    print("扫描源码根：%s" % "  ".join(os.path.abspath(r) for r in roots))
    blob, paths, names = load_sources(roots)
    print("读入 %d 个文件，源码文本 %.1f MB   模式：%s\n"
          % (len(paths), len(blob) / 1048576.0, "完工验收" if args.strict else "设计期"))

    rep = Report()
    check_paths(docs, paths, names, rep, args.strict)
    check_idents(docs, blob, rep, args.strict)
    check_task_ids(design, manual, args.task_pattern, rep, args.strict)
    check_ledger(ledger, blob, args.ledger_pattern, rep, args.strict)
    check_manual_fences(manual, rep)
    check_section_refs(design, rep)
    check_field_tables(design, rep)
    check_table_columns(docs, roots, rep)
    check_name_length(docs, rep, args.name_limit)
    check_signature_drift(docs, roots, rep)
    check_readlist_closure(design, manual, rep)
    check_glossary(design, rep)

    print()
    if rep.fail:
        print(color("对账未通过：%d 项失败" % rep.fail, RED))
        sys.exit(1)
    print(color("对账通过", GREEN))


if __name__ == "__main__":
    main()
