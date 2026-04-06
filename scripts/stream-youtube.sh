#!/usr/bin/env bash
# stream-youtube.sh — relay the motion MJPEG stream to YouTube Live via RTMP
#
# Prerequisites:
#   1. motion must be running (provides the MJPEG source at localhost:8081)
#   2. YouTube stream key must be set in /etc/hummingbird-cam.env or passed as $1
#
# Usage:
#   ./stream-youtube.sh                    # uses YOUTUBE_STREAM_KEY from env
#   ./stream-youtube.sh <stream-key>       # pass key directly
#
# Architecture:
#   [Webcam] → [motion :8081 MJPEG] → [ffmpeg] → [YouTube RTMP ingest]
#
# The Pi Zero 2 W can handle this at 640x480 @ 10fps with ultrafast preset.
# Expected bandwidth: ~500kbps up. Check your WiFi.

set -euo pipefail

# Load env if available
if [[ -f /etc/hummingbird-cam.env ]]; then
    source /etc/hummingbird-cam.env
fi

STREAM_KEY="${1:-${YOUTUBE_STREAM_KEY:-}}"
MOTION_STREAM="${MOTION_STREAM_URL:-http://localhost:8081}"
YOUTUBE_RTMP="rtmp://a.rtmp.youtube.com/live2"

if [[ -z "$STREAM_KEY" ]]; then
    echo "Error: No YouTube stream key provided."
    echo ""
    echo "Either:"
    echo "  1. Set YOUTUBE_STREAM_KEY in /etc/hummingbird-cam.env"
    echo "  2. Pass it as an argument: $0 <stream-key>"
    echo ""
    echo "Get your stream key from: https://studio.youtube.com → Go Live → Stream"
    exit 1
fi

echo "=== Hummingbird Cam → YouTube Live ==="
echo "Source:  ${MOTION_STREAM}"
echo "Target:  ${YOUTUBE_RTMP}/****"
echo ""

# Check that motion stream is accessible
if ! curl -s --max-time 3 -o /dev/null "$MOTION_STREAM"; then
    echo "Error: Cannot reach motion stream at ${MOTION_STREAM}"
    echo "Is the hummingbird-cam service running?"
    echo "  sudo systemctl status hummingbird-cam"
    exit 1
fi

echo "Stream is live. Press Ctrl+C to stop."
echo ""

# ffmpeg relay: MJPEG in → H.264 out → YouTube RTMP
# - ultrafast preset: minimal CPU usage (critical for Pi Zero 2 W)
# - zerolatency tune: reduces stream delay
# - 500kbps: reasonable for 640x480 on WiFi
# - GOP 20 (2s at 10fps): YouTube recommendation for low-latency
exec ffmpeg \
    -i "$MOTION_STREAM" \
    -c:v libx264 \
    -preset ultrafast \
    -tune zerolatency \
    -b:v 500k \
    -maxrate 600k \
    -bufsize 1200k \
    -g 20 \
    -keyint_min 10 \
    -pix_fmt yuv420p \
    -f flv \
    "${YOUTUBE_RTMP}/${STREAM_KEY}"
