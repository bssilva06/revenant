"""Python port of CBACT04C (CardDemo interest calculator batch program).

For each transaction-category balance record (read in key order) the program
looks up the account, the card cross reference and the disclosure group
interest rate, then writes one interest transaction per category with a
non-zero rate and adds the account's total interest to its current balance.

Files are modelled as fixed-width text files, one record per line, using the
record layouts from the original copybooks. Signed numeric fields use the
COBOL DISPLAY sign-overpunch convention (e.g. "{" = +0, "}" = -0).

Behaviour kept from the COBOL source:
  * Interest is truncated (not rounded) to 2 decimals.
  * The last account in the balance file is never updated, because the
    COBOL loop ends on end-of-file before the final 1050-UPDATE-ACCOUNT can
    run. Pass ``update_last_account=True`` to run() to update it anyway.
  * A missing account or cross reference is fatal (abend). A missing
    disclosure group falls back to group 'DEFAULT'.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Callable, Dict, Iterable, List, Optional, Tuple

ABEND_CODE = 999

TCATBAL_LEN = 50
XREF_LEN = 50
DISCGRP_LEN = 50
ACCOUNT_LEN = 300
TRANSACTION_LEN = 350


class AbendError(Exception):
    """Equivalent of 9999-ABEND-PROGRAM (CEE3ABD with code 999)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.code = ABEND_CODE


# --------------------------------------------------------------------------
# Field codecs
# --------------------------------------------------------------------------
_POS = "{ABCDEFGHI"
_NEG = "}JKLMNOPQR"


def decode_unsigned(text: str, scale: int = 0) -> int | Decimal:
    """PIC 9(n)[V9(scale)] DISPLAY -> int (scale 0) or Decimal."""
    if not text.isdigit():
        raise ValueError(f"invalid unsigned numeric field: {text!r}")
    value = int(text)
    return value if scale == 0 else Decimal(value).scaleb(-scale)


def decode_signed(text: str, scale: int) -> Decimal:
    """PIC S9(n)V9(scale) DISPLAY with trailing sign overpunch -> Decimal."""
    if not text:
        raise ValueError("empty signed numeric field")
    last = text[-1]
    if last in _POS:
        sign, digit = 1, _POS.index(last)
    elif last in _NEG:
        sign, digit = -1, _NEG.index(last)
    elif last.isdigit():  # unsigned digit: treat as positive
        sign, digit = 1, int(last)
    else:
        raise ValueError(f"invalid signed numeric field: {text!r}")
    digits = text[:-1] + str(digit)
    if not digits.isdigit():
        raise ValueError(f"invalid signed numeric field: {text!r}")
    return Decimal(sign * int(digits)).scaleb(-scale)


def encode_signed(value: Decimal, digits: int, scale: int) -> str:
    """Decimal -> PIC S9(digits-scale)V9(scale) DISPLAY with sign overpunch.

    Excess decimals are truncated and excess high-order digits are dropped,
    as COBOL does for MOVE/ADD without ON SIZE ERROR.
    """
    scaled = int(Decimal(value).scaleb(scale).to_integral_value(ROUND_DOWN))
    negative = scaled < 0
    body = str(abs(scaled)).zfill(digits)[-digits:]
    table = _NEG if negative else _POS
    return body[:-1] + table[int(body[-1])]


def encode_unsigned(value: int, digits: int) -> str:
    return str(value).zfill(digits)[-digits:]


def _pad(text: str, length: int) -> str:
    return text[:length].ljust(length)


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------
@dataclass
class TranCatBal:  # CVTRA01Y
    acct_id: str
    type_cd: str
    cat_cd: str  # kept as 4-digit string; compared as a key
    balance: Decimal

    @classmethod
    def from_record(cls, rec: str) -> "TranCatBal":
        rec = _pad(rec, TCATBAL_LEN)
        return cls(
            acct_id=rec[0:11],
            type_cd=rec[11:13],
            cat_cd=rec[13:17],
            balance=decode_signed(rec[17:28], 2),
        )

    def to_record(self) -> str:
        return _pad(
            self.acct_id + self.type_cd + self.cat_cd
            + encode_signed(self.balance, 11, 2),
            TCATBAL_LEN,
        )


