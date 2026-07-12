#!/usr/bin/env python3
"""science.py — the hummingbird-cam declared-intent harness.

Principle (from WAYFINDING): status is DERIVED from files + git, never declared in
editable prose. The Secure Enclave seals; git timestamps and chains; this script
verifies the seals and enforces the science gates.

Commands:
  seal <doc> --type prereg|manifest|verdict|selftest --author NAME
        Append a signed, hash-chained row to the ledger (doc must be a real file).
  seal-hidden <secretfile> --label NAME --author NAME
        Commit-reveal: seal ONLY the hash of a private file (content stays out of git).
  reveal <secretfile>
        Prove a previously sealed-hidden file and record the reveal.
  verify
        Check every ledger row: content hash, Secure Enclave signature, chain link.
  check
        verify + run the science gates (G1-G4) derived from git history. Exit != 0 on any
        violation. This is what the pre-commit hook runs.
  status
        Human-readable derived view of experiments and their gate status.

Signing needs `sesign` (Shiro-only). Verifying needs only `openssl` + the committed
public key, so it runs anywhere (Hans, CI, a stranger's laptop).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd: list[str], input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=input_bytes, capture_output=True)


def repo_root() -> str:
    r = run(["git", "rev-parse", "--show-toplevel"])
    if r.returncode != 0:
        die("not inside a git repository")
    return r.stdout.decode().strip()


ROOT = repo_root()
SCIENCE = os.path.join(ROOT, "science")
LEDGER = os.path.join(SCIENCE, "ledger.jsonl")
PUBKEY = os.path.join(SCIENCE, "keys", "shiro-se.pub.pem")
SESIGN = os.path.join(SCIENCE, "tools", "sesign")
EXPERIMENTS = os.path.join(SCIENCE, "experiments")

ZERO = "0" * 64
CONTENT_TYPES = {"prereg", "manifest", "verdict", "selftest"}  # content must be an in-repo file


def die(msg: str, code: int = 1):
    print(f"science: {msg}", file=sys.stderr)
    sys.exit(code)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def preimage(row: dict) -> str:
    # The exact byte string the enclave signs and the chain hashes. Excludes 'sig'.
    return "v1|{seq}|{ts}|{type}|{path}|{sha256}|{prev}|{author}|{key}".format(**row)


def read_ledger() -> list[dict]:
    if not os.path.exists(LEDGER):
        return []
    rows = []
    with open(LEDGER) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_ledger(row: dict):
    with open(LEDGER, "a") as f:
        f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


# ---- Secure Enclave (sign only; Shiro-only) ----

def se_available() -> bool:
    return os.path.exists(SESIGN)


def se_fingerprint() -> str:
    r = run([SESIGN, "fingerprint"])
    if r.returncode != 0:
        die("sesign fingerprint failed: " + r.stderr.decode().strip())
    return r.stdout.decode().strip()


def se_sign(text: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(text.encode())
        tmp = tf.name
    try:
        r = run([SESIGN, "sign", "--in", tmp])
        if r.returncode != 0:
            die("sesign sign failed: " + r.stderr.decode().strip())
        return r.stdout.decode().strip()
    finally:
        os.unlink(tmp)


# ---- portable verify (openssl; anywhere) ----

def openssl_verify(text: str, b64sig: str) -> bool:
    if not os.path.exists(PUBKEY):
        die(f"public key not found at {PUBKEY}")
    with tempfile.NamedTemporaryFile(delete=False) as msg_f:
        msg_f.write(text.encode())
        msg = msg_f.name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".der") as der_f:
        der_f.write(base64.b64decode(b64sig))
        der = der_f.name
    try:
        r = run(["openssl", "dgst", "-sha256", "-verify", PUBKEY, "-signature", der, msg])
        # openssl dgst -verify exits 0 only on a successful verify; the "Verified OK" string
        # placement is version-dependent, so gate on the exit code (portable, fail-closed).
        return r.returncode == 0
    finally:
        os.unlink(msg)
        os.unlink(der)


# ---- git helpers (all operate on committed history) ----

def git_first_epoch(path: str):
    r = run(["git", "log", "--follow", "--format=%ct", "--", path])
    epochs = [int(x) for x in r.stdout.decode().split()]
    return min(epochs) if epochs else None


def git_last_epoch(path: str):
    r = run(["git", "log", "--follow", "--format=%ct", "--", path])
    epochs = [int(x) for x in r.stdout.decode().split()]
    return max(epochs) if epochs else None


def git_commit_count(path: str) -> int:
    r = run(["git", "log", "--follow", "--format=%H", "--", path])
    return len([h for h in r.stdout.decode().split() if h])


def git_first_commit(path: str):
    r = run(["git", "log", "--follow", "--format=%H", "--", path])
    hs = [h for h in r.stdout.decode().split() if h]
    return hs[-1] if hs else None


def git_last_commit(path: str):
    r = run(["git", "log", "--follow", "--format=%H", "--", path])
    hs = [h for h in r.stdout.decode().split() if h]
    return hs[0] if hs else None


def relpath(path: str) -> str:
    return os.path.relpath(os.path.abspath(path), ROOT)


# ---- commands ----

def cmd_seal(argv: list[str], hidden: bool = False):
    author = opt(argv, "--author")
    if not author:
        die("--author NAME is required (who declares this intent)", 64)
    if not se_available():
        die(f"sesign not built at {SESIGN} — run science/tools/build.sh (Shiro only)", 3)

    if hidden:
        label = opt(argv, "--label") or die("seal-hidden requires --label NAME", 64)
        secret = argv[0] if argv and not argv[0].startswith("--") else die("seal-hidden requires a secret file", 64)
        sha = sha256_file(secret)
        typ, path = "sealed-hidden", label
    else:
        doc = argv[0] if argv and not argv[0].startswith("--") else die("seal requires a doc path", 64)
        typ = opt(argv, "--type") or "prereg"
        if typ not in CONTENT_TYPES:
            die(f"--type must be one of {sorted(CONTENT_TYPES)}", 64)
        if not os.path.isfile(doc):
            die(f"doc not found: {doc}")
        sha = sha256_file(doc)
        path = relpath(doc)

    rows = read_ledger()
    seq = rows[-1]["seq"] + 1 if rows else 1
    prev = sha256_bytes(preimage(rows[-1]).encode()) if rows else ZERO
    row = {
        "seq": seq, "ts": utcnow(), "type": typ, "path": path,
        "sha256": sha, "prev": prev, "author": author, "key": se_fingerprint(),
    }
    for f in ("ts", "type", "path", "author", "key", "sha256", "prev"):
        if "|" in str(row[f]) or "\n" in str(row[f]):
            die(f"illegal delimiter char in field {f!r}: {row[f]!r} (would corrupt the signed preimage)")
    row["sig"] = se_sign(preimage(row))
    append_ledger(row)
    print(f"sealed #{seq}  {typ}  {path}")
    print(f"  sha256 {sha}")
    print(f"  key    {row['key']}  chain-prev {prev[:12]}…")
    print("  commit the ledger + doc, then `git push` to timestamp-witness the seal.")


def cmd_reveal(argv: list[str]):
    secret = argv[0] if argv and not argv[0].startswith("--") else die("reveal requires a file", 64)
    sha = sha256_file(secret)
    author = opt(argv, "--author") or die("--author NAME required", 64)
    match = next((r for r in read_ledger() if r["type"] == "sealed-hidden" and r["sha256"] == sha), None)
    if not match:
        die("no sealed-hidden row matches this file's hash — it was never sealed (or was altered)")
    print(f"match: sealed-hidden #{match['seq']} ({match['path']}) sealed at {match['ts']}")
    cmd_seal([secret, "--type", "manifest", "--author", author])  # record the reveal as a normal seal


def cmd_verify(quiet: bool = False) -> bool:
    rows = read_ledger()
    if not rows:
        if not quiet:
            print("ledger is empty (nothing sealed yet)")
        return True
    ok = True
    expected_prev = ZERO
    for r in rows:
        problems = []
        if r["prev"] != expected_prev:
            problems.append(f"chain break (prev {r['prev'][:12]}… != expected {expected_prev[:12]}…)")
        if r["type"] in CONTENT_TYPES:
            fpath = os.path.join(ROOT, r["path"])
            if not os.path.isfile(fpath):
                problems.append(f"sealed doc missing: {r['path']}")
            elif sha256_file(fpath) != r["sha256"]:
                problems.append(f"content changed since seal: {r['path']}")
        if not openssl_verify(preimage(r), r["sig"]):
            problems.append("signature INVALID")
        mark = "OK " if not problems else "FAIL"
        if not quiet or problems:
            print(f"  [{mark}] #{r['seq']} {r['type']} {r['path']}")
            for p in problems:
                print(f"         ! {p}")
        ok = ok and not problems
        expected_prev = sha256_bytes(preimage(r).encode())
    if not quiet:
        print(("verify: all seals intact" if ok else "verify: SEAL VIOLATIONS FOUND") + f" ({len(rows)} rows)")
    return ok


def cmd_check() -> bool:
    print("== ledger seals ==")
    seals_ok = cmd_verify(quiet=True)
    print("  all seals intact" if seals_ok else "  SEAL VIOLATIONS (run `verify` for detail)")
    print("== science gates ==")
    gates_ok = True
    for name, gates in gate_status().items():
        marks = " ".join(f"{g}{sym}" for g, (state, sym) in gates.items())
        print(f"  {name}: {marks}")
        gates_ok = gates_ok and all(state is not False for state, _ in gates.values())
    ok = seals_ok and gates_ok
    print("check:", "PASS" if ok else "FAIL")
    return ok


def experiment_dirs() -> list[str]:
    if not os.path.isdir(EXPERIMENTS):
        return []
    out = []
    for name in sorted(os.listdir(EXPERIMENTS)):
        d = os.path.join(EXPERIMENTS, name)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "pre-registration.md")):
            out.append(d)
    return out


def read_header(path: str) -> dict:
    """Tiny YAML-front-matter reader for the inline `science:` block. Stdlib only."""
    hdr = {}
    if not os.path.isfile(path):
        return hdr
    with open(path) as f:
        text = f.read()
    if text.startswith("---"):
        end = text.find("\n---", 3)
        block = text[3:end] if end != -1 else ""
        for line in block.splitlines():
            line = line.strip()
            if ":" in line and not line.endswith(":"):
                k, v = line.split(":", 1)
                hdr[k.strip()] = v.strip().split("#", 1)[0].strip()
    return hdr


def gate_status() -> dict:
    """Derive G1-G4 per experiment from git history. state: True pass / False fail / None pending."""
    out = {}
    for d in experiment_dirs():
        name = os.path.basename(d)
        prereg = os.path.join(d, "pre-registration.md")
        manifest = os.path.join(d, "data-manifest.jsonl")
        verdict = os.path.join(d, "VERDICT.md")

        prereg_epoch = git_first_epoch(prereg)
        data_epoch = git_first_epoch(manifest)

        # G1: prereg committed strictly before data
        if data_epoch is None:
            g1 = None
        else:
            g1 = prereg_epoch is not None and prereg_epoch < data_epoch

        # G2: raw-data manifest never re-committed (immutable results)
        g2 = None if data_epoch is None else (git_commit_count(manifest) == 1)

        # G3: prereg not edited after data landed (no goalpost-moving).
        # `<=` alone misses editing the prereg in the SAME commit that adds the data; strict
        # `<` alone would misfire on legit same-second-but-different commits. So check both:
        # time not-after AND not bundled into the data commit.
        if data_epoch is None:
            g3 = None
        else:
            prereg_last = git_last_epoch(prereg)
            same_commit = git_first_commit(manifest) == git_last_commit(prereg)
            g3 = prereg_last is not None and prereg_last <= data_epoch and not same_commit

        # G4: reviewer != author
        if not os.path.isfile(verdict):
            g4 = None
        else:
            author = read_header(prereg).get("author", "")
            reviewer = read_header(verdict).get("reviewer", "")
            g4 = bool(reviewer) and reviewer != author

        def sym(x):
            return "✓" if x is True else ("✗" if x is False else "·")

        out[name] = {
            "G1-prereg-before-data": (g1, sym(g1)),
            "G2-results-immutable": (g2, sym(g2)),
            "G3-prereg-frozen": (g3, sym(g3)),
            "G4-reviewer!=author": (g4, sym(g4)),
        }
    return out


def cmd_status():
    rows = read_ledger()
    print(f"ledger: {len(rows)} sealed rows" + (f" (latest: {rows[-1]['ts']})" if rows else ""))
    exps = experiment_dirs()
    if not exps:
        print("experiments: none yet")
        return
    print("experiments:")
    for name, gates in gate_status().items():
        marks = "  ".join(f"{g.split('-')[0]}{sym}" for g, (_, sym) in gates.items())
        print(f"  {name}   {marks}")


def opt(argv: list[str], name: str):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def main():
    if len(sys.argv) < 2:
        die(__doc__, 64)
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == "seal":
        cmd_seal(argv)
    elif cmd == "seal-hidden":
        cmd_seal(argv, hidden=True)
    elif cmd == "reveal":
        cmd_reveal(argv)
    elif cmd == "verify":
        sys.exit(0 if cmd_verify() else 1)
    elif cmd == "check":
        sys.exit(0 if cmd_check() else 1)
    elif cmd == "status":
        cmd_status()
    else:
        die(f"unknown command: {cmd}", 64)


if __name__ == "__main__":
    main()
