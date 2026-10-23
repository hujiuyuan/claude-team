import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'ccds-panel', component: 'Pane', requestId: 'ccds-jobs',
  props: { title: 'ccds 任务', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 40 }, view: {} },
} as const

const job = (id: string, name: string) => ({
  id, name, cwd: '/r', status: 'done', start: Date.now() / 1000 - 60, end: Date.now() / 1000, turns: 3, maxTurns: 10,
  step: '完成', steps: [['10:00', '读文件：a.py', 'ok'], ['10:01', '跑命令：测试', 'ok']],
  files: { 'a.py': [3, 1] }, note: '验收通过：好', noteOk: true,
})

test('两张卡片能同时展开，并显示步骤', async ($, on) => {
  on('command.register', () => ({ value: { command: 'ccds' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.panes', () => ({ value: [] }))
  on('clock.every', () => ({ value: 1 }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('fs.exists', () => ({ value: true }))
  on('fs.list', () => ({ value: [
    { name: 'a.state.json', kind: 'file', size: 1, mtimeMs: 1, isLink: false },
    { name: 'b.state.json', kind: 'file', size: 1, mtimeMs: 1, isLink: false },
  ] }))
  on('fs.read', (_, e: any) => ({ value: JSON.stringify(String(e.path ?? e).includes('a.') ? job('a', '任务A') : job('b', '任务B')) }))

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.press({ key: 'head-a' })
  await ui.press({ key: 'head-b' })
  const steps = await ui.findAll({ type: 'Text', text: /读文件：a\.py/ })
  expect(steps.length).toBeGreaterThanOrEqual(2)
  expect((await ui.findAll({ type: 'Text', text: /^验收通过：好$/ })).length).toBe(2)
  await ui.unmount()
})
