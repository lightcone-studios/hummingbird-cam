#!/usr/bin/env bash
# Start detached, segmented recordings from every mic on the rig.
#
# THE RIG (2026-07-12)
#   shotgun  Sennheiser shotgun -> M-Audio M-Track Duo INPUT 1 (+48V) -> USB
#            The wide shot. Sits on the porch. Also the CONTROL: if a close mic hears a
#            chip and the shotgun does not, that proves the close mic is earning its keep.
#   tx1      Rode Wireless GO transmitter 1 (omni lav) -> Wireless GO RX ch 1 -> USB
#   tx2      Rode Wireless GO transmitter 2 (omni lav) -> Wireless GO RX ch 2 -> USB
#            The close mics. A lav capsule can sit inches from the flowers while the TX
#            body stays sheltered and dry — which is worth ~+23 dB over the porch position
#            (inverse square) and costs nothing.
#
# TWO THINGS THIS SCRIPT REFUSES TO GET WRONG
#
#   1. DEVICE INDICES DRIFT. On 2026-07-12 the M-Track moved from [3] to [4] the moment
#      the Rode was plugged in. Hardcoding an index means silently recording the WRONG
#      MIC — the worst possible failure, because the data looks fine. Everything here is
#      resolved BY NAME, every launch.
#
#   2. THE RODE MUST BE IN SPLIT MODE. In merged mode the receiver mixes both transmitters
#      into one signal and copies it to both channels — the tree mic and the feeder mic
#      become one indistinguishable blob. This script CHECKS for that and refuses to record
#      merged. (Fix: hold BOTH buttons on the RX for 3s. Split shows two meters on its
#      screen, merged shows one.)
#
# USAGE
#   scripts/record-loop.sh                 record all mics, 12 h cap
#   scripts/record-loop.sh 9000            record 2.5 h (a dawn session)
#   scripts/record-loop.sh --stop
#   scripts/record-loop.sh --status
#
# Output: captures/audio/<date>/{shotgun,tx1,tx2}/<YYYYMMDD-HHMMSS>.wav   (mono 48k PCM)

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DAY="$REPO/captures/audio/$(date +%Y-%m-%d)"

SHOTGUN_NAME="USB AUDIO"        # the M-Track Duo enumerates as "USB AUDIO  CODEC"
RODE_NAME="Wireless GO RX"

find_device() {  # $1 = name fragment -> avfoundation audio index, or empty
  # NB: `-list_devices` always exits nonzero (it "fails" to open an input after listing),
  # so this must tolerate that.
  ffmpeg -f avfoundation -list_devices true -i "" 2>&1 |
    sed -n '/AVFoundation audio devices/,$p' |
    grep -F "$1" |
    grep -oE '\[[0-9]+\]' | tail -1 | tr -d '[]'
}

case "${1:-}" in
  --stop)
    stopped=0
    for p in "$DAY"/.*.pid; do
      [[ -e "$p" ]] || continue
      pid=$(cat "$p")
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"; echo "stopped $(basename "$p" .pid | tr -d '.') (PID $pid)"; stopped=1
      fi
      rm -f "$p"
    done
    (( stopped )) || echo "nothing recording."
    exit 0
    ;;
  --status)
    any=0
    for p in "$DAY"/.*.pid; do
      [[ -e "$p" ]] || continue
      pid=$(cat "$p"); name=$(basename "$p" .pid | tr -d '.')
      kill -0 "$pid" 2>/dev/null && { echo "RECORDING  $name (PID $pid)"; any=1; }
    done
    (( any )) || echo "NOT RECORDING"
    for d in shotgun tx1 tx2; do
      [[ -d "$DAY/$d" ]] || continue
      n=$(find "$DAY/$d" -name '*.wav' | wc -l | tr -d ' ')
      sz=$(du -sh "$DAY/$d" 2>/dev/null | cut -f1)
      printf "  %-8s %3s segment(s)  %8s\n" "$d" "$n" "$sz"
    done
    exit 0
    ;;
esac

DURATION="${1:-43200}"
SEG="${2:-300}"

for p in "$DAY"/.*.pid; do
  [[ -e "$p" ]] && kill -0 "$(cat "$p")" 2>/dev/null && {
    echo "Already recording. Use --stop first." >&2; exit 1; }
done

# ---- resolve devices by name -------------------------------------------------
SG_IDX=$(find_device "$SHOTGUN_NAME")
RODE_IDX=$(find_device "$RODE_NAME")

echo "devices:"
[[ -n "$SG_IDX"   ]] && echo "  [$SG_IDX] shotgun (M-Track Duo)"   || echo "  --  shotgun NOT FOUND"
[[ -n "$RODE_IDX" ]] && echo "  [$RODE_IDX] Wireless GO RX"        || echo "  --  Wireless GO RX not present (skipping)"

