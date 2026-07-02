# StreamVault Wiki

StreamVault is a self-hosted Twitch recorder, live player, and media library. It combines Streamlink, FFmpeg, FastAPI, PostgreSQL, and a Vue PWA to record streams, watch live HLS playback, and manage a media server friendly archive.

## Start here

- [Installation](Installation.md)
- [Configuration](Configuration.md)
- [Usage](Usage.md)
- [Live Streaming](Live-Streaming.md)
- [Development](Development.md)
- [Troubleshooting](Troubleshooting.md)

## Core concepts

- **Streamer**: A Twitch channel managed by StreamVault.
- **Recording**: A saved stream with generated metadata, artwork, and optional chapters.
- **Live session**: Temporary HLS playback created on demand for a live Twitch stream.
- **Browser token**: Optional Twitch auth token used for higher quality recording options.
- **Cleanup policy**: Storage rule that removes old recordings by age, size, or count.
