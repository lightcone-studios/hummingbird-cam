---
science:
  claim_id: H1-DISH-GAIN
  author: aaron
  status: draft
---

# H1 — The parabolic umbrella dish measurably improves capture of hummingbird chip calls

> **DRAFT — not sealed.** This is a candidate hypothesis drafted from the rig-design
> conversation. Read it, edit the thresholds to match your intent, then seal it as your
> declared intent: `science.py seal .../pre-registration.md --type prereg --author aaron`.
> Nothing below is binding until it is sealed.

Instrument-first. Before making any claim about what hummingbirds are *saying*, prove the
tool actually hears them better. If the dish doesn't beat a bare mic, every downstream
biological result is built on sand.

## Scope limiter — what this does NOT test
- **No biological claim.** Nothing here about individual identity, vocal learning, or
  communication. This tests the *microphone rig*, full stop.
- Not the wing hum (~40–50 Hz) — the dish is physically too small to focus it. Chip calls
  and song only.
- Not localization / TDOA. That is a separate, later pre-registration.

## Why this is falsifiable
The honesty hazard is picking the dish's best moment and the bare mic's worst. Guard rails:
both capsules record the **same calls at the same instant** through the one receiver (common
clock), mounted at the **same height**; calls are selected for isolation *before* the SNR is
computed, by a rule that can't see the channel identity.

## Method (precise enough to reproduce)
- **Dish channel:** GO3 capsule at the umbrella's focus (~11 in from center, facing the
  fabric, on a slider trimmed by the key-jingle sweep), furry windjammer.
- **Bare-reference channel:** a second GO3 capsule at the *same height*, ~30 cm to the side,
  no dish, same windjammer.
- **Chain:** both transmitters → one GO3 receiver → one recorder (common clock); 32-bit
  float onboard as backup; a hand-clap at session start to lock the inter-channel offset.
- **Chip call:** the sharp broadband call (energy mostly 2–10 kHz). A call is *eligible* only
  if it is isolated — no overlapping bird, traffic, or wind transient in the 200 ms before or
  the call itself — judged on a channel-blinded mixdown.
- **Estimator (locked):** for each eligible call, band-limited SNR over **2–10 kHz** =
  10·log10( in-band energy of the call window / in-band energy of the 200 ms immediately
  preceding it ). **Dish gain** for that call = SNR(dish) − SNR(bare). The reported statistic
  is the **median dish gain across the session's eligible calls.**

## The single claim under test
> The median dish gain (2–10 kHz band-limited SNR, dish minus bare reference) across a
> session's eligible chip calls is **≥ +6 dB**.

## Pre-set decision thresholds (locked BEFORE any data)
- **PASS if:** median dish gain ≥ **+6 dB**
- **FAIL if:** median dish gain < **+3 dB**
- **AMBIGUOUS if:** median dish gain is **+3 to +6 dB** (rig helps, but under the target — retune focus/aim and re-run as a new pre-registration)

## Stopping rule
The first porch session that yields **≥ 20 eligible chip calls captured on both channels**.
Data is **not pooled across sessions** for this calibration. A session ending with < 20
eligible calls is discarded, not merged. N = 20, single session, decided in advance.

## Honesty pre-registration (the locked values)
Changing any value below after seeing a result **VOIDS the run**:
- estimator: median of per-call (dish − bare) 2–10 kHz band-limited SNR
- band: 2–10 kHz; noise window: 200 ms pre-call; call selection: channel-blinded isolation rule
- thresholds: PASS ≥ +6 dB / FAIL < +3 dB / AMBIGUOUS +3–6 dB
- N: 20 eligible calls, single session, no cross-session pooling

## Results log (append-only — the water only drops once)
<empty until data lands>
