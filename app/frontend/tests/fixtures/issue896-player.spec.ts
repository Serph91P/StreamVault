import { expect, test } from '@playwright/test'
import {
  installSyntheticApi,
  readyForMeasuredClick,
  readyForSettledMotion,
} from './issue828Browser'
import { syntheticVideos } from './issue828SyntheticApi'
import { longClockMedia } from './media/issue894Media'
import axe from 'axe-core'

for (const sample of [
  { width: 320, height: 568, scale: 1 },
  { width: 360, height: 640, scale: 1 },
  { width: 412, height: 892, scale: 1 },
  { width: 448, height: 998, scale: 1 },
  { width: 412, height: 720, scale: 1.5 },
  { width: 412, height: 892, scale: 2 },
  { width: 892, height: 412, scale: 1 },
  { width: 568, height: 320, scale: 1 },
  { width: 412, height: 892, scale: 1, inset: 24 },
  { width: 412, height: 720, scale: 1.5, inset: 24 },
  { width: 412, height: 892, scale: 2, inset: 24 },
  { width: 892, height: 412, scale: 1, inset: 24 },
  { width: 892, height: 412, scale: 2, inset: 24 },
]) {
  test(`controls are not initially clipped at ${sample.width}, ${sample.scale}x text, ${sample.inset ?? 0}px safe areas`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: sample.width, height: sample.height })
    if (sample.inset) {
      const session = await page.context().newCDPSession(page)
      await session.send('Emulation.setSafeAreaInsetsOverride', {
        insets: {
          top: sample.inset,
          left: sample.inset,
          right: sample.inset,
          bottom: sample.inset,
        },
      })
    }
    const api = await installSyntheticApi(page, 'many')
    api.releaseChapters()
    await page.route('**/api/videos', (route) =>
      route.fulfill({
        json: syntheticVideos.map((video) => ({
          ...video,
          streamer_name: 'synthetic_recorder_1234567'.slice(0, 25),
          title:
            'Synthetic recorded stream with a descriptive title for responsive player testing. '
              .repeat(2)
              .slice(0, 140),
        })),
      }),
    )
    await page.route('**/api/videos/*/stream', longClockMedia)
    await page.goto('/videos/1', { waitUntil: 'domcontentloaded' })
    if (sample.scale !== 1) {
      const size = await page
        .locator('html')
        .evaluate((el) => parseFloat(getComputedStyle(el).fontSize))
      await page.addStyleTag({
        content: `html { font-size: ${size * sample.scale}px !important; }`,
      })
    }
    await expect(page.locator('.loading-overlay')).toHaveCount(0)
    await readyForSettledMotion(page.locator('.player-card'))
    // Observation BEFORE scrollIntoView/click: those can horizontally scroll a
    // clipped ancestor and accidentally repair the very layout being tested.
    const report = await page.evaluate(() => {
      const targets = [
        ['Back', '.back-button'],
        ['Play', '.play-pause-button'],
        ['Mute', 'button[aria-label="Mute"]'],
        ['Chapters', '.chapters-button'],
        ['Fullscreen', 'button[aria-label="Fullscreen"]'],
        ['Progress', '[role="slider"][aria-label="Video progress"]'],
      ]
      for (const button of document.querySelectorAll(
        '.video-controls-overlay button[aria-label]',
      )) {
        const label = button.getAttribute('aria-label')!
        if (button.getClientRects().length && !targets.some(([name]) => name === label))
          targets.push([label, `button[aria-label="${label}"]`])
      }
      return targets.map(([name, selector]) => {
        const el = document.querySelector<HTMLElement>(selector)!
        const rect = el.getBoundingClientRect()
        const clips: Array<{ ancestor: string; left: number; right: number; scrollLeft: number }> =
          []
        for (let parent = el.parentElement; parent; parent = parent.parentElement) {
          if (parent.classList.contains('video-wrapper')) {
            const box = parent.getBoundingClientRect()
            if (rect.top < box.top - 0.5 || rect.bottom > box.bottom + 0.5) {
              clips.push({
                ancestor: 'video-wrapper (vertical)',
                left: box.left,
                right: box.right,
                scrollLeft: parent.scrollLeft,
              })
            }
          }
          if (getComputedStyle(parent).overflowX === 'visible') continue
          const box = parent.getBoundingClientRect()
          const left = box.left + parent.clientLeft
          const right = left + parent.clientWidth
          if (rect.left < left - 0.5 || rect.right > right + 0.5) {
            clips.push({
              ancestor: parent.className || parent.tagName,
              left,
              right,
              scrollLeft: parent.scrollLeft,
            })
          }
        }
        return {
          name,
          selector,
          enabled: !(el instanceof HTMLButtonElement && el.disabled),
          rect: rect.toJSON(),
          clips,
          viewportWidth: innerWidth,
        }
      })
    })
    await testInfo.attach('initial-control-geometry', {
      body: JSON.stringify(report),
      contentType: 'application/json',
    })
    for (const item of report) {
      expect(item.rect.width, `${item.name} touch width`).toBeGreaterThanOrEqual(43.9)
      expect(item.rect.height, `${item.name} touch height`).toBeGreaterThanOrEqual(43.9)
      expect(item.rect.left, `${item.name} left viewport edge`).toBeGreaterThanOrEqual(-0.5)
      expect(item.rect.right, `${item.name} right viewport edge`).toBeLessThanOrEqual(
        item.viewportWidth + 0.5,
      )
      expect(
        item.clips,
        `${item.name} fully visible through every ancestor before automatic scrolling`,
      ).toEqual([])
    }
    // Initial clip-port geometry is already verified. Now scroll vertically as
    // a user can on a short screen, then exercise the actual input surfaces.
    for (const item of report.filter((control) => control.enabled)) {
      const control = page.locator(item.selector)
      // A usable navigation button has intentional static opacity .9, so the
      // opacity-1 motion helper is not its readiness contract.
      await control.evaluate((el) =>
        el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' }),
      )
      await control.click({ trial: true })
      // The offline fixture's fixed connectivity pill also grows with text.
      // A real vertical scroll must bring the whole target above bottom UI;
      // initial horizontal/ancestor clipping was already checked unmodified.
      const position = (await control.boundingBox())!
      if (position.y + position.height > sample.height * 0.6) {
        await page.mouse.move(position.x + position.width / 2, position.y + position.height / 2)
        await page.mouse.wheel(0, Math.ceil(position.y + position.height - sample.height * 0.6))
        await page.evaluate(
          () =>
            new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
        )
      }
      const hits = await control.evaluate((el) => {
        const box = el.getBoundingClientRect()
        // Test full diameters, not the empty corners of circular controls.
        return [
          [0.1, 0.5],
          [0.9, 0.5],
          [0.5, 0.1],
          [0.5, 0.9],
          [0.5, 0.5],
        ].map(([dx, dy]) => {
          const x = box.x + box.width * dx,
            y = box.y + box.height * dy
          const hit = document.elementFromPoint(x, y)
          return { x, y, ok: el.contains(hit), obstructing: hit?.outerHTML.slice(0, 220) }
        })
      })
      expect(
        hits.every((hit) => hit.ok),
        `${item.name} hit surface: ${JSON.stringify(hits)}`,
      ).toBe(true)
    }
    const play = page.getByRole('button', { name: 'Play', exact: true })
    await play.tap()
    await expect
      .poll(() => page.locator('video').evaluate((el) => (el as HTMLVideoElement).paused))
      .toBe(false)
    await page.getByRole('button', { name: 'Pause', exact: true }).tap()
    await page.getByRole('button', { name: 'Mute', exact: true }).tap()
    await expect
      .poll(() => page.locator('video').evaluate((el) => (el as HTMLVideoElement).muted))
      .toBe(true)
    if (sample.inset && sample.scale === 1)
      await page.screenshot({ path: testInfo.outputPath(`player-${sample.width}.png`) })
    expect(api.unexpected).toEqual([])
  })
}

