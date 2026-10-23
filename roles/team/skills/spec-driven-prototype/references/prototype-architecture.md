# 原型构建架构与自检

写代码时读。目标产物是一个 300KB+ 的单文件 HTML，手工维护会崩，必须工程化。

## 一、模块化构建

```
proto.html          底板：CSS + 渲染引擎 + 骨架（不含任何页面内容）
n2..n6.js           页面定义（按模块拆，每个文件一到两个业务模块）
n10..n16.js         流程图引擎与逐页流程定义
n17..n19.js         需求说明 / 建议 / 变更 / 落库 数据
n7.js               导航 + 路由 + 弹窗（必须最后加载，它调用 buildNav/render）
build.py            注入 CSS、改骨架、按顺序拼装、输出产物
```

**铁律：只改模块，不改产物。** 每次改动都重新 `python build.py`。改产物会在下次构建时被覆盖，而且产物里的行号对不上任何源文件。

`build.py` 的三件事：

```python
s = open('proto.html').read()
s = s.replace(CSS_MARK, NEW_CSS + CSS_MARK, 1)      # 1. 注入样式
s = s.replace(TOPBAR_MARK, NEW_BUTTONS, 1)          # 2. 改骨架
add = ''.join(open(f'n{i}.js').read() for i in ORDER)
s = s.replace('\n</script>', add + '\n</script>', 1) # 3. 拼装
open(OUT, 'w').write(s)
```

注入用 `assert mark in s` 保护。标记找不到时立刻失败，比默默跳过好——静默跳过会产出一个缺样式的产物，而你以为构建成功了。

## 二、渲染引擎

页面定义是数据不是 HTML：

```js
P['hq/members'] = {
  c: '面包屑',  t: '页面标题',  ref: '机构后台 · 行 10-13',  d: '一句话说明',
  b: () => [
    {t:'table', filter:[...], cols:[...], rows:[...]},
    {t:'note', html:'...'}
  ]
};
```

`b` 是函数而非数组，避免模块加载时求值（此时依赖可能还没定义）。

引擎提供的块类型：`table` `detail` `form` `tabs` `timeline` `tree` `cards` `chart` `split` `kpi` `steps` `perm` `note` `bare` `phone` `web`。新页面优先复用，不要每页手写 HTML。

**表格操作列右侧固定悬浮**：

```css
.tblwrap{overflow-x:auto;position:relative}
th.stk,td.stk{position:sticky;right:0;z-index:2;background:#fff;
  box-shadow:inset 1px 0 0 var(--line),-9px 0 11px -9px rgba(21,34,51,.20)}
th.stk{background:#FAFBFC;z-index:3}
```

`border-collapse:collapse` 下 sticky 单元格的边框会丢，必须用 `inset` 阴影补左边框。背景色也必须显式给，否则横向滚动时会透出下层文字。

## 三、页面版式：上下分区

**界面在上、文档在下，两者都占全宽。**

```css
.wrap{max-width:none;min-width:1200px}
.split2{display:block}
.lpane{margin-bottom:26px}
.lpane:after{content:"";display:block;border-top:1px dashed var(--line);margin-top:22px}
#body{overflow-x:auto}
```

### 为什么不用左右分栏

左右分栏是最容易想到的方案，实际做完才发现两个问题：

**文档栏被挤到折行。** 需求说明里有字段表、状态枚举表、缺口清单表，字段与落库里有字段表加落库表加权限点。这些都是宽内容，塞进 40% 宽的侧栏后大面积折行，读起来非常费劲。

**界面栏也不够宽。** 列表页动辄 8-9 列加操作列，压到 55% 宽之后横向滚动条常驻。

试过的补救办法和它们的问题：

| 补救 | 问题 |
|---|---|
| 给 `.wrap` 设 `min-width:1680px` + `#body` 横向滚动 | 正常屏幕上整页横向滚，比折行更难受 |
| 右栏 `sticky` + 固定高度 + 内部滚动 | 出现「页面滚动条 + 右栏内滚动条」两层滚动，非常难用 |
| 右栏做成页签 | 一次只能看一块，评审时需要对照着看 |
| 可拖拽的竖分隔条 | 治不了根本问题，只是把痛苦在两栏之间转移 |

