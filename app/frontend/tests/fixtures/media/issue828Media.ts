import { readFileSync } from 'node:fs'
import type { Route } from '@playwright/test'

const media = readFileSync(new URL('./issue-828-seek.bin', import.meta.url))

// Native media seeks require byte-range semantics, not a repeated 200 response.
export function localSeekMedia(route: Route) {
  const range = route.request().headers().range
  const match = range?.match(/^bytes=(\d+)-(\d*)$/)
  const start = match ? Number(match[1]) : 0
  const end = match?.[2] ? Math.min(Number(match[2]), media.length - 1) : media.length - 1
  if (start > end || start >= media.length) {
    return route.fulfill({ status: 416, headers: { 'Content-Range': `bytes */${media.length}` } })
  }
  const body = media.subarray(start, end + 1)
  return route.fulfill({
    status: match ? 206 : 200,
    contentType: 'video/mp4',
    headers: {
      'Accept-Ranges': 'bytes',
      'Content-Length': String(body.length),
      ...(match ? { 'Content-Range': `bytes ${start}-${end}/${media.length}` } : {}),
    },
    body,
  })
}
