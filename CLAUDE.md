# CLAUDE.md — hummingbird-cam

## What This Is

Hummingbird nest monitoring system. Motion-activated notifications with a 24/7 YouTube live stream. Runs on **Hans** (2012 Mac mini, Ubuntu 24.04) with a Logitech C270 webcam pointed at a rescued hummingbird nest on Aaron's porch.

Migrated off Suzu (Pi Zero 2 W) after USB reliability issues. Suzu is back to radio duty.

## Stack

- **Host:** Hans — Mac mini, Intel i7-3720QM (8 cores), 16 GB RAM, 110 GB SSD
- **OS:** Ubuntu 24.04 LTS
- **Camera:** Logitech HD Webcam C270 at `/dev/video0`, 1280×720 MJPG
- **Motion detection:** `motion` daemon (frame-differencing)
- **Notifications:** ntfy with bearer-token auth, delivered to a self-hosted ntfy instance
- **Streaming:** motion MJPEG on `:8081` → ffmpeg H.264 relay → YouTube Live via RTMP
- **Broadcast management:** `youtube-control.sh` uses the YouTube Data API (OAuth refresh token) to create/end broadcasts daily

## Architecture

```
[C270 Webcam] → [motion daemon on Hans]
                    ├── motion detected → notify.sh → ntfy push with snapshot
                    ├── MJPEG stream on :8081 ──→ [ffmpeg] ──→ YouTube RTMP
                    └── snapshots/videos → /var/lib/motion/
```

Daily schedule: `youtube-stream-start.timer` creates a broadcast and starts the relay at 07:00, `youtube-stream-stop.timer` ends it at 19:00.

## Host Layout (Hans)

```
/opt/hummingbird-cam/
  notify.sh             — ntfy event handler
  stream-youtube.sh     — ffmpeg RTMP relay
  youtube-control.sh    — broadcast lifecycle via YouTube API
  thumbnail.jpg         — broadcast thumbnail

/etc/motion/motion.conf       — motion daemon config
/etc/hummingbird-cam.env      — secrets (stream key, ntfy token) — mode 0600
/etc/youtube_token.json       — YouTube OAuth refresh token — mode 0600

/etc/systemd/system/
  hummingbird-cam.service       — motion daemon
  youtube-stream.service        — ffmpeg RTMP relay
  youtube-stream-start.service  — API call to create broadcast + start relay
  youtube-stream-start.timer    — 07:00 daily
  youtube-stream-stop.service   — API call to end broadcast + stop relay
  youtube-stream-stop.timer     — 19:00 daily
```

## Deploying Changes

```bash
# From this repo on Shiro (default target: hans):
./deploy/deploy.sh
```

This rsyncs scripts, config, and systemd units to Hans, then restarts motion. Secrets in `/etc/hummingbird-cam.env` and `/etc/youtube_token.json` live only on the host and are never touched by the deploy.

To set up a fresh host, see `deploy/hummingbird-cam.env.example` for the shape of the env file.

## Operational Notes

- Sleep/suspend/hibernate are systemd-masked on Hans — the box stays awake 24/7.
- `ssh hans` should just work from Shiro (key auth, passwordless sudo configured).
- Motion writes to `/var/lib/motion` (disk is plentiful, no rotation set up yet — monitor if this grows).
- YouTube broadcast ID and OAuth token are cached in `/tmp/` (ephemeral, recreated per session).
- `healthStatus=good` on the YouTube stream is the indicator that ffmpeg's output rate matches YouTube's expectations. `videoIngestionStarved` usually means the input framerate flags on ffmpeg are wrong — see stream-youtube.sh comments.

## File Layout (repo)

```
config/motion.conf              — motion daemon configuration
scripts/notify.sh               — ntfy notification handler
scripts/stream-youtube.sh       — ffmpeg RTMP relay
scripts/youtube-control.sh      — YouTube broadcast lifecycle
scripts/setup.sh                — (legacy Pi setup, not used on Hans)
thumbnail.jpg                   — broadcast thumbnail
deploy/deploy.sh                — rsync repo to host, install, restart
deploy/*.service, *.timer       — systemd units
deploy/hummingbird-cam.env.example — env shape for secrets
```

## Conventions

- Config authored here, deployed to Hans via `deploy.sh`
- Motion output (snapshots, videos) stays on the host, never committed
- Secrets never committed — example env shows the shape only
- Broadcast assets (thumbnail, stream key, OAuth creds) are part of the deploy pipeline
