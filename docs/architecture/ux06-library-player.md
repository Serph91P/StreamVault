# UX-06 media architecture and verification

Candidate scope: StreamVault issue #828, base `develop@14bff396a2055e45d679cc1f900bdc17990e7cb3`, local-only branch `design/828-library-players`.

## Playback strategy

`LivePlayerView` calls the small `hlsPlayback` boundary. A browser with native HLS receives the playlist directly and never imports hls.js or starts its worker. Other browsers lazy-import the complete hls.js 1.7.3 build. The fallback points to the Vite-emitted, hashed `hls.worker-*.js` on the application origin. If worker construction fails, hls.js continues its documented main-thread transmuxing path; no CDN or light build is used.

Terminal media HTTP responses are consumer states, not generic reconnects:

- 401: expired playback session, with sign-in/retry guidance.
- 403: permission denied.
- 404: unavailable live media/offline guidance.
- 410: ended live session.
- Other recoverable HLS network/media failures retain hls.js recovery behavior.

Route teardown destroys hls.js, pauses and clears the media source, clears timers and stops an active live session through `liveApi`.

## Worker budget isolation

The original application limits remain `jsBytes=1196533`, `jsGzipBytes=380431`, and `totalBytes=2754341`. The budget gate recognizes exactly one hashed `assets/hls.worker-*.js`, verifies the installed lockfile version is 1.7.3, and permits at most 116764 raw / 40615 gzip bytes for that artifact alone. It reports full aggregate metrics plus application-only and worker metrics. Missing, duplicate, unversioned, oversized workers and an oversized application all fail closed.

Measured locally with Node 22.23.2 and Vite 8.3.0 after the mock build:

- aggregate JS: 1313297 raw / 419830 gzip bytes
- application JS without worker: 1196533 raw / 379215 gzip bytes
- worker: 116764 raw / 40615 gzip bytes
- aggregate output: 2866954 bytes
- application output without worker: 2750190 bytes

This is not a Node 24 CI result.

## Product and contract evidence

The Playwright product test opens the built application's real `/live/:streamer` route. It serves generated H264/AAC HLS with two alternate audio tracks and one WebVTT subtitle track to the route's actual video element. Beyond discovery, a query-gated E2E seam selects the commentary audio and subtitle tracks on the actual hls.js instance; the test observes the commentary playlist and segment, the subtitle playlist and VTT request, arrival of the `Synthetic subtitle` cue, and playback continuing after the switch. The seam exposes no player instance and is inactive without `t=1`. The test also observes construction of the hashed same-origin worker, verifies media time advances, forces worker construction to fail and verifies main-thread playback still advances. The HEVC fallback test deliberately stubs `canPlayType` to report HLS/HEVC as unsupported, then proves that this simulated capability result selects H264 and that Chromium really decodes the synthetic H264/AAC fixture. It does not measure Chromium's native HEVC capability. Native Safari/HEVC decode remains a platform gate.

Lifecycle coverage uses a real router link, not a document-replacing `page.goto`: with service workers blocked for this one fetch-interception test, it first proves that the lazy hls.js chunk request entered and remains blocked, navigates in-app to Library, confirms unmount, and only then releases the chunk. A query-gated completion signal proves the delayed import continuation actually resumed; the test then asserts zero worker constructions and zero playlist/media requests after unmount. The component also generation-guards every async start/import continuation and stops a session that resolves after disposal.

The unchanged Workbox precache policy is measured separately and fail-closed by `npm run test:ux06-loading` plus an active-service-worker Chromium test. Static asset sizes are: initial document graph 801832 B with zero HLS fallback entries; playback fallback 692466 B (575702 B complete hls.js + 116764 B worker); and the generated precache manifest contains 85 entries / 2838577 raw B, including the same two HLS artifacts / 692466 raw B. With an already populated active cache, document `PerformanceResourceTiming` reports the initial route at 151636 encoded / 157036 transferred bytes and later requests for both HLS assets at 575702 encoded / 0 transferred bytes (cache hits). Separately reading cached `Response` bodies reports 85 entries / 2838577 raw B. These are static sizes, document resource timings, and CacheStorage response bytes—not a full service-worker install-transfer trace. Lazy loading prevents initial application execution/requesting, but because both HLS assets remain in precache it does not avoid their PWA install download.

It also exercises 401, 403, 404 and 410 through the actual LivePlayer consumer on desktop and mobile Chromium. SPA teardown removes the player. At 390 px, the title's bounding box remains within the viewport and the Actions control is programmatically scrolled, focused and tapped while its lower edge remains above the fixed bottom navigation.

The separate ffmpeg/Chromium transport harness remains explicitly narrower: it proves MP4/HLS decode, AAC decode, seek, byte range 206/416, expired-token 401, missing media 404, stopped-live 410 and reconnect 200 on a local HTTP seam. It is not a StreamVault backend or provider test.

## Feature parity

- Library: catalog loading/error/empty states, search, streamer/date/duration filters, sort, grid/list persistence, select mode and confirmed bulk deletion retained. Unit coverage verifies search/routing and failure-safe bulk deletion.
- Stored player: backend catalog metadata, chapters, stream URL, keyboard seek, chapter seek, download, share-token generation/copy and confirmed delete retained. Existing contract tests reject demo fallback and incomplete metadata.
- Live player: start/stop, codec selection, mute/play, fullscreen/theater, buffering/reconnect states and lifecycle cleanup retained; native-HLS-first and lazy complete hls.js are now explicit.

## Honest boundaries

No live Twitch/provider, production credential, real StreamVault backend, installed-PWA shell or install-transfer trace, physical Android/iOS, native Safari, Firefox or WebKit acceptance was run in this local slice. Alternate-audio switching, related media requests, subtitle cue arrival, and H264/AAC decode are covered with local synthetic media through the built product player; real provider renditions and native HEVC/Safari decode remain integration/platform gates.
