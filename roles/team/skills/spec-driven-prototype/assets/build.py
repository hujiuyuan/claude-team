#!/usr/bin/env python3
"""
原型构建脚本 · spec-driven-prototype

职责：把底板 base.html + 若干页面模块 n*.js 拼装成单文件产物。
铁律：只改模块，不改产物。每次改动都重新跑本脚本。

用法：
    python build.py                    # 构建
    python build.py --check            # 构建并跑自检

模块加载顺序很重要：
  - 页面定义模块（定义 P[...]）必须在引擎之后
  - 数据模块（SPEC / UIF / ADV / CHG / DBM）必须在使用它们的面板模块之前
  - 导航与路由模块必须最后（它结尾调用 buildNav(); render();）
"""
import re, subprocess, sys, os

BASE   = 'base.html'
OUT    = os.environ.get('PROTO_OUT', 'prototype.html')
ORDER  = [2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15, 16, 8, 9, 17, 18, 19, 7]

# 注入点：底板里的锚文本。找不到就立刻失败，不要静默跳过。
CSS_MARK    = "@media(max-width:860px){\n  #side{position:fixed"
TOPBAR_MARK = '<div class="tenant" id="tenant"></div>'

CSS = r"""
/* 在此追加本项目的样式块。建议分节：
   泳道流程图 / 交互流程界面态 / 上下分区 / 需求面板手风琴 / 粘性操作列

   上下分区的必要样式（照抄即可）：
   .wrap{max-width:none;min-width:1200px}
   .split2{display:block}
   .lpane{margin-bottom:26px}
   .lpane:after{content:"";display:block;border-top:1px dashed var(--line);margin-top:22px}
   #body{overflow-x:auto}
   @media(max-width:1200px){ .wrap{min-width:0} }
   .rsec>header{cursor:pointer;user-select:none}
   .rsec:not(.open) .rsecb{display:none}
   .rsec:not(.open) .racc{transform:rotate(-90deg)}
   th.stk,td.stk{position:sticky;right:0;z-index:2;background:#fff;
     box-shadow:inset 1px 0 0 var(--line),-9px 0 11px -9px rgba(21,34,51,.20)}
   th.stk{background:#FAFBFC;z-index:3}
*/
"""

TOPBAR = ('<button class="btn sm" onclick="go(\'doc/regions\')">区域索引</button>\n'
          '      <div class="tenant" id="tenant"></div>')

REPLACE = [
    # ('底板中的文本', '替换为'),
]


def build():
    s = open(BASE, encoding='utf-8').read()

    assert CSS_MARK in s, 'CSS 注入点未找到，检查 base.html 是否被改动'
    s = s.replace(CSS_MARK, CSS + '\n' + CSS_MARK, 1)

    assert TOPBAR_MARK in s, '顶栏注入点未找到'
    s = s.replace(TOPBAR_MARK, TOPBAR, 1)

    for a, b in REPLACE:
        assert a in s, f'替换目标未找到：{a[:40]}'
        s = s.replace(a, b)

    missing = [i for i in ORDER if not os.path.exists(f'n{i}.js')]
    assert not missing, f'缺少模块：{missing}'
    add = ''.join(open(f'n{i}.js', encoding='utf-8').read() for i in ORDER)

    assert '\n</script>' in s, '找不到脚本结束标记'
    s = s.replace('\n</script>', add + '\n</script>', 1)

    open(OUT, 'w', encoding='utf-8').write(s)
    print(f'构建完成 {len(s)} bytes | 模块顺序 {ORDER}')
    return s


def check(s):
    m = re.search(r'<script>(.*)</script>', s, re.S)
    open('/tmp/chk.js', 'w', encoding='utf-8').write(m.group(1))

    r = subprocess.run(['node', '--check', '/tmp/chk.js'], capture_output=True, text=True)
    if r.returncode:
        print('语法错误：\n' + r.stderr); sys.exit(1)
    print('语法通过')

    if os.path.exists('validate.js'):
        with open('/tmp/run.js', 'w', encoding='utf-8') as f:
            for p in ('validate.js', '/tmp/chk.js'):
                f.write(open(p, encoding='utf-8').read())
            f.write('\n;__validate();\n')
        r = subprocess.run(['node', '/tmp/run.js'], capture_output=True, text=True)
        print(r.stdout or r.stderr)
        if '问题 0' not in r.stdout:
            sys.exit(1)


if __name__ == '__main__':
    s = build()
    if '--check' in sys.argv:
        check(s)
