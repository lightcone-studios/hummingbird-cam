#!/usr/bin/env python3
"""
Detect Anna's Hummingbird (Calypte anna) CHIP NOTES and measure inter-chip intervals.

WHY THESE PARAMETERS
--------------------
Every number below is taken from the published method in:

    Glassman, S. R.-Y., Domer, A., & Dudley, R.
    "Vocal Dimorphism in Anna's Hummingbirds"
    UC Berkeley, Dept. of Integrative Biology
    (docs/final-vocal-dimorphism-in-annas-hummingbirds-1.pdf)

They ran Raven Pro 1.6's Interactive Detector with:
    min frequency   8000 Hz          <- BAND_LOW
    max frequency  10000 Hz          <- BAND_HIGH
    min duration      0.01 s         <- MIN_DUR
    max duration      0.10 s         <- MAX_DUR
    min separation    0.05 s         <- MIN_SEP
    SNR threshold    11 dB above background   <- SNR_DB
    background block  2 s, hop 1 s   <- BG_BLOCK / BG_HOP

This band matters. A chip is broadband, but a naive wideband detector on a rainy
porch just finds rain: the weather bed is LOW-frequency and loud. The 8-10 kHz
window is where the chip is bright and the weather is not. Detecting in that
window is what separates a bird from an umbrella.

THE MEASURABLE
--------------
The paper's finding is that the CHIP INTERVAL (onset of one chip -> onset of the
next) is sexually dimorphic:

    Male    n=41   mean 0.32 s  (SD 0.08)
    Female  n=26   mean 0.43 s  (SD 0.15)
    Unknown n=39   mean 0.38 s  (SD 0.13)
    -> males chip ~1.4x faster than females (z=-3.85, p<0.001)

So chip interval is the number worth extracting from every bout we record.

This script only MEASURES. It declares no hypothesis and makes no claim about
which birds are on Aaron's porch. Interpretation is a separate, later step —
see science/README.md for how a hypothesis gets sealed before data is used.

USAGE
-----
    detect-chips.py FILE.wav [FILE2.wav ...]     analyze recordings
    detect-chips.py --dir captures/audio/2026-07-12   analyze a capture dir
    detect-chips.py FILE.wav --plot out.png      mark detections on a spectrogram
    detect-chips.py FILE.wav --json out.json     write chip onsets + intervals
    detect-chips.py FILE.wav --min-chips 1       report even sparse files

Requires the repo venv:  .venv/bin/python scripts/detect-chips.py ...
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

# --- the paper's detector settings (see docstring) ---------------------------
# RETUNED 2026-07-12 after recording OUR FIRST REAL BIRD. The paper's detector used
# 8-10 kHz, and I took that as gospel for a whole morning. But that was the window THEY
# chose for THEIR recordings — it is not where a chip's energy actually lives. Measured
# on real chips (n=62 ours, n=96 reference), BOTH birds peak at 6-7 kHz:
#
#   band          our bird    reference
#   8-10 kHz       -1.5 dB     +17.9 dB    <- the paper's window; BELOW ZERO on our birds
#   5-10 kHz       +5.9 dB     +28.7 dB    <- where the energy actually is
#
# +7.5 dB on our birds and +10.8 dB on the reference, for free, just by listening in the
# right place. Lesson: a published parameter is a starting point, not a fact about the world.
BAND_LOW = 5000.0    # Hz
BAND_HIGH = 10000.0  # Hz
MIN_DUR = 0.01       # s   a chip is a single short syllable
MAX_DUR = 0.10       # s   "less than 0.1 s in duration"
MIN_SEP = 0.05       # s   two chips closer than this are one detection
SNR_DB = 11.0        # dB  above the local background
BG_BLOCK = 2.0       # s   background is estimated over a 2 s block...
BG_HOP = 1.0         # s   ...recomputed every 1 s

# --- band-contrast gate (OUR addition — not in the paper) --------------------
# The paper's detector ran on a recordist's clean, close, hand-aimed recordings.
# Our mic sits under an umbrella in Pacific Northwest rain, and rain is the enemy:
# a raindrop is a broadband CLICK with real energy up at 8-10 kHz, so it sails
# straight through a bandpass and registers as a chip. On 2026-07-12 this produced
# 405 "chips" in 8 minutes of porch audio — every last one of them weather.
#
# What actually separates them is the SHAPE of the event's spectrum:
#
#   real Anna's chip (n=98, XC1077841):  8-10 kHz is +17.8 dB LOUDER than 1-3 kHz
#   rain/wind on the umbrella (n=259):   8-10 kHz is -14.7 dB QUIETER than 1-3 kHz
#
# 32.5 dB of separation with ZERO overlap — not one of the 259 rain events reached
# even the 10th percentile of the real chips. A chip is genuinely a high-frequency
# event; a raindrop just peaks low and splashes everywhere. The threshold below sits
# in the empty gap between the two populations.
LOW_REF_LOW = 1000.0    # Hz \ the reference band the chip band is compared against
LOW_REF_HIGH = 3000.0   # Hz /
CONTRAST_DB = 6.0       # dB  SCREENING threshold — deliberately permissive (see below)

# ===========================================================================================
# *** READ THIS BEFORE TRUSTING ANY CONTRAST NUMBER BELOW ***
#
# THE CONTRAST GATE DOES NOT WORK ON REAL BIRDS. Falsified 2026-07-12, the same day it was
# built, by our first confirmed hummingbird.
#
# It LOOKED excellent when validated against XC1077841 — a recordist's pristine, close-miked
# bird whose chips blaze at +28 dB of band contrast while rain sits at -8 dB. 36 dB apart.
# Beautiful. Wrong.
#
# Then we recorded an actual hummingbird on Aaron's porch — seen with his own eyes, heard on
# three microphones at 6.9 sigma coincidence — and measured it:
#
#                        p10      median     p90
#     reference bird    +22.7     +28.7     +33.1     <- pristine close-up
#     OUR REAL BIRD      +1.6      +5.9      +8.9     <- wild, distant, through foliage
#     rain              -15.3      -8.4      -0.1
#     Aaron's footsteps -13.9      -5.2      +4.5     <- reaches HIGHER than our bird's p10
#
#     ALL REAL BIRDS p10 = +1.1 dB   |   ALL NOISE p90 = +1.8 dB   -> THE POPULATIONS OVERLAP
#
# A real bird at real distance loses its high frequencies to air and leaves. There is no
# threshold that keeps our hummingbird and rejects our footsteps. Had we trusted this gate,
# it would have DISCARDED a confirmed hummingbird as noise.
#
# WHAT ACTUALLY WORKS IS RHYTHM. A chipping bird is a metronome (CV <= 0.20); rain is a
# Poisson process; footsteps are ragged (CV 0.60). See match-chips.py — the bout test found
# our bird and rejected BOTH rain and footsteps, where contrast failed at both ends.
#
# CONTRAST_DB is therefore kept ONLY as a cheap permissive pre-screen, never as a verdict.
# The tiers below are calibrated on the reference and are known NOT to fit real birds:
# our confirmed hummingbird scores "doubtful". Do not read them as truth. Use match-chips.py.
#
# The general lesson, learned twice in one day: a parameter validated on someone else's
# clean recording is a HYPOTHESIS about your own data, not a fact about it.
# ===========================================================================================
CHIP_CONTRAST_STRONG = 14.0   # dB — reference-calibrated; REAL birds do not reach this
CHIP_DUR_MIN = 0.020          # s
CHIP_DUR_MAX = 0.060          # s


def tier(c: "Chip") -> str:
    """How much a survivor actually looks like a chip. Descriptive, never a species claim."""
    if c.contrast_db >= CHIP_CONTRAST_STRONG and CHIP_DUR_MIN <= c.duration <= CHIP_DUR_MAX:
        return "STRONG"      # inside the reference chips' own range on both axes
    if c.contrast_db >= CHIP_CONTRAST_STRONG or CHIP_DUR_MIN <= c.duration <= CHIP_DUR_MAX:
        return "weak"        # right on one axis, wrong on the other
    return "doubtful"        # cleared the screen but looks nothing like a chip

# Reference values from the paper, for comparison only.
PAPER = {"male": (0.32, 0.08), "female": (0.43, 0.15), "unknown": (0.38, 0.13)}

ENV_HOP = 0.002      # s   envelope resolution (2 ms) — fine enough for a 10 ms chip


@dataclass
class Chip:
    start: float
    end: float
    peak_db: float
    contrast_db: float = 0.0   # how much the chip band beats the low band; see CONTRAST_DB

    @property
    def duration(self) -> float:
        return self.end - self.start


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Read a mono waveform. Anything ffmpeg understands is accepted."""
    if path.suffix.lower() != ".wav":
        return _load_via_ffmpeg(path)
    try:
        with wave.open(str(path), "rb") as w:
            if w.getsampwidth() != 2:          # e.g. 32-bit float WAV
                return _load_via_ffmpeg(path)
            sr = w.getframerate()
            raw = w.readframes(w.getnframes())
            x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            if w.getnchannels() > 1:
                x = x.reshape(-1, w.getnchannels()).mean(axis=1)
            return x, sr
    except (wave.Error, EOFError):
        return _load_via_ffmpeg(path)


