import { describe, expect, it } from 'vitest'
import { runInNewContext } from 'node:vm'
import { compactProductionChunks } from '../compact-production-chunks'

async function compact(code: string, format: 'es' | 'iife') {
  const plugin = compactProductionChunks()
  const render = plugin.renderChunk as (code: string, chunk: { fileName: string }, options: { format: string }) => Promise<{ code: string }>
  return (await render(code, { fileName: 'test.js' }, { format })).code
}

describe('production chunk compression', () => {
  it('preserves getter and Proxy reads used by reactive consumers', async () => {
    const code = await compact(`export function read(events) {
      const getter = { get current() { events.push('getter'); return 1 } };
      const proxy = new Proxy({}, { get() { events.push('proxy'); return 2 } });
      getter.current;
      proxy.current;
      return events;
    }`, 'es')
    const module = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
    expect(module.read([])).toEqual(['getter', 'proxy'])
  })

  it('preserves full module exports, side effects and error behavior', async () => {
    const source = `
      export const version = 'synthetic';
      export default function playback(options) {
        if (!options.workerPath) throw new Error('worker path required');
        options.events.push('init');
        return { worker: options.workerPath, codecs: ['avc1', 'mp4a', 'hvc1', 'av01'] };
      }
    `
    const code = await compact(source, 'es')
    const module = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
    const events: string[] = []
    expect(module.version).toBe('synthetic')
    expect(module.default({ workerPath: '/same-origin-worker.js', events })).toEqual({
      worker: '/same-origin-worker.js', codecs: ['avc1', 'mp4a', 'hvc1', 'av01'],
    })
    expect(events).toEqual(['init'])
    expect(() => module.default({ events })).toThrow('worker path required')
  })

  it('preserves standalone classic-worker registration and transferable data', async () => {
    const source = `(() => {
      self.addEventListener('message', event => {
        const buffer = new Uint8Array(event.data).buffer;
        self.postMessage({ event: 'buffer', length: buffer.byteLength }, [buffer]);
      });
    })();`
    let listener!: (event: { data: number[] }) => void
    const messages: unknown[] = []
    const self = {
      addEventListener: (name: string, callback: typeof listener) => { expect(name).toBe('message'); listener = callback },
      postMessage: (message: unknown, transfers: ArrayBuffer[]) => { messages.push(message); expect(transfers[0].byteLength).toBe(3) },
    }
    runInNewContext(await compact(source, 'iife'), { self, Uint8Array })
    listener({ data: [1, 2, 3] })
    expect(messages).toEqual([{ event: 'buffer', length: 3 }])
  })
})
