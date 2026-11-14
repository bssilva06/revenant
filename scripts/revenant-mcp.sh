#!/usr/bin/env bash
# Starts the Revenant MCP server on stdio inside the container, with the repo mounted.
# Kiro launches this from .kiro/settings/mcp.json. It resolves the repo from its own
# location, so it works whatever directory Kiro starts it in.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
image="${REVENANT_IMAGE:-revenant:dev}"

# A GUI-launched app may not inherit the shell's PATH.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# stdout carries the protocol, so anything else must go to stderr.
if ! docker image inspect "$image" >/dev/null 2>&1; then
  echo "revenant-mcp: image $image not found; run ./rv true once to build it" >&2
  exit 1
fi

exec docker run --rm -i \
  -e REVENANT_LAUNCH_CWD="$PWD" \
  -e REVENANT_HOST_ROOT="$root" \
  -v "$root":/work -w /work \
  "$image" python3 scripts/mcp_stub.py
