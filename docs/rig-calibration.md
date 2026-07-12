# Rig calibration state

**The recording is a MEASUREMENT, not a mix.** Every number this project produces — chip
levels, thrum amplitude, distance falloff, mic comparisons — is only meaningful if the signal
chain is fixed and known. This file is that state.

**If any of it changes, record the change and the time.** A silent change to the chain
invalidates every level comparison across the seam, and you will not be able to tell from the
audio that it happened.

Established 2026-07-12, during a deliberate shakedown session — *before* serious collection.

---

## The chain

```
[Sennheiser shotgun] --XLR--> [M-Audio M-Track Duo IN 1] --USB--> [Shiro]
[Rode Wireless GO TX1] ~~2.4GHz~~> [Wireless GO RX] --USB--> [Shiro]
[Rode Wireless GO TX2] ~~2.4GHz~~>
```

## Locked settings

| element | setting | why it matters |
|---|---|---|
| **Shotgun** | Sennheiser shotgun, XLR → M-Track **INPUT 1** | |
| | **+48V phantom: ON** | it is a condenser — silent without it |
| | **Gain: 8 / 10** | |
| | **Low-cut: ON** (the `/——` switch) | **deliberately deletes the thrum.** Keep it: it protects the capsule from wind overload, which would distort the whole spectrum including the chip band. The Rode TXs carry the thrum instead — they are ~14 dB better at 79 Hz anyway. |
| **TX1 / TX2** | Rode Wireless GO, **BUILT-IN omni capsule** (not the lav attachments) | omnidirectional, 50 Hz–20 kHz — flat bass by construction, which is why they hear the thrum |
| | furry windshields fitted | |
| | **Gain: 0 dB** | |
| **Wireless GO RX** | **SPLIT mode** (two meters on screen, not one) | merged mode fuses both transmitters into one signal — the two mics become indistinguishable and the recording is useless. `record-loop.sh` **refuses to record** if it detects merged. |
| | **Manual/fixed gain — NEVER auto** | see below |
| **Capture** | 48 kHz / 16-bit / mono per channel, 5-min segments | |

## NOTHING ADAPTIVE. NOTHING AUTOMATIC.

**No AGC. No auto-gain. No auto-levelling. No noise reduction. No limiting.**

An automatic gain circuit exists *specifically* to erase level differences — it turns a loud
bird down and a quiet bird up. **Level differences are the signal.** They encode distance,
proximity, and which mic is closer. Everything the project wants from "falloff the farther
away they get" IS level. AGC would silently destroy it, and nothing in the audio would tell
you it had happened.

*(Caught on 2026-07-12 when the RX was briefly flipped to an auto mode during the shakedown.
Reverted immediately. This is exactly the kind of thing a shakedown exists to catch — in a
"serious" session it would have quietly corrupted hours of data.)*

## Geometry (tape-measured, 2026-07-12)

| | distance to feeder |
|---|---|
| shotgun | **50 in** |
| TX1 | **120 in** |
| TX2 | **120 in** |
| feeder declination below the TX plane | 4–8° |

## Measured system response (TX minus shotgun, on the same ambient sound)

This is a **system** measurement — mic + preamp + gain, as actually recorded. Use these numbers,
not a single flat offset, when comparing channels.

| band | tx1 − shotgun | tx2 − shotgun | |
|---|---|---|---|
| 50–100 Hz | **+12.5 dB** | **+14.9 dB** | ← the thrum. The shotgun's low-cut lives here. |
| 100–200 Hz | +6.3 | +9.0 | |
| 200–400 Hz | +0.6 | +2.9 | |
| 400–800 Hz | +0.8 | +2.1 | |
| 800–1600 Hz | +2.3 | +3.6 | |
| 1600–3200 Hz | +5.3 | +5.8 | ← the calibration bell lives here |
| 3200–6400 Hz | +5.3 | +5.4 | |
| 6400–10000 Hz | +5.9 | +4.2 | ← **the chip band** |

**The shotgun rolls off ~6 dB/octave below ~300 Hz** — a first-order high-pass, i.e. the low-cut
switch, measured from the outside.

**The lesson that produced this table:** the bell was used to calibrate a *single* mic-difference
number (+6.5 dB) at 3.3 kHz, and that number was then applied at 79 Hz to predict the thrum. It
was wrong by 17 dB. **Microphones have frequency responses, not gain offsets.** Never carry a
one-number mic model again.

## OPEN — unresolved, do not paper over

**The geometric model does not close.** Using the measured 50–100 Hz response and tape-measured
distances, the prediction misses by **7–13 dB**:

```
distance penalty to the TXs (120" vs 50"):   -7.6 dB
TX advantage at 50-100 Hz (measured):       +12.5 / +14.9 dB
predicted TX advantage on the thrum:         +4.9 / +7.3 dB
MEASURED TX advantage on the thrum:         +18.2 / +14.0 dB
residual:                                   +13.3 / +6.7 dB   <- UNEXPLAINED
```

**And the two TXs disagree by 4 dB** despite identical gain, identical model, and identical
tape-measured distance. That is not geometry — it is something about the mics or their mounting,
and it means the model has a hole unrelated to the shotgun.

Hypotheses **eliminated**: eyeballed distances (they were tape-measured), gain settings (already
baked into the measured response), the low-cut (accounted for).

Remaining candidates, unranked and untested:
- **Wing-dipole directivity.** Wings push air back and forth with no net volume change — a dipole,
  not a monopole. Dipoles do not radiate like point sources and do not obey simple inverse-square
  near the source. This is the most physically interesting candidate.
- Mounting / obstruction differences between the two umbrellas.
- Unit-to-unit variation between the two transmitters.

**Consequence:** absolute distance-from-amplitude ("depth", the falloff) is **NOT yet possible**.
Relative work — chip detection, bout detection, thrum presence — is unaffected and stands.

**The fix:** a controlled calibration. Play a known tone at measured distances, sweep frequency,
measure all three channels. Build a real per-channel response curve. ~30 min, indoors, no birds
needed — a good task for the painting window.