for (const viewport of [
  { width: 360, height: 640 },
  { width: 412, height: 892 },
  { width: 892, height: 412 },
  { width: 412, height: 892, theme: 'dark' },
]) {
  test(`chapters use four readable rows and a large safe overlay at ${viewport.width} in ${viewport.theme ?? 'light'}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize(viewport)
    const session = await page.context().newCDPSession(page)
    await session.send('Emulation.setSafeAreaInsetsOverride', {
      insets: { top: 24, left: 24, right: 24, bottom: 24 },
    })
    const api = await installSyntheticApi(page, 'many')
    api.releaseChapters()
    const title = 'Synthetic chapter title showing every part of the recorded event '
      .repeat(3)
      .trim()
    const chapters = Array.from({ length: 12 }, (_, index) => ({
      id: index + 1,
      title: `${title} ${index + 1}`,
      category_name: 'Synthetic category',
      start: index * 600 + 1.25,
      end: index * 600 + 301.75,
    }))
    await page.route('**/api/videos/*/chapters', (route) => route.fulfill({ json: chapters }))
    await page.route('**/api/categories/image/*', (route) =>
      route.fulfill({ json: { image_url: 'icon:gamepad' } }),
    )
    await page.route('**/api/videos/*/stream', longClockMedia)
    await page.goto('/videos/1', { waitUntil: 'domcontentloaded' })
    if (viewport.theme === 'dark')
      await page.getByRole('button', { name: 'Switch to dark mode' }).tap()
    const video = page.locator('video.video-element')
    await expect
      .poll(() => video.evaluate((el) => (el as HTMLVideoElement).readyState))
      .toBeGreaterThanOrEqual(2)
    await expect(page.locator('.loading-overlay')).toHaveCount(0)
    const inline = page.locator('.chapters-list .chapter-item').first()
    await readyForSettledMotion(inline)
    const rows = inline.locator(
      '.chapter-title, .chapter-category, .chapter-time, .chapter-duration',
    )
    await expect(rows).toHaveText([
      chapters[0].title,
      'Synthetic category',
      '0:01 - 5:01',
      'Duration: 5:00',
    ])
    expect(
      await inline.locator('.chapter-title').evaluate((el) => {
        const style = getComputedStyle(el)
        return (
          style.whiteSpace === 'normal' &&
          style.textOverflow !== 'ellipsis' &&
          el.scrollHeight <= el.clientHeight + 1 &&
          el.scrollWidth <= el.clientWidth + 1
        )
      }),
      'inline title is completely rendered, not merely present in the DOM',
    ).toBe(true)

    const opener = page.getByRole('button', { name: 'Chapters', exact: true })
    const before = await readyForMeasuredClick(page, opener)
    const origin = (await opener.boundingBox())!
    await page.touchscreen.tap(origin.x + origin.width / 2, origin.y + origin.height / 2)
    const dialog = page.getByRole('dialog', { name: 'Chapters' })
    await readyForSettledMotion(dialog)
    const panel = (await dialog.boundingBox())!
    expect(panel.x).toBeGreaterThanOrEqual(23.5)
    expect(panel.y).toBeGreaterThanOrEqual(23.5)
    expect(panel.x + panel.width).toBeLessThanOrEqual(viewport.width - 23.5)
    expect(panel.y + panel.height).toBeLessThanOrEqual(viewport.height - 23.5)
    expect(panel.height).toBeGreaterThanOrEqual((viewport.height - 48) * 0.7)
    const item = dialog.locator('.chapter-item').first()
    await expect(
      item.locator('.chapter-title, .chapter-category, .chapter-time, .chapter-duration'),
    ).toHaveText([chapters[0].title, 'Synthetic category', '0:01 - 5:01', 'Duration: 5:00'])
    expect(
      await item.locator('.chapter-title').evaluate((el) => {
        const style = getComputedStyle(el)
        return (
          style.whiteSpace === 'nowrap' &&
          style.textOverflow === 'ellipsis' &&
          el.scrollWidth > el.clientWidth
        )
      }),
      'only the overlay title truncates visually',
    ).toBe(true)
    const boxes = await item
      .locator('.chapter-title, .chapter-category, .chapter-time, .chapter-duration')
      .evaluateAll((elements) => elements.map((el) => el.getBoundingClientRect().toJSON()))
    for (let index = 1; index < boxes.length; index++)
      expect(boxes[index].top).toBeGreaterThanOrEqual(boxes[index - 1].bottom)
    await expect(item).toHaveAccessibleName(new RegExp(chapters[0].title))
    await expect(item.locator('.chapter-info')).toHaveCSS(
      'color',
      await dialog.locator('h3').evaluate((el) => getComputedStyle(el).color),
    )
    await page.addScriptTag({ content: axe.source })
    const contrast = await page.evaluate(async () => {
      const engine = (window as unknown as { axe: typeof import('axe-core') }).axe
      return engine.run(document.querySelector('.chapter-list-panel') as HTMLElement, {
        runOnly: ['color-contrast'],
      })
    })
    expect(
      contrast.violations,
      'chapter information remains readable in the selected theme',
    ).toEqual([])
    expect(await page.evaluate(() => scrollY)).toBe(before)
    await page.screenshot({ path: testInfo.outputPath(`chapters-${viewport.width}.png`) })
    const touch = {
      x: panel.x + panel.width / 2,
      y: panel.y + panel.height - 40,
      id: 1,
      radiusX: 4,
      radiusY: 4,
      force: 1,
    }
    await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [touch] })
    for (let step = 1; step <= 10; step++) {
      await session.send('Input.dispatchTouchEvent', {
        type: 'touchMove',
        touchPoints: [{ ...touch, y: touch.y - (Math.min(200, panel.height - 110) * step) / 10 }],
      })
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)))
    }
    await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect.poll(() => dialog.evaluate((el) => el.scrollTop)).toBeGreaterThan(0)
    expect(await page.evaluate(() => scrollY)).toBe(before)
    await page.mouse.move(panel.x + panel.width / 2, panel.y + panel.height / 2)
    await page.mouse.wheel(0, 100_000)
    await expect
      .poll(() =>
        dialog.evaluate((el) => Math.abs(el.scrollTop - el.scrollHeight + el.clientHeight)),
      )
      .toBeLessThanOrEqual(1)
    await page.mouse.wheel(0, 400)
    await page.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
    )
    expect(await page.evaluate(() => scrollY)).toBe(before)
    await expect(dialog.getByRole('button', { name: 'Close chapters' })).toBeInViewport()
    const second = dialog.locator('.chapter-item').nth(1)
    await readyForMeasuredClick(page, second)
    const point = (await second.boundingBox())!
    await page.touchscreen.tap(point.x + point.width / 2, point.y + point.height / 2)
    await expect
      .poll(() => video.evaluate((el) => (el as HTMLVideoElement).currentTime))
      .toBeCloseTo(601.25, 2)
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(opener).toBeFocused()
    expect(await page.evaluate(() => scrollY)).toBe(before)
    expect(api.unexpected).toEqual([])
    await page.getByRole('button', { name: 'Back to previous page' }).tap()
    await expect(page).toHaveURL(/\/videos$/)
  })
}
