# Live Streaming

StreamVault can play live Twitch streams directly in the web app.

## How it works

1. The frontend starts a live session for a streamer.
2. Streamlink reads the Twitch stream.
3. FFmpeg transmuxes the stream into HLS segments.
4. The frontend plays the playlist with bundled `hls.js`.
5. Playlist and segment requests are authenticated with playback tokens.

## Codec behavior

Recordings can use high quality codec preferences such as H.265 or AV1. Live browser playback uses browser compatible options when needed so hls.js and Media Source Extensions can play video reliably.

## Temporary files

Live HLS files are written to `/tmp/streamvault-live`. The Docker Compose file mounts this as tmpfs for speed and cleanup.

## Limits

The live streaming service limits concurrent sessions globally and per user. Idle sessions are stopped automatically.