@dataclass
class CardXref:  # CVACT03Y
    card_num: str
    cust_id: str
    acct_id: str

    @classmethod
    def from_record(cls, rec: str) -> "CardXref":
        rec = _pad(rec, XREF_LEN)
        return cls(rec[0:16], rec[16:25], rec[25:36])

    def to_record(self) -> str:
        return _pad(self.card_num + self.cust_id + self.acct_id, XREF_LEN)


@dataclass
class DisclosureGroup:  # CVTRA02Y
    group_id: str
    type_cd: str
    cat_cd: str
    int_rate: Decimal

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.group_id.rstrip(), self.type_cd, self.cat_cd)

    @classmethod
    def from_record(cls, rec: str) -> "DisclosureGroup":
        rec = _pad(rec, DISCGRP_LEN)
        return cls(rec[0:10].rstrip(), rec[10:12], rec[12:16], decode_signed(rec[16:22], 2))

    def to_record(self) -> str:
        return _pad(
            _pad(self.group_id, 10) + self.type_cd + self.cat_cd
            + encode_signed(self.int_rate, 6, 2),
            DISCGRP_LEN,
        )


@dataclass
class Account:  # CVACT01Y
    acct_id: str
    active_status: str
    curr_bal: Decimal
    credit_limit: Decimal
    cash_credit_limit: Decimal
    open_date: str
    expiration_date: str
    reissue_date: str
    curr_cyc_credit: Decimal
    curr_cyc_debit: Decimal
    addr_zip: str
    group_id: str
    filler: str = field(default=" " * 178, repr=False)

    @classmethod
    def from_record(cls, rec: str) -> "Account":
        rec = _pad(rec, ACCOUNT_LEN)
        return cls(
            acct_id=rec[0:11],
            active_status=rec[11:12],
            curr_bal=decode_signed(rec[12:24], 2),
            credit_limit=decode_signed(rec[24:36], 2),
            cash_credit_limit=decode_signed(rec[36:48], 2),
            open_date=rec[48:58],
            expiration_date=rec[58:68],
            reissue_date=rec[68:78],
            curr_cyc_credit=decode_signed(rec[78:90], 2),
            curr_cyc_debit=decode_signed(rec[90:102], 2),
            addr_zip=rec[102:112].rstrip(),
            group_id=rec[112:122].rstrip(),
            filler=rec[122:300],
        )

    def to_record(self) -> str:
        return _pad(
            self.acct_id
            + _pad(self.active_status, 1)
            + encode_signed(self.curr_bal, 12, 2)
            + encode_signed(self.credit_limit, 12, 2)
            + encode_signed(self.cash_credit_limit, 12, 2)
            + _pad(self.open_date, 10)
            + _pad(self.expiration_date, 10)
            + _pad(self.reissue_date, 10)
            + encode_signed(self.curr_cyc_credit, 12, 2)
            + encode_signed(self.curr_cyc_debit, 12, 2)
            + _pad(self.addr_zip, 10)
            + _pad(self.group_id, 10)
            + _pad(self.filler, 178),
            ACCOUNT_LEN,
        )


