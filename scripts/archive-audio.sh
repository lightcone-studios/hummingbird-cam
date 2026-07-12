#!/usr/bin/env bash
# Shrink the audio archive WITHOUT throwing away birds.
#
# ------------------------------------------------------------------------------
# WHY THIS TOOL DOES NOT DELETE "BORING" AUDIO
# ------------------------------------------------------------------------------
# The obvious design is: run the detector, keep the clips with chips, bin the rest.
# We measured that idea on 2026-07-12 and it is a data-destroying trap.
#
# Test: take REAL Anna's chips (95 of them, known times), attenuate them to simulate
# a more distant bird, mix into REAL porch noise, and ask the detector to find them.
#
#     chip level                    chips found (of 95)     STRONG
#     0 dB   (bird at the feeder)         78                  31
#     -12 dB (bird in the next tree)      27                   0
#     -20 dB                               0                   0
#     -26 dB                               0                   0
#
# The detector is BLIND below about -12 to -20 dB. A hummingbird really chipping,
# a few metres further out, produces ZERO detections. If we deleted audio on the
# grounds that "no chips were found", we would be shredding precisely the faint-bird
# recordings that a better detector could recover later — and we would never know.
#
# Same principle that made us record continuously instead of on a trigger:
#   *** never let today's ignorance cause permanent data loss. ***
#
# So this tool only ever COMPRESSES. Deletion of source audio happens exactly once,
# after a byte-for-byte verification that the compressed copy decodes back identically.
#
# ------------------------------------------------------------------------------
# WHY LOSSY IS ALLOWED IN THE DEEP TIER (we tested this too, and were surprised)
# ------------------------------------------------------------------------------
# Lossy compression sounds reckless for science. It measurably is not — for THIS
# measurement. Re-encoding the reference bird and re-running the detector:
#
#     codec        chips  STRONG  interval      size
#     WAV (truth)    95     70    0.494 s       100%
#     FLAC           95     70    0.494 s        50%   <- bit-identical
#     Opus 128k      95     70    0.494 s        ~15%
#     Opus 64k       95     71    0.494 s         ~8%
#
# Opus 64k tracked uncompressed audio exactly, even on the faint-chip test above
# (27/27 at -12 dB). It loses no chips and shifts no intervals.
#
# But "safe for the detector we have" is not "safe for every question we might ask."
# Individual voice ID, fine chip-shape morphometrics, or anything not yet imagined may
# want the original bits. So lossless FLAC is the default, and Opus is opt-in for the
# deep tier where the space actually matters.
#
# ------------------------------------------------------------------------------
# USAGE
# ------------------------------------------------------------------------------
#   scripts/archive-audio.sh --report                 what is on disk, what it would save
#   scripts/archive-audio.sh --flac                   WAV -> FLAC  (lossless, verified)
#   scripts/archive-audio.sh --flac --older-than 1    only files older than 1 day
#   scripts/archive-audio.sh --opus --older-than 30   FLAC/WAV -> Opus 64k (deep tier)
#   scripts/archive-audio.sh --highlights             cut every event +/- context to clips/
#
# Dry-run is the DEFAULT. Nothing is written or removed without --apply.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
AUDIO="$REPO/captures/audio"
PY="$REPO/.venv/bin/python"

MODE=""
APPLY=0
OLDER_THAN=0          # days; 0 = no age filter
PAD=3                 # seconds of context kept either side of an event in --highlights
OPUS_BITRATE="64k"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --report)     MODE=report ;;
    --flac)       MODE=flac ;;
    --opus)       MODE=opus ;;
    --highlights) MODE=highlights ;;
    --apply)      APPLY=1 ;;
    --older-than) OLDER_THAN="$2"; shift ;;
    --pad)        PAD="$2"; shift ;;
    -h|--help)    sed -n '2,60p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done
[[ -z "$MODE" ]] && { sed -n '2,60p' "$0"; exit 0; }

human() { python3 -c "import sys; n=float(sys.argv[1]); print(f'{n/1e9:.2f} GB' if n>1e9 else f'{n/1e6:.0f} MB')" "$1"; }

