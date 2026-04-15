#!/usr/bin/env bash
# deploy.sh — push scripts, config, and systemd units from this repo to the camera host
#
# Run from the development machine (Shiro).
# Usage: ./deploy/deploy.sh [hostname]
#
# Default target is `hans` (Mac mini running Ubuntu 24.04).
# Secrets (YOUTUBE_STREAM_KEY, NTFY_TOKEN, YouTube OAuth refresh token)
# live on the host at /etc/hummingbird-cam.env and /etc/youtube_token.json.
# This script never touches those.

set -euo pipefail

HOST="${1:-hans}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Deploying hummingbird-cam to ${HOST} ==="

echo "--- Staging files in /tmp/hbc-stage ---"
ssh "$HOST" "mkdir -p /tmp/hbc-stage"

rsync -az \
    "$REPO_DIR/config/motion.conf" \
    "$REPO_DIR/scripts/notify.sh" \
    "$REPO_DIR/scripts/stream-youtube.sh" \
    "$REPO_DIR/scripts/youtube-control.sh" \
    "$REPO_DIR/thumbnail.jpg" \
    "$REPO_DIR/deploy/"*.service \
    "$REPO_DIR/deploy/"*.timer \
    "${HOST}:/tmp/hbc-stage/"

echo "--- Installing files ---"
ssh "$HOST" "sudo bash -s" << 'INSTALL'
set -e
cd /tmp/hbc-stage

install -m 755 notify.sh          /opt/hummingbird-cam/notify.sh
install -m 755 stream-youtube.sh  /opt/hummingbird-cam/stream-youtube.sh
install -m 755 youtube-control.sh /opt/hummingbird-cam/youtube-control.sh
install -m 644 thumbnail.jpg      /opt/hummingbird-cam/thumbnail.jpg
install -m 644 motion.conf        /etc/motion/motion.conf

install -m 644 hummingbird-cam.service      /etc/systemd/system/hummingbird-cam.service
install -m 644 youtube-stream.service       /etc/systemd/system/youtube-stream.service
install -m 644 youtube-stream-start.service /etc/systemd/system/youtube-stream-start.service
install -m 644 youtube-stream-start.timer   /etc/systemd/system/youtube-stream-start.timer
install -m 644 youtube-stream-stop.service  /etc/systemd/system/youtube-stream-stop.service
install -m 644 youtube-stream-stop.timer    /etc/systemd/system/youtube-stream-stop.timer

systemctl daemon-reload
systemctl restart hummingbird-cam
INSTALL

echo "--- Status ---"
ssh "$HOST" "systemctl --no-pager is-active hummingbird-cam youtube-stream youtube-stream-start.timer youtube-stream-stop.timer"

echo ""
echo "=== Deploy complete ==="
echo "MJPEG stream: http://${HOST}:8081"
