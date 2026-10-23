# -*- coding: utf-8 -*-
"""第 12 项「术语表对账」的测试。

每条用例都标了「它在什么情况下会假」，见各 case 的 docstring。
跑法：python3 test_glossary.py
"""
import importlib.util
import os
import io
import sys
import contextlib

SPEC = importlib.util.spec_from_file_location(
    "ca", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-anchors.py"))
ca = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ca)

CLEAN = """# 设计

## 1. 术语表

| 术语 | 一句话是什么 | 在本项目里具体指什么 | **不是什么** | 在哪能看到 |
|---|---|---|---|---|
| **冲正** | 记错了反向再记一笔 | 只动账 | **不是**退款，钱不回对端 | `TxnDao.java` |
| **催缴** | 到期前提醒交钱 | 定时任务发信 | **不是**罚款 | `DunningJob.java` |

## 2. 正文

冲正发生时不产生退款。催缴由定时任务发起，见 §1 术语表「冲正」。
"""


def run(text):
    """跑一次检查，返回 (失败计数, 输出文本)。"""
    rep = ca.Report()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ca.check_glossary(("设计文档", text) if text is not None else None, rep)
    return rep.fail, buf.getvalue()


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def t_no_design():
    """没给设计文档 → 跳过。会假：如果改成报失败，S 档全员误报。"""
    f, out = run(None)
    assert f == 0, out
    assert "跳过" in out, out


@case
def t_no_glossary_section():
    """有文档但没有术语表小节 → 跳过。
    会假：M 档按 design-doc.md:51 可略去术语表，报红就是误报。"""
    f, out = run("# 设计\n\n## 2. 正文\n\n随便写点什么。\n")
    assert f == 0, out
    assert "跳过" in out, out


@case
def t_clean_passes():
    """干净的术语表 → 零失败。会假：任一子项误伤合格文档。"""
    f, out = run(CLEAN)
    assert f == 0, out
    assert "✔" in out, out


@case
def t_padded_entry_fails():
    """收了词条但正文一次都没用到 → 红（词条注水）。
    会假：把'幽灵词'的判定写成永远找得到。"""
    bad = CLEAN.replace("| **催缴** |", "| **幽灵词** |")
    f, out = run(bad)
    assert f >= 1, out
    assert "幽灵词" in out, out
    assert "正文没用到" in out, out


@case
def t_dangling_backref_fails():
    """正文写「术语表「X」」但 X 不在表里 → 红（回指断链）。
    会假：回指正则抓不到「术语表「X」」这个写法。"""
    bad = CLEAN.replace("见 §1 术语表「冲正」", "见 §1 术语表「核销」")
    f, out = run(bad)
    assert f >= 1, out
    assert "核销" in out, out


@case
def t_empty_fourth_column_fails():
    """第四列「不是什么」空着 → 红。
    会假：把空值判定写成只认 None 不认空串。"""
    bad = CLEAN.replace("| **不是**退款，钱不回对端 |", "|  |")
    f, out = run(bad)
    assert f >= 1, out
    assert "不是什么" in out, out


@case
def t_uncollected_candidate_is_warning_only():
    """正文加粗了未收录的名词 → 只提醒，不算失败。
    会假：把候选提醒写成 fatal，178 条噪声会让整个脚本永远红。"""
    # 只追加一个未收录的加粗名词，不动已有词条的用例（动了会误触子项①词条注水）
    warn = CLEAN + "\n又：**线下核销**由人工发起，走同一条入账。\n"
    f, out = run(warn)
    assert f == 0, "候选提醒不许算失败\n" + out
    assert "线下核销" in out, out


def main():
    passed = failed = 0
    for fn in CASES:
        try:
            fn()
            print("  PASS  %s" % fn.__name__)
            passed += 1
        except AssertionError as e:
            print("  FAIL  %s\n        %s" % (fn.__name__, str(e).split("\n")[0][:120]))
            failed += 1
        except Exception as e:
            print("  ERROR %s: %s: %s" % (fn.__name__, type(e).__name__, e))
            failed += 1
    print("\n%d passed, %d failed" % (passed, failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
