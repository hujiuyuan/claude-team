import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Job } from '../types'

const PANE = 'ccds-jobs'
const TITLE = 'ccds 任务'
const DIR = '/tmp/ccds-runs'
const KEEP_MS = 24 * 3600e3

const jobs = atom({ plugin: 'ccds-panel', key: 'jobs' } as const, [] as Job[])
const openIds = atom({ plugin: 'ccds-panel', key: 'openIds' } as const, [] as string[])
const filter = atom({ plugin: 'ccds-panel', key: 'filter' } as const, 'all' as 'all' | 'running' | 'end')
const confirmDiscard = atom({ plugin: 'ccds-panel', key: 'confirmDiscard' } as const, null as string | null)
const now = atom({ plugin: 'ccds-panel', key: 'now' } as const, 0)

const LABEL: Record<Job['status'], string> = {
  running: '在跑', done: '完成', failed: '失败', timeout: '超时', stopped: '已停止',
}
const DOT: Record<Job['status'], string> = {
  running: 'suggestion', done: 'success', failed: 'error', timeout: 'warning', stopped: 'inactive',
}

const elapsed = (ms: number) => {
  const s = Math.max(0, Math.floor(ms / 1000))
  const m = Math.floor(s / 60)
  const h = Math.floor(m / 60)
  return h ? `${h} 小时 ${m % 60} 分` : `${m}:${String(s % 60).padStart(2, '0')}`
}

let lastSig = ''

async function scan($: any) {
  let list: Job[] = []
  if (await $.fs.exists(DIR)) {
    const entries = await $.fs.list(DIR)
    for (const ent of entries) {
      if (!ent.name.endsWith('.state.json')) continue
      try {
        list.push(JSON.parse(await $.fs.read(`${DIR}/${ent.name}`)) as Job)
      } catch {
        // 正在被写的文件，下一轮再读
      }
    }
  }
  const t = Date.now()
  list = list
    .filter(j => j.status === 'running' || t - (j.end ?? j.start) * 1000 < KEEP_MS)
    .sort((a, b) => (a.status === 'running' ? 0 : 1) - (b.status === 'running' ? 0 : 1) || b.start - a.start)
  const sig = JSON.stringify(list)
  if (sig !== lastSig) {
    const hadRunning = JSON.parse(lastSig || '[]').some((j: Job) => j.status === 'running')
    lastSig = sig
    await update($, jobs, () => list)
    const hasRunning = list.some(j => j.status === 'running')
    if (hasRunning && !hadRunning) {
      const isUp = (await $.ui.panes()).some((p: any) => p.id === PANE)
      if (!isUp) void $.ui.open({ id: PANE, title: TITLE })
    }
  }
  if (list.some(j => j.status === 'running')) await update($, now, () => t)
}

