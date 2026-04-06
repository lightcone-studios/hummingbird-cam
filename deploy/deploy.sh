#!/usr/bin/env bash
# deploy.sh — push config from this repo to Suzu and restart the service
#
# Run from the development machine (Shiro).
# Usage: ./deploy/deploy.sh [hostname]

set -euo pipefail

PI_HOST="${1:-suzu}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Deploying hummingbird-cam to ${PI_HOST} ==="

echo "--- Copying motion config ---"
scp "$REPO_DIR/config/motion.conf" "${PI_HOST}:/tmp/motion.conf"
ssh "$PI_HOST" "sudo cp /tmp/motion.conf /etc/motion/motion.conf"

echo "--- Copying notification script ---"
scp "$REPO_DIR/scripts/notify.sh" "${PI_HOST}:/tmp/notify.sh"
ssh "$PI_HOST" "sudo cp /tmp/notify.sh /opt/hummingbird-cam/notify.sh && sudo chmod +x /opt/hummingbird-cam/notify.sh"

echo "--- Copying YouTube stream script ---"
scp "$REPO_DIR/scripts/stream-youtube.sh" "${PI_HOST}:/tmp/stream-youtube.sh"
ssh "$PI_HOST" "sudo cp /tmp/stream-youtube.sh /opt/hummingbird-cam/stream-youtube.sh && sudo chmod +x /opt/hummingbird-cam/stream-youtube.sh"

echo "--- Copying systemd services ---"
scp "$REPO_DIR/deploy/hummingbird-cam.service" "${PI_HOST}:/tmp/hummingbird-cam.service"
scp "$REPO_DIR/deploy/youtube-stream.service" "${PI_HOST}:/tmp/youtube-stream.service"
ssh "$PI_HOST" "sudo cp /tmp/hummingbird-cam.service /tmp/youtube-stream.service /etc/systemd/system/ && sudo systemctl daemon-reload"

echo "--- Restarting motion service ---"
ssh "$PI_HOST" "sudo systemctl restart hummingbird-cam"

echo "--- Checking status ---"
ssh "$PI_HOST" "sudo systemctl status hummingbird-cam --no-pager -l" || true

echo ""
echo "=== Deploy complete ==="
echo "Stream: http://$(ssh "$PI_HOST" "hostname -I | awk '{print \$1}'" 2>/dev/null):8081"
