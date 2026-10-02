"""Run the backend and frontend dev servers together (`just dev`). Ctrl+C stops both.

Output lines are prefixed with [api] / [web]. Docker services must be up (`just up`).
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SERVERS = {
    "api": (["uv", "run", "uvicorn", "app.main:app", "--reload", "--port", "8000"], ROOT / "backend"),
    "web": (["pnpm", "dev"], ROOT / "frontend"),
}


def stream(name: str, proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        print(f"[{name}] {line}", end="", flush=True)


def main() -> int:
    # Windows consoles default to cp1252, which can't print Next.js's "▲" and kills the stream thread
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    procs: dict[str, subprocess.Popen[str]] = {}
    for name, (cmd, cwd) in SERVERS.items():
        if not cwd.exists():
            print(f"[{name}] skipped: {cwd.name}/ does not exist yet")
            continue
        procs[name] = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", shell=sys.platform == "win32",
        )
        threading.Thread(target=stream, args=(name, procs[name]), daemon=True).start()

    print("api: http://localhost:8000/api/v1/health   web: http://localhost:3000   (Ctrl+C to stop)")
    try:
        for proc in procs.values():
            proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in procs.values():
            if proc.poll() is None:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                else:
                    proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
