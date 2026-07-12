#!/usr/bin/env bash
# Watch the live recording and scan each segment for Anna's Hummingbird CHIPPING BOUTS
# as soon as it closes. Handles every mic on the rig (shotgun, tx1, tx2).
#
# Emits ONE line per completed segment per mic — so silence never leaves you wondering
# whether it died — and shouts only when a real rhythmic bout appears.
#
# WHY IT ALARMS ON BOUTS, NOT CHIPS: the matched filter hears ~18 dB further than an
# energy detector but costs a few false alarms a minute. Those die to RHYTHM. A chipping
# bird is a metronome (CV <= 0.20); rain is Poisson; footsteps are ragged (CV 0.60 — they
# fooled the detector on 2026-07-12 until the regularity test went in). See match-chips.py.
#
# Reads segments.csv — ffmpeg writes a row there only when a segment is CLOSED, which is
# exactly the "safe to analyze" signal. It never touches the file still being written.
#
# Usage: scripts/watch-chips.sh [day-dir]

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DAY="${1:-$REPO/captures/audio/$(date +%Y-%m-%d)}"
PY="$REPO/.venv/bin/python"

# Older sessions were flat (one mic, no subdirs); newer ones are per-mic. Support both.
MICS=()
for m in shotgun tx1 tx2; do
  [[ -d "$DAY/$m" ]] && MICS+=("$m")
done
(( ${#MICS[@]} )) || MICS=(".")

while true; do
  for mic in "${MICS[@]}"; do
    dir="$DAY/$mic"
    csv="$dir/segments.csv"
    seen="$dir/.scanned"
    [[ -f "$csv" ]] || continue
    touch "$seen"

    while IFS=, read -r name _s _e; do
      [[ -z "${name:-}" ]] && continue
      grep -qxF "$name" "$seen" 2>/dev/null && continue
      wav="$dir/$name"
      [[ -f "$wav" ]] || continue

      out=$("$PY" "$REPO/scripts/match-chips.py" "$wav" 2>/dev/null)
      bouts=$(echo "$out" | sed -n 's/.*\*\*\* \([0-9]*\) CHIPPING BOUT.*/\1/p')
      hits=$(echo "$out"  | sed -n 's/  \([0-9]*\) detection(s).*/\1/p')

      # the energy detector is kept purely as a cheap health check: it reports the noise
      # floor, which is how we notice a dead mic or a wind event
      bg=$("$PY" "$REPO/scripts/detect-chips.py" "$wav" --min-chips 99 2>/dev/null |
           awk -F'band: ' '/background in/{print $2}')
      clock="${name:9:2}:${name:11:2}:${name:13:2}"
      label=$([[ "$mic" == "." ]] && echo "mic" || echo "$mic")

      if [[ "${bouts:-0}" -gt 0 ]]; then
        echo "*** HUMMINGBIRD  $clock  [$label]  ${bouts} CHIPPING BOUT(S) -- GO LISTEN"
        echo "$out" | sed -n '/CHIPPING BOUT/,$p' | grep -E "chips over|chip interval"
      else
        printf "clear  %s  [%-7s] no bouts  (%s unrhythmic, floor %s)\n" \
          "$clock" "$label" "${hits:-0}" "${bg:-?}"
      fi

      echo "$name" >> "$seen"
    done < "$csv"
  done
  sleep 20
done
