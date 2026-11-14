#!/usr/bin/env python3
"""Milestone 1 determinism check:  ./rv python3 scripts/m1_determinism.py

Runs the old program 100 times on the seed data and 100 times on a one-account input, then
reports which output byte positions ever varied. Throwaway harness, not the engine.
"""
from __future__ import annotations

import sys

from m1_proof import ACCT_LEN, INPUTS, SEED, TRAN_LEN, one_account_world, run_witness

RUNS = 100
# TRAN-ORIG-TS and TRAN-PROC-TS are X(26) at record offsets 278 and 304.
# Layout YYYY-MM-DD-HH.MM.SS.hh0000: the hundredths digits are at +20 and +21.
EXPECTED = {278 + 20, 278 + 21, 304 + 20, 304 + 21}


def seed_files() -> dict[str, list[bytes]]:
    files = {}
    for name, _, length, seed in INPUTS:
        lines = (SEED / seed).read_bytes().replace(b"\r", b"").split(b"\n")
        files[name] = [line.ljust(length) for line in lines if line]
    return files


def varying(outputs: list[bytes], record_length: int) -> set[int]:
    """Offsets within a record at which any run differed from the first run."""
    first = outputs[0]
    if any(len(o) != len(first) for o in outputs):
        return {-1}
    return {i % record_length for o in outputs[1:] for i in range(len(first)) if o[i] != first[i]}


def check(label: str, files: dict[str, list[bytes]]) -> bool:
    tx, accts, consoles, codes = [], [], [], set()
    for _ in range(RUNS):
        code, t, a, console = run_witness(files)
        codes.add(code)
        tx.append(t)
        accts.append(a)
        consoles.append(console)
    tx_var, acct_var = varying(tx, TRAN_LEN), varying(accts, ACCT_LEN)
    console_same = len(set(consoles)) == 1
    ok = codes == {0} and tx_var <= EXPECTED and not acct_var and console_same
    print(f"{label:<12} {RUNS} runs, exit codes {sorted(codes)}, "
          f"{len(tx[0]) // TRAN_LEN} transaction records")
    print(f"  transaction offsets that varied: {sorted(tx_var) or 'none'} "
          f"(timestamp hundredths are {sorted(EXPECTED)})")
    print(f"  account file offsets that varied: {sorted(acct_var) or 'none'}")
    print(f"  console output identical: {console_same}")
    print(f"  sample TRAN-ORIG-TS: {tx[0][278:304].decode()}  /  {tx[-1][278:304].decode()}")
    return ok


def main() -> int:
    ok = check("SEED DATA", seed_files())
    ok = check("ONE ACCOUNT", one_account_world(10050, 1500)) and ok
    print("DETERMINISTIC after masking timestamp hundredths" if ok else "NOT DETERMINISTIC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
