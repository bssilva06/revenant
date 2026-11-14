#!/usr/bin/env python3
"""Milestone 1 proof. Runs inside the Revenant container:  ./rv python3 scripts/m1_proof.py

This is a throwaway harness, not the engine. It shows two things:
  1. The unmodified CBACT04C runs CardDemo's seed data to exit code 0.
  2. On a hand-written input, the old program and a naive Python calculation disagree.

Money and rates are integers of the smallest unit throughout.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "build" / "cbact04c"
SEED = ROOT / "exhibits" / "cbact04c" / "seed"

CLOCK = "2026/11/14 12:00:00"
RUN_DATE = "2022071800"

# ddname, loader, record length, seed file
INPUTS = [
    ("TCATBALF", "loadtcat", 50, "tcatbal.txt"),
    ("XREFFILE", "loadxref", 50, "cardxref.txt"),
    ("ACCTFILE", "loadacct", 300, "acctdata.txt"),
    ("DISCGRP", "loaddisc", 50, "discgrp.txt"),
]
TRAN_LEN, ACCT_LEN = 350, 300


def call(args: list[str], env: dict[str, str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, env=env, cwd=cwd, capture_output=True, timeout=5)


def run_witness(files: dict[str, list[bytes]], run_date: str = RUN_DATE):
    """Load the four input files, run the old program, unload the account file."""
    with tempfile.TemporaryDirectory() as d:
        base = {"PATH": "/usr/bin:/bin", "COB_CURRENT_DATE": CLOCK}
        dd = {f"DD_{name}": f"{d}/{name}" for name, *_ in INPUTS}
        for name, loader, length, _ in INPUTS:
            records = files[name]
            assert all(len(r) == length for r in records), name
            Path(d, f"{name}.in").write_bytes(b"".join(records))
            p = call([str(BIN / loader)], base | dd | {"DD_LOADIN": f"{d}/{name}.in"}, d)
            if p.returncode != 0:
                raise RuntimeError(f"{loader} failed: {p.stdout.decode()}{p.stderr.decode()}")
        p = call([str(BIN / "runint"), run_date], base | dd | {"DD_TRANSACT": f"{d}/TRANSACT"}, d)
        transactions = Path(d, "TRANSACT").read_bytes() if Path(d, "TRANSACT").exists() else b""
        accounts = b""
        if p.returncode == 0:
            q = call([str(BIN / "dumpacct")], base | dd | {"DD_DUMPOUT": f"{d}/ACCT.after"}, d)
            if q.returncode != 0:
                raise RuntimeError(f"dumpacct failed: {q.stdout.decode()}{q.stderr.decode()}")
            accounts = Path(d, "ACCT.after").read_bytes()
        return p.returncode, transactions, accounts, p.stdout.decode("ascii", "replace")


# --- minimal codec, enough for this proof -------------------------------------------------

def uint(value: int, length: int) -> bytes:
    return str(value).rjust(length, "0").encode()


def alnum(text: str, length: int) -> bytes:
    return text.ljust(length).encode()


POS, NEG = "{ABCDEFGHI", "}JKLMNOPQR"


def sdec(value: int, length: int) -> bytes:
    """Signed display number with a mainframe sign overpunch on the last digit."""
    digits = str(abs(value)).rjust(length, "0")
    assert len(digits) == length
    table = NEG if value < 0 else POS
    return (digits[:-1] + table[int(digits[-1])]).encode()


def unsdec(raw: bytes) -> int:
    s = raw.decode()
    last = s[-1]
    if last in POS:
        return int(s[:-1] + str(POS.index(last)))
    if last in NEG:
        return -int(s[:-1] + str(NEG.index(last)))
    return int(s)


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def one_account_world(balance: int, rate: int) -> dict[str, list[bytes]]:
    """One account in group G1 with one category balance and one matching rate."""
    acct = (uint(1, 11) + b"Y" + sdec(0, 12) + sdec(500000, 12) + sdec(100000, 12)
            + alnum("2020-01-01", 10) + alnum("2030-01-01", 10) + alnum("2025-01-01", 10)
            + sdec(0, 12) + sdec(0, 12) + alnum("00000", 10) + alnum("G1", 10) + b" " * 178)
    return {
        "TCATBALF": [uint(1, 11) + b"01" + uint(2, 4) + sdec(balance, 11) + b" " * 22],
        "XREFFILE": [alnum("4000000000000001", 16) + uint(1, 9) + uint(1, 11) + b" " * 14],
        "ACCTFILE": [acct],
        "DISCGRP": [alnum("G1", 10) + b"01" + uint(2, 4) + sdec(rate, 6) + b" " * 28],
    }


def naive_interest(balance: int, rate: int) -> int:
    """What a port that rounds half up would compute. Deliberately wrong."""
    exact = Decimal(balance) * Decimal(rate) / Decimal(120000)
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))


# --- the two demonstrations -----------------------------------------------------------------

def seed_run() -> bool:
    files = {}
    for name, _, length, seed in INPUTS:
        lines = (SEED / seed).read_bytes().replace(b"\r", b"").split(b"\n")
        files[name] = [line.ljust(length) for line in lines if line]
    t = time.perf_counter()
    code, tx, accts, console = run_witness(files)
    ms = (time.perf_counter() - t) * 1000
    n = len(tx) // TRAN_LEN
    print(f"SEED DATA   exit code {code}, {n} transaction records, {len(tx)} bytes, "
          f"{len(accts) // ACCT_LEN} accounts unloaded, {ms:.0f} ms")
    if code != 0:
        print(console)
    return code == 0 and n == 50 and len(tx) == 50 * TRAN_LEN


def probe(balance: int, rate: int) -> bool:
    code, tx, accts, console = run_witness(one_account_world(balance, rate))
    if code != 0 or len(tx) != TRAN_LEN:
        print(f"PROBE       witness failed, exit {code}\n{console}")
        return False
    old = unsdec(tx[132:143])            # TRAN-AMT
    acct_after = unsdec(accts[12:24])    # ACCT-CURR-BAL
    new = naive_interest(balance, rate)
    verdict = "agree" if old == new else "DIFFER"
    print(f"PROBE       balance {money(balance):>10} at rate {money(rate):>5}   "
          f"old TRAN-AMT {money(old):>6} (bytes {tx[132:143].decode()})   "
          f"naive {money(new):>6}   {verdict}   account balance after: {money(acct_after)}")
    return True


def main() -> int:
    ok = seed_run()
    for balance, rate in [(100, 600), (10050, 1500), (-10050, 1500), (123456789, 1500)]:
        ok = probe(balance, rate) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
