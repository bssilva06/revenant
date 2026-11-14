# Revenant: repository structure

## Exists today (Milestone 1)

```text
.kiro/steering/        product.md  tech.md  structure.md
docker/Dockerfile      toolchain image (revenant:dev)
docs/                  design.md  build-log.md
exhibits/cbact04c/
  legacy/              CBACT04C.cbl  cpy/*.cpy   verbatim upstream, never edited
  support/             RUNINT.cbl  load-unload/*.cbl   driver and file utilities
  seed/                CardDemo seed data (4 files)
  build.sh             verifies hashes, then builds with cobc
  SHA256SUMS           pins every upstream file
  UPSTREAM.md  NOTICE  LICENSE.upstream
scripts/m1_proof.py    Milestone 1 proof
rv                     runs a command inside the container
build/                 build output, git-ignored
```

## Planned, not yet created

```text
.kiro/specs/ hooks/ agents/ settings/    specs, post-edit hook, three agents, MCP config
exhibits/cbact04c/exhibit.toml           files, schemas, normalisations, profiles
exhibits/cbact04c/world.py               world model and physical file mapping
exhibits/cbact04c/regressions/           C-0001.json ...   stored disagreements
ports/cbact04c/checked/                  port.py  tests/
ports/cbact04c/first_attempt/            port.py  PROMPT.md   frozen, never edited
ports/cbact04c/mutants/                  round_half_up.py  post_every_account.py  float_math.py
engine/revenant/                         copybook, codec, oracle, differ, runner, record, cli
mcp/revenant_mcp/server.py               MCP server, thin wrapper over the engine
api/                                     app.py  runs.py  sse.py
crypt/                                   React app
power/revenant/                          Kiro power package
records/cbact04c/*.json                  committed verification records
tests/                                   unit/  property/  integration/
.github/workflows/ci.yml
README.md  pyproject.toml  docker/compose.yaml  scripts/revenant-mcp.sh
```

Also planned: `.kiro/steering/cobol-semantics.md`, and `docs/kiro-usage.md` and
`docs/architecture.md`.

## Conventions

- Create a planned path only when its milestone starts. Check the file exists before
  describing it as present.
- Never edit anything under `exhibits/cbact04c/legacy/` or the pinned upstream files.
  If a hash in `SHA256SUMS` changes, something is wrong.
- Support files (driver, loaders) go in `support/`, never in `legacy/`.
- `ports/.../first_attempt/` is frozen. `mutants/` are labelled and each has an
  expected disagreement class.
- Engine core stays exhibit-agnostic. Exhibit-specific logic lives in
  `exhibits/<name>/world.py`.
- The MCP server and API add no logic of their own. They call the engine.
- The Porter agent may write only under `ports/`.
- Build log entries go in `docs/build-log.md`, stating which tool was used.
- `.kiro/` must stay tracked by git. Do not add it to `.gitignore`.

## Roadmap

1. Toolchain proof (done).
2. Verification engine.
3. Kiro integration.
4. The Crypt.
5. Submission.
