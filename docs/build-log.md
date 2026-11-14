# Build log

## 2026-11-14: Milestone 1, toolchain proof

Tool used: Claude Code, for the environment proof only. No engine, port, spec, steering or
agent file was written in this session; those are to be built in Kiro.

Environment: Apple Silicon Mac, Docker CLI with Colima (aarch64 VM), image `revenant:dev`
from `docker/Dockerfile` (Ubuntu 24.04, `gnucobol3` 3.1.2-5.1ubuntu1, Python 3.12.3).

Observed:

- The arm64 `gnucobol3` package reports `indexed file handler: BDB`. No emulation or source
  build is needed.
- `CBACT04C.cbl` compiles unmodified with `cobc -x -std=ibm`, linked behind the `RUNINT` driver.
- CardDemo seed data: exit code 0, 50 transaction records, 17,500 bytes, 50 accounts unloaded,
  about 15 ms for four loads, the run and one unload.
- Every category balance in the seed data is zero, so every seed transaction amount is zero.
  The seed run exercises the file handling, not the arithmetic.
- Hand-written one-account inputs against a round-half-up calculation:

  | Balance | Rate | Old program | Round half up |
  | --- | --- | --- | --- |
  | 1.00 | 6.00 | 0.00 | 0.01 |
  | 100.50 | 15.00 | 1.25 | 1.26 |
  | -100.50 | 15.00 | -1.25 (bytes `0000000012u`) | -1.26 |
  | 1,234,567.89 | 15.00 | 15,432.09 | 15,432.10 |

- In each one-account input the transaction is written but the account balance stays 0.00,
  consistent with the last-account behaviour described in the design document.
- Negative values round-trip through the old program using the runtime's own sign convention
  (last digit `p` to `y`).

Reproduce:

```
./rv exhibits/cbact04c/build.sh
./rv python3 scripts/m1_proof.py
```

Not done: determinism test, Kiro validation, public repository.
