# hummingbird-cam

Raspberry Pi-powered hummingbird nest monitor with motion-activated push notifications and live streaming.

Built to keep watch over two rescued baby hummingbirds — confirming mom returns, tracking feeding visits, and sharing the nest with anyone who wants to watch.

## What It Does

- **Motion detection** — frame-differencing via `motion` daemon, tuned for tiny bird movements
- **Push notifications** — instant alerts with nest snapshots via [ntfy](https://ntfy.sh)
- **Live stream** — MJPEG stream viewable on any browser (LAN + public relay)
- **Low power** — runs 24/7 on a Raspberry Pi Zero 2 W drawing ~1.5W

## Hardware

| Component | Model |
|-----------|-------|
| Computer | Raspberry Pi Zero 2 W |
| Camera | Logitech HD Webcam C615 |
| Power | USB battery pack / wall adapter |

## Quick Start

```bash
# 1. Clone to your Pi
git clone https://github.com/lightcone-studios/hummingbird-cam.git
cd hummingbird-cam

# 2. Run setup (installs motion + dependencies)
chmod +x scripts/setup.sh
./scripts/setup.sh

# 3. Start the service
sudo systemctl enable --now hummingbird-cam

# 4. Subscribe to notifications
# Open ntfy.sh/hummingbird-nest on your phone
```

## Deploying Config Changes

From the development machine:

```bash
./deploy/deploy.sh
```

## Architecture

```
[Webcam] → [motion on Pi Zero 2 W]
               ├── motion event → ntfy push + snapshot
               ├── MJPEG stream → http://<pi-ip>:8081
               └── saved media → /var/lib/motion/
```

## License

MIT
