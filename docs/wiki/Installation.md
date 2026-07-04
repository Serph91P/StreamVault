# Installation

## Requirements

- Docker and Docker Compose.
- Public HTTPS URL for Twitch EventSub.
- Twitch developer application.
- At least 2 GB RAM and enough disk space for recordings.

## Docker Compose

```bash
git clone https://github.com/Serph91P/StreamVault.git
cd StreamVault
```

Edit `.env` and set Twitch, database, base URL, and timezone values. Then start the stack:

```bash
docker compose -f docker/docker-compose.yml up -d
```

## Reverse proxy

Point your reverse proxy to port `7000`. Twitch EventSub requires HTTPS with a valid certificate.

Example Caddy route:

```caddy
streamvault.example.com {
    reverse_proxy localhost:7000
}
```

## Persistent data

Keep backups of the PostgreSQL volume and the `recordings` directory. The recordings directory contains the media files and generated artwork used by media servers.
