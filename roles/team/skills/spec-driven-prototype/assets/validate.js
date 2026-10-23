/* 自检脚本 · spec-driven-prototype
   用法：与产物中提取的脚本拼在一起用 node 跑（见 build.py 的 check()）。
   注意：不要在本文件里定义 render / M / S / D / T / U 等名字——会覆盖应用的同名符号。 */

function __mk() {
  return { innerHTML:'', textContent:'', style:{}, dataset:{},
    classList:{ add(){}, remove(){}, toggle(){}, contains(){return false} },
    addEventListener(){}, removeEventListener(){},
    querySelectorAll(){ return []; }, querySelector(){ return null; },
    closest(){ return __mk(); }, scrollIntoView(){}, appendChild(){} };
}
global.document = { querySelector: () => __mk(), querySelectorAll: () => [],
                    addEventListener(){}, createElement: () => __mk() };
global.window = global;
global.location = { hash: '' };
global.innerWidth = 1400;
global.addEventListener = () => {};
global.setTimeout = () => {};
global.clearTimeout = () => {};
global.scrollTo = () => {};
global.navigator = {};
global.console.table = global.console.table || (() => {});

function __validate() {
  let bad = 0;
  const fail = (...a) => { console.log(' ✗', ...a); bad++; };

  // 1. 导航与页面互相覆盖
  const navKeys = new Set();
  for (const e of Object.keys(NAV))
    for (const g of NAV[e])
      for (const i of g.items) if (i.k) navKeys.add(i.k);
  for (const k of navKeys) if (!P[k]) fail('导航指向的页面不存在:', k);
  for (const k of Object.keys(P)) if (!navKeys.has(k)) fail('页面无导航入口:', k);

  // 2. 逐页渲染
  const fns = new Set();
  for (const k of Object.keys(P)) {
    let html;
    try { html = R(P[k].b()); }
    catch (e) { fail('渲染失败:', k, e.message); continue; }
    if (html.length < 200)     fail('内容过短:', k);
    if (/undefined/.test(html)) fail('含 undefined:', k);
    if (/NaN/.test(html))       fail('含 NaN:', k);
    for (const m of html.matchAll(/onclick="([A-Za-z_$][\w$]*)\(/g)) fns.add(m[1]);
  }

  // 3. onclick 引用的函数都已定义
  for (const f of fns) {
    let ok = false;
    try { ok = typeof eval(f) === 'function'; } catch (e) {}
    if (!ok) fail('onclick 引用了未定义的函数:', f);
  }

  // 4. 区域地址：无重复、符合命名规范
  if (typeof rightPane === 'function') {
    const RE = /^[a-z]+\/[a-z0-9-]+#[a-z]+(\/[a-z0-9-]+)?$/;
    for (const k of Object.keys(P)) {
      let html;
      try { html = rightPane(k); } catch (e) { continue; }
      const addrs = [...html.matchAll(/data-region="([^"]+)"/g)].map(m => m[1]);
      const dup = addrs.filter((a, i) => addrs.indexOf(a) !== i);
      if (dup.length) fail('区域地址重复:', k, [...new Set(dup)].join(','));
      for (const a of addrs) if (!RE.test(a)) fail('区域地址不合规:', a);
    }
  }

  // 5. 流程图几何：包围盒重叠 / 越界
  if (typeof UIF === 'object' && typeof uif === 'function') {
    for (const k of Object.keys(UIF)) {
      const raw = UIF[k], sp = raw.W ? raw : uif(raw);
      const bx = sp.nodes.filter(n => n.k !== 'band');
      for (const n of bx)
        if (n.x < 0 || n.y < 0 || n.x + n.w > sp.W + 1 || n.y + (n.h || 0) > sp.H + 1)
          fail('节点越界:', k, n.id);
      for (let i = 0; i < bx.length; i++)
        for (let j = i + 1; j < bx.length; j++) {
          const a = bx[i], c = bx[j];
          const ox = Math.min(a.x + a.w, c.x + c.w) - Math.max(a.x, c.x);
          const oy = Math.min(a.y + (a.h||0), c.y + (c.h||0)) - Math.max(a.y, c.y);
          if (ox > 2 && oy > 2) fail('节点重叠:', k, a.id + '×' + c.id);
        }
    }
  }

  console.log(`页面 ${Object.keys(P).length} · 导航 ${navKeys.size} · 问题 ${bad}`);
  return bad;
}
