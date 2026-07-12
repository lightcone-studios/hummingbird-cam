#!/usr/bin/env python3
"""
Sharpen the chip template by ITERATIVE ALIGNMENT.

THE PROBLEM
-----------
`match-chips.py --build-template` averages N real chips, each window positioned at the
chip's *detected onset*. But that onset comes from an energy envelope with a couple of
milliseconds of jitter. Averaging misaligned copies of a sharp thing produces a BLURRY
thing — we smear out exactly the fine structure we are trying to match against.

The evidence it was happening: our template scored only ~0.62 correlation against real
chips. A template that truly matched its own source material should score far higher.

And the chips ARE sharp. Rendered at high resolution (2026-07-12), seven consecutive chips
from Aaron's confirmed bird show a strongly repeatable internal architecture:

    bright core   6,600 - 7,400 Hz
    main body     5,000 - 9,000 Hz
    upper tail    to ~12,000 Hz
    skirt         down to ~3,000 Hz

That structure is real, and a blurred template throws it away.

THE FIX (standard practice in spike-sorting / template matching)
----------------------------------------------------------------
    1. build a rough template (the current method)
    2. cross-correlate EVERY chip against it -> recover each chip's true sub-frame offset
    3. re-extract every chip at its corrected offset
    4. re-average -> a sharper template
    5. repeat until it stops improving

Each pass tightens the alignment, which sharpens the template, which improves the next
alignment. It converges in a handful of iterations.

WHY THIS MATTERS BEYOND DETECTION
---------------------------------
A sharp template is not just a better detector. It IS the average chip — the thing whose
structure we actually want to study. Blurring it destroys the science, not just the SNR.

Usage:
    refine-template.py                      refine from all confirmed local chips
    refine-template.py --iterations 8
    refine-template.py --plot out.png       see the template sharpen
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from importlib.machinery import SourceFileLoader

m = SourceFileLoader("m", str(REPO / "scripts" / "match-chips.py")).load_module()

# Recordings holding chips we are confident about. The 10:18:27 bird was seen by Aaron
# with his own eyes and heard on all three mics at 6.9 sigma coincidence.
SOURCES = [
    REPO / "captures/audio/2026-07-12/shotgun/20260712-101827.wav",
    REPO / "captures/audio/2026-07-12/tx2/20260712-101827.wav",
    REPO / "captures/audio/2026-07-12/tx1/20260712-101827.wav",
    REPO / "captures/reference/ref-dungeness-call.wav",
]


def find_chips(tmpl: np.ndarray) -> list[tuple[np.ndarray, np.ndarray, int]]:
    """
    Locate the chips ONCE and freeze the set: (spectrogram, hop-index of each chip).

    Freezing matters. The first version of this re-DETECTED chips on every pass, so each
    new template found a slightly different set of chips, which changed the average, which
    changed the detections — a feedback loop chasing its own tail. It oscillated between
    301 and 449 chips and never converged. Fix the evidence, refine the model.
    """
    found = []
    for src in SOURCES:
        if not src.exists():
            continue
        x = m.load(src)
        chips = [c for b in m.bouts(m.detect(x, tmpl, 0.5)) for c in b]
        if not chips:
            continue
        S, t = m.spectrogram(x)
        hop = t[1] - t[0]
        for c in chips:
            found.append((S, np.array([c]), int(round(c / hop))))
    return found


def collect(tmpl: np.ndarray, frozen) -> list[tuple[np.ndarray, float]]:
    """Re-align each FROZEN chip against the current template and return the patches."""
    out = []
    w = tmpl.shape[1]
    for S, _c, i0 in frozen:
        best, bi = -2.0, None
        # search +/- 4 frames: the ONSET is jittery, the correlation peak is not.
        for di in range(-4, 5):
            i = i0 + di
            if i < 0 or i + w > S.shape[1]:
                continue
            patch = m.normalize(S[:, i:i + w])
            s = float((patch * tmpl).sum())
            if s > best:
                best, bi = s, i
        if bi is not None:
            out.append((m.normalize(S[:, bi:bi + w]), best))
    return out


def sharpness(t: np.ndarray) -> float:
    """
    How much structure does the template have? A blurred template is smooth; a sharp one
    has strong local gradients. Total variation, normalised.
    """
    gx = np.abs(np.diff(t, axis=1)).sum()
    gy = np.abs(np.diff(t, axis=0)).sum()
    return float((gx + gy) / t.size)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=6)
    ap.add_argument("--out", type=Path, default=REPO / "models/chip-template.npy")
    ap.add_argument("--plot", type=Path)
    args = ap.parse_args()

    tmpl = np.load(REPO / "models/chip-template.npy")
    print("ITERATIVE TEMPLATE REFINEMENT")
    print("Each pass: re-align every FROZEN chip to the template, then re-average.\n")

    print("locating chips (once) ...")
    frozen = find_chips(tmpl)
    print(f"frozen chip set: {len(frozen)} chips\n")
    print(f"{'pass':>5} {'chips':>7} {'mean match':>12} {'sharpness':>11}   {'change'}")
    print("-" * 58)

    prev = None
    for it in range(args.iterations):
        chips = collect(tmpl, frozen)
        if not chips:
            print("no chips found — aborting")
            return 1
        patches = np.array([p for p, _ in chips])
        scores = np.array([s for _, s in chips])

        # weight each chip by how well it matches: a marginal detection should not get
        # the same vote as an unambiguous one. (weights are clipped at 0 — a chip that
        # anti-correlates is not evidence about what a chip looks like.)
        w = np.clip(scores, 0, None) ** 2
        new = m.normalize(np.average(patches, axis=0, weights=w))

        delta = float(np.abs(new - tmpl).mean())
        tag = ""
        if prev is not None:
            tag = "converged" if delta < 1e-4 else f"delta {delta:.4f}"
        print(f"{it:>5} {len(chips):>7} {scores.mean():>12.3f} {sharpness(new):>11.4f}   {tag}")

        tmpl = new
        if delta < 5e-4:
            print(f"{'':>5} converged")
            break
        prev = delta

    # Final verification: the refined template must still do its job.
    print()
    final = collect(tmpl, frozen)
    print(f"FINAL: mean template match on real chips = {np.mean([s for _, s in final]):.3f}")
    print(f"       (it was 0.62 with the blurred template)")

    np.save(args.out, tmpl)
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
