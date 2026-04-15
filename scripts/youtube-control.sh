#!/usr/bin/env bash
# youtube-control.sh — manage YouTube Live broadcasts via API
set -euo pipefail

TOKEN_FILE="/etc/youtube_token.json"
ACCESS_TOKEN_CACHE="/tmp/youtube_access_token"
API="https://www.googleapis.com/youtube/v3"

# --- Broadcast defaults ---
TITLE="Baby Humming Birds in Seattle, WA"
DESCRIPTION="This is a live feed of a humming bird nest on my porch in NE Seattle.\nThe nest had fallen out of a tree and so they needed a new home."
CATEGORY_ID="15"  # Pets & Animals
TAGS='["hummingbird","bird nest","live cam","seattle","nature","wildlife","birds","nest cam","baby birds"]'

# --- Auth ---

get_access_token() {
    if [[ -f "$ACCESS_TOKEN_CACHE" ]]; then
        local age=$(( $(date +%s) - $(stat -c %Y "$ACCESS_TOKEN_CACHE" 2>/dev/null || echo 0) ))
        if [[ $age -lt 3000 ]]; then
            cat "$ACCESS_TOKEN_CACHE"
            return
        fi
    fi

    local client_id client_secret refresh_token token_uri
    client_id=$(jq -r .client_id "$TOKEN_FILE")
    client_secret=$(jq -r .client_secret "$TOKEN_FILE")
    refresh_token=$(jq -r .refresh_token "$TOKEN_FILE")
    token_uri=$(jq -r .token_uri "$TOKEN_FILE")

    local response
    response=$(curl -s -X POST "$token_uri" \
        -d "client_id=${client_id}" \
        -d "client_secret=${client_secret}" \
        -d "refresh_token=${refresh_token}" \
        -d "grant_type=refresh_token")

    local token
    token=$(echo "$response" | jq -r '.access_token // empty')
    if [[ -z "$token" ]]; then
        echo "ERROR: Failed to get access token" >&2
        echo "$response" >&2
        return 1
    fi

    echo "$token" > "$ACCESS_TOKEN_CACHE"
    echo "$token"
}

api_get() {
    local token
    token=$(get_access_token)
    curl -s -H "Authorization: Bearer ${token}" "$@"
}

api_post() {
    local token
    token=$(get_access_token)
    curl -s -H "Authorization: Bearer ${token}" -H "Content-Type: application/json" "$@"
}

# --- Commands ---

