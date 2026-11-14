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

## 2026-11-14: Foundation steering

Tool used: Kiro IDE, default agent, one chat prompt (session "Create Foundation…"). The prompt
was typed by Claude Code through desktop control; the files were written by Kiro.

- Added `docs/design.md`, the product requirements and technical design.
- Kiro wrote `.kiro/steering/product.md`, `tech.md` and `structure.md` from sections 4 and 14
  of the design, the build log, `UPSTREAM.md` and the file tree. About 0.91 credits, 49 s.

## 2026-11-14: Determinism check

Tool used: Claude Code (toolchain proof, throwaway script `scripts/m1_determinism.py`).

- 100 executions of the seed data and 100 of a one-account input, all exit code 0.
- With `COB_CURRENT_DATE` set, the only transaction bytes that varied were record offsets
  298, 299, 324 and 325: the hundredths digits of `TRAN-ORIG-TS` and `TRAN-PROC-TS`.
- The account file and the console output were identical across all runs.
- Decision confirmed for arm64: pin the clock, mask those four bytes, nothing else.

Reproduce: `./rv python3 scripts/m1_determinism.py`

## 2026-11-14: Stub MCP server for Kiro validation

Tool used: Claude Code (launch plumbing only; the real server is to be built in Kiro).

- Image now includes the Python MCP SDK, pinned to 2.3.0. In SDK 2.x `FastMCP` is renamed
  `MCPServer` (`from mcp.server.mcpserver import MCPServer`); the design's sample uses the
  1.x name.
- `scripts/mcp_stub.py` exposes one read-only tool, `environment`. `scripts/revenant-mcp.sh`
  starts it in the container and resolves the repo from its own location.
- From a shell, launched from `/tmp`: initialize, tools/list and tools/call all succeed.
- Registered in `.kiro/settings/mcp.json`. Kiro did not load it: its log shows the workspace
  is not trusted, which skips workspace-scope MCP config and disables hook execution
  (`workspace scope skipped: workspace is not trusted`,
  `hooks.v2.executionDisabledUntrustedWorkspace`). Kiro's log also shows `autoApprove`
  entries being migrated into a `permissions.yaml`.

- Cause: the Kiro window had been opened before the workspace was trusted, and it kept that
  state. A new chat session did not help; closing and reopening the window did. The same
  stale window was also loading no workspace steering (`[Steering] ExistingFiles:` empty).
- After reopening, Kiro started the container and its default agent called `environment`:
  `launched_from_workspace_root: true`, `repo_mounted: true`, `exhibit_built: true`. So Kiro
  launches local MCP servers with the workspace root as the working directory, and the
  relative path in `mcp.json` works. The session also showed "Included Steering".
- Kiro reported "Migrated 1 MCP tool auto-approval to Trust v2": the `autoApprove` entry was
  copied into a per-workspace `permissions.yaml` under `~/.kiro/workspace-roots/`.

## 2026-11-14: Kiro agent permissions and hook validation

Tools used: Kiro IDE wrote `.kiro/agents/verifier.*`, `.kiro/agents/porter.*` and
`.kiro/hooks/scratch-save-log.json` from section 6 of the design (default agent, sessions
"Set Up Kiro Verifica…" and "Create Porter Cust…"). Claude Code typed the prompts through
desktop control, ran the tests and changed one line of the hook (see below).

Hook (`PostFileSave`, command action):

- Did not fire when the agent created a new file. Kiro has separate File Create and File Save
  triggers.
