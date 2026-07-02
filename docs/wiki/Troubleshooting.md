# Troubleshooting

## EventSub does not trigger recordings

- Confirm `BASE_URL` is public HTTPS.
- Check the Twitch application redirect URL.
- Verify `EVENTSUB_SECRET` is set and stable.
- Check container logs with `docker compose -f docker/docker-compose.yml logs app`.

## Live player buffers forever

- Confirm FFmpeg exists in the container.
- Check the live session API response for an error message.
- Verify `/tmp/streamvault-live` is writable by the app user.
- Check whether Twitch provides a browser compatible stream variant.

## Higher quality options are missing

- Store a browser token in **Settings > Twitch Connection**.
- Confirm the token status is valid.
- Remember that Twitch only exposes some codecs and resolutions for some channels.

## Disk fills up

- Configure cleanup policies.
- Move `recordings` to a larger disk.
- Review unfinished or orphaned recordings after interrupted streams.
