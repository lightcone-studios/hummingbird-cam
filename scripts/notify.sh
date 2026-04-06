#!/usr/bin/env bash
# notify.sh — send push notifications via ntfy on motion events
#
# Called by motion daemon via on_event_start, on_picture_save, on_event_end
# Usage:
#   notify.sh event_start
#   notify.sh picture_save /path/to/snapshot.jpg
#   notify.sh event_end

set -euo pipefail

# Configuration — override via /etc/hummingbird-cam.env
NTFY_TOPIC="${NTFY_TOPIC:-hummingbird-nest}"
NTFY_SERVER="${NTFY_SERVER:-http://192.168.8.212:2586}"
NTFY_TOKEN="${NTFY_TOKEN:-}"
NTFY_PRIORITY="${NTFY_PRIORITY:-default}"

# Load environment overrides if present
if [[ -f /etc/hummingbird-cam.env ]]; then
    source /etc/hummingbird-cam.env
fi

EVENT_TYPE="${1:-unknown}"
FILE_PATH="${2:-}"

# Build auth header if token is set
AUTH_ARGS=()
if [[ -n "$NTFY_TOKEN" ]]; then
    AUTH_ARGS=(-H "Authorization: Bearer ${NTFY_TOKEN}")
fi

case "$EVENT_TYPE" in
    event_start)
        curl -s \
            "${AUTH_ARGS[@]}" \
            -H "Title: Nest Activity Detected" \
            -H "Priority: ${NTFY_PRIORITY}" \
            -H "Tags: bird,eyes" \
            -d "Motion detected at the hummingbird nest!" \
            "${NTFY_SERVER}/${NTFY_TOPIC}" > /dev/null 2>&1 &
        ;;

    picture_save)
        if [[ -n "$FILE_PATH" && -f "$FILE_PATH" ]]; then
            # Send snapshot image as attachment
            curl -s \
                "${AUTH_ARGS[@]}" \
                -H "Title: Nest Snapshot" \
                -H "Priority: ${NTFY_PRIORITY}" \
                -H "Tags: camera" \
                -H "Filename: nest-snapshot.jpg" \
                --data-binary @"$FILE_PATH" \
                "${NTFY_SERVER}/${NTFY_TOPIC}" > /dev/null 2>&1 &
        fi
        ;;

    event_end)
        # Quiet notification — motion event ended
        curl -s \
            "${AUTH_ARGS[@]}" \
            -H "Title: Nest Quiet" \
            -H "Priority: min" \
            -H "Tags: zzz" \
            -d "Motion event ended at the nest." \
            "${NTFY_SERVER}/${NTFY_TOPIC}" > /dev/null 2>&1 &
        ;;

    *)
        echo "Unknown event type: $EVENT_TYPE" >&2
        exit 1
        ;;
esac
