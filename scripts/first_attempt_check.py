#!/usr/bin/env python3
"""Hand comparison of the frozen first AI attempt with the old program.

    ./rv python3 scripts/first_attempt_check.py

Throwaway harness, not the engine. Each world is given to the old program as encoded files
and to the port as logical values through its own run() function. The port formats its own
output records. Outputs are compared field by field, as decoded values and as raw bytes.
"""
from __future__ import annotations

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ports" / "cbact04c" / "first_attempt"))
sys.path.insert(0, str(ROOT / "scripts"))

import cbact04c as port  # noqa: E402  the frozen first attempt
from m1_proof import RUN_DATE, alnum, run_witness, sdec, uint  # noqa: E402

CLOCK = datetime(2026, 11, 14, 12, 0, 0)

# name, offset, length, kind
TRAN = [("TRAN-ID", 0, 16, "x"), ("TRAN-TYPE-CD", 16, 2, "x"), ("TRAN-CAT-CD", 18, 4, "x"),
        ("TRAN-SOURCE", 22, 10, "x"), ("TRAN-DESC", 32, 100, "x"), ("TRAN-AMT", 132, 11, "s"),
        ("TRAN-MERCHANT-ID", 143, 9, "x"), ("TRAN-MERCHANT-NAME", 152, 50, "x"),
        ("TRAN-MERCHANT-CITY", 202, 50, "x"), ("TRAN-MERCHANT-ZIP", 252, 10, "x"),
        ("TRAN-CARD-NUM", 262, 16, "x"), ("TRAN-ORIG-TS", 278, 26, "t"),
        ("TRAN-PROC-TS", 304, 26, "t"), ("FILLER", 330, 20, "x")]
ACCT = [("ACCT-ID", 0, 11, "x"), ("ACCT-ACTIVE-STATUS", 11, 1, "x"),
        ("ACCT-CURR-BAL", 12, 12, "s"), ("ACCT-CREDIT-LIMIT", 24, 12, "s"),
        ("ACCT-CASH-CREDIT-LIMIT", 36, 12, "s"), ("ACCT-OPEN-DATE", 48, 10, "x"),
        ("ACCT-EXPIRAION-DATE", 58, 10, "x"), ("ACCT-REISSUE-DATE", 68, 10, "x"),
        ("ACCT-CURR-CYC-CREDIT", 78, 12, "s"), ("ACCT-CURR-CYC-DEBIT", 90, 12, "s"),
        ("ACCT-ADDR-ZIP", 102, 10, "x"), ("ACCT-GROUP-ID", 112, 10, "x"),
        ("FILLER", 122, 178, "x")]

POS, NEG = "{ABCDEFGHI", "}JKLMNOPQR"


def any_signed(raw: bytes):
    """Decode a signed display number in either sign convention. None if not decodable."""
    s = raw.decode("ascii", "replace")
    last, sign = s[-1], 1
    if last.isdigit():
        d = last
    elif "p" <= last <= "y":
        d, sign = str(ord(last) - ord("p")), -1
    elif last in POS:
        d = str(POS.index(last))
    elif last in NEG:
        d, sign = str(NEG.index(last)), -1
    else:
        return None
    return sign * int(s[:-1] + d) if (s[:-1] + d).isdigit() else None


def mask_ts(raw: bytes) -> bytes:
    return raw[:20] + b"##" + raw[22:]


