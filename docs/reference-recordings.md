# Reference recordings — the clean target

Known-good Anna's Hummingbird (*Calypte anna*) audio, used as the **positive control**
for the chip detector (`scripts/detect-chips.py`). A detector that cannot find chips in
these has no business reporting chips on our porch.

The audio itself lives in `captures/reference/` and is **gitignored** — per the science
harness rule, raw audio stays on disk and only its hash goes into git. Re-fetch with the
URLs below; verify with the SHA-256.

## XC1077841 — the primary control

| Field | Value |
|---|---|
| **Species** | Anna's Hummingbird, *Calypte anna* |
| **Sound type** | **call** (chip notes — what we're detecting) |
| **Recordist** | Greg Irving |
| **Date** | 2026-02-03, 14:52 |
| **Location** | Dungeness Recreation Area, Clallam County, **Washington**, USA |
| **Elevation** | 40 m |
| **Duration** | 54.7 s |
| **Format** | MP3, 48 kHz mono, 320 kbps |
| **URL** | https://xeno-canto.org/1077841 |
| **SHA-256** | `dd9005ff3cac9ad9e22fdc8e2d21dd32acb87e73fd83f02a5afbc21cc3667cb3` |
| **Fetched** | 2026-07-12 |

**Why this one.** Clallam County is the Olympic Peninsula — the same Pacific Northwest
population as the birds on Aaron's porch, not a California population that might chip
differently. It is a *call* recording, not a song, so it is chips end to end. And 54 s is
long enough to yield ~95 chips, which is a real sample rather than an anecdote.

**What the detector measures on it** (the numbers any change to `detect-chips.py` must
not break):

```
95 chips in 54.7 s
chip interval:  median 0.494 s   mean 0.489 s ± 0.085
chip duration:  median 38 ms  (18-78 ms)   <- all within the paper's "<0.1 s"
band contrast:  +17.8 dB median (8-10 kHz vs 1-3 kHz)
```

## XC1074392 — secondary

| Field | Value |
|---|---|
| **Sound type** | territorial call |
| **Recordist** | Frank Severson |
| **Date** | 2026-01-24, 12:03 |
| **Location** | West Sacramento, Yolo County, California, USA |
| **Duration** | 21.1 s |
| **Format** | WAV, 44.1 kHz mono, 32-bit float (served with an `.mp3` URL — it is a WAV) |
| **URL** | https://xeno-canto.org/1074392 |
| **SHA-256** | `ac1a6f64a425d50e31de5c5b969d6372acef7dcef533355eedd2f83e2514c4ea` |
| **Fetched** | 2026-07-12 |

A California bird in an explicitly *territorial* context — useful later as a contrast to
the Washington bird, since the Berkeley paper found chip rate varies with territorial
behavior (DAT chips are faster than chasing chips).

## Licensing — CONFIRM BEFORE ANY REDISTRIBUTION

xeno-canto recordings are Creative Commons licensed, but the specific license is set
**per recording** by the recordist (the family runs from CC0 through CC BY-NC-SA and
CC BY-NC-ND). The recording pages are JavaScript-rendered, so the license string could
not be scraped and **has not been verified for either file above.**

- Using them **locally as a detector control** (what we are doing) is fine under any of
  the CC variants.
- **Publishing, redistributing, or putting the audio in a video/post is NOT cleared.**
  Open the recording page, read the license, and credit the recordist by name and XC
  number before any of that.

## Refetch

```bash
curl -L -o captures/reference/XC1077841.mp3 https://xeno-canto.org/1077841/download
shasum -a 256 captures/reference/XC1077841.mp3   # must match the hash above
```

Note: xeno-canto's **API** now requires an account key (since 2025-10-10), but the direct
`/download` URLs above still work without one.
