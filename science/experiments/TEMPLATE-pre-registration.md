---
science:
  claim_id: <SHORT-ID>        # e.g. H1-DISH-GAIN
  author: <you>              # who declares this intent
  status: draft              # draft | sealed  — set to sealed only via `science.py seal`
---

# <Title> — one line of framing

## Scope limiter — what this does NOT test
<Name the adjacent claims this run is *not* making. Keep the hypothesis narrow.>

## Why this is falsifiable
<The honest hazard: how could this fool you into a false PASS? What keeps the test fair?>

## Method (precise enough for someone else to reproduce)
- Rig / geometry / recording chain / environment / controls.
- **The estimator, fixed in advance.** The way the number is measured IS part of the hypothesis.

## The single claim under test
> <One formal, falsifiable prediction — an inequality or a directional effect.>

## Pre-set decision thresholds (locked BEFORE any data)
- **PASS if:** <threshold>
- **FAIL if:** <threshold>
- **AMBIGUOUS if:** <the band between>

## Stopping rule
<How much data, over what window, decided in advance. When collection ends and what happens to a short session.>

## Honesty pre-registration (the locked values)
Changing any value below after seeing a result **VOIDS the run**:
- estimator: <...>
- thresholds: <...>
- N / sessions: <...>

## Results log (append-only — the water only drops once)
<empty until data lands>
