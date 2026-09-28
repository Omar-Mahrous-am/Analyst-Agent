# workflows/mcp_server.py
import asyncio
import uuid
from asyncio.subprocess import DEVNULL, PIPE

from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP(
    name="Secure Python Runner",
    instructions="Runs Python code inside an isolated, network-less Docker sandbox.",
)

IMAGE = "python-sandbox"        # built from workflows/Dockerfile.sandbox
TIMEOUT_SECONDS = 30            # pandas imports are slow, so 10s is too tight
MAX_OUTPUT_CHARS = 5_000_000    # base64 charts are large; a truncated chart can't be decoded


@mcp.tool()
async def run_python(
    code: str = Field(description="Complete Python code. Use print() to show results."),
) -> str:
    """Run Python code in an isolated Docker sandbox and return its output.

    Limits: no internet access, 512MB memory, 30 second timeout.
    Files are not kept between calls. You must use print() to see any result.
    """
    # Unique name so we can kill exactly this container if it times out
    name = f"sandbox-{uuid.uuid4().hex[:12]}"

    cmd = [
        "docker", "run",
        "--rm",                                   # delete the container when it exits
        "-i",                                     # keep stdin open so we can pipe the code in
        "--name", name,
        "--network", "none",                      # no network at all
        "--memory", "512m",
        "--memory-swap", "512m",                  # same value = no swap to bypass the limit
        "--cpus", "1",
        "--pids-limit", "128",                    # blocks fork bombs (numpy needs a few threads)
        "--read-only",                            # read-only root filesystem
        "--tmpfs", "/tmp:rw,noexec,size=64m",     # small writable scratch space in memory
        "--cap-drop", "ALL",                      # drop all Linux capabilities
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",                  # run as 'nobody', not root
        "-e", "HOME=/tmp",                        # matplotlib needs a writable home/cache dir
        "-e", "MPLCONFIGDIR=/tmp",
        "-e", "OPENBLAS_NUM_THREADS=1",           # keep numpy from spawning many threads
        IMAGE,
        "python", "-",                            # read the script from stdin
    ]

    # asyncio keeps the server responsive while the code runs
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE
    )

    try:
        # Send the code via stdin (avoids shell quoting and injection problems)
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(code.encode()),
            timeout=TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        # Kill the container itself, not just the local `docker` command,
        # otherwise an infinite loop would keep running in the background
        killer = await asyncio.create_subprocess_exec(
            "docker", "kill", name, stdout=DEVNULL, stderr=DEVNULL
        )
        await killer.wait()
        proc.kill()
        return (
            f"Execution stopped: exceeded the {TIMEOUT_SECONDS}s timeout. "
            "Check for an infinite loop."
        )

    out = stdout.decode(errors="replace")
    err = stderr.decode(errors="replace")

    # Exit code 137 usually means the process was killed (often out of memory)
    if proc.returncode == 137:
        return "Execution stopped: memory limit exceeded."

    result = out
    if err:
        result += f"\n[stderr]\n{err}"

    if len(result) > MAX_OUTPUT_CHARS:
        result = result[:MAX_OUTPUT_CHARS] + "\n... (output truncated)"

    return result or "(No output. Did you forget to use print()?)"


if __name__ == "__main__":
    mcp.run()  # stdio transport; never use print() in this file, stdout carries the protocol