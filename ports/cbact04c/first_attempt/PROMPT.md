# First AI attempt: provenance

This folder is frozen. `cbact04c.py` and `test_cbact04c.py` are Kiro's output, copied without
any change. Do not edit them.

| Item | Value |
| --- | --- |
| Date | 2026-11-14, about 13:07 MST |
| Tool | Kiro IDE, default agent, model set to Auto |
| Workspace | A separate folder holding only `CBACT04C.cbl` and its five copybooks, all matching the pinned upstream hashes. No steering, specs, hooks, agents or MCP servers |
| Revenant tools available | None |
| Follow-up prompts | None |
| Credits, time | 2.46 credits, 1 min 59 s |

## Prompt, verbatim

```
Port this program to Python and write unit tests.
```

## Its own tests

`python3 -m unittest`: 35 tests, all passing, on Python 3.15.2 on the host. Kiro had three
failures on its first run, edited `cbact04c.py` to strip trailing spaces from text fields when
parsing, and reran to 35 passing, all within the one session.

## File hashes (SHA-256)

```
8c65fd50d9309e97bf059039c15bf4900f139800d21bcc6aa7b5c6faab953fa1  cbact04c.py
9b00fbf37ce457eb945b3d5ff4807fcf9a2b0342713c4a352f31c88d27e2263d  test_cbact04c.py
```

## What Kiro said about its port

- Interest is truncated to two decimals, not rounded, as in the COBOL.
- The last account is never updated, as in the COBOL. It kept that behaviour and added an
  `update_last_account` option, off by default.
- Signed numbers use COBOL sign overpunch (`{` for +0, `}` for -0).
- Outputs are written only after a successful run; the COBOL would leave partial output on
  an abend.