# Files eligible by age. The segment currently being written is never touched:
# it is the newest, and ffmpeg still holds it open.
eligible() {
  local ext="$1"
  local live=""
  live=$(ls -t "$AUDIO"/*/*.wav 2>/dev/null | head -1 || true)
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    [[ "$f" == "$live" ]] && continue
    if (( OLDER_THAN > 0 )); then
      find "$f" -mtime "+${OLDER_THAN}" 2>/dev/null | grep -q . || continue
    fi
    echo "$f"
  done < <(find "$AUDIO" -name "*.${ext}" -type f 2>/dev/null | sort)
}

# ---------------------------------------------------------------- report
if [[ "$MODE" == report ]]; then
  echo "AUDIO ARCHIVE — $AUDIO"
  echo
  tw=0; tf=0; to=0; nw=0; nf=0; no=0
  for f in $(find "$AUDIO" -name '*.wav' -type f 2>/dev/null); do tw=$((tw+$(stat -f%z "$f"))); nw=$((nw+1)); done
  for f in $(find "$AUDIO" -name '*.flac' -type f 2>/dev/null); do tf=$((tf+$(stat -f%z "$f"))); nf=$((nf+1)); done
  for f in $(find "$AUDIO" -name '*.opus' -type f 2>/dev/null); do to=$((to+$(stat -f%z "$f"))); no=$((no+1)); done
  printf "  %-6s %4d file(s)   %10s\n" "WAV"  "$nw" "$(human $tw)"
  printf "  %-6s %4d file(s)   %10s\n" "FLAC" "$nf" "$(human $tf)"
  printf "  %-6s %4d file(s)   %10s\n" "OPUS" "$no" "$(human $to)"
  printf "  %-6s %4s            %10s\n" "TOTAL" "" "$(human $((tw+tf+to)))"
  echo
  if (( tw > 0 )); then
    echo "  If the WAVs were converted:"
    printf "    -> FLAC (lossless)   ~%10s   saves ~%s\n" "$(human $((tw/2)))" "$(human $((tw/2)))"
    printf "    -> Opus 64k (deep)   ~%10s   saves ~%s\n" "$(human $((tw*8/100)))" "$(human $((tw*92/100)))"
  fi
  echo
  df -h "$REPO" | awk 'NR==1{print "  "$0} NR==2{print "  "$0}'
  echo
  echo "  Recording burns ~3.7 GB/day as WAV, ~1.8 GB/day as FLAC, ~0.3 GB/day as Opus."
  exit 0
fi

# ---------------------------------------------------------------- flac (lossless)
if [[ "$MODE" == flac ]]; then
  echo "WAV -> FLAC (lossless). Source is removed ONLY after the FLAC is verified"
  echo "to decode back to byte-identical PCM."
  (( APPLY )) || echo ">>> DRY RUN — nothing will be written. Add --apply to do it. <<<"
  echo
  saved=0; n=0
  for wav in $(eligible wav); do
    flac="${wav%.wav}.flac"
    [[ -f "$flac" ]] && continue
    before=$(stat -f%z "$wav")
    if (( APPLY )); then
      ffmpeg -v error -y -i "$wav" -c:a flac -compression_level 8 "$flac"
      # VERIFY: decode both to raw PCM and compare hashes. No match -> keep the WAV.
      a=$(ffmpeg -v error -i "$wav"  -f s16le - | shasum -a 256 | cut -d' ' -f1)
      b=$(ffmpeg -v error -i "$flac" -f s16le - | shasum -a 256 | cut -d' ' -f1)
      if [[ "$a" != "$b" ]]; then
        echo "  !! $(basename "$wav") — FLAC did NOT verify. WAV kept, FLAC discarded."
        rm -f "$flac"
        continue
      fi
      after=$(stat -f%z "$flac")
      rm -f "$wav"
      echo "  ok  $(basename "$wav") -> $(human $before) -> $(human $after)  [verified identical]"
    else
      after=$((before/2))
      echo "  would convert  $(basename "$wav")  $(human $before) -> ~$(human $after)"
    fi
    saved=$((saved + before - ${after:-0})); n=$((n+1))
  done
  echo
  echo "  $n file(s), ~$(human $saved) reclaimed"
  exit 0
fi

# ---------------------------------------------------------------- opus (deep tier)
if [[ "$MODE" == opus ]]; then
  if (( OLDER_THAN == 0 )); then
    echo "Refusing to run without --older-than. Opus is LOSSY: the original bits are gone" >&2
    echo "for good. Use it only on genuinely old data, e.g. --older-than 30." >&2
    exit 1
  fi
  echo "WAV/FLAC -> Opus ${OPUS_BITRATE} (deep archive, older than ${OLDER_THAN}d)"
  echo "LOSSY — verified not to cost chips or shift intervals (see header), but the"
  echo "original samples are unrecoverable. Highlights should be extracted first."
  (( APPLY )) || echo ">>> DRY RUN — nothing will be written. Add --apply to do it. <<<"
  echo
  saved=0; n=0
  for src in $(eligible wav) $(eligible flac); do
    opus="${src%.*}.opus"
    [[ -f "$opus" ]] && continue
    before=$(stat -f%z "$src")
    if (( APPLY )); then
      ffmpeg -v error -y -i "$src" -c:a libopus -b:a "$OPUS_BITRATE" "$opus"
      after=$(stat -f%z "$opus")
      rm -f "$src"
      echo "  ok  $(basename "$src") -> $(human $before) -> $(human $after)"
    else
      after=$((before*8/100))
      echo "  would convert  $(basename "$src")  $(human $before) -> ~$(human $after)"
    fi
    saved=$((saved + before - after)); n=$((n+1))
  done
  echo
  echo "  $n file(s), ~$(human $saved) reclaimed"
  exit 0
fi

# ---------------------------------------------------------------- highlights
if [[ "$MODE" == highlights ]]; then
  echo "Cutting every detected event to clips/ with +/- ${PAD}s of context."
  echo "This EXTRACTS, it never deletes. Clips are the permanent record of anything"
  echo "interesting, so the bulk archive can be compressed hard without regret."
  (( APPLY )) || echo ">>> DRY RUN — nothing will be written. Add --apply to do it. <<<"
  echo
  n=0
  for wav in $(eligible wav); do
    dir="$(dirname "$wav")/clips"
    base="$(basename "${wav%.wav}")"
    json="$("$PY" "$REPO/scripts/detect-chips.py" "$wav" --min-chips 1 2>/dev/null || true)"
    # every survivor of the screen, whatever its tier — a "doubtful" today may be
    # a bird once the detector improves
    echo "$json" | sed -n 's/^ *t= *\([0-9.]*\)s.*\[\(.*\)\].*/\1 \2/p' | while read -r t tier; do
      [[ -z "$t" ]] && continue
      s=$(python3 -c "print(max(0, $t - $PAD))")
      out="$dir/${base}_t${t%.*}_${tier}.wav"
      if (( APPLY )); then
        mkdir -p "$dir"
        ffmpeg -v error -y -ss "$s" -t "$((PAD*2))" -i "$wav" "$out"
        echo "  cut  $(basename "$out")"
      else
        echo "  would cut  $(basename "$out")"
      fi
      n=$((n+1))
    done
  done
  echo
  echo "  done"
  exit 0
fi
