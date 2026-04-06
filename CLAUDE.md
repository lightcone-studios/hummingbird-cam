# CLAUDE.md — hummingbird-cam

## What This Is

Raspberry Pi-powered hummingbird nest monitoring system. Motion-activated notifications with live streaming. Runs on **Suzu** (Pi Zero 2 W) with a Logitech C615 webcam pointed at a rescued hummingbird nest on Aaron's porch.

## Stack

- **Hardware:** Raspberry Pi Zero 2 W (512MB RAM, quad-core A53 @ 1GHz)
- **Camera:** Logitech HD Webcam C615 at `/dev/video0`
- **Motion detection:** `motion` daemon (frame-differencing, lightweight)
- **Notifications:** ntfy.sh push notifications with snapshot images
- **Streaming:** motion built-in MJPEG stream (LAN) + relay for public access
- **OS:** Raspbian Bookworm (Debian 12)

## Architecture

```
[C615 Webcam] → [motion daemon on Suzu]
                    ├── motion detected → notify.sh → ntfy.sh push notification (with image)
                    ├── MJPEG stream → :8081 (LAN access)
                    └── snapshots/videos → /var/lib/motion/
```

## Deploying Changes

```bash
# From this repo on Shiro:
./deploy/deploy.sh
```

This SCPs config files to Suzu and restarts the motion service.

## Key Constraints

- **RAM is tight.** 425MB total. Capture at 640x480, not 1080p.
- **CPU is limited.** 10-15 fps max. No ML inference on-device.
- **WiFi only.** Stream bandwidth limited by Pi Zero 2 W's single-band WiFi.
- **USB 2.0 via OTG.** Webcam shares the single USB port.

## File Layout

```
config/motion.conf    — motion daemon configuration (deployed to Suzu)
scripts/notify.sh     — ntfy notification script (called by motion on events)
scripts/setup.sh      — first-time Pi setup (install deps)
deploy/deploy.sh      — push config to Suzu and restart service
deploy/hummingbird-cam.service — systemd unit file
```

## Conventions

- Config is authored here, deployed to Suzu via `deploy.sh`
- Motion output (snapshots, videos) stays on the Pi, never committed
- Notifications go through ntfy.sh (public, no self-hosted dependency)
