# Revenant: product

Revenant checks a Python replacement for a legacy COBOL batch program. It runs the
old program and the port on the same generated inputs, reports the smallest input on
which they differ, and writes a reproducible record of what was tested.

Revenant verifies. It does not translate. The legacy program is the oracle.

## Status

Milestone 1 (toolchain proof) is done. See `docs/build-log.md`. Everything else below
is planned and does not exist yet: the engine, the MCP server, the API, The Crypt,
ports, agents, hooks and specs. Do not describe planned parts as working.

## Exhibit

The first and only exhibit is `CBACT04C.cbl` from AWS CardDemo (commit `59cc6c2f`),
an interest calculation batch job. Source: `exhibits/cbact04c/`.

## Planned parts

- **Engine**: copybook parser, codec, world model, oracle runner, differ, Hypothesis
  runner, record writer, CLI.
- **MCP server**: exposes engine functions as tools to Kiro agents.
- **API and The Crypt**: FastAPI plus a React page with two panes, run controls, live
  progress, disagreement detail and records.
- **Kiro agents**: Archaeologist (documents behaviour), Porter (writes the port),
  Verifier (runs verification).
- **Ports**: a checked port, a frozen first AI attempt with its prompt, and at least
  two labelled mutants.

## Non-negotiable requirements

1. The legacy source is never modified. The driver and file load/unload utilities are
   separate files.
2. No floats for business values. Money and rates are integers of the smallest unit
   in every interface.
3. No model calls inside Revenant. All AI reasoning happens in Kiro.
4. A passing run is described as "no disagreement in N generated trials within
   profile P". Never "proven", "equivalent" or a confidence percentage.
5. Oracle errors and timeouts are never counted as agreement.
6. Every disagreement is stored as explicit input JSON and replayed first on later
   runs.
7. Unsupported data clauses raise an error naming the item. Nothing is guessed.
8. The public service executes only code baked into its image and accepts only
   validated values. No uploads.
9. Revenant never edits a port and never decides that a disagreement is acceptable.
10. The repository is public, Apache 2.0, with `/.kiro` at the root and tracked by git.

## Verdicts

`AGREED`, `DISAGREED`, `AGREED_WITH_ACCEPTED_DIVERGENCE`, `INCONCLUSIVE`.

## Out of scope

Translation engines, other languages, procedure-code parsing, packed or binary
numerics, repeating groups, redefinitions, screens, databases, queues, job control,
invalid-input testing, console-output comparison, performance comparison, accounts,
uploads, WebAssembly, multi-agent frameworks.

No text in the product or its documents may claim proof.
