import os
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal as D

import cbact04c as c

NOW = datetime(2022, 7, 19, 23, 16, 5, 780000)
FIXED_NOW = lambda: NOW  # noqa: E731
QUIET = lambda _msg: None  # noqa: E731


def acct(acct_id="00000000001", bal="100.00", group="GRP", cyc_cr="5.00", cyc_db="7.00"):
    return c.Account(
        acct_id=acct_id, active_status="Y", curr_bal=D(bal), credit_limit=D("1000.00"),
        cash_credit_limit=D("200.00"), open_date="2020-01-01", expiration_date="2030-01-01",
        reissue_date="2025-01-01", curr_cyc_credit=D(cyc_cr), curr_cyc_debit=D(cyc_db),
        addr_zip="12345", group_id=group,
    )


def xref(acct_id="00000000001", card="4111111111111111"):
    return c.CardXref(card, "000000001", acct_id)


def bal(acct_id="00000000001", type_cd="01", cat="0001", amount="1200.00"):
    return c.TranCatBal(acct_id, type_cd, cat, D(amount))


def rate(group="GRP", type_cd="01", cat="0001", r="12.00"):
    return c.DisclosureGroup(group, type_cd, cat, D(r))


class CodecTests(unittest.TestCase):
    def test_signed_roundtrip(self):
        for v in ["0.00", "1.23", "-1.23", "12345.60", "-0.90", "99999999.99"]:
            enc = c.encode_signed(D(v), 11, 2)
            self.assertEqual(len(enc), 11)
            self.assertEqual(c.decode_signed(enc, 2), D(v))

    def test_overpunch_values(self):
        self.assertEqual(c.encode_signed(D("1.20"), 4, 2), "012{")
        self.assertEqual(c.encode_signed(D("-1.20"), 4, 2), "012}")
        self.assertEqual(c.encode_signed(D("0.05"), 4, 2), "000E")
        self.assertEqual(c.encode_signed(D("-0.05"), 4, 2), "000N")

    def test_encode_truncates_extra_digits(self):
        self.assertEqual(c.encode_signed(D("1.239"), 4, 2), "012C")
        # high-order digits are dropped: 12345600 -> 5600
        self.assertEqual(c.encode_signed(D("123456.00"), 4, 2), "560{")

    def test_decode_invalid(self):
        with self.assertRaises(ValueError):
            c.decode_signed("12x", 2)
        with self.assertRaises(ValueError):
            c.decode_signed("", 2)
        with self.assertRaises(ValueError):
            c.decode_unsigned("12a")

    def test_unsigned_unsigned_digit_is_positive(self):
        self.assertEqual(c.decode_signed("00123", 2), D("1.23"))


class RecordTests(unittest.TestCase):
    def test_tcatbal_roundtrip(self):
        r = bal(amount="-45.67")
        text = r.to_record()
        self.assertEqual(len(text), c.TCATBAL_LEN)
        self.assertEqual(c.TranCatBal.from_record(text), r)

    def test_xref_roundtrip(self):
        x = xref()
        text = x.to_record()
        self.assertEqual(len(text), c.XREF_LEN)
        self.assertEqual(c.CardXref.from_record(text), x)

    def test_discgrp_roundtrip(self):
        d = rate(r="18.50")
        text = d.to_record()
        self.assertEqual(len(text), c.DISCGRP_LEN)
        self.assertEqual(c.DisclosureGroup.from_record(text), d)

    def test_account_roundtrip_preserves_filler(self):
        a = acct(bal="-10.50")
        a.filler = "X" * 178
        text = a.to_record()
        self.assertEqual(len(text), c.ACCOUNT_LEN)
        self.assertEqual(c.Account.from_record(text), a)
        self.assertEqual(c.Account.from_record(text).filler, "X" * 178)

    def test_transaction_roundtrip(self):
        t = c.build_interest_transaction("2022-07-18", 3, acct(), xref(), D("12.34"), NOW)
        text = t.to_record()
        self.assertEqual(len(text), c.TRANSACTION_LEN)
        self.assertEqual(c.Transaction.from_record(text), t)


class InterestMathTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(c.compute_monthly_interest(D("1200.00"), D("12.00")), D("12.00"))

    def test_truncates_not_rounds(self):
        # 100.00 * 18.99 / 1200 = 1.5825 -> 1.58
        self.assertEqual(c.compute_monthly_interest(D("100.00"), D("18.99")), D("1.58"))
        # 100.00 * 19.99 / 1200 = 1.665833 -> 1.66
        self.assertEqual(c.compute_monthly_interest(D("100.00"), D("19.99")), D("1.66"))

    def test_negative_truncates_toward_zero(self):
        self.assertEqual(c.compute_monthly_interest(D("-100.00"), D("18.99")), D("-1.58"))

    def test_zero_balance(self):
        self.assertEqual(c.compute_monthly_interest(D("0.00"), D("18.99")), D("0.00"))


