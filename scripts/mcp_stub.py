#!/usr/bin/env python3
"""Stub MCP server for validating how Kiro launches a local server.

Not the Revenant MCP server. It exposes one read-only tool that reports where and how it was
started, so the launch assumptions in the design can be checked from inside Kiro. The real
server (mcp/revenant_mcp/server.py) replaces it in milestone 3.
"""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("revenant")

REPO = Path("/work")


@mcp.tool()
def environment() -> dict:
    """Report where this server is running: host launch directory, container, toolchain."""
    try:
        cobc = subprocess.run(["cobc", "--version"], capture_output=True, text=True,
                              timeout=5).stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        cobc = None
    return {
        "stub": True,
        "host_launch_cwd": os.environ.get("REVENANT_LAUNCH_CWD"),
        "host_repo_root": os.environ.get("REVENANT_HOST_ROOT"),
        "launched_from_workspace_root":
            os.environ.get("REVENANT_LAUNCH_CWD") == os.environ.get("REVENANT_HOST_ROOT"),
        "container_cwd": os.getcwd(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cobc": cobc,
        "repo_mounted": (REPO / "exhibits" / "cbact04c" / "legacy" / "CBACT04C.cbl").exists(),
        "exhibit_built": (REPO / "build" / "cbact04c" / "runint").exists(),
        "steering_files": sorted(p.name for p in (REPO / ".kiro" / "steering").glob("*.md")),
    }


if __name__ == "__main__":
    mcp.run()
