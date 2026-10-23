export type Job = {
  id: string
  name: string
  cwd: string
  status: 'running' | 'done' | 'failed' | 'timeout' | 'stopped'
  start: number
  end: number | null
  turns: number
  maxTurns: number
  step: string
  steps: [string, string, string][]
  files: Record<string, [number, number]>
  model?: string
  note?: string | null
  noteOk?: boolean
  result?: string
}

declare module 'claude-code' {
  interface PluginState {
    'ccds-panel': {
      jobs: Job[]
      openIds: string[]
      filter: 'all' | 'running' | 'end'
      confirmDiscard: string | null
      now: number
    }
  }
}