async function runner($: any, args: string[]) {
  // ccds-run 和 ccds 都在 ~/.local/bin（setup.sh 装的），面板进程的 PATH 里不一定有
  const r = await $.process.run(['/bin/sh', '-c', 'PATH="$HOME/.local/bin:$PATH"; exec ccds-run "$@"', 'ccds-run', ...args], { timeoutMs: 20000 })
  const msg = (r.stdout || r.stderr || '').trim()
  if (msg) $.ui.toast(msg)
  await scan($)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'ccds', description: '打开 ccds 任务面板' })
    await scan($)
    $.clock.every(2000, () => scan($))
    if ((await read($, jobs)).some(j => j.status === 'running')) void $.ui.open({ id: PANE, title: TITLE })
    return next(e)
  })

  on('command.run', { command: 'ccds' }, async $ => {
    await scan($)
    await $.ui.open({ id: PANE, title: TITLE })
    return { text: 'ccds 任务面板已打开。' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const list = await read($, jobs)
    const open = await read($, openIds)
    const f = await read($, filter)
    const confirm = await read($, confirmDiscard)
    const t = Math.max(await read($, now), Date.now())

    const run = list.filter(j => j.status === 'running').length
    const ok = list.filter(j => j.status === 'done').length
    const bad = list.filter(j => (j.status === 'failed' || j.status === 'timeout') && !j.note).length
    const shown = list.filter(j => f === 'all' || (f === 'running' ? j.status === 'running' : j.status !== 'running'))

    const tab = (key: 'all' | 'running' | 'end', label: string, n: number) => (
      <Button key={`tab-${key}`} plain dimColor={f !== key} onPress={() => update($, filter, () => key)}>
        {f === key ? <Text bold>{label} {n}</Text> : `${label} ${n}`}
      </Button>
    )

    // 已验收的任务，状态行显示验收结论而不是「等待验收」
    const headline = (j: Job) => {
      if (j.note) return { text: j.noteOk === false ? '验收不通过' : '已验收', color: j.noteOk === false ? 'error' : 'success' }
      if (j.status === 'done') return { text: '待验收', color: 'warning' }
      return { text: LABEL[j.status], color: DOT[j.status] }
    }

    const card = (j: Job) => {
      const isOpen = open.includes(j.id)
      const fl = Object.entries(j.files || {})
      const add = fl.reduce((s, [, v]) => s + v[0], 0)
      const del = fl.reduce((s, [, v]) => s + v[1], 0)
      const ms = ((j.end ?? t / 1000) - j.start) * 1000
      const pct = Math.min(1, j.turns / Math.max(1, j.maxTurns))
      const filled = Math.round(pct * 24)
      const head = headline(j)
      const toggle = () => update($, openIds, cur => (cur.includes(j.id) ? cur.filter(x => x !== j.id) : [...cur, j.id]))

      return (
        <Box key={`job-${j.id}`} flexDirection="column" borderStyle="round"
          borderColor={isOpen ? 'claude' : 'promptBorder'} paddingX="sm" paddingY="xs" gap="xs">
          <Box flexDirection="row" justifyContent="space-between" alignItems="center">
            <Button key={`head-${j.id}`} plain onPress={toggle}>
              <Text color={DOT[j.status]}>{j.status === 'running' ? '◉' : '●'}</Text> <Text weight="semibold">{j.name}</Text>
            </Button>
            <Text dimColor mono size="caption">{elapsed(ms)}</Text>
          </Box>
          <Box flexDirection="row" gap="sm">
            <Text color={head.color} size="caption" weight="medium">{head.text}</Text>
            <Text dimColor size="caption">
              {fl.length ? `${fl.length} 个文件 ` : '未改文件'}
              {fl.length ? <Text color="diffAdded">+{add}</Text> : ''}{fl.length ? ' ' : ''}
              {fl.length ? <Text color="diffRemoved">-{del}</Text> : ''}
              {' · '}{j.turns}/{j.maxTurns} 步
            </Text>
          </Box>
          {j.status === 'running' && (
            <Text dimColor size="caption" wrap="truncate-end">{j.step}</Text>
          )}
          {j.status === 'running' && (
            <Text size="caption"><Text color="suggestion">{'━'.repeat(filled)}</Text><Text dimColor>{'━'.repeat(24 - filled)}</Text></Text>
          )}
          {isOpen && (
            <Box flexDirection="column" gap="xs" marginTop="xs">
              {j.note && <Text color={head.color} wrap="wrap">{j.note}</Text>}
              {!j.note && j.result && j.status !== 'running' && <Text dimColor wrap="wrap" size="caption">{j.result.slice(0, 400)}</Text>}
              <Box flexDirection="column">
                {(j.steps || []).slice(-10).map((s, i) => (
                  <Text key={`s-${j.id}-${i}`} size="caption" wrap="truncate-end">
                    <Text dimColor mono>{s[0]}</Text>{'  '}
                    <Text color={s[2] === 'err' ? 'error' : s[2] === 'cur' ? 'suggestion' : undefined} dimColor={s[2] === 'ok'}>{s[1]}</Text>
                  </Text>
                ))}
              </Box>
              {fl.length > 0 && (
                <Box flexDirection="column">
                  {fl.map(([name, v]) => (
                    <Text key={`f-${j.id}-${name}`} mono size="caption" wrap="truncate-start">
                      {name}  <Text color="diffAdded">+{v[0]}</Text> <Text color="diffRemoved">-{v[1]}</Text>
                    </Text>
                  ))}
                </Box>
              )}
              <Box flexDirection="row" gap="sm" flexWrap="wrap">
                {j.status === 'running' && (
                  <Button key={`stop-${j.id}`} onPress={() => runner($, ['stop', j.id])}>停止</Button>
                )}
                {j.status === 'done' && !j.note && (
                  <Button key={`check-${j.id}`} variant="primary"
                    onPress={() => $.prompt.submit({ text: `验收 ccds 任务 ${j.id}（${j.name}），结论用 ccds-run note 写回面板。` })}>
                    让 Claude 验收
                  </Button>
                )}
                {(j.status === 'failed' || j.status === 'timeout' || j.status === 'stopped') && (
                  <Button key={`resume-${j.id}`} variant="primary" onPress={() => runner($, ['resume', j.id])}>
                    让它接着做
                  </Button>
                )}
                {j.status !== 'running' && fl.length > 0 && (
                  confirm === j.id
                    ? <Button key={`discard2-${j.id}`} onPress={async () => { await update($, confirmDiscard, () => null); await runner($, ['discard', j.id]) }}>
                        <Text color="error">确认丢弃 {fl.length} 个文件的改动</Text>
                      </Button>
                    : <Button key={`discard-${j.id}`} dimColor onPress={() => update($, confirmDiscard, () => j.id)}>丢弃改动</Button>
                )}
              </Box>
              <Text dimColor size="caption" wrap="truncate-start">{j.model ?? ''}  {j.cwd}</Text>
            </Box>
          )}
        </Box>
      )
    }

    return (
      <Box flexDirection="column" gap="sm">
        <Box flexDirection="row" gap="md">
          {tab('all', '全部', list.length)}
          {tab('running', '在跑', run)}
          {tab('end', '已结束', list.length - run)}
        </Box>
        {(ok > 0 || bad > 0) && (
          <Text size="caption" dimColor>
            {ok} 个完成{bad ? <Text color="error"> · {bad} 个失败待处理</Text> : ''}
          </Text>
        )}
        {shown.length === 0 && <Text dimColor>没有任务。派活时用 ccds-run 启动，这里会自动出现。</Text>}
        {shown.map(card)}
        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
          <Text dimColor size="caption">DeepSeek · 不占 Claude 额度</Text>
          {list.some(j => j.status !== 'running') && (
            <Button key="clean" plain dimColor onPress={() => runner($, ['clean'])}>清理已结束</Button>
          )}
        </Box>
      </Box>
    )
  })
}
