#!/usr/bin/env python3
"""
What is actually out there? A general acoustic survey — NOT a hummingbird detector.

`detect-chips.py` and `match-chips.py` are deliberately narrow: they hunt one signal in one
band and ignore everything else. This does the opposite. It looks at the whole spectrum and
asks "what kinds of sound live here, and when?"

Why bother, when we only care about hummingbirds?

  1. EVERY OTHER SOUND IS A POTENTIAL FALSE POSITIVE. On 2026-07-12 we were fooled twice —
     once by rain, once by footsteps. Both would have been obvious if we had characterised
     the soundscape first instead of going straight for the bird.
  2. AIRCRAFT ARE A REAL CONFOUND for a dawn session. A plane raises the noise floor for
     MINUTES, not milliseconds — which quietly destroys sensitivity for a whole passage of
     recording. We need to know when that happened, so we don't report "no chips" for a
     window where we were simply deaf.
  3. OTHER BIRDS tell us the dawn chorus is happening — i.e. that the microphone and the
     morning are both working, even when the hummingbirds are absent.

Events are classified by SHAPE, not loudness:

    plane / traffic   long (>3 s), energy concentrated LOW, slowly varying
    bird              short (0.05-2 s), energy in 2-10 kHz, tonal
    impulse           very short (<50 ms), broadband — rain, a click, a knock
    rumble            sustained low with no structure — wind

Usage:
    soundscape.py FILE.wav [--plot out.png]
    soundscape.py --dir captures/audio/2026-07-12/shotgun
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.signal import stft

SR = 48000

# The bands worth naming. Chosen to match what actually lives in each.
BANDS = [
    ("rumble",   20,   250, "wind, traffic, aircraft body"),
    ("low",     250,  1000, "engines, creek, road, voices"),
    ("mid",    1000,  3000, "most songbird song, rain bed"),
    ("high",   3000,  8000, "songbird calls, chip skirts"),
    ("chip",   8000, 11000, "ANNA'S CHIP BAND"),
    ("ultra", 11000, 20000, "insects, sibilance, mechanical noise"),
]


def load(path: Path) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(out, dtype="<f4").copy()


def band_energies(x: np.ndarray) -> tuple[dict, np.ndarray]:
    """dB energy per band over time."""
    f, t, Z = stft(x, fs=SR, nperseg=2048, noverlap=1024, boundary=None)
    P = np.abs(Z) ** 2
    out = {}
    for name, lo, hi, _ in BANDS:
        sel = (f >= lo) & (f < hi)
        out[name] = 10 * np.log10(P[sel].mean(axis=0) + 1e-12)
    return out, t


def survey(path: Path) -> None:
    x = load(path)
    dur = len(x) / SR
    E, t = band_energies(x)

    print(f"\n{path.name}   {dur:.0f}s")
    print(f"{'band':<8} {'range':<14} {'median':>8} {'loudest':>9}   what lives here")
    print("-" * 78)
    for name, lo, hi, desc in BANDS:
        e = E[name]
        mark = "  <<<" if name == "chip" else ""
        print(f"{name:<8} {f'{lo/1000:.0f}-{hi/1000:.0f} kHz':<14} "
              f"{np.median(e):>8.1f} {np.percentile(e, 99):>9.1f}   {desc}{mark}")

    # --- aircraft: sustained low-band energy well above that band's own baseline ---
    low = E["rumble"] + E["low"]
    base = np.median(low)
    hot = low > base + 6
    hop = t[1] - t[0]
    runs, run = [], 0
    for v in hot:
        if v:
            run += 1
        else:
            if run * hop > 3.0:
                runs.append(run * hop)
            run = 0
    if run * hop > 3.0:
        runs.append(run * hop)

    print()
    if runs:
        total = sum(runs)
        print(f"AIRCRAFT / SUSTAINED LOW-FREQUENCY EVENTS: {len(runs)} "
              f"({total:.0f}s = {100*total/dur:.0f}% of the recording)")
        print(f"   longest {max(runs):.0f}s. These raise the noise floor for MINUTES —")
        print(f"   sensitivity to a faint chip is degraded for their whole duration.")
    else:
        print("AIRCRAFT / SUSTAINED LOW-FREQUENCY EVENTS: none detected")

    # --- birds: short events with energy up in 2-10 kHz and NOT dominated by the low bed ---
    birdish = (E["high"] + E["chip"]) / 2 - (E["low"] + E["mid"]) / 2
    thr = np.percentile(birdish, 97)
    hits = birdish > max(thr, np.median(birdish) + 6)
    n, run = 0, 0
    events = []
    for i, v in enumerate(hits):
        if v:
            run += 1
        else:
            if 0.03 < run * hop < 2.0:
                events.append((t[i - run], run * hop))
                n += 1
            run = 0

    print()
    print(f"BIRD-LIKE EVENTS (short, energy up high, not the low bed): {n}")
    if events:
        print(f"   first few:  " + "  ".join(f"{s:.1f}s({d*1000:.0f}ms)" for s, d in events[:8]))
        print(f"   rate: {n/dur*60:.0f}/min  — the dawn chorus is a good sign the mic and the")
        print(f"   morning are both working, even with no hummingbirds present.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--plot", type=Path)
    a = ap.parse_args()

    files = list(a.files)
    if a.dir:
        files += sorted(a.dir.glob("*.wav"))
    if not files:
        ap.error("give a file or --dir")

    for f in files:
        survey(f)
        if a.plot and len(files) == 1:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-i", str(f),
                 "-lavfi", "showspectrumpic=s=1600x700:legend=1:gain=3:color=intensity",
                 str(a.plot)], check=True)
            print(f"\n-> {a.plot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