def _load_via_ffmpeg(path: Path) -> tuple[np.ndarray, int]:
    sr = 48000
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(out, dtype="<f4").copy(), sr


def band_envelope(x: np.ndarray, sr: int) -> tuple[np.ndarray, float]:
    """Energy envelope inside the chip band, in dB. Returns (env_db, hop_seconds)."""
    nyq = sr / 2.0
    high = min(BAND_HIGH, nyq * 0.99)
    if BAND_LOW >= high:
        raise ValueError(f"sample rate {sr} Hz is too low for a {BAND_LOW}-{BAND_HIGH} Hz band")

    sos = butter(4, [BAND_LOW / nyq, high / nyq], btype="band", output="sos")
    band = sosfiltfilt(sos, x)

    hop = max(1, int(round(ENV_HOP * sr)))
    win = hop * 4                                  # 8 ms analysis window, 2 ms hop
    n = (len(band) - win) // hop + 1
    if n <= 0:
        return np.zeros(0), hop / sr

    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    frames = band[idx]
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1))
    env_db = 20.0 * np.log10(rms + 1e-12)
    return env_db, hop / sr


def rolling_background(env_db: np.ndarray, hop_s: float) -> np.ndarray:
    """
    Local background level, per the paper's 2 s block / 1 s hop.

    The MEDIAN (not the mean) is the right statistic here: chips are brief, loud
    outliers, and a median over a 2 s block is barely moved by them — so the
    background stays a background instead of creeping up to meet the birds.
    """
    block = max(1, int(round(BG_BLOCK / hop_s)))
    hop = max(1, int(round(BG_HOP / hop_s)))
    if len(env_db) <= block:
        return np.full_like(env_db, float(np.median(env_db)))

    centers, levels = [], []
    for s in range(0, len(env_db) - block + 1, hop):
        centers.append(s + block // 2)
        levels.append(np.median(env_db[s:s + block]))
    return np.interp(np.arange(len(env_db)), centers, levels)


def bandpass(x: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    nyq = sr / 2.0
    sos = butter(4, [lo / nyq, min(hi, nyq * 0.99) / nyq], btype="band", output="sos")
    return sosfiltfilt(sos, x)


def detect(x: np.ndarray, sr: int, gate: bool = True) -> tuple[list[Chip], float]:
    """
    Find chips. Returns (chips, median_background_db).

    gate=False disables the band-contrast filter — used to show what the raw
    frequency-band detector would have reported, i.e. how much weather it eats.
    """
    env_db, hop_s = band_envelope(x, sr)
    if len(env_db) == 0:
        return [], float("nan")

    bg = rolling_background(env_db, hop_s)
    over = env_db > (bg + SNR_DB)

    # contiguous runs above threshold
    edges = np.diff(over.astype(np.int8))
    starts = list(np.flatnonzero(edges == 1) + 1)
    ends = list(np.flatnonzero(edges == -1) + 1)
    if over[0]:
        starts.insert(0, 0)
    if over[-1]:
        ends.append(len(over))

    raw = [(s * hop_s, e * hop_s, float(env_db[s:e].max()))
           for s, e in zip(starts, ends) if e > s]

    # merge anything closer than the minimum separation — that is one chip, not two
    merged: list[list[float]] = []
    for s, e, p in raw:
        if merged and s - merged[-1][1] < MIN_SEP:
            merged[-1][1] = e
            merged[-1][2] = max(merged[-1][2], p)
        else:
            merged.append([s, e, p])

    candidates = [Chip(s, e, p) for s, e, p in merged if MIN_DUR <= (e - s) <= MAX_DUR]

    # Band-contrast gate: is this event actually BRIGHT UP HIGH, like a chip —
    # or is it a low-peaking broadband splat, like rain? (see CONTRAST_DB)
    hi_band = bandpass(x, sr, BAND_LOW, BAND_HIGH)
    lo_band = bandpass(x, sr, LOW_REF_LOW, LOW_REF_HIGH)

    chips = []
    for c in candidates:
        a, b = int(c.start * sr), int(c.end * sr)
        if b <= a:
            continue
        e_hi = np.sqrt((hi_band[a:b].astype(np.float64) ** 2).mean()) + 1e-12
        e_lo = np.sqrt((lo_band[a:b].astype(np.float64) ** 2).mean()) + 1e-12
        c.contrast_db = float(20.0 * np.log10(e_hi / e_lo))
        if not gate or c.contrast_db >= CONTRAST_DB:
            chips.append(c)

    return chips, float(np.median(bg))


def intervals_of(chips: list[Chip]) -> np.ndarray:
    """Chip interval = onset-to-onset, exactly as the paper measures it."""
    if len(chips) < 2:
        return np.zeros(0)
    return np.diff(np.array([c.start for c in chips]))


def summarize(name: str, chips: list[Chip], bg_db: float, dur: float, min_chips: int) -> dict:
    iv = intervals_of(chips)

    # The paper drops the top 5% of intervals: a bird pausing to feed leaves a long
    # gap that is a break BETWEEN bouts, not a slow chip rate WITHIN one.
    iv_trim = iv[iv <= np.percentile(iv, 95)] if len(iv) >= 4 else iv

    rate = len(chips) / dur * 60 if dur > 0 else 0.0
    row = {
        "file": name,
        "duration_s": round(dur, 1),
        "chips": len(chips),
        "chips_per_min": round(rate, 1),
        "band_background_db": round(bg_db, 1),
    }

    tiers = {t: [c for c in chips if tier(c) == t] for t in ("STRONG", "weak", "doubtful")}
    row["strong"] = len(tiers["STRONG"])

    print(f"\n{name}")
    print(f"  {dur:.1f}s  |  background in {BAND_LOW/1000:.0f}-{BAND_HIGH/1000:.0f} kHz band: {bg_db:.1f} dB")
    print(f"  cleared the screen: {len(chips)}  "
          f"(STRONG {len(tiers['STRONG'])} | weak {len(tiers['weak'])} | doubtful {len(tiers['doubtful'])})")
    for c in chips:
        t = tier(c)
        flag = "  <<<" if t == "STRONG" else ""
        print(f"     t={c.start:8.2f}s  {c.duration*1000:3.0f} ms  contrast {c.contrast_db:+5.1f} dB   [{t}]{flag}")
    if chips and not tiers["STRONG"]:
        print(f"  -- nothing STRONG. Real chips sit at >= +{CHIP_CONTRAST_STRONG:.0f} dB contrast "
              f"and {CHIP_DUR_MIN*1000:.0f}-{CHIP_DUR_MAX*1000:.0f} ms. Treat the above as noise "
              f"unless a human confirms otherwise. --")

    if len(chips) < min_chips:
        print(f"  -- fewer than {min_chips} chips; no interval statistics --")
        row["verdict"] = "too few chips"
        return row

    if len(iv_trim):
        med = float(np.median(iv_trim))
        mean = float(iv_trim.mean())
        sd = float(iv_trim.std())
        row |= {
            "interval_median_s": round(med, 3),
            "interval_mean_s": round(mean, 3),
            "interval_sd_s": round(sd, 3),
            "n_intervals": int(len(iv_trim)),
        }
        print(f"  chip interval:  median {med:.3f}s   mean {mean:.3f}s +/- {sd:.3f}  (n={len(iv_trim)})")

        # Distance to each published class — descriptive only, NOT a sex call.
        near = {k: abs(mean - m) for k, (m, _) in PAPER.items()}
        closest = min(near, key=near.get)
        print("  vs. published means:  " + "   ".join(
            f"{k} {m:.2f}s (d={near[k]:+.3f})" for k, (m, _) in PAPER.items()))
        print(f"  -> closest to published {closest.upper()} mean "
              f"(descriptive only — sex is NOT identifiable from interval alone)")
        row["closest_published_class"] = closest

    if chips:
        durs = np.array([c.duration for c in chips])
        print(f"  chip duration:  median {np.median(durs)*1000:.0f} ms  "
              f"(range {durs.min()*1000:.0f}-{durs.max()*1000:.0f} ms)")
        row["chip_dur_median_ms"] = round(float(np.median(durs)) * 1000, 1)

    return row


def plot(path: Path, chips: list[Chip], out: Path, dur: float,
         t0: float = 0.0, t1: float | None = None) -> None:
    """
    Spectrogram with each detected chip ticked, so a human can check the machine.

    Ticks go BELOW the image, not across it — a full-height line drawn over a chip
    hides the evidence it is supposed to confirm. Pass t0/t1 to zoom; at full length
    ~100 chips in 1600px is too dense to verify anything by eye.
    """
    t1 = dur if t1 is None else min(t1, dur)
    span = max(t1 - t0, 1e-6)
    win = [c for c in chips if t0 <= c.start < t1]

    W, H, PAD = 1600, 560, 40
    ticks = "".join(
        f"drawbox=x={(c.start - t0) / span:.6f}*(iw):y=ih-{PAD}:w=3:h={PAD}:color=cyan@0.95:t=fill,"
        for c in win
    )
    # shade the detection band so it is obvious WHERE the detector is looking
    top = (1 - BAND_HIGH / 24000) * (H - PAD)
    height = (BAND_HIGH - BAND_LOW) / 24000 * (H - PAD)
    band = f"drawbox=x=0:y={top:.1f}:w=iw:h={height:.1f}:color=yellow@0.5:t=2,"

    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", str(span), "-i", str(path),
         "-lavfi",
         f"showspectrumpic=s={W}x{H - PAD}:legend=0:gain=3,"
         f"pad=w={W}:h={H}:x=0:y=0:color=black,{band}{ticks}null",
         str(out)],
        check=True,
    )
    print(f"  -> {out}  ({len(win)} chips ticked in cyan below; "
          f"detection band {BAND_LOW/1000:.0f}-{BAND_HIGH/1000:.0f} kHz boxed in yellow"
          + (f"; {t0:.1f}-{t1:.1f}s" if (t0 or t1 < dur) else "") + ")")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--dir", type=Path, help="analyze every .wav in this directory")
    ap.add_argument("--plot", type=Path, help="write an annotated spectrogram (single file only)")
    ap.add_argument("--zoom", nargs=2, type=float, metavar=("T0", "T1"),
                    help="restrict --plot to this time window (seconds) — use it; "
                         "100 chips across a full page is unverifiable by eye")
    ap.add_argument("--json", type=Path, help="write results as JSON")
    ap.add_argument("--min-chips", type=int, default=10,
                    help="minimum chips before reporting intervals (paper used 10)")
    args = ap.parse_args()

    files = list(args.files)
    if args.dir:
        files += sorted(p for p in args.dir.glob("*.wav"))
    if not files:
        ap.error("give at least one audio file, or --dir")

    print(f"Anna's Hummingbird chip detector")
    print(f"band {BAND_LOW/1000:.0f}-{BAND_HIGH/1000:.0f} kHz | "
          f"duration {MIN_DUR*1000:.0f}-{MAX_DUR*1000:.0f} ms | "
          f"SNR +{SNR_DB:.0f} dB | min separation {MIN_SEP*1000:.0f} ms")
    print("(parameters from Glassman, Domer & Dudley — see docs/)")

    rows, all_chips = [], {}
    for f in files:
        if not f.exists():
            print(f"\n{f.name}: NOT FOUND", file=sys.stderr)
            continue
        x, sr = load_audio(f)
        dur = len(x) / sr
        chips, bg = detect(x, sr)
        ungated, _ = detect(x, sr, gate=False)
        rejected = len(ungated) - len(chips)
        rows.append(summarize(f.name, chips, bg, dur, args.min_chips))
        if rejected:
            print(f"  band-contrast gate rejected {rejected} broadband event(s) "
                  f"(rain/wind/impulse — energy peaked low, not in the chip band)")
        all_chips[f.name] = chips
        if args.plot and len(files) == 1:
            z = args.zoom or (0.0, dur)
            plot(f, chips, args.plot, dur, t0=z[0], t1=z[1])

    if args.json:
        args.json.write_text(json.dumps({
            "detector": {
                "band_hz": [BAND_LOW, BAND_HIGH], "dur_s": [MIN_DUR, MAX_DUR],
                "min_sep_s": MIN_SEP, "snr_db": SNR_DB,
                "source": "Glassman, Domer & Dudley — Vocal Dimorphism in Anna's Hummingbirds",
            },
            "results": rows,
            "chips": {k: [asdict(c) for c in v] for k, v in all_chips.items()},
        }, indent=2))
        print(f"\n-> {args.json}")

    total = sum(r["chips"] for r in rows)
    print(f"\n{total} chip(s) across {len(rows)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
