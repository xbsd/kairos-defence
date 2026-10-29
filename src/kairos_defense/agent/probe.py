"""A minimal MCP client for the exit check: start a server over stdio and list its tools.

``python -m kairos_defense.agent.probe [--timeout 90] [--expect N] -- make mcp`` prints one tool
name per line and a count, and exits 0 (1 on a timeout, an error, or a count other than
``--expect``). The deadline kills the server process, so a stuck server never hangs a gate.
"""

from __future__ import annotations

import argparse
import os
import sys


async def list_tools(cmd: list[str], timeout_s: float = 90.0, cwd: str | None = None) -> list[str]:
    """Tool names of the MCP server started by ``cmd`` (stdio), within ``timeout_s`` seconds."""
    import anyio
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(command=cmd[0], args=list(cmd[1:]), env=dict(os.environ),
                                   cwd=cwd or os.getcwd())  # fmt: skip
    with anyio.fail_after(timeout_s):
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            res = await session.list_tools()
            return [t.name for t in res.tools]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[argv.index("--") + 1 :] if "--" in argv else []
    opts = argv[: argv.index("--")] if "--" in argv else argv
    p = argparse.ArgumentParser(prog="python -m kairos_defense.agent.probe",
                                description="List an MCP server's tools over stdio.")  # fmt: skip
    p.add_argument("--timeout", type=float, default=90.0, help="seconds before giving up")
    p.add_argument("--expect", type=int, default=None, help="fail unless this many tools")
    a = p.parse_args(opts)
    if not cmd:
        p.error("give the server command after --, e.g. -- make mcp")
    import anyio

    try:
        names = anyio.run(list_tools, cmd, a.timeout)
    except TimeoutError:
        sys.stderr.write(f"no answer from `{' '.join(cmd)}` within {a.timeout:g} s\n")
        return 1
    except Exception as exc:  # report any client or server failure as a failed probe
        sys.stderr.write(f"probe failed: {type(exc).__name__}: {exc}\n")
        return 1
    sys.stdout.write("".join(f"{n}\n" for n in names))
    sys.stdout.write(f"{len(names)} tools from `{' '.join(cmd)}`\n")
    return 0 if a.expect is None or len(names) == a.expect else 1


if __name__ == "__main__":
    sys.exit(main())