if [[ -z "$SG_IDX" && -z "$RODE_IDX" ]]; then
  echo "ERROR: no mics found. Is anything plugged in?" >&2
  exit 1
fi

# ---- the Rode MUST be split, not merged --------------------------------------
if [[ -n "$RODE_IDX" ]]; then
  probe=$(mktemp /tmp/rode-probe.XXXX.wav)
  ffmpeg -v error -y -f avfoundation -i ":$RODE_IDX" -t 3 -ar 48000 "$probe" 2>/dev/null
  diff_rms=$(ffmpeg -hide_banner -i "$probe" -af "pan=mono|c0=c0-c1,astats" -f null - 2>&1 |
             awk '/Overall/{o=1} o && /RMS level/{print $NF; exit}')
  rm -f "$probe"
  if [[ "$diff_rms" == "-inf" ]]; then
    echo >&2
    echo "ERROR: the Wireless GO RX is in MERGED mode." >&2
    echo "  Both transmitters are being mixed into one signal — the tree mic and the" >&2
    echo "  feeder mic would be indistinguishable, and the recording would be useless." >&2
    echo "  FIX: hold BOTH buttons on the receiver for 3 seconds." >&2
    echo "       Split = two meters on its screen. Merged = one." >&2
    exit 1
  fi
  echo "  Rode is in SPLIT mode (ch1-ch2 = $diff_rms dB) — TX1 and TX2 are separate."
fi

mkdir -p "$DAY"

# ---- launch (double-fork; macOS has no setsid, and a plain background job dies
#      with the agent session — we lost audio that way on 2026-07-12) ------------
launch() {  # $1 label  $2 pidfile  $3.. ffmpeg args
  local label="$1" pidfile="$2"; shift 2
  python3 - "$DAY" "$pidfile" "$label" "$@" <<'PY'
import os, sys
day, pidfile, label, *args = sys.argv[1:]
if os.fork() > 0: sys.exit(0)
os.setsid()
if os.fork() > 0: sys.exit(0)
os.chdir(day)
log = os.open(f".{label}.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND)
os.dup2(log, 1); os.dup2(log, 2)
os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
open(pidfile, "w").write(str(os.getpid()))
os.execvp("ffmpeg", ["ffmpeg"] + args)
PY
}

SEGARGS=(-f segment -segment_time "$SEG" -reset_timestamps 1 -strftime 1 -segment_list_type csv)

if [[ -n "$SG_IDX" ]]; then
  mkdir -p "$DAY/shotgun"
  launch shotgun "$DAY/.shotgun.pid" \
    -hide_banner -nostdin -y -f avfoundation -i ":$SG_IDX" \
    -af "pan=mono|c0=c0" -ar 48000 -c:a pcm_s16le \
    "${SEGARGS[@]}" -segment_list "shotgun/segments.csv" -t "$DURATION" \
    "shotgun/%Y%m%d-%H%M%S.wav"
fi

if [[ -n "$RODE_IDX" ]]; then
  mkdir -p "$DAY/tx1" "$DAY/tx2"
  # One process, one clock, two outputs: channelsplit keeps TX1 and TX2 sample-locked
  # to each other while writing them as separate mono files, so every downstream tool
  # keeps working unchanged.
  launch rode "$DAY/.rode.pid" \
    -hide_banner -nostdin -y -f avfoundation -i ":$RODE_IDX" \
    -filter_complex "[0:a]channelsplit=channel_layout=stereo[l][r]" \
    -map "[l]" -ar 48000 -c:a pcm_s16le "${SEGARGS[@]}" \
      -segment_list "tx1/segments.csv" -t "$DURATION" "tx1/%Y%m%d-%H%M%S.wav" \
    -map "[r]" -ar 48000 -c:a pcm_s16le "${SEGARGS[@]}" \
      -segment_list "tx2/segments.csv" -t "$DURATION" "tx2/%Y%m%d-%H%M%S.wav"
fi

sleep 3
echo
ok=0
for p in "$DAY"/.*.pid; do
  [[ -e "$p" ]] || continue
  pid=$(cat "$p")
  if kill -0 "$pid" 2>/dev/null; then
    echo "RECORDING  $(basename "$p" .pid | tr -d '.')  PID $pid"
    ok=1
  fi
done
if (( ok )); then
  echo "  ${SEG}s segments, ${DURATION}s cap -> $DAY"
  echo "  stop with: scripts/record-loop.sh --stop"
else
  echo "FAILED to start — see $DAY/.*.log" >&2
  tail -3 "$DAY"/.*.log 2>/dev/null >&2
  exit 1
fi
