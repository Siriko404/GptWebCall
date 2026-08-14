"""Install GPT Web Call end to end. One command, run once, from the checkout.

There are two halves to an installation and they used to be separate errands:
the native-messaging host that lets Chrome talk to the companion, and the
`webcall` skills that give an agent session a way to drive it. Neither is useful
without the other, and doing one and forgetting the other produces a system that
looks installed and does nothing.

    python scripts/setup.py
    python scripts/setup.py --dry-run    # report the plan, change nothing

Everything a machine can do is done here. Two things are left, and they are
stated at the end rather than assumed: a person loads the unpacked extension in
Chrome, because Chrome has no supported way to let a script do that, and a
person restarts Claude Code, because slash commands register at startup.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GUIDE = """\
How to use it, in full:

  /webcall:prep   describe the task; it writes the request, freezes the files
                  and hands you an exchange to launch
  /webcall:menu   everything else: status, health, finish, repair, stop, delete
  /webcall:init   recheck this installation and run a live smoke test

  In the side panel: Go -> click ChatGPT's own Attach files -> check what
  attached -> Send -> download the one archive -> Done and validate.

  The extension never sends and never reads the reply page. Those clicks are
  yours by design, not by omission.
"""


def run(command: list[str], what: str) -> None:
    print(f"\n--- {what} ---", flush=True)
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(
            f"\n{what} failed with exit code {result.returncode}. "
            "Nothing further was attempted; read the output above."
        )


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv

    if os.name != "nt":
        print(
            "GPT Web Call installs on Windows only: it registers a Chrome native "
            "host under HKCU and the extension asserts Windows attachment paths.",
            file=sys.stderr,
        )
        return 1
    if sys.version_info < (3, 10):
        print(
            f"Python 3.10 or newer is required; this is {sys.version.split()[0]}.",
            file=sys.stderr,
        )
        return 1
    if not (ROOT / "WEB_CALL_PROTOCOL.md").is_file():
        print(f"not a complete checkout: {ROOT}", file=sys.stderr)
        return 1

    installer = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ROOT / "scripts" / "install.ps1"),
    ]
    if dry_run:
        installer.append("-WhatIf")
    run(installer, "Native messaging host")

    skill = [sys.executable, str(ROOT / "scripts" / "install_skill.py")]
    if dry_run:
        skill.append("--dry-run")
    run(skill, "Claude Code skills")

    if dry_run:
        print("\nDry run. Nothing was changed.")
        return 0

    extension = ROOT / "extension"
    print(
        f"""
=== Two steps left, and both need your hands ===

1. Load the extension. Open chrome://extensions, turn on Developer mode,
   click Load unpacked, and choose:

       {extension}

   If it is already loaded, click its reload button instead. Then open the
   side panel: a green dot means the companion answered.

2. Restart Claude Code. Slash commands register at startup, so /webcall:*
   appears in the next session, not this one.

Then run /webcall:init once. It rechecks everything above and finishes with a
live smoke test it invents on the spot, so a green dot is not the last word.

{GUIDE}"""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
