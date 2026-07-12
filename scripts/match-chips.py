#!/usr/bin/env python3
"""
Spectrogram cross-correlation detector for Anna's Hummingbird chips.

WHY BUILD A SECOND DETECTOR
---------------------------
`detect-chips.py` asks "is there ENERGY in the chip band?". That works on a loud, close
bird and fails on a quiet one. Measured on 2026-07-12, against ground truth (95 real chips
mixed into real porch noise):

    bird at the feeder    78 of 95 found
    bird 12 dB further    27 of 95 found      <- most of them lost
    bird 20 dB further     0 of 95 found      <- totally deaf

An energy threshold cannot do better, because at those levels the chip's energy simply is
not above the local noise. But energy is not the only thing we know about a chip — we know
its SHAPE. A chip is a ~38 ms downsweep with a bright core around 6-10 kHz, and rain, wind
and traffic look nothing like that.

So instead of thresholding energy, we ask a different question:

    "how much does this moment look like a chip?"

We build a template from the 95 REAL chips in the reference recording, then slide it across
the spectrogram and compute a normalised correlation. This is standard practice in
bioacoustics (spectrogram cross-correlation, SPCC) and it is the right tool precisely
because it exploits structure that noise does not have.

Correlation is done on the SPECTROGRAM, not the waveform, on purpose: two chips from the
same bird are not phase-aligned, so a waveform matched filter would cancel itself out. The
spectrogram throws phase away and keeps the shape, which is the part that repeats.

The template is normalised per-frame before correlating, so the score measures SHAPE, not
loudness — a faint chip and a loud chip score the same. That is exactly the property the
energy detector lacked.

USAGE
    match-chips.py FILE.wav                        detect chips
    match-chips.py FILE.wav --threshold 0.4        looser / tighter
    match-chips.py --build-template                rebuild template from the reference
    match-chips.py --benchmark                     score BOTH detectors against ground truth

Requires the repo venv: .venv/bin/python scripts/match-chips.py ...
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.signal import stft, butter, sosfiltfilt

REPO = Path(__file__).resolve().parent.parent
REFERENCE = REPO / "captures" / "reference" / "ref-dungeness-call.wav"
TEMPLATE = REPO / "models" / "chip-template.npy"

SR = 48000
NPERSEG = 256           # ~5.3 ms frames — a 38 ms chip spans ~7 frames of real structure
NOVERLAP = 192          # 75% overlap -> ~1.3 ms hop, fine enough to time a chip onset
F_LOW, F_HIGH = 3000, 13000   # the band the chip's SHAPE lives in (wider than the 8-10k core:
                              # the downsweep and its skirts are part of what we're matching)
TEMPLATE_MS = 40        # a chip is ~38 ms

# Calibrated by --benchmark against ground truth in real porch noise. At 0.6 the matched
# filter finds 94/95 chips at feeder distance and 87/95 at -12 dB (the energy detector gets
# 27), for only 4-8 false alarms per minute. Lower and the false alarms explode (70/min at
# 0.4); higher and distant birds start dropping out (47/95 at -18 dB by 0.7).
THRESHOLD = 0.60
MIN_SEP = 0.05          # s, same as the paper: two peaks closer than this are one chip

# --- bout detection: the thing that finally separates a bird from the weather ------------
# The matched filter buys ~18 dB of hearing but costs a few false alarms a minute. Those
# are killed not by a better filter but by RHYTHM, the one property noise cannot fake:
#
#   a real chipping bout is REGULAR   — reference: interval 0.494 s, SD 0.085
#   rain is a Poisson process         — measured this morning: SD ~= mean
#
# So a lone detection is worth nothing, and a RUN of detections at plausible chip spacing
# is worth a lot. The Berkeley paper leaned on the same fact: they discarded any recording
# with fewer than ten chip notes, because sparse detections give "inconsistent and outlying
# intervals" — i.e. they are not a bout, they are noise.
BOUT_MIN_CHIPS = 4      # a run shorter than this proves nothing
BOUT_IV_MIN = 0.15      # s \ plausible chip spacing, generous around the paper's
BOUT_IV_MAX = 0.80      # s / 0.32 (male) - 0.43 (female)

# ...but "spaced like a chip" is not enough, and this cost us a false bird on day one.
# A HUMAN WALKING has a cadence of roughly 0.4-0.5 s per step — squarely inside the window
# above. On 2026-07-12 the detector called Aaron's footsteps a hummingbird.
#
# What actually separates them is REGULARITY. A chipping bird is a metronome; a walker is
# not. Coefficient of variation (SD / mean) of the intervals within a bout:
#
#     real bird, clean            CV 0.15, 0.20
#     real bird, -18 dB in noise  CV 0.07, 0.09, 0.16, 0.20
#     Aaron's footsteps           CV 0.60          <- 3x more ragged than any real bout
#
# Threshold sits above every real bout observed and far below the footsteps.
BOUT_MAX_CV = 0.35

PAPER_MEANS = {"male": 0.32, "female": 0.43, "unknown": 0.38}   # Glassman et al., Table 5


def load(path: Path) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(out, dtype="<f4").copy()


def spectrogram(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Log-magnitude spectrogram restricted to the chip's frequency band."""
    f, t, Z = stft(x, fs=SR, nperseg=NPERSEG, noverlap=NOVERLAP, boundary=None)
    keep = (f >= F_LOW) & (f <= F_HIGH)
    S = 20 * np.log10(np.abs(Z[keep]) + 1e-10)
    return S, t


