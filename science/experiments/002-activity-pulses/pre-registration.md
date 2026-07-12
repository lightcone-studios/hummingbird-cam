---
science:
  claim_id: H2-ACTIVITY-PULSES
  author: claude
  status: draft
---

# H2 — Hummingbird activity at this site is PULSED, not random

## The claim in one line

Chipping activity arrives in **recurring pulses on a characteristic period**, not as a random
(Poisson) trickle.

## Where this came from

**Aaron's prior, and it is a real one.** In April 2026 he rescued a hummingbird nest and recorded
the mother provisioning the nestlings. His record shows her returning **every 20–30 minutes**
through the day. That is an independent, timestamped observation made months before this rig
existed and before any of today's analysis — it is not a post-hoc rationalisation of our data.

**Aaron's hypothesis (his words, 2026-07-12):** that "somewhat similar patterns" govern how birds
move through and between flowers, plus "macro patterns that align with different parts of the day."

**And today's exploratory block agrees, unprompted.** The clean 15-min window (10:59:06–11:14:06)
was not a steady trickle — it was **48 bouts in two minutes (10:59–11:00), then near-silence for
eight minutes.** That is the shape of a pulse.

**The biology backs it.** Hummingbirds are documented **trapliners**: they fly a repeating circuit
of nectar sources, returning to each at an interval tuned to its nectar-renewal rate. Too early and
the flower is empty; too late and a competitor has drained it. Traplining predicts *periodicity*.

## Scope limiter — what this does NOT test

- It does NOT claim the period is 20–30 min. Aaron's April figure is a **prior, not a prediction**;
  provisioning nestlings and traplining flowers are different behaviours that may run on different
  clocks. The period is **estimated**, not assumed. Any period in the search band can PASS.
- It does NOT claim the pulses are the SAME bird returning. Multiple birds on independent schedules
  could produce periodicity; so could one bird on a circuit. Not distinguishable here.
- It does NOT test the diel / time-of-day ("macro") pattern. That is near-certainly real and already
  known to Aaron (birds at the porch 05:00–07:00), so it is not a risky claim and is not worth a seal.
  **Tracked separately as an observation, not a hypothesis.**
- It does NOT claim the pulses relate to feeding vs territorial behaviour.

## Why this is falsifiable — and the honest hazards

**The null is sharp and easy to lose to.** A Poisson process has **exponentially** distributed
inter-arrival times — no characteristic scale. A pulsed/periodic process has a **peaked** one. These
are different shapes and the data will happily tell us it is Poisson.

**Hazard 1 — BURSTY ≠ PERIODIC, and confusing them would be the easy mistake.** Activity can be
clumped (bursty) with the clumps arriving at *random* times. That is NOT this hypothesis. Bursty-but-
random still FAILS. The claim is specifically that the **intervals between pulses** carry a
characteristic period. The estimator below is built to separate these two, and the pre-condition
makes burstiness a *prerequisite for even running the test*, never evidence for it.

**Hazard 2 — the observer creates the pulse.** A human walking to the rig suppresses birds, then they
return: that manufactures a pulse with a period set by *Aaron's* behaviour, not the birds'. **Mitigation:
only segments with NO human activity at the rig are admissible** (see Method). The 2026-07-12 sessions
where Aaron approached the rig are excluded outright.

**Hazard 3 — detector duty-cycle artefacts.** Segment boundaries (5-min files) could impose a false
5-min period. **Mitigation: any periodogram peak within ±10% of 5 min, or of a harmonic of it, is
discarded as an artefact, not reported as a finding.**

**Hazard 4 — periodogram peaks are cheap.** Any noisy series will show *some* peak. Guarded by a
permutation null (below), not by an analytic p-value.

**Hazard 5 — too little data.** You cannot see a 25-min period in a 15-min recording. Guarded by the
stopping rule, which demands enough cycles to be meaningful.

## Method

**Data.** Continuous multi-mic recordings from the porch array (`scripts/record-loop.sh`), only from
windows with **no human at the rig**. Detector: `scripts/match-chips.py` @ `b1246ce` with
`models/chip-template.npy`. Bouts de-duplicated across mics with a 0.5 s window (as in H1).

**The event train.** Each de-duplicated bout is one event, timestamped at its first chip.

**Estimator (frozen — the estimator IS part of the hypothesis):**

