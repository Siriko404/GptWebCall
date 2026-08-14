"""Work out the Chrome extension ID for this checkout's `extension\\` directory.

The host manifest must pin one exact `chrome-extension://<id>/` origin, and that
id used to be copied by hand off `chrome://extensions`. Thirty-two characters
transcribed by a person is the step an install fails on, and it forced an order
on the install too: the extension had to be loaded before the host could be
registered, because there was no id until then.

Neither is necessary. Chrome derives an unpacked extension's id from where it
sits on disk, so the id exists before Chrome has ever seen the directory, and
once Chrome has seen it the id is recorded in that profile's own preferences.

Three sources, most authoritative first:

1. An id the caller supplies. Nothing overrides an explicit instruction.
2. Chrome's own state: the profile that has this exact directory loaded knows
   its id as a fact rather than a derivation.
3. The derivation: SHA-256 of the absolute path encoded UTF-16LE, first sixteen
   bytes, each hex digit mapped onto a..p. Verified against a real installed
   extension, and it is what lets the host be registered first.

Windows only, like the rest of the installer. UTF-16LE is how Chrome encodes a
path on this platform, and the registry key it pins is per-user.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

ID_PATTERN = "abcdefghijklmnop"


def derive_extension_id(directory: Path) -> str:
    """The id Chrome will give an unpacked extension loaded from `directory`."""
    absolute = str(Path(directory).resolve())
    digest = hashlib.sha256(absolute.encode("utf-16-le")).hexdigest()[:32]
    return "".join(ID_PATTERN[int(char, 16)] for char in digest)


def chrome_user_data() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"


def loaded_extension_id(directory: Path, user_data: Path | None = None) -> str | None:
    """The id Chrome has actually recorded for `directory`, or None.

    Every profile is searched, because the operator may not be using Default and
    an extension loaded in any of them still gets messages from this host. Both
    preference files are read: an unpacked extension normally lands in `Secure
    Preferences`, but older profiles carry it in `Preferences`.
    """
    target = str(Path(directory).resolve()).casefold()
    base = Path(user_data) if user_data is not None else chrome_user_data()
    if not base.is_dir():
        return None
    for profile in sorted(base.iterdir()):
        if not profile.is_dir():
            continue
        for name in ("Secure Preferences", "Preferences"):
            path = profile / name
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            settings = data.get("extensions", {})
            settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
            if not isinstance(settings, dict):
                continue
            for extension_id, value in settings.items():
                if not isinstance(value, dict):
                    continue
                where = value.get("path")
                if isinstance(where, str) and where.casefold() == target:
                    return str(extension_id)
    return None


def wait_for_extension(
    directory: Path, timeout: float = 300.0, poll: float = 2.0
) -> str | None:
    """Block until Chrome reports this directory as a loaded extension.

    Loading an unpacked extension is the one step of the install a machine
    cannot perform. Chrome removed `--load-extension` from stable, and writing
    into a profile's preferences by hand defeats the HMAC that protects them, so
    a person clicks Load unpacked. Verified against Chrome 151: launching with
    `--load-extension` on a fresh profile leaves the extension absent.

    Waiting is not the same as assuming. When this returns an id, Chrome has
    recorded the directory itself, which is the difference between an installer
    that says "now go and click" and one that knows whether the click happened.
    """
    deadline = time.monotonic() + timeout
    while True:
        found = loaded_extension_id(directory)
        if found:
            return found
        if time.monotonic() >= deadline:
            return None
        time.sleep(poll)


def resolve(directory: Path, explicit: str | None = None) -> dict[str, str]:
    """The id to pin, and where it came from."""
    directory = Path(directory)
    derived = derive_extension_id(directory)
    if explicit:
        return {"id": explicit, "source": "given", "derived": derived}
    loaded = loaded_extension_id(directory)
    if loaded:
        return {"id": loaded, "source": "chrome", "derived": derived}
    return {"id": derived, "source": "derived", "derived": derived}


def main(argv: list[str]) -> int:
    directory = Path(argv[0]) if argv else Path(__file__).resolve().parents[1] / "extension"
    if not (directory / "manifest.json").is_file():
        print(f"not an extension directory: {directory}", file=sys.stderr)
        return 1
    print(json.dumps(resolve(directory), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
