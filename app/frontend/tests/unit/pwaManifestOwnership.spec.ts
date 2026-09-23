import { access, readFile } from 'node:fs/promises'
import { constants } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(import.meta.dirname, '../..')
const canonicalManifestPath = '/manifest.webmanifest'

async function source(relativePath: string) {
  return readFile(resolve(frontendRoot, relativePath), 'utf8')
}

function manifestLinks(html: string) {
  const document = new DOMParser().parseFromString(html, 'text/html')
  return [...document.querySelectorAll<HTMLLinkElement>('link[rel="manifest"]')]
    .map(link => link.getAttribute('href'))
}

describe('PWA manifest ownership', () => {
  it('leaves manifest-link injection to VitePWA for every source entry document', async () => {
    const entryDocuments = await Promise.all([
      source('index.html'),
      source('public/index.html'),
    ])

    for (const html of entryDocuments) {
      expect(manifestLinks(html)).toEqual([])
    }
  })

  it('has no public manifest that can conflict with VitePWA output', async () => {
    for (const manifest of ['public/manifest.json', 'public/manifest.webmanifest']) {
      await expect(access(resolve(frontendRoot, manifest), constants.F_OK)).rejects.toThrow()
    }
  })

  it('keeps diagnostics aligned with the VitePWA manifest path', async () => {
    const debugSource = await source('src/utils/pwaDebug.ts')
    expect(debugSource).toContain(`fetch('${canonicalManifestPath}')`)
    expect(debugSource).not.toContain("fetch('/manifest.json')")
  })
})
