"""``make mcp`` as the exit check names it (SPEC §20 phase 9): an MCP client lists the tools.

Drives the real Makefile target over stdio through ``kairos_defense.agent.probe``, which covers
the silent ``@`` recipe (make must not echo the command into the protocol stream). The probe's
deadline kills the server, so this never hangs the gate. Run with ``make test-all``.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from kairos_defense.agent.tools import READ_ONLY

pytestmark = pytest.mark.slow


def test_make_mcp_lists_the_read_only_tools(root) -> None:
    res = subprocess.run(
        [sys.executable, "-m", "kairos_defense.agent.probe", "--timeout", "120", "--expect", "6",
         "--", "make", "--no-print-directory", "mcp"],
        cwd=root, capture_output=True, text=True, timeout=300,
    )  # fmt: skip
    assert res.returncode == 0, res.stderr
    lines = res.stdout.splitlines()
    assert lines[:6] == list(READ_ONLY)
    assert lines[-1] == "6 tools from `make --no-print-directory mcp`"