cmd_start() {
    echo "=== YouTube Live: Starting broadcast ==="

    local now
    now=$(date -u +%Y-%m-%dT%H:%M:%S.000Z)
    local broadcast_response
    broadcast_response=$(api_post -X POST \
        "${API}/liveBroadcasts?part=snippet,status,contentDetails" \
        -d "{
            \"snippet\": {
                \"title\": \"${TITLE}\",
                \"description\": \"${DESCRIPTION}\",
                \"scheduledStartTime\": \"${now}\",
                \"categoryId\": \"${CATEGORY_ID}\"
            },
            \"status\": {
                \"privacyStatus\": \"public\",
                \"selfDeclaredMadeForKids\": false
            },
            \"contentDetails\": {
                \"enableAutoStart\": true,
                \"enableAutoStop\": true,
                \"latencyPreference\": \"normal\"
            }
        }")

    local broadcast_id
    broadcast_id=$(echo "$broadcast_response" | jq -r '.id // empty')
    if [[ -z "$broadcast_id" ]]; then
        echo "ERROR: Failed to create broadcast" >&2
        echo "$broadcast_response" >&2
        return 1
    fi
    echo "Created broadcast: ${broadcast_id}"

    # Set tags via videos.update (tags aren't in liveBroadcasts API)
    api_post -X PUT \
        "${API}/videos?part=snippet" \
        -d "{
            \"id\": \"${broadcast_id}\",
            \"snippet\": {
                \"title\": \"${TITLE}\",
                \"description\": \"${DESCRIPTION}\",
                \"categoryId\": \"${CATEGORY_ID}\",
                \"tags\": ${TAGS}
            }
        }" > /dev/null 2>&1 || echo "WARNING: Could not set tags"

    # Upload thumbnail
    local thumb_token
    thumb_token=$(get_access_token)
    curl -s -X POST \
        "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=${broadcast_id}" \
        -H "Authorization: Bearer ${thumb_token}" \
        -H "Content-Type: image/jpeg" \
        --data-binary @/opt/hummingbird-cam/thumbnail.jpg > /dev/null 2>&1 || echo "WARNING: Could not set thumbnail"

    # Get existing stream
    local streams_response
    streams_response=$(api_get "${API}/liveStreams?part=id,cdn,status&mine=true")
    local stream_id
    stream_id=$(echo "$streams_response" | jq -r '.items[0].id // empty')

    if [[ -z "$stream_id" ]]; then
        echo "ERROR: No stream found. Create one in YouTube Studio first." >&2
        return 1
    fi
    echo "Using stream: ${stream_id}"

    # Bind stream to broadcast
    local bind_response
    bind_response=$(api_post -X POST \
        "${API}/liveBroadcasts/bind?part=id,contentDetails&id=${broadcast_id}&streamId=${stream_id}")
    local bound
    bound=$(echo "$bind_response" | jq -r '.contentDetails.boundStreamId // empty')
    if [[ -z "$bound" ]]; then
        echo "WARNING: Bind may have failed" >&2
        echo "$bind_response" >&2
    else
        echo "Bound stream to broadcast"
    fi

    echo "$broadcast_id" > /tmp/youtube_broadcast_id
    echo "Broadcast ready — will auto-start when RTMP data arrives"
    echo "=== Done ==="
}

cmd_stop() {
    echo "=== YouTube Live: Stopping broadcast ==="

    local broadcast_id=""
    if [[ -f /tmp/youtube_broadcast_id ]]; then
        broadcast_id=$(cat /tmp/youtube_broadcast_id)
    fi

    if [[ -z "$broadcast_id" ]]; then
        local result
        result=$(api_get "${API}/liveBroadcasts?part=id&broadcastStatus=active&mine=true")
        broadcast_id=$(echo "$result" | jq -r '.items[0].id // empty')
    fi

    if [[ -z "$broadcast_id" ]]; then
        echo "No active broadcast found"
        rm -f /tmp/youtube_broadcast_id
        return 0
    fi

    echo "Stopping broadcast: ${broadcast_id}"
    local response
    response=$(api_post -X POST "${API}/liveBroadcasts/transition?broadcastStatus=complete&id=${broadcast_id}&part=id,status")
    local status
    status=$(echo "$response" | jq -r '.status.lifeCycleStatus // "unknown"')
    echo "Broadcast status: ${status}"

    rm -f /tmp/youtube_broadcast_id
    echo "=== Done ==="
}

cmd_status() {
    echo "=== YouTube Live: Broadcast Status ==="

    local active
    active=$(api_get "${API}/liveBroadcasts?part=id,status,snippet&broadcastStatus=active&mine=true")
    local count
    count=$(echo "$active" | jq -r '.pageInfo.totalResults // 0')
    echo "Active broadcasts: ${count}"
    echo "$active" | jq -r '.items[] | "  \(.id) — \(.snippet.title) — \(.status.lifeCycleStatus)"' 2>/dev/null

    local upcoming
    upcoming=$(api_get "${API}/liveBroadcasts?part=id,status,snippet&broadcastStatus=upcoming&mine=true")
    count=$(echo "$upcoming" | jq -r '.pageInfo.totalResults // 0')
    echo "Upcoming broadcasts: ${count}"
    echo "$upcoming" | jq -r '.items[] | "  \(.id) — \(.snippet.title) — \(.status.lifeCycleStatus)"' 2>/dev/null

    echo "=== Done ==="
}

case "${1:-}" in
    start)  cmd_start ;;
    stop)   cmd_stop ;;
    status) cmd_status ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
