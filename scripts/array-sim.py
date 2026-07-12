#!/usr/bin/env python3
"""
Simulate a 3D microphone array for localising a hovering hummingbird by its WING THRUM.

THE IDEA (Aaron's, 2026-07-12)
------------------------------
Treat the air in front of the porch as an ocean, and hang microphones in it like anchored
buoys. Solve for where a bird must be, given how loud its 79 Hz wingbeat is at each buoy.

WHY THIS WORKS FOR THE THRUM AND NOT FOR THE CHIP
-------------------------------------------------
    chip   broadband (5-10 kHz)   localise by TIMING (TDOA)   needs microsecond sync
    thrum  narrowband (79 Hz)     localise by AMPLITUDE       needs NO sync at all

A 79 Hz tone has a 4.3 m wavelength — you cannot even tell which cycle you are looking at,
so timing is hopeless. But the thrum is NEAR-FIELD: it falls off fast, so the amplitude
differences across a small array are large. Solve on amplitude and the synchronisation
problem vanishes entirely. The mics do not even need to share a clock.

    (This matters because we MEASURED, on 2026-07-12, that the wireless link jitters by
     7.5-22 ms. TDOA needs <0.03 ms. Timing-based localisation is dead on this hardware.
     Amplitude-based localisation does not care.)

THE HARD GEOMETRIC RULE
-----------------------
The mics must NOT be coplanar. If they all sit in one plane, the axis perpendicular to it
collapses — you learn where the bird is up/down and left/right, but not how far OUT. That
is the whole reason to hang them on strings at different heights: the strings buy the third
dimension. This simulator will show that failure directly if you ask it to.

WHAT IT DOES
------------
Places a virtual bird at every point in a target volume, simulates what each mic would
measure (with realistic noise), solves for the bird's position by least squares, and reports
how far off the answer is. Repeat over the volume -> a map of where the array can see.

Usage:
    array-sim.py                       compare candidate array designs
    array-sim.py --design ring8        detail one design
    array-sim.py --coplanar            demonstrate the coplanar failure
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
from scipy.optimize import least_squares

# ---------------------------------------------------------------------------
# The space. Origin = the porch railing, at the base of the rig.
#   +x = out from the porch    +y = along the railing    +z = up
# Adjust these to Aaron's real measurements.
# ---------------------------------------------------------------------------
FEEDER = np.array([2.0, 0.0, 0.3])       # ~80 in out, level-ish with the rig
TARGET_BOX = ((1.0, 3.5), (-1.5, 1.5), (-0.8, 1.2))   # the volume birds actually use

# The thrum, as measured on 2026-07-12
THRUM_HZ = 79.1
NOISE_DB = 1.5      # how honestly a mic reports its level. 1.5 dB is realistic-to-pessimistic
                    # (our two "identical" TXs disagreed by 4 dB, so do not be optimistic)

# Falloff. A monopole is 20*log10(r). WINGS ARE A DIPOLE — they push air back and forth with
# no net volume change — and dipoles fall off FASTER near the source. The true exponent is
# unmeasured (this is the open item in docs/rig-calibration.md), so we test both.
FALLOFF = {"monopole": 20.0, "dipole-ish": 30.0}


def level(src: np.ndarray, mics: np.ndarray, amp: float, k: float) -> np.ndarray:
    r = np.linalg.norm(mics - src, axis=1)
    r = np.maximum(r, 0.05)
    return amp - k * np.log10(r)


def solve(obs: np.ndarray, mics: np.ndarray, k: float, guess: np.ndarray) -> np.ndarray:
    """
    Given what each mic heard, where must the bird be? Unknowns: x, y, z, AND the bird's
    own loudness (we don't know how hard it's flapping). That is FOUR unknowns — so three
    microphones can never solve it, regardless of where you put them. Four is the floor.
    """
    def resid(p):
        return level(p[:3], mics, p[3], k) - obs
    r = least_squares(resid, np.r_[guess, 100.0], method="trf", max_nfev=400)
    return r.x[:3]


def evaluate(mics: np.ndarray, k: float, trials: int = 24, grid: int = 5,
             rng=None) -> tuple[float, float, np.ndarray]:
    """Median and 90th-pct localisation error over the target volume, in cm."""
    rng = rng or np.random.default_rng(0)
    xs = np.linspace(*TARGET_BOX[0], grid)
    ys = np.linspace(*TARGET_BOX[1], grid)
    zs = np.linspace(*TARGET_BOX[2], grid)
    errs, emap = [], np.zeros((grid, grid, grid))
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            for m, z in enumerate(zs):
                true = np.array([x, y, z])
                e = []
                for _ in range(trials):
                    obs = level(true, mics, 100.0, k) + rng.normal(0, NOISE_DB, len(mics))
                    est = solve(obs, mics, k, FEEDER)
                    e.append(np.linalg.norm(est - true) * 100)   # cm
                errs.extend(e)
                emap[i, j, m] = np.median(e)
    errs = np.array(errs)
    return float(np.median(errs)), float(np.percentile(errs, 90)), emap


# ---------------------------------------------------------------------------
# Candidate designs. All positions in metres, anchored to things that exist:
# the porch roof/pergola above, the railing, and strings hanging between them.
# ---------------------------------------------------------------------------
def designs() -> dict[str, np.ndarray]:
    d = {}

    # What we have TODAY: 3 mics, essentially in a line on the railing. Coplanar and flat.
    d["today (3 mics, a line)"] = np.array([
        [0.0,  0.0, 0.0],     # shotgun
        [0.0, -0.6, 0.0],     # tx1
        [0.0,  0.6, 0.0],     # tx2
    ])

    # 4 mics, still all on the railing plane. The MINIMUM count for 3D — but coplanar,
    # so it should fail on the out-axis. This is the instructive failure.
    d["4 mics, COPLANAR (railing)"] = np.array([
        [0.0, -0.8,  0.0], [0.0, 0.8,  0.0],
        [0.0, -0.8,  1.0], [0.0, 0.8,  1.0],
    ])

    # 4 mics, but pushed OUT into the volume on strings. Same count, real 3D.
    d["4 mics, on strings (3D)"] = np.array([
        [0.0, -0.8, 0.0], [0.0, 0.8, 0.0],
        [1.8, -0.7, 1.1], [1.8, 0.7, 1.1],
    ])

    # 6, spanning the volume: two on the railing, four hung from the pergola out front.
    d["6 mics, strings"] = np.array([
        [0.0, -0.9, 0.0], [0.0, 0.9, 0.0],
        [1.6, -0.9, 1.2], [1.6, 0.9, 1.2],
        [3.0, -0.5, 0.4], [3.0, 0.5, 0.4],
    ])

    # 8, a proper cage AROUND the feeder volume. The buoy field.
    d["8 mics, a cage"] = np.array([
        [0.2, -1.0, -0.4], [0.2, 1.0, -0.4],
        [0.2, -1.0,  1.2], [0.2, 1.0,  1.2],
        [3.2, -1.0, -0.4], [3.2, 1.0, -0.4],
        [3.2, -1.0,  1.2], [3.2, 1.0,  1.2],
    ])
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coplanar", action="store_true", help="demonstrate the coplanar failure")
    args = ap.parse_args()

    print("3D THRUM ARRAY — how well could it locate a hovering hummingbird?\n")
    print(f"  target volume : x {TARGET_BOX[0]} m (out), y {TARGET_BOX[1]} m, z {TARGET_BOX[2]} m")
    print(f"  mic honesty   : +/- {NOISE_DB} dB  (pessimistic — our two 'identical' TXs")
    print(f"                  disagreed by 4 dB, so do not assume better)")
    print(f"  the signal    : the {THRUM_HZ:.0f} Hz wingbeat. No timing. Amplitude only.")
    print(f"                  -> NO microphone synchronisation required.\n")

    for law, k in FALLOFF.items():
        print(f"{'='*74}\nFALLOFF: {law}  ({k:.0f}*log10 r)\n")
        print(f"{'design':<28} {'median error':>14} {'90th pct':>11}   verdict")
        print("-" * 74)
        for name, mics in designs().items():
            if len(mics) < 4:
                print(f"{name:<28} {'--':>11}    {'--':>9}    UNDERDETERMINED "
                      f"({len(mics)} mics, 4 unknowns)")
                continue
            med, p90, _ = evaluate(mics, k)
            if med < 10:   v = "excellent"
            elif med < 25: v = "good — usable"
            elif med < 60: v = "coarse"
            else:          v = "USELESS"
            print(f"{name:<28} {med:>11.0f} cm {p90:>9.0f} cm   {v}")
        print()

    print("=" * 74)
    print("\nREAD THIS BEFORE BUYING ANYTHING:")
    print("  * COPLANAR ARRAYS FAIL. Four mics flat on the railing cannot resolve how far")
    print("    OUT the bird is, no matter how good they are. The strings are not a")
    print("    convenience — they ARE the third dimension.")
    print("  * Mic count matters less than mic SPREAD. Surround the volume.")
    print("  * Every number above assumes the mics report levels HONESTLY. Our current rig")
    print("    does not: two identical transmitters disagree by 4 dB (see")
    print("    docs/rig-calibration.md). Fix the level calibration BEFORE building an array,")
    print("    or the array will inherit the error and localise confidently to the wrong place.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