@dataclass
class Transaction:  # CVTRA05Y
    tran_id: str
    type_cd: str
    cat_cd: int
    source: str
    desc: str
    amount: Decimal
    merchant_id: int
    merchant_name: str
    merchant_city: str
    merchant_zip: str
    card_num: str
    orig_ts: str
    proc_ts: str

    @classmethod
    def from_record(cls, rec: str) -> "Transaction":
        rec = _pad(rec, TRANSACTION_LEN)
        return cls(
            tran_id=rec[0:16],
            type_cd=rec[16:18],
            cat_cd=int(decode_unsigned(rec[18:22])),
            source=rec[22:32].rstrip(),
            desc=rec[32:132].rstrip(),
            amount=decode_signed(rec[132:143], 2),
            merchant_id=int(decode_unsigned(rec[143:152])),
            merchant_name=rec[152:202].rstrip(),
            merchant_city=rec[202:252].rstrip(),
            merchant_zip=rec[252:262].rstrip(),
            card_num=rec[262:278],
            orig_ts=rec[278:304],
            proc_ts=rec[304:330],
        )

    def to_record(self) -> str:
        return _pad(
            _pad(self.tran_id, 16)
            + _pad(self.type_cd, 2)
            + encode_unsigned(self.cat_cd, 4)
            + _pad(self.source, 10)
            + _pad(self.desc, 100)
            + encode_signed(self.amount, 11, 2)
            + encode_unsigned(self.merchant_id, 9)
            + _pad(self.merchant_name, 50)
            + _pad(self.merchant_city, 50)
            + _pad(self.merchant_zip, 10)
            + _pad(self.card_num, 16)
            + _pad(self.orig_ts, 26)
            + _pad(self.proc_ts, 26),
            TRANSACTION_LEN,
        )


# --------------------------------------------------------------------------
# Business logic
# --------------------------------------------------------------------------
def db2_timestamp(now: datetime) -> str:
    """Z-GET-DB2-FORMAT-TIMESTAMP: YYYY-MM-DD-HH.MM.SS.hh0000 (26 chars)."""
    hundredths = now.microsecond // 10000
    return (
        f"{now.year:04d}-{now.month:02d}-{now.day:02d}-"
        f"{now.hour:02d}.{now.minute:02d}.{now.second:02d}.{hundredths:02d}0000"
    )


def compute_monthly_interest(balance: Decimal, annual_rate: Decimal) -> Decimal:
    """1300-COMPUTE-INTEREST: (balance * rate) / 1200, truncated to 2 places."""
    return (balance * annual_rate / Decimal(1200)).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )


def build_interest_transaction(
    parm_date: str,
    suffix: int,
    account: Account,
    xref: CardXref,
    amount: Decimal,
    now: datetime,
) -> Transaction:
    """1300-B-WRITE-TX (record construction only)."""
    ts = db2_timestamp(now)
    return Transaction(
        tran_id=_pad(parm_date, 10) + encode_unsigned(suffix, 6),
        type_cd="01",
        cat_cd=5,
        source="System",
        desc="Int. for a/c " + account.acct_id,
        amount=amount,
        merchant_id=0,
        merchant_name="",
        merchant_city="",
        merchant_zip="",
        card_num=xref.card_num,
        orig_ts=ts,
        proc_ts=ts,
    )


