import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const scriptPath = resolve(process.cwd(), 'scripts/inventory-frontend.mjs')
const inventoryPath = resolve(process.cwd(), '../../docs/architecture/frontend-inventory.json')

describe('frontend inventory', () => {
  it('records Vue click modifiers as click-semantics evidence', () => {
    execFileSync(process.execPath, [scriptPath], { stdio: 'pipe' })
    const inventory = JSON.parse(readFileSync(inventoryPath, 'utf8')) as {
      clickSemantics?: Array<{ file: string; line: number; match: string }>
      counts: Record<string, number>
    }

    expect(inventory.clickSemantics).toBeDefined()
    expect(inventory.counts.clickSemantics).toBeGreaterThan(0)
    expect(inventory.clickSemantics?.some(entry => entry.match.includes('@click'))).toBe(true)
  })

  it('excludes dynamic RouterLink props from navigation destinations', () => {
    execFileSync(process.execPath, [scriptPath], { stdio: 'pipe' })
    const inventory = JSON.parse(readFileSync(inventoryPath, 'utf8')) as {
      navigationDestinations: string[]
    }

    expect(inventory.navigationDestinations).not.toContain('to')
  })
})