1. **Pre-condition — is it even bursty?** Compute the **Fano factor** (variance/mean of bout counts in
   60 s bins). Poisson ⇒ Fano ≈ 1. Clumped ⇒ Fano > 1.
   **If Fano ≤ 1.5, there are no pulses to have a period, and the run is FAIL — not ambiguous.**
2. **Define pulses.** Cluster bouts into pulses: bouts separated by more than **180 s** start a new
   pulse. A pulse must contain **≥ 3 bouts** to count (a single bout is not a pulse).
3. **The test.** Lomb–Scargle periodogram of the binned event train (60 s bins), searched over periods
   **5–90 min**. (Lomb–Scargle because the series is unevenly sampled and gappy.)
4. **The null — permutation, not theory.** Generate 1000 surrogate trains by drawing the SAME number
   of events with inter-arrival times shuffled (destroys periodicity, preserves the interval
   distribution and thus the burstiness). The null peak-power distribution comes from these.
5. **Report** the highest periodogram peak in-band, its period, and its p-value against the
   permutation null.

## The single claim under test

> The Lomb–Scargle periodogram of the bout-event train has a peak in the 5–90 min band whose power
> exceeds the 99th percentile of a permutation null that preserves burstiness but destroys periodicity.

## Pre-set decision thresholds (locked BEFORE any data)

- **PASS if:** peak power > **99th percentile** of the permutation null (p < 0.01), **AND** the peak
  period is **not** within ±10% of 5 min or its harmonics (segment-boundary artefact), **AND** the
  pre-condition (Fano > 1.5) held.
- **FAIL if:** peak power < 95th percentile of the null (p > 0.05) — activity is consistent with a
  random (possibly bursty) process with no characteristic period. **OR** Fano ≤ 1.5.
- **AMBIGUOUS if:** 0.01 ≤ p ≤ 0.05, **or** fewer than **8 pulses** observed (too few cycles to speak).
- **VOID if:** any admitted segment turns out to contain human activity at the rig.

## Stopping rule

**Data:** dawn sessions, **05:00–07:30 PDT** (the window in which Aaron reports birds are at the porch),
recorded with no human at the rig.

**Collect until ≥ 8 pulses are observed across ≥ 3 separate days,** to a maximum of **7 days**. Three
days minimum so that a single anomalous morning cannot carry the result; 8 pulses because you cannot
claim a period from fewer cycles than that.

If 7 days pass with < 8 pulses → **AMBIGUOUS (underpowered)**. Not a FAIL — a bird that does not show
up is not evidence against periodicity. We would re-scope, not re-analyse.

**No peeking-and-stopping.** The analysis runs ONCE, after the stopping rule is met. Interim looks at
the raw audio for other purposes (H1, instrument health) are permitted, but **the H2 estimator is not
run until collection is complete.**

## Parallel independent tracking (the reason this is sealed *now*)

Aaron is tracking this same question **independently, by his own method**, and we compare at a date
to be set. **Both methods must therefore be committed in advance** — otherwise, on comparison, we will
each unconsciously drift toward the other and mistake convergence for corroboration. This document is
my half of that bargain, sealed before either of us has looked.

Aaron's method is his own to declare. A disagreement between us will be **more informative than an
agreement**, and neither of us should soften it.

## Honesty pre-registration (the locked values)

Changing any value below after seeing a result **VOIDS the run**:

- **event:** one de-duplicated bout (0.5 s cross-mic window), timestamped at its first chip
- **detector:** `match-chips.py` @ `b1246ce`, `models/chip-template.npy`, THRESHOLD 0.60,
  BOUT_MIN_CHIPS 4, BOUT_IV_MIN 0.15, BOUT_IV_MAX 0.80, BOUT_MAX_CV 0.35
- **pre-condition:** Fano factor (60 s bins) > 1.5, else FAIL
- **pulse definition:** gap > 180 s starts a new pulse; a pulse needs ≥ 3 bouts
- **estimator:** Lomb–Scargle on 60 s-binned event train, period band 5–90 min
- **null:** 1000 permutations, inter-arrival times shuffled (preserves burstiness, kills periodicity)
- **thresholds:** PASS p < 0.01 · FAIL p > 0.05 or Fano ≤ 1.5 · AMBIGUOUS between, or < 8 pulses
- **artefact rule:** peaks within ±10% of 5 min or its harmonics are discarded
- **admissibility:** no human at the rig; dawn window 05:00–07:30
- **stopping:** ≥ 8 pulses across ≥ 3 days, max 7 days
- **reviewer:** must not be `claude` (G4)

## Results log (append-only — the water only drops once)

<empty until data lands>