class TimestampTests(unittest.TestCase):
    def test_format(self):
        ts = c.db2_timestamp(NOW)
        self.assertEqual(ts, "2022-07-19-23.16.05.780000")
        self.assertEqual(len(ts), 26)


class RunTests(unittest.TestCase):
    def go(self, tcatbal, xrefs, discs, accounts, **kw):
        return c.run(tcatbal, xrefs, discs, accounts, "2022-07-18",
                     now=FIXED_NOW, log=QUIET, **kw)

    def test_transaction_fields(self):
        accounts = {"00000000001": acct()}
        trans = self.go([bal()], [xref()], [rate()], accounts)
        self.assertEqual(len(trans), 1)
        t = trans[0]
        self.assertEqual(t.tran_id, "2022-07-18000001")
        self.assertEqual(t.type_cd, "01")
        self.assertEqual(t.cat_cd, 5)
        self.assertEqual(t.source, "System")
        self.assertEqual(t.desc, "Int. for a/c 00000000001")
        self.assertEqual(t.amount, D("12.00"))
        self.assertEqual(t.merchant_id, 0)
        self.assertEqual(t.merchant_name, "")
        self.assertEqual(t.card_num, "4111111111111111")
        self.assertEqual(t.orig_ts, "2022-07-19-23.16.05.780000")
        self.assertEqual(t.proc_ts, t.orig_ts)

    def test_zero_rate_writes_nothing(self):
        accounts = {"00000000001": acct()}
        trans = self.go([bal()], [xref()], [rate(r="0.00")], accounts)
        self.assertEqual(trans, [])

    def test_account_updated_when_next_account_starts(self):
        accounts = {"00000000001": acct(), "00000000002": acct("00000000002", bal="50.00")}
        xrefs = [xref(), xref("00000000002", "4222222222222222")]
        tcat = [
            bal(cat="0001", amount="1200.00"),
            bal(cat="0002", amount="600.00"),
            bal("00000000002", amount="1200.00"),
        ]
        discs = [rate(cat="0001", r="12.00"), rate(cat="0002", r="24.00")]
        trans = self.go(tcat, xrefs, discs, accounts)

        self.assertEqual([t.amount for t in trans], [D("12.00"), D("12.00"), D("12.00")])
        self.assertEqual([t.tran_id[-6:] for t in trans], ["000001", "000002", "000003"])
        a1 = accounts["00000000001"]
        self.assertEqual(a1.curr_bal, D("124.00"))
        self.assertEqual(a1.curr_cyc_credit, D("0.00"))
        self.assertEqual(a1.curr_cyc_debit, D("0.00"))
        self.assertEqual(trans[2].card_num, "4222222222222222")

    def test_last_account_not_updated_like_cobol(self):
        accounts = {"00000000001": acct()}
        self.go([bal()], [xref()], [rate()], accounts)
        a = accounts["00000000001"]
        self.assertEqual(a.curr_bal, D("100.00"))
        self.assertEqual(a.curr_cyc_credit, D("5.00"))

    def test_last_account_updated_with_option(self):
        accounts = {"00000000001": acct()}
        self.go([bal()], [xref()], [rate()], accounts, update_last_account=True)
        a = accounts["00000000001"]
        self.assertEqual(a.curr_bal, D("112.00"))
        self.assertEqual(a.curr_cyc_credit, D("0.00"))
        self.assertEqual(a.curr_cyc_debit, D("0.00"))

    def test_total_resets_between_accounts(self):
        accounts = {"00000000001": acct(), "00000000002": acct("00000000002", bal="0.00")}
        xrefs = [xref(), xref("00000000002")]
        tcat = [bal(), bal("00000000002", amount="2400.00"), bal("00000000003")]
        accounts["00000000003"] = acct("00000000003")
        xrefs.append(xref("00000000003"))
        self.go(tcat, xrefs, [rate()], accounts)
        self.assertEqual(accounts["00000000001"].curr_bal, D("112.00"))
        self.assertEqual(accounts["00000000002"].curr_bal, D("24.00"))

    def test_default_group_fallback(self):
        accounts = {"00000000001": acct(group="UNKNOWN")}
        trans = self.go([bal()], [xref()], [rate("DEFAULT", r="6.00")], accounts)
        self.assertEqual(trans[0].amount, D("6.00"))

    def test_specific_group_preferred_over_default(self):
        accounts = {"00000000001": acct()}
        trans = self.go([bal()], [xref()], [rate("DEFAULT", r="6.00"), rate(r="12.00")], accounts)
        self.assertEqual(trans[0].amount, D("12.00"))

    def test_missing_default_group_abends(self):
        accounts = {"00000000001": acct(group="UNKNOWN")}
        with self.assertRaises(c.AbendError) as cm:
            self.go([bal()], [xref()], [rate()], accounts)
        self.assertEqual(cm.exception.code, 999)

    def test_missing_account_abends(self):
        with self.assertRaises(c.AbendError):
            self.go([bal()], [xref()], [rate()], {})

    def test_missing_xref_abends(self):
        with self.assertRaises(c.AbendError):
            self.go([bal()], [], [rate()], {"00000000001": acct()})

    def test_first_xref_wins_for_duplicate_account(self):
        accounts = {"00000000001": acct()}
        xrefs = [xref(card="1111111111111111"), xref(card="2222222222222222")]
        trans = self.go([bal()], xrefs, [rate()], accounts)
        self.assertEqual(trans[0].card_num, "1111111111111111")

    def test_empty_input(self):
        self.assertEqual(self.go([], [], [], {}), [])

    def test_short_parm_date_is_padded(self):
        accounts = {"00000000001": acct()}
        trans = c.run([bal()], [xref()], [rate()], accounts, "2022", now=FIXED_NOW, log=QUIET)
        self.assertEqual(len(trans[0].tran_id), 16)
        self.assertEqual(trans[0].tran_id, "2022      000001")

    def test_logging(self):
        lines = []
        c.run([], [], [], {}, "2022-07-18", log=lines.append)
        self.assertEqual(lines[0], "START OF EXECUTION OF PROGRAM CBACT04C")
        self.assertEqual(lines[-1], "END OF EXECUTION OF PROGRAM CBACT04C")


class MainTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def write(self, name, records):
        c.write_records(self.path(name), records)

    def args(self, *extra):
        return ["--date", "2022-07-18", "--tcatbal", self.path("tcat"),
                "--xref", self.path("xref"), "--discgrp", self.path("disc"),
                "--acct", self.path("acct"), "--transact", self.path("tran"), *extra]

    def setup_files(self):
        self.write("tcat", [bal("00000000002").to_record(), bal().to_record()])  # unsorted
        self.write("xref", [xref().to_record(), xref("00000000002").to_record()])
        self.write("disc", [rate().to_record()])
        self.write("acct", [acct().to_record(), acct("00000000002").to_record()])

    def test_end_to_end(self):
        self.setup_files()
        rc = c.main(self.args())
        self.assertEqual(rc, 0)
        trans = [c.Transaction.from_record(r) for r in c.read_records(self.path("tran"))]
        self.assertEqual([t.desc.rstrip() for t in trans],
                         ["Int. for a/c 00000000001", "Int. for a/c 00000000002"])
        accts = {a.acct_id: a for a in map(c.Account.from_record, c.read_records(self.path("acct")))}
        self.assertEqual(accts["00000000001"].curr_bal, D("112.00"))
        self.assertEqual(accts["00000000002"].curr_bal, D("100.00"))  # last, not updated

    def test_update_last_flag(self):
        self.setup_files()
        c.main(self.args("--update-last-account"))
        accts = {a.acct_id: a for a in map(c.Account.from_record, c.read_records(self.path("acct")))}
        self.assertEqual(accts["00000000002"].curr_bal, D("112.00"))

    def test_abend_leaves_outputs_untouched(self):
        self.setup_files()
        self.write("xref", [])
        before = open(self.path("acct")).read()
        rc = c.main(self.args())
        self.assertEqual(rc, 1)
        self.assertEqual(open(self.path("acct")).read(), before)
        self.assertFalse(os.path.exists(self.path("tran")))

    def test_missing_input_file(self):
        self.setup_files()
        os.remove(self.path("disc"))
        self.assertEqual(c.main(self.args()), 1)

    def test_bad_numeric_data(self):
        self.setup_files()
        self.write("tcat", ["0000000000101" + "0001" + "BAD!BAD!BAD"])
        self.assertEqual(c.main(self.args()), 1)


if __name__ == "__main__":
    unittest.main()