def run(
    tcatbal: Iterable[TranCatBal],
    xrefs: Iterable[CardXref],
    discgrps: Iterable[DisclosureGroup],
    accounts: Dict[str, Account],
    parm_date: str,
    *,
    now: Callable[[], datetime] = datetime.now,
    update_last_account: bool = False,
    log: Callable[[str], None] = print,
) -> List[Transaction]:
    """Run the interest calculation.

    ``accounts`` is keyed by account id and is updated in place (the COBOL
    REWRITE). Returns the interest transactions in the order written.
    Raises AbendError where the COBOL program would abend.
    """
    log("START OF EXECUTION OF PROGRAM CBACT04C")

    xref_by_acct: Dict[str, CardXref] = {}
    for x in xrefs:  # alternate key: first record for an account wins
        xref_by_acct.setdefault(x.acct_id, x)
    disc = {d.key: d for d in discgrps}

    transactions: List[Transaction] = []
    last_acct: str = " " * 11
    first_time = True
    total_int = Decimal("0.00")
    tran_suffix = 0
    account: Optional[Account] = None
    xref: Optional[CardXref] = None

    def update_account() -> None:  # 1050-UPDATE-ACCOUNT
        assert account is not None
        account.curr_bal += total_int
        account.curr_cyc_credit = Decimal("0.00")
        account.curr_cyc_debit = Decimal("0.00")
        accounts[account.acct_id] = account

    for rec in tcatbal:
        log(rec.to_record())
        if rec.acct_id != last_acct:
            if not first_time:
                update_account()
            else:
                first_time = False
            total_int = Decimal("0.00")
            last_acct = rec.acct_id

            account = accounts.get(rec.acct_id)  # 1100-GET-ACCT-DATA
            if account is None:
                log(f"ACCOUNT NOT FOUND: {rec.acct_id}")
                log("ERROR READING ACCOUNT FILE")
                raise AbendError("account not found: " + rec.acct_id)

            xref = xref_by_acct.get(rec.acct_id)  # 1110-GET-XREF-DATA
            if xref is None:
                log(f"ACCOUNT NOT FOUND: {rec.acct_id}")
                log("ERROR READING XREF FILE")
                raise AbendError("xref not found for account: " + rec.acct_id)

        assert account is not None and xref is not None

        # 1200-GET-INTEREST-RATE, with fallback to the DEFAULT group
        group = account.group_id.rstrip()
        found = disc.get((group, rec.type_cd, rec.cat_cd))
        if found is None:
            log("DISCLOSURE GROUP RECORD MISSING")
            log("TRY WITH DEFAULT GROUP CODE")
            found = disc.get(("DEFAULT", rec.type_cd, rec.cat_cd))
            if found is None:
                log("ERROR READING DEFAULT DISCLOSURE GROUP")
                raise AbendError("default disclosure group not found")

        if found.int_rate != 0:
            monthly = compute_monthly_interest(rec.balance, found.int_rate)
            total_int += monthly
            tran_suffix += 1
            transactions.append(
                build_interest_transaction(
                    parm_date, tran_suffix, account, xref, monthly, now()
                )
            )
            # 1400-COMPUTE-FEES is an empty paragraph in the original.

    if update_last_account and not first_time:
        update_account()

    log("END OF EXECUTION OF PROGRAM CBACT04C")
    return transactions


# --------------------------------------------------------------------------
# File I/O and command line
# --------------------------------------------------------------------------
def read_records(path: str) -> List[str]:
    with open(path, "r", encoding="ascii", newline="") as fh:
        return [ln.rstrip("\r\n") for ln in fh if ln.strip("\r\n")]


def write_records(path: str, records: Iterable[str]) -> None:
    with open(path, "w", encoding="ascii", newline="") as fh:
        for r in records:
            fh.write(r + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="CBACT04C interest calculator")
    p.add_argument("--date", required=True, help="PARM-DATE (10 chars, e.g. 2022-07-18)")
    p.add_argument("--tcatbal", required=True, help="transaction category balance file (input)")
    p.add_argument("--xref", required=True, help="card cross reference file (input)")
    p.add_argument("--discgrp", required=True, help="disclosure group file (input)")
    p.add_argument("--acct", required=True, help="account file (input, rewritten in place)")
    p.add_argument("--transact", required=True, help="interest transaction file (output)")
    p.add_argument("--update-last-account", action="store_true",
                   help="also update the final account (the COBOL program does not)")
    args = p.parse_args(argv)

    try:
        # Records are processed in key order, as an indexed file would be read.
        tcatbal = sorted(
            (TranCatBal.from_record(r) for r in read_records(args.tcatbal)),
            key=lambda t: (t.acct_id, t.type_cd, t.cat_cd),
        )
        xrefs = [CardXref.from_record(r) for r in read_records(args.xref)]
        discgrps = [DisclosureGroup.from_record(r) for r in read_records(args.discgrp)]
        accounts = {a.acct_id: a for a in map(Account.from_record, read_records(args.acct))}
        transactions = run(
            tcatbal, xrefs, discgrps, accounts, args.date,
            update_last_account=args.update_last_account,
        )
    except AbendError as exc:
        print("ABENDING PROGRAM")
        print(f"abend code {exc.code}: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print("ABENDING PROGRAM")
        print(f"abend code {ABEND_CODE}: {exc}", file=sys.stderr)
        return 1

    # Outputs are written only after a successful run (the COBOL program
    # would leave partial updates behind on abend).
    write_records(args.transact, (t.to_record() for t in transactions))
    write_records(args.acct, (a.to_record() for a in accounts.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