def normalize(patch: np.ndarray) -> np.ndarray:
    """
    Zero-mean, unit-norm. This is what makes the score about SHAPE and not LOUDNESS:
    after this, a faint chip and a loud chip are the same pattern, and only the pattern
    is compared.
    """
    p = patch - patch.mean()
    n = np.linalg.norm(p)
    return p / n if n > 1e-9 else p


def build_template() -> np.ndarray:
    """Average the 95 known chips in the reference into one canonical chip."""
    sys.path.insert(0, str(REPO / "scripts"))
    from importlib.machinery import SourceFileLoader
    d = SourceFileLoader("d", str(REPO / "scripts" / "detect-chips.py")).load_module()

    x = load(REFERENCE)
    chips, _ = d.detect(x, SR)
    print(f"building template from {len(chips)} real chips in {REFERENCE.name}")

    S, t = spectrogram(x)
    hop = t[1] - t[0]
    width = max(3, int(round((TEMPLATE_MS / 1000) / hop)))

    stack = []
    for c in chips:
        # centre the window on the chip's energy peak, not its ragged onset
        i = int(round(c.start / hop))
        lo, hi = max(0, i - 1), min(S.shape[1], i + width)
        if hi - lo < width:
            continue
        patch = S[:, lo:lo + width]
        if patch.shape[1] == width:
            stack.append(normalize(patch))

    if not stack:
        raise SystemExit("no usable chips found — cannot build a template")

    tmpl = normalize(np.mean(stack, axis=0))
    np.save(TEMPLATE, tmpl)
    print(f"template: {tmpl.shape[0]} freq bins x {tmpl.shape[1]} frames "
          f"({width*hop*1000:.0f} ms), from {len(stack)} chips")
    print(f"-> {TEMPLATE}")
    return tmpl