**上下布局一次解决全部。** 两块都是全宽，表格不折行，界面不压缩，只有一个滚动条。

并排布局只在**两边内容都窄**时才成立，例如「表单 + 单列说明文字」。一旦文档侧有表格就不要并排。

### 页面变长用手风琴控制

上下布局的代价是页面变长（右栏内容中位数约 1900 字，最多 3400 字）。用折叠而不是分栏来控制：

```css
.rsec>header{cursor:pointer;user-select:none}
.rsec:not(.open) .rsecb{display:none}
.rsec:not(.open) .racc{transform:rotate(-90deg)}
.rsec:not(.open)>header{border-bottom:0}
```

要点：

- **默认全展开。** 折叠是给「我只想看界面」的人用的，不是默认状态。默认折叠会让人以为文档区是空的。
- **点整条标题栏折叠**，不是只点小箭头。命中区域越大越好用。
- **顶部给一条【全部收起 / 全部展开】。** 单页六块，逐个点太慢。
- **标题栏里放区域地址和内容量**（如 `hq/orders#advice` · 2 条建议）。折叠状态下也能知道这块有没有东西，不用展开才发现是空的。
- **标题栏内的按钮要 `event.stopPropagation()`**，否则点复制按钮会误触折叠。

### 最小宽度的取值

`min-width` 只用来防止表格在小窗口被压烂，不要用它来给某一栏争宽度：

```css
.wrap{min-width:1200px}
@media(max-width:1200px){ .wrap{min-width:0} }   /* 窄屏交给表格自己的横向滚动 */
```

1200px 够 8-9 列表格加粘性操作列。超宽内容（流程图画布可达 2680px）保留自己的内层横向滚动，不要让它撑开外层——否则整页会变成 4000px+ 宽。

## 四、区域寻址规范

让工具和 AI 能精确引用某一块，而不是啃整页 HTML。

```
区域地址 = <端>/<页面>#<区域类型>[/<子区>]

端        hq | club | web | doc | flow
页面      与路由第二段一致，kebab-case，不含中文
区域类型   ui / req / flow / advice / change / todo / field
子区      sec-N | chain-N | a-N | c-N | w-N | f-N | v1..vN
```

落到 DOM：

```html
<section class="rg" data-region="hq/members#req" data-kind="req" data-title="需求说明">
```

挂一个全局对象供控制台与自动化调用：

```js
window.DEMO = {
  read(addr){ const e=document.querySelector(`[data-region="${addr}"]`);
              return e ? e.innerText.trim() : null; },
  index(){ return [...document.querySelectorAll('[data-region]')].map(e=>({
             region:e.dataset.region, kind:e.dataset.kind,
             title:e.dataset.title, chars:e.innerText.trim().length })); },
  meta(route){ /* 该页有无各面板、落库表 */ },
  all(){ return Object.keys(P).map(r=>this.meta(r)); }
};
```

`index()` 先给目录、`read()` 再按需取内容，避免把整份 300KB 塞进上下文。

五条命名约束：

- **地址稳定优先。** 页面重命名时保留原路由段；确需改动时在变更记录里登记旧地址。
- **不含中文、空格、大写。** 只用小写字母、数字、连字符与 `/ # -`。
- **区域类型是封闭集合。** 七类之外不新增；新需求先归入现有类型。
- **子区编号从 1 起、随内容顺序。** 删除条目后不复用旧号，避免历史引用错位。
- **不嵌套同类型区域。** 保证 `read()` 取到的是完整且不重复的内容。

包装器与内容渲染要分离，否则会嵌套出重复地址：

```js
const inner = x => x.replace(/^<section[^>]*>/,'').replace(/<\/section>$/,'');
rSec(k, 'req', '需求说明', inner(pReq(k)))   // pReq 内部的 RG 外壳被剥掉
```

## 五、变更记录与点击高亮

每条变更记一个目标（卡片标题文本），点击后在左栏查找并高亮：