- Did not fire on an edit while the matcher was `^scratch/.*\.txt$`. It fired once the `^`
  was removed, so the matcher is tested against a path that does not start at the workspace
  root (Kiro's log shows absolute paths). The design's sample matcher
  `^ports/cbact04c/.*\.py$` would never fire; use `ports/cbact04c/.*\.py$`.
- The command ran with the workspace root as its working directory.
- A hook file added mid-session was not registered until a new session started
  (`hooks.reload.loaded {"read":0}` then `{"read":1,"registered":1}`). A later edit to the
  hook file took effect in the same session.

Verifier (`tools: ["read", "@revenant"]`, deny all `fs_write`):

- Called `environment` on the `revenant` MCP server; Kiro logged the policy result as allow.
- Has no write tool and no shell tool at all, so it could not attempt either. The separation
  here comes from the `tools` list; its deny rule was not exercised.

Porter (`tools: ["read", "write", "@revenant"]`, allow `ports/cbact04c/**`, deny the rest):

- Write to `ports/cbact04c/permission-probe.txt`: allowed.
- Write to `scratch/porter-outside.txt` and append to `docs/build-log.md`: both refused with
  "Blocked by a permission rule (deny fs_write matching \"**\"); the user did not reject it.
  Source: agent-profile."
- So the allow rule plus the deny rule with `exclude` behaves as the design intends.

Not tested: whether the Porter has any shell access that could bypass the write rule, and
the behaviour of all of the above in the Kiro CLI. Test files were deleted afterwards.

## 2026-11-14: First AI attempt frozen and checked by hand

Tools used: Kiro IDE wrote the port (see `ports/cbact04c/first_attempt/PROMPT.md`). Claude
Code copied it in unchanged and wrote the throwaway comparison `scripts/first_attempt_check.py`.

Four hand-written worlds: three one-account probes (1.00 at 6.00, 100.50 at 15.00, -100.50 at
15.00) and one with two accounts, a default-group fallback and a zero rate. The port received
the same logical values through its own `run()` and formatted its own records.

- Against the witness as built so far (GnuCOBOL default sign convention): every decoded value
  agrees, including truncation, the unposted last account, the default-group fallback and the
  skipped zero rate. Every text field and filler is byte-identical. The only differences are
  class `format`, on every signed field: the witness writes `00000000125` and `0000000012u`,
  the port writes `0000000012E` and `0000000012N`.
- The port's convention is the mainframe one, which is also what CardDemo's seed data uses.
- Against a witness built with `cobc -fsign=EBCDIC`: all four worlds are byte-identical after
  the timestamp mask. The seed data also runs to exit 0 with 50 records under that build and
  keeps its `{` signs.

Consequences:

- The first AI attempt does not disagree with the old program on these inputs. This is four
  hand-written inputs, not a verification run; generated inputs may still find something.
- The sign difference comes from the GnuCOBOL default, not from the port. Decision needed:
  build the exhibit with `-fsign=EBCDIC` so the witness matches the original platform's
  convention. That would also remove the silent mis-read of seed-data negatives.

Reproduce: `./rv python3 scripts/first_attempt_check.py`, and with `REVENANT_SIGN=EBCDIC`
after building `build/cbact04c-ebcdic` with the extra flag.

## 2026-11-14: Exhibit now built with mainframe sign encoding

Decision by the owner, following the first-attempt check: build with `cobc -fsign=EBCDIC`.
This replaces the design's decision to use the runtime's native sign convention.

- `exhibits/cbact04c/build.sh` adds the flag for the legacy program and the utilities.
- Signed display fields now use the overpunch `{`, `A` to `I` (positive) and `}`, `J` to `R`
  (negative). The four probes give the same values as before with new bytes: 1.25 is
  `0000000012E`, -1.25 is `0000000012N`.
- Seed data: exit 0, 50 records, and its `{` signs are preserved through the run.
- Determinism rerun: 100 executions of two inputs, only the four timestamp-hundredths bytes vary.
- First AI attempt: all four hand-written worlds byte-identical after the timestamp mask.
- `.kiro/steering/tech.md` corrected by hand (two lines) to state the new convention.
- `docs/design.md` is unchanged and still describes the native convention in sections 5 and 12.

Tool used: Claude Code.

## 2026-11-14: copybook-codec spec, requirements stage

Tool used: Kiro IDE, Spec agent, "Build a Feature" (requirements-first). Kiro wrote
`.kiro/specs/copybook-codec/requirements.md`: 11 requirements in EARS form with round-trip,
idempotence, invariant and error-condition properties.

Review before approval (Claude Code checked the file against the copybooks, the seed data and
the old program; the owner sent the corrections to Kiro, which revised the file):

- `ACCT-EXPIRAION-DATE` offset corrected from 35 to 58.
- A sign test through the load and unload utilities was replaced, since those copy bytes
  without interpreting them. The test now runs the old program and compares `TRAN-AMT` bytes.
- Added: pinned pytest and Hypothesis in the image, and an import check for the engine package.
- A pretty-printer was removed from the product; the parser round trip uses a test-only helper.

New observations used as acceptance values: a negative amount that truncates to zero is
written as positive zero (`-1.00` at `6.00` gives `0000000000{`), and `-1.20` at `10.00`
gives `0000000000J`. All 201 seed lines decode under the spec's rules.