def compare(label: str, schema, old: bytes, new: bytes, length: int) -> list[str]:
    out = []
    if len(old) != len(new):
        return [f"  {label}: STRUCTURE old {len(old) // length} records, new {len(new) / length:g}"]
    for i in range(len(old) // length):
        a, b = old[i * length:(i + 1) * length], new[i * length:(i + 1) * length]
        for name, off, n, kind in schema:
            x, y = a[off:off + n], b[off:off + n]
            if kind == "t":
                x, y = mask_ts(x), mask_ts(y)
            if x == y:
                continue
            if kind == "s" and any_signed(x) is not None and any_signed(x) == any_signed(y):
                cls = "format "
            elif kind == "s":
                cls = "NUMERIC"
            else:
                cls = "text   "
            out.append(f"  {label}[{i}] {cls} {name:<22} old {x.decode('ascii', 'replace')!r:<16} "
                       f"new {y.decode('ascii', 'replace')!r}")
    return out


def world(accounts, balances, rates):
    """accounts: [(id, group, balance)]  balances: [(acct, type, cat, cents)]
    rates: [(group, type, cat, rate)]. All money and rates are integers."""
    w_acct, p_acct = [], {}
    for aid, group, bal in accounts:
        w_acct.append(uint(aid, 11) + b"Y" + sdec(bal, 12) + sdec(500000, 12) + sdec(100000, 12)
                      + alnum("2020-01-01", 10) + alnum("2030-01-01", 10)
                      + alnum("2025-01-01", 10) + sdec(12345, 12) + sdec(-6789, 12)
                      + alnum("00000", 10) + alnum(group, 10) + b" " * 178)
        key = f"{aid:011d}"
        p_acct[key] = port.Account(
            acct_id=key, active_status="Y", curr_bal=Decimal(bal) / 100,
            credit_limit=Decimal(5000), cash_credit_limit=Decimal(1000),
            open_date="2020-01-01", expiration_date="2030-01-01", reissue_date="2025-01-01",
            curr_cyc_credit=Decimal("123.45"), curr_cyc_debit=Decimal("-67.89"),
            addr_zip="00000", group_id=group)
    files = {
        "ACCTFILE": w_acct,
        "TCATBALF": [uint(a, 11) + alnum(t, 2) + uint(c, 4) + sdec(v, 11) + b" " * 22
                     for a, t, c, v in balances],
        "XREFFILE": [alnum(f"40000000000000{aid:02d}", 16) + uint(aid, 9) + uint(aid, 11)
                     + b" " * 14 for aid, _, _ in accounts],
        "DISCGRP": [alnum(g, 10) + alnum(t, 2) + uint(c, 4) + sdec(r, 6) + b" " * 28
                    for g, t, c, r in rates],
    }
    logical = dict(
        tcatbal=[port.TranCatBal(f"{a:011d}", t, f"{c:04d}", Decimal(v) / 100)
                 for a, t, c, v in sorted(balances)],
        xrefs=[port.CardXref(f"40000000000000{aid:02d}", aid, f"{aid:011d}")
               for aid, _, _ in accounts],
        discgrps=[port.DisclosureGroup(g, t, f"{c:04d}", Decimal(r) / 100)
                  for g, t, c, r in rates],
        accounts=p_acct,
    )
    return files, logical


WORLDS = {
    "1.00 at 6.00": world([(1, "G1", 0)], [(1, "01", 2, 100)], [("G1", "01", 2, 600)]),
    "100.50 at 15.00": world([(1, "G1", 0)], [(1, "01", 2, 10050)], [("G1", "01", 2, 1500)]),
    "-100.50 at 15.00": world([(1, "G1", 0)], [(1, "01", 2, -10050)], [("G1", "01", 2, 1500)]),
    "two accounts, default group, zero rate": world(
        [(1, "G1", 250000), (2, "G2", -4000)],
        [(1, "01", 1, 123456), (1, "01", 2, 99999), (2, "01", 1, 55555), (2, "02", 3, 777)],
        [("G1", "01", 1, 1850), ("G1", "01", 2, 0), ("DEFAULT", "01", 1, 2499),
         ("DEFAULT", "02", 3, 999)]),
}


def main() -> int:
    for name, (files, logical) in WORLDS.items():
        code, old_tx, old_acct, _ = run_witness(files)
        try:
            txs = port.run(logical["tcatbal"], logical["xrefs"], logical["discgrps"],
                           logical["accounts"], RUN_DATE, now=lambda: CLOCK, log=lambda s: None)
            new_tx = "".join(t.to_record() for t in txs).encode("ascii")
            new_acct = "".join(logical["accounts"][k].to_record()
                               for k in sorted(logical["accounts"])).encode("ascii")
            err = None
        except Exception as e:  # the port raising is itself a result
            new_tx = new_acct = b""
            err = repr(e)
        diffs = compare("transactions", TRAN, old_tx, new_tx, 350)
        diffs += compare("accounts", ACCT, old_acct, new_acct, 300)
        print(f"\nWORLD: {name}   (old exit {code}, {len(old_tx) // 350} transactions)")
        if err:
            print(f"  port raised: {err}")
        print("\n".join(diffs) if diffs else "  no difference, bytes identical after timestamp mask")
    return 0


if __name__ == "__main__":
    sys.exit(main())
