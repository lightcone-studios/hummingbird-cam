# Harness self-test (genesis seal)

This document exists to be sealed as the first row of `ledger.jsonl`. It carries no
scientific claim. Sealing it exercises the whole machine end to end:

1. the Secure Enclave signs a canonical preimage,
2. the ledger records a hash-chained row (genesis `prev` = all zeros),
3. `science.py verify` re-hashes this file, verifies the signature with `openssl`, and
   confirms the chain link,
4. altering one byte of this file makes `verify` report a content-changed violation.

If `science.py verify` reports this row `OK`, the declared-intent machine works.