def correlate(x: np.ndarray, tmpl: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Slide the template across the spectrogram. Returns (score per frame, frame times)."""
    S, t = spectrogram(x)
    w = tmpl.shape[1]
    if S.shape[1] < w:
        return np.zeros(0), np.zeros(0)

    # Sliding windows over time, each normalised the same way the template was.
    win = np.lib.stride_tricks.sliding_window_view(S, w, axis=1)   # (freq, nwin, w)
    win = win.transpose(1, 0, 2)                                   # (nwin, freq, w)

    m = win.mean(axis=(1, 2), keepdims=True)
    z = win - m
    norms = np.sqrt((z ** 2).sum(axis=(1, 2))) + 1e-9
    scores = (z * tmpl[None]).sum(axis=(1, 2)) / norms
    return scores, t[: len(scores)]


def detect(x: np.ndarray, tmpl: np.ndarray, threshold: float = THRESHOLD) -> list[float]:
    scores, t = correlate(x, tmpl)
    if len(scores) == 0:
        return []
    hits = np.flatnonzero(scores >= threshold)
    if len(hits) == 0:
        return []

    # peak-pick: within a MIN_SEP cluster keep only the best-scoring frame
    onsets, cluster = [], [hits[0]]
    for i in hits[1:]:
        if t[i] - t[cluster[-1]] <= MIN_SEP:
            cluster.append(i)
        else:
            onsets.append(float(t[cluster[int(np.argmax(scores[cluster]))]]))
            cluster = [i]
    onsets.append(float(t[cluster[int(np.argmax(scores[cluster]))]]))
    return onsets


def bouts(onsets: list[float]) -> list[list[float]]:
    """
    Group detections into RHYTHMIC RUNS. A bout is >= BOUT_MIN_CHIPS detections whose
    consecutive gaps all fall in the plausible chip-interval window. Scattered noise
    does not form these; a chipping hummingbird does nothing else.
    """
    def keep(run: list[float]) -> bool:
        """Long enough AND regular enough. Regularity is what rules out footsteps."""
        if len(run) < BOUT_MIN_CHIPS:
            return False
        iv = np.diff(run)
        return bool(iv.mean() > 0 and iv.std() / iv.mean() <= BOUT_MAX_CV)

    if len(onsets) < BOUT_MIN_CHIPS:
        return []
    out, run = [], [onsets[0]]
    for t in onsets[1:]:
        if BOUT_IV_MIN <= t - run[-1] <= BOUT_IV_MAX:
            run.append(t)
        else:
            if keep(run):
                out.append(run)
            run = [t]
    if keep(run):
        out.append(run)
    return out


def truth_times() -> list[float]:
    """The 95 chip onsets in the reference — our ground truth."""
    sys.path.insert(0, str(REPO / "scripts"))
    from importlib.machinery import SourceFileLoader
    d = SourceFileLoader("d", str(REPO / "scripts" / "detect-chips.py")).load_module()
    chips, _ = d.detect(load(REFERENCE), SR)
    return [c.start for c in chips]


def score(found: list[float], truth: list[float], tol: float = 0.05) -> tuple[int, int]:
    """(hits, false alarms) — a detection counts if it lands within tol of a real chip."""
    truth = sorted(truth)
    used, hits, fa = set(), 0, 0
    for f in found:
        near = [i for i, tt in enumerate(truth) if abs(tt - f) <= tol and i not in used]
        if near:
            used.add(near[0]); hits += 1
        else:
            fa += 1
    return hits, fa


def benchmark() -> None:
    """
    The honest test: build a bird we KNOW the answer for, bury it in real porch noise
    at decreasing volume, and ask both detectors to find it.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    from importlib.machinery import SourceFileLoader
    d = SourceFileLoader("d", str(REPO / "scripts" / "detect-chips.py")).load_module()

    tmpl = np.load(TEMPLATE) if TEMPLATE.exists() else build_template()
    truth = truth_times()
    noise_seg = sorted((REPO / "captures" / "audio").glob("*/2*.wav"))
    if not noise_seg:
        raise SystemExit("no porch audio to use as noise")
    noise_file = noise_seg[len(noise_seg) // 2]

    print(f"\nGROUND TRUTH: {len(truth)} real Anna's chips (XC1077841)")
    print(f"NOISE:        real porch audio, {noise_file.name}")
    print(f"\nEach row: the same bird, quieter — i.e. further away.\n")
    print(f"{'bird level':<26} {'ENERGY detector':<22} {'MATCHED FILTER':<22}")
    print(f"{'':<26} {'found  (false alarms)':<22} {'found  (false alarms)':<22}")
    print("-" * 70)

    for att in (0, -6, -12, -18, -24, -30):
        mix = REPO / f".bench{att}.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(REFERENCE), "-i", str(noise_file),
             "-filter_complex",
             f"[0:a]volume={att}dB[c];[1:a]atrim=0:55,asetpts=PTS-STARTPTS[n];"
             f"[c][n]amix=inputs=2:duration=first:normalize=0[o]",
             "-map", "[o]", "-ar", str(SR), "-ac", "1", str(mix)],
            check=True,
        )
        x = load(mix)

        e_chips, _ = d.detect(x, SR)
        e_hits, e_fa = score([c.start for c in e_chips], truth)

        m_hits, m_fa = score(detect(x, tmpl), truth)

        label = f"{att:+3d} dB" + ("  (at feeder)" if att == 0 else "  (distant)" if att <= -12 else "")
        print(f"{label:<26} {f'{e_hits:3d}/{len(truth)}   ({e_fa})':<22} "
              f"{f'{m_hits:3d}/{len(truth)}   ({m_fa})':<22}")
        mix.unlink(missing_ok=True)

    print("\n'found' = detections landing within 50 ms of a real chip.")
    print("'false alarms' = detections that match no real chip (mostly rain).")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--build-template", action="store_true")
    ap.add_argument("--benchmark", action="store_true")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    args = ap.parse_args()

    if args.build_template:
        build_template()
        return 0
    if args.benchmark:
        benchmark()
        return 0
    if not args.files:
        ap.error("give an audio file, or --benchmark / --build-template")

    tmpl = np.load(TEMPLATE) if TEMPLATE.exists() else build_template()
    for f in args.files:
        onsets = detect(load(f), tmpl, args.threshold)
        bs = bouts(onsets)

        print(f"\n{f.name}")
        print(f"  {len(onsets)} detection(s) at correlation >= {args.threshold}")

        if not bs:
            print(f"  NO BOUTS. A lone detection is not a bird — a bird chips in a rhythm.")
            print(f"  (need >= {BOUT_MIN_CHIPS} in a row spaced {BOUT_IV_MIN}-{BOUT_IV_MAX}s)")
            continue

        print(f"  *** {len(bs)} CHIPPING BOUT(S) — this is what a hummingbird sounds like ***")
        for b in bs:
            iv = np.diff(b)
            mean = float(iv.mean())
            near = min(PAPER_MEANS, key=lambda k: abs(mean - PAPER_MEANS[k]))
            print(f"\n    {b[0]:.2f}s - {b[-1]:.2f}s   {len(b)} chips over {b[-1]-b[0]:.1f}s")
            print(f"    chip interval: mean {mean:.3f}s  SD {iv.std():.3f}")
            print(f"    closest published mean: {near.upper()} ({PAPER_MEANS[near]:.2f}s) "
                  f"-- DESCRIPTIVE ONLY, one bout cannot sex a bird")
    return 0


if __name__ == "__main__":
    sys.exit(main())
