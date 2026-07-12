---
science:
  claim_id: H1-CHIP-INTERVAL-BIMODALITY
  author: claude
  status: draft
---

# H1 — Chip-bout intervals at this feeder are bimodal, not unimodal

## Where this came from (and why that matters)

On 2026-07-12 we recorded a deliberately **exploratory** 15-minute block (10:59:06–11:14:06 PDT,
three mics) with no hypothesis in mind — at Aaron's explicit insistence that we "record without
priors." It yielded **58 chipping bouts / 464 chips**. Their mean chip intervals showed two
density peaks — **0.234 s** and **0.445 s** — separated by an empty gap at 0.375–0.400 s.

**That block generated this hypothesis and therefore cannot test it.** Fitting a bimodality test
to the same numbers that suggested bimodality is circular and would produce a meaningless result.
This pre-registration exists to bind us to a test on **data we have not seen.**

## Scope limiter — what this does NOT test

This claim is about the **shape of a distribution**, and nothing else. It explicitly does NOT claim:

- that the two modes correspond to **individual birds** (that is the eventual goal, not this test);
- that they correspond to **sex** — although the published means (male 0.32 s, female 0.43 s;
  Glassman, Domer & Dudley) are suggestive, and although our fast mode is *faster* than their male
  mean, this run makes no sex claim whatsoever;
- that they correspond to **behavioural context** (the same paper found territorial-announcement
  chipping is faster than chasing — a fully sufficient alternative explanation for two modes from
  ONE bird);
- anything about **how many birds** are present.

A PASS here means only: *the intervals do not come from a single distribution.* Every interesting
interpretation of that fact remains untested.

## Why this is falsifiable — and the honest hazards

**Hazard 1 — the detector could manufacture the slow mode.** If the matched filter misses every
other chip in a fast bout, the measured interval **doubles**: 0.234 × 2 = 0.468 ≈ the observed slow
peak of 0.445. This would fabricate a second population out of nothing but missed detections, and it
would land exactly where a female's rate is expected. *This was tested on the exploratory data*: the
correlation-score midpoints inside slow bouts show **no hidden chips** (excess −0.026, i.e. no bump
where a missed chip would be). The artefact hypothesis was rejected there. **It will be re-run as a
mandatory pre-condition on the confirmatory data — if hidden chips appear, this run is VOID, not a
PASS.**

**Hazard 2 — the bout detector's own parameters could impose structure.** `BOUT_IV_MIN = 0.15 s`,
`BOUT_IV_MAX = 0.80 s`, `BOUT_MAX_CV = 0.35`. These are frozen (below) and were set on 2026-07-12
*before* the exploratory block was recorded, for reasons unrelated to interval structure (they were
set to reject rain and Aaron's footsteps). They are not tuned to this question.

**Hazard 3 — the same bird, chipping at two rates in two contexts.** Fully plausible and NOT
excluded by a PASS. See scope limiter.

**Hazard 4 — small N.** Guarded by the stopping rule.

## Method

**Rig (frozen).** Porch array, Shiro. Three mics, all recorded simultaneously at 48 kHz/16-bit mono:
- `shotgun` — Sennheiser shotgun → M-Audio M-Track Duo IN 1 (+48 V phantom) → USB
- `tx1`, `tx2` — Rode Wireless GO omni lavs, each at the focus of an umbrella reflector, →
  Wireless GO RX (**split mode**) → USB

**Detector (frozen).** `scripts/match-chips.py` at commit `b1246ce`, using `models/chip-template.npy`
(the iteratively-refined local template, built from confirmed local chips + the XC1077841 reference).
Spectrogram cross-correlation, `THRESHOLD = 0.60`; a bout is ≥ 4 detections spaced 0.15–0.80 s with
coefficient of variation ≤ 0.35.

**Estimator (frozen — the estimator IS part of the hypothesis).**
1. Take every bout in the confirmatory window, from all three mics.
2. **Deduplicate across mics**: bouts whose start times fall within 0.5 s of one another are the SAME
   acoustic event heard by multiple microphones and count **once** (keep the one with the most chips).
   Not doing this would triple-count every bird and fake the sample size.
3. The unit of analysis is one bout's **mean chip interval** (onset-to-onset, as in Glassman et al.).
4. Fit a 1-component and a 2-component Gaussian mixture (`sklearn.mixture.GaussianMixture`,
   `random_state=0`, `n_init=10`) to those means.
5. Compare by **BIC**. `ΔBIC = BIC(1) − BIC(2)`. Positive ΔBIC favours two components.

## The single claim under test

> The distribution of bout mean chip intervals is better described by **two** Gaussian components
> than by **one**, with the two component means separated by more than 0.10 s.

## Pre-set decision thresholds (locked BEFORE any data)

- **PASS if:** `ΔBIC > 10` **AND** `|μ₂ − μ₁| > 0.10 s`
- **FAIL if:** `ΔBIC < 2`
- **AMBIGUOUS if:** `2 ≤ ΔBIC ≤ 10`, **or** `|μ₂ − μ₁| ≤ 0.10 s`, **or** N < 30 bouts (underpowered)
- **VOID if:** the missed-chip pre-condition fails — i.e. median correlation-score excess at slow-bout
  midpoints exceeds the fast-bout control excess by more than **+0.08**. (The slow mode would then be
  a detector artefact, and the run proves nothing about birds.)

## Stopping rule

**Confirmatory data = the "hidden-window" recording** begun automatically at **11:14:06 PDT on
2026-07-12** (Aaron behind a blind, no human at the rig), 60-minute cap, five-minute segments, all
three mics. **This audio existed before this pre-registration was written, but has NOT been analysed,
listened to, or inspected in any way by author or reviewer.** No detector has been run on it.

Collection ends when that recording's 60-minute cap expires. **No extension, no second look, no
adding a later session if N falls short** — if N < 30 the result is AMBIGUOUS and we re-run the whole
protocol on a fresh session. One shot.

## Honesty pre-registration (the locked values)

Changing any value below after seeing a result **VOIDS the run**:

- **estimator:** GaussianMixture 1-comp vs 2-comp on de-duplicated bout mean chip intervals; ΔBIC
- **detector:** `match-chips.py` @ `b1246ce`, `models/chip-template.npy`, THRESHOLD 0.60,
  BOUT_MIN_CHIPS 4, BOUT_IV_MIN 0.15, BOUT_IV_MAX 0.80, BOUT_MAX_CV 0.35
- **dedup window:** 0.5 s across mics
- **thresholds:** PASS ΔBIC > 10 and |Δμ| > 0.10 s · FAIL ΔBIC < 2 · AMBIGUOUS otherwise or N < 30
- **VOID condition:** slow-bout midpoint score excess > fast-bout control excess by > +0.08
- **N / sessions:** one session — the 60-min hidden window begun 2026-07-12 11:14:06 PDT
- **reviewer:** must not be `claude` (G4: you don't grade your own homework)

## Results log (append-only — the water only drops once)

<empty until data lands>
