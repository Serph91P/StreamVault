import { describe, expect, it } from 'vitest'
import ts from 'typescript'
import playerSource from '@/components/VideoPlayer.vue?raw'
import viewSource from '@/views/VideoPlayerView.vue?raw'
import { formatTime } from '../playerClock'

// Exact legacy bodies before consolidation, including their nonfinite and
// negative behavior. The human-readable Player duration is a different API.
const legacyPlayer = (seconds: number): string => {
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
const legacyView = (seconds: number): string => {
  const whole = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(whole / 3600)
  const minutes = Math.floor((whole % 3600) / 60)
  const remainder = String(whole % 60).padStart(2, '0')
  return `${hours ? `${hours}:` : ''}${hours ? String(minutes).padStart(2, '0') : minutes}:${remainder}`
}
const legacyDuration = (seconds: number): string => {
  const minutes = Math.floor(seconds / 60)
  return minutes > 60
    ? `${Math.floor(minutes / 60)}h ${minutes % 60}m`
    : `${minutes}m ${Math.floor(seconds % 60)}s`
}

function sourceFormatter(source: string, name: string) {
  const expression = source.match(new RegExp(`const ${name} = [\\s\\S]*?(?=\\n\\n)`))?.[0]
  if (!expression) throw new Error(`Missing actual ${name}`)
  const js = ts.transpileModule(expression, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  const dependencies = name === 'formatDuration' && source === viewSource
    ? `${ts.transpileModule(viewSource.match(/const formatTimestamp = [\s\S]*?(?=\n\n)/)![0], { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText}\n`
    : ''
  return new Function('formatTime', `${dependencies}${js}; return ${name}`)(formatTime) as (n: number) => string
}
const inputs = [0, -0, 0.1, 1, 1.9, 59.999, 60, 60.001, 3599.999, 3600, 3600.9, 3661, 36060.5, 1e12, Number.MAX_SAFE_INTEGER, Number.MAX_VALUE, -0.1, -1, -60.1, -3600.75, NaN, Infinity, -Infinity]

describe('Player clock exact legacy compatibility', () => {
  it.each(inputs)('preserves all three actual output contracts for %s', seconds => {
    expect(formatTime(seconds)).toBe(legacyPlayer(seconds))
    expect(sourceFormatter(viewSource, 'formatTimestamp')(seconds)).toBe(legacyView(seconds))
    expect(sourceFormatter(viewSource, 'formatDuration')(seconds)).toBe(
      Number.isFinite(seconds) && seconds >= 0 ? legacyView(seconds) : 'Unavailable'
    )
    expect(sourceFormatter(playerSource, 'formatDuration')(seconds)).toBe(legacyDuration(seconds))
  })
  it('uses the same Player core without introducing another formatter option API', () => {
    expect(playerSource).toContain("import { formatTime } from '@/utils/playerClock'")
    expect(playerSource).not.toContain('const formatTime =')
  })
})
