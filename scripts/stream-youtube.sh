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
# Tuned for Hans (Mac mini, i7-3720QM, 16GB RAM) at 1280x720. Input framerate
# auto-detected from motion — the C270 caps around 7-10 fps at 720p MJPG.

set -euo pipefail

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
    exit 1
fi

echo "=== Hummingbird Cam → YouTube Live ==="
echo "Source:  ${MOTION_STREAM}"
echo "Target:  ${YOUTUBE_RTMP}/****"
echo ""

HEALTH_CODE=$(curl -s --max-time 3 -o /dev/null -w '%{http_code}' "$MOTION_STREAM" 2>/dev/null || true)
if [[ "$HEALTH_CODE" != "200" ]]; then
    echo "Error: Cannot reach motion stream at ${MOTION_STREAM}"
    echo "Is the hummingbird-cam service running?"
    echo "  sudo systemctl status hummingbird-cam"
    exit 1
fi

echo "Stream is live. Press Ctrl+C to stop."
echo ""

# ffmpeg relay: MJPEG in → H.264 out → YouTube RTMP
# - No input -r flag: let ffmpeg detect actual motion rate (no reinterpretation)
# - -use_wallclock_as_timestamps: MJPEG has no internal timestamps; use wall clock
#   so slow/variable source framerate is handled correctly
# - -vsync cfr + output -r 15: upsample to constant 15fps (dup frames) so YouTube
#   sees a steady stream even when the webcam delivers 6-8 fps
# - libx264 veryfast: good quality/CPU balance on the i7
# - Keyframe every 2s at 15fps output = -g 30
# - 2500k average / 4000k max at 720p
exec ffmpeg \
    -thread_queue_size 512 \
    -use_wallclock_as_timestamps 1 \
    -i "$MOTION_STREAM" \
    -f lavfi -i anullsrc=r=44100:cl=stereo \
    -c:v libx264 \
    -preset veryfast \
    -tune zerolatency \
    -vsync cfr \
    -r 15 \
    -b:v 2500k \
    -maxrate 4000k \
    -bufsize 8000k \
    -g 30 \
    -keyint_min 30 \
    -pix_fmt yuv420p \
    -c:a aac \
    -b:a 128k \
    -ar 44100 \
    -shortest \
    -f flv \
    "${YOUTUBE_RTMP}/${STREAM_KEY}"
