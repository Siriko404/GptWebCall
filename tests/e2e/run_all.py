"""Run every suite the repository has, in dependency order.

The Python counterpart of run_all.ps1. Each stage stops the run with its name
in the message, so a failure is attributed before anything downstream runs on
top of it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def run(command: list[str], stage: str) -> None:
    print(f"\n=== {stage} ===", flush=True)
    result = subprocess.run(command, cwd=REPOSITORY_ROOT)
    if result.returncode != 0:
        raise SystemExit(f"{stage} failed with exit code {result.returncode}.")


def main() -> int:
    run(["gofmt", "-l", "."], "gofmt")
    run(["go", "test", "./...", "-race", "-count=1"], "Go tests")
    run(
        [sys.executable, "-m", "unittest", "discover", "-s", "companion/tests", "-v"],
        "Python tests",
    )
    npm = shutil.which("npm")
    if npm:
        run([npm, "--prefix", "extension", "test"], "Extension tests")
    else:
        print("\n=== Extension tests ===\nskipped: npm not found")
    if shutil.which("go"):
        run(["/bin/sh", str(HERE / "build.sh")], "Native host build")
    run([sys.executable, str(HERE / "fixture_call.py")], "Fixture call")
    run([sys.executable, str(HERE / "manual_fallback.py")], "Manual fallback")
    run(["git", "diff", "--check"], "Git whitespace validation")
    print("\nAll stages passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
