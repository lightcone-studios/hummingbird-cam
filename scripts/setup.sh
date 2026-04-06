#!/usr/bin/env bash
# setup.sh — first-time setup for hummingbird-cam on Raspberry Pi
#
# Run this on the Pi (Suzu) to install dependencies and configure motion.
# Assumes Raspbian Bookworm.

set -euo pipefail

echo "=== Hummingbird Cam Setup ==="

# Check we're on the Pi
if [[ "$(uname -m)" != "armv7l" && "$(uname -m)" != "aarch64" ]]; then
    echo "Warning: This doesn't look like a Raspberry Pi ($(uname -m))"
    echo "Continuing anyway..."
fi

echo ""
echo "--- Installing packages ---"
sudo apt-get update
sudo apt-get install -y motion v4l-utils curl

echo ""
echo "--- Creating directories ---"
sudo mkdir -p /var/lib/motion
sudo mkdir -p /var/log/motion
sudo mkdir -p /var/run/motion
sudo mkdir -p /opt/hummingbird-cam

# Set motion user permissions
sudo chown motion:motion /var/lib/motion
sudo chown motion:motion /var/log/motion
sudo chown motion:motion /var/run/motion

echo ""
echo "--- Deploying configuration ---"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

sudo cp "$REPO_DIR/config/motion.conf" /etc/motion/motion.conf
sudo cp "$REPO_DIR/scripts/notify.sh" /opt/hummingbird-cam/notify.sh
sudo chmod +x /opt/hummingbird-cam/notify.sh

echo ""
echo "--- Enabling motion daemon ---"
# Ensure motion is allowed to run as daemon
sudo sed -i 's/start_motion_daemon=no/start_motion_daemon=yes/' /etc/default/motion 2>/dev/null || true

echo ""
echo "--- Installing systemd service ---"
sudo cp "$REPO_DIR/deploy/hummingbird-cam.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hummingbird-cam

echo ""
echo "=== Setup complete ==="
echo ""
echo "Start the camera:"
echo "  sudo systemctl start hummingbird-cam"
echo ""
echo "View the stream:"
echo "  http://$(hostname -I | awk '{print $1}'):8081"
echo ""
echo "Subscribe to notifications:"
echo "  https://ntfy.sh/hummingbird-nest"
echo ""
