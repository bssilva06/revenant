# Revenant: technology

## Stack

- Python 3.12, Hypothesis, pytest, SQLite (run state), JSON files (cases, records).
- FastAPI with Server-Sent Events for progress, and the Python MCP SDK over stdio.
- React, TypeScript, Vite, Tailwind CSS, Radix primitives for The Crypt.
- GnuCOBOL 3.x from Ubuntu 24.04's `gnucobol3` package (3.1.2). Docker. GitHub Actions.

Today only the container image (`docker/Dockerfile`: Ubuntu 24.04, `gnucobol3`,
Python 3.12) and the `./rv` wrapper exist. The rest is planned.

## Toolchain rules

- The engine always runs inside the container, including during local development.
  There is no native macOS COBOL toolchain.
- Do not use `gnucobol4`. On Ubuntu 24.04 it is built without indexed files and
  cannot compile the exhibit. `gnucobol3` reports `indexed file handler: BDB`.
- Build the legacy program with `cobc -x -std=ibm`, linked behind the `RUNINT`
  driver. Build with `./rv exhibits/cbact04c/build.sh`. The script refuses to build
  if any file differs from `exhibits/cbact04c/SHA256SUMS`.
- `./rv <command>` runs a command in the `revenant:dev` image with the repo mounted
  at `/work`. In Milestone 1 it is a passthrough. The engine CLI replaces it in
  Milestone 2.
- Reproduce the Milestone 1 proof with `./rv python3 scripts/m1_proof.py`.

## Data rules

- Money and rates are integers of the smallest unit. No floats.
- Records are fixed-width display items: `PIC X`, `PIC 9`, `PIC S9..V9..`. Packed and
  binary numerics are unsupported and must raise an error naming the item.
- Signed display values use the runtime's own sign convention (last digit `p` to
  `y` for negatives). Compare raw bytes as well as parsed values.
- Port entry point: `run(world, clock) -> Outputs`, with `transactions: bytes`
  (350-byte records) and `accounts: list[bytes]` (300-byte records), formatted by
  the port itself.
- Oracle: `run_oracle(exhibit, world, clock) -> Outputs`, plus `console` and
  `exit_code`. Run each trial in a temporary directory with a fixed clock, a timeout
  and resource limits.
- Disagreement classes: `numeric`, `text`, `format`, `structure`, `error`, `timeout`.

## Testing requirements

- Unit tests for parser, codec and differ.
- Property tests for codec round trips and differ reflexivity.
- Integration test: seed data gives exit code 0 and 50 transaction records.
- Determinism test: 100 identical executions.
- CI: checked port is `AGREED` on 2,000 trials with a fixed seed. Every mutant is
  `DISAGREED` with its expected class. CI regenerates the committed record.

## Security

- No model calls from Revenant code.
- The hosted container is non-root with a read-only image, no MCP server, no
  uploads, one run at a time, and only curated ports.
- Use subprocess argument lists, never shell strings built from input.
