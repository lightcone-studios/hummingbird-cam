# The declared-intent harness

How we do science in this repo: **the hypothesis is declared, hashed, and sealed *before* the data exists** — so a result can never be reverse-engineered into a prediction. Dialed back from `WAYFINDING_AI_RESEARCH`: the rigor lives in four git-enforced gates; the Secure Enclave adds a non-forgeable authorship seal on top.

## The four gates (this is the actual science)

Status is **derived from files + git**, never declared in prose. `science.py check` computes it.

| Gate | Rule | How it's checked |
|---|---|---|
| **G1 prereg-before-data** | The hypothesis commit must predate the first data commit | git commit-order |
| **G2 results immutable** | Raw-data manifest is committed once, never edited | `git log` commit count == 1 |
| **G3 prereg frozen** | The prereg is never edited after data lands | prereg last-commit ≤ first-data-commit |
| **G4 reviewer ≠ author** | You don't grade your own homework | header compare |

A gate is `✓` pass, `✗` fail (blocks commits), `·` not-yet-applicable (e.g. no data collected yet).

## The seal (non-forgeable authorship)

Every declared doc is SHA-256'd and signed by **Shiro's Secure Enclave** — a P-256 key whose private half physically cannot leave the chip. The signature proves *this machine attests to this exact content*. Seals are recorded in `ledger.jsonl`, an append-only, hash-chained log (each row links to the previous row's hash; git is the outer chain and the timestamp).

- **Sign** happens on Shiro only (needs the enclave): `science/tools/build.sh` then `sesign`.
- **Verify** runs anywhere with just `openssl` + the committed public key (`keys/shiro-se.pub.pem`) — Hans, CI, or a skeptic's laptop. No Apple hardware needed to check the seals.

## Declaring a hypothesis

```
1. cp science/experiments/TEMPLATE-pre-registration.md \
      science/experiments/00X-your-name/pre-registration.md
2. Fill it in. Lock the estimator and the PASS/FAIL/AMBIGUOUS thresholds BEFORE any data.
3. git add + commit the prereg.                      # git timestamp = the freeze
4. python3 science/tools/science.py seal \
      science/experiments/00X-your-name/pre-registration.md \
      --type prereg --author you
5. git add science/ledger.jsonl + commit, then `git push`.   # GitHub = the third-party witness
```

Then collect data → write `data-manifest.jsonl` (the sha256 of each raw recording; the big WAV files stay on the host, never committed) → commit it (that trips G1/G2/G3 into live checking) → write `VERDICT.md` with a reviewer who isn't you.

## Sealing something you're not ready to show (commit-reveal)

Prove you knew something at time T without publishing it yet:

```
python3 science/tools/science.py seal-hidden secret.md --label my-prediction --author you
# ...later, when you're ready to reveal:
python3 science/tools/science.py reveal secret.md --author you
```

The first step seals only the hash (content stays private/gitignored). The reveal proves the later plaintext matches the earlier hash, unchanged.

## Verifying

```
python3 science/tools/science.py verify    # every seal: content hash + signature + chain
python3 science/tools/science.py check     # verify + the four gates (what the pre-commit hook runs)
python3 science/tools/science.py status    # the derived view
```

Install the gate as a pre-commit hook once per clone: `science/hooks/install.sh`.

## Honest limits (what this does and does not prove)

- **The enclave seal proves authorship and integrity, not correctness.** A sealed hypothesis can still be wrong — that's the point; it's falsifiable.
- **A local git timestamp is spoofable** (`GIT_COMMITTER_DATE`). The real "existed-before-T" evidence is the **push to GitHub** — GitHub's own record witnesses the time. Push your seals promptly. (RFC-3161 trusted-timestamping is the optional upgrade if you ever need to prove precedence to someone who doesn't trust GitHub's clock.)
- **Seals are frictionless by default** (no Touch ID per seal, so hooks and scripts work). If you want a deliberate human gesture per seal, the enclave key can be regenerated with a user-presence requirement — a one-line change in `sesign.swift`.
