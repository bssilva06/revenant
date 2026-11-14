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
