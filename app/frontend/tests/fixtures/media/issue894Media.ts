import { readFileSync } from 'node:fs'
import type { Route } from '@playwright/test'

// Generated synthetic media, no recording/provider content:
// ffmpeg -f lavfi -i color=c=0x243b53:s=320x180:r=1/3600 -t 50400 \
//   -c:v libx264 -g 1 -pix_fmt yuv420p -movflags +faststart -an issue-894-long-clock.bin
// (Use -f mp4 for a .bin output.) Native duration: 14 hours; only fourteen frames.
const media = readFileSync(new URL('./issue-894-long-clock.bin', import.meta.url))

export function longClockMedia(route: Route) {
  const range = route.request().headers().range?.match(/^bytes=(\d+)-(\d*)$/)
  const start = range ? Number(range[1]) : 0
  const end = range?.[2] ? Math.min(Number(range[2]), media.length - 1) : media.length - 1
  if (start > end || start >= media.length) return route.fulfill({
    status: 416, headers: { 'Content-Range': `bytes */${media.length}` },
  })
  const body = media.subarray(start, end + 1)
  return route.fulfill({
    status: range ? 206 : 200,
    contentType: 'video/mp4',
    headers: {
      'Accept-Ranges': 'bytes', 'Content-Length': String(body.length),
      ...(range ? { 'Content-Range': `bytes ${start}-${end}/${media.length}` } : {}),
    },
    body,
  })
}