```js
function hlGo(txt, el){
  const lp = document.querySelector('.lpane');
  let hit = null;
  lp.querySelectorAll('.card>header h3').forEach(h => {
    if (!hit && h.textContent.indexOf(txt) >= 0) hit = h.closest('.card'); });
  if (!hit) lp.querySelectorAll('.tab').forEach(t => { /* Tab 也要找 */ });
  if (!hit) lp.querySelectorAll('.card').forEach(c => { /* 兜底全文匹配 */ });
  if (!hit) { toast('本页未找到「'+txt+'」'); return; }
  hit.scrollIntoView({behavior:'smooth', block:'center'});
  hit.classList.remove('hl'); void hit.offsetWidth; hit.classList.add('hl');
}
```

按标题文本而不是索引定位——索引会随内容增删错位，标题文本相对稳定。`void offsetWidth` 是强制重排，否则连续点同一条时动画不会重播。

## 六、自检清单

产物太大，肉眼看不出问题。每次构建后必跑。

**语法**

```bash
python -c "
import re
s=open(OUT).read()
m=re.search(r'<script>(.*)</script>', s, re.S)
open('/tmp/chk.js','w').write(m.group(1))"
node --check /tmp/chk.js
```

**假 DOM 渲染全页**（`assets/validate.js`）

```js
function mk(){return {innerHTML:'',style:{},classList:{add(){},remove(){},toggle(){}},
  dataset:{},addEventListener(){},querySelectorAll(){return []},
  querySelector(){return null},closest(){return mk()},scrollIntoView(){}};}
global.document={querySelector:()=>mk(),querySelectorAll:()=>[],addEventListener(){}};
global.window=global; global.location={hash:'#'}; global.innerWidth=1400;
```

然后 `cat pre.js chk.js validate.js > run.js && node run.js`。

必查项：

| 检查 | 为什么 |
|---|---|
| 每个导航条目有对应页面 | 点了报错 |
| 每个页面有导航入口 | 孤儿页永远打不开 |
| 渲染结果不含 `undefined` / `NaN` | 见下方坑 |
| 所有 `onclick` 引用的函数已定义 | 点了报错 |
| 图表节点包围盒无重叠、无越界 | 自动布局算错 |
| 区域地址无重复、符合命名规范正则 | 破坏 `read()` |
| 正文引用的 Q 编号 == 清单定义的 Q 编号 | 双向索引断裂 |

**注意**：自检脚本里不要定义叫 `render` 的函数——会覆盖应用的 `render()`，然后应用初始化时用错误参数调用你的函数。同理避开 `M` `S` `D` `T` `U` 这类单字母名，实际撞过 `M`（金额格式化 vs 弹窗构造器）。

## 七、真实踩过的坑

这些都是自检抓出来、肉眼绝对发现不了的：

**类型判断写错，122 个节点静默渲染成 `undefined`。** 构造函数返回 `{k:'d'}`，渲染器判断 `n.k === 'dec'`，不匹配就落到默认分支用了不存在的 `n.html`。教训：构造器与渲染器的类型常量要么共用一个枚举，要么渲染器同时接受两种写法。

**未给高度导致坐标算出 `NaN`。** 注释框高度由内容决定所以没设 `h`，但连线中心点计算 `y + h/2` 得到 `NaN`，整条 SVG path 失效。教训：几何计算用到的字段必须有值，即使视觉上不需要——可以只用于计算不用于渲染。

**函数重名。** 金额格式化 `const M=v=>...` 和弹窗构造器 `function M(title,...)` 撞名，`node --check` 直接报 `Identifier 'M' has already been declared`。教训：跨模块的公共函数用 3 个字母以上的名字。

**CSS 插入点找错。** 底板是干净模板，前几轮的样式是在构建时注入到产物的。第二次注入时去底板里找上一轮的标记，找不到。教训：所有注入都写进 `build.py` 并加 `assert`，不要依赖「上一轮已经注入过」。

**Excel 内嵌图片提取不到。** markitdown 只读单元格。用 `unzip -j spec.xlsx "xl/drawings/media/*"`，取出后分 6-8 段放大读（整图缩略后中文不可辨）。

**长文本列截断。** 读单元格时设了 200 字符截断，而操作说明列常有 400+ 字符，字段定义就藏在被截掉的部分。
