"""The install is only worth anything if a stranger can run it.

These cover the parts of it that are ordinary code: working out the extension
ID, and the documents that tell an agent what to run. What Chrome does with a
registry key is not testable here; what we hand Chrome is.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from extension_id import (  # noqa: E402
    derive_extension_id,
    loaded_extension_id,
    resolve,
)


class ExtensionIdTests(unittest.TestCase):
    def test_the_id_is_derived_the_way_chrome_derives_it(self):
        """Pinned against a real installed extension.

        Chrome hashes the absolute path encoded UTF-16LE, keeps sixteen bytes,
        and maps each hex digit onto a..p. This pair was read off a working
        machine: the directory, and the ID Chrome gave it. If this ever breaks,
        the host will pin an origin Chrome does not use and the side panel will
        say the companion is unavailable with nothing else wrong.
        """
        self.assertEqual(
            derive_extension_id(
                Path(r"C:\GptWebCall\extension")
            ),
            "ffibgohmjphlbdjfjgddjdfemfemecmm",
        )

    def test_every_derived_id_is_thirty_two_characters_of_a_to_p(self):
        for name in ("extension", "Extension Files", "a"):
            with self.subTest(name=name):
                value = derive_extension_id(Path("C:/somewhere") / name)
                self.assertEqual(len(value), 32)
                self.assertTrue(set(value) <= set("abcdefghijklmnop"), value)

    def test_the_derivation_does_not_depend_on_the_directory_existing(self):
        """The pinned pair above was measured on a machine where that path
        exists. `resolve()` is allowed to consult the filesystem, so if it ever
        rewrote an existing path the test would pass there and fail on every
        machine that has never had that directory. Same string in, same id out,
        present or not."""
        present = Path(__file__).resolve().parents[2] / "extension"
        self.assertTrue(present.is_dir(), "fixture assumes this checkout")
        absent = Path(str(present) + "-does-not-exist")

        self.assertEqual(
            derive_extension_id(present),
            derive_extension_id(Path(str(present))),
        )
        self.assertNotEqual(derive_extension_id(present), derive_extension_id(absent))

    def test_a_different_directory_gets_a_different_id(self):
        """Two checkouts are two extensions, which is why the path is the input
        and why moving a checkout means installing again."""
        self.assertNotEqual(
            derive_extension_id(Path("C:/one/extension")),
            derive_extension_id(Path("C:/two/extension")),
        )

    def test_chrome_s_own_record_is_read_when_it_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            extension = base / "checkout" / "extension"
            extension.mkdir(parents=True)
            profile = base / "User Data" / "Profile 6"
            profile.mkdir(parents=True)
            (profile / "Secure Preferences").write_text(
                json.dumps(
                    {
                        "extensions": {
                            "settings": {
                                "unrelatedextensionidentifierxx": {
                                    "path": str(base / "elsewhere")
                                },
                                "aaaabbbbccccddddeeeeffffgggghhhh": {
                                    "path": str(extension)
                                },
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            found = loaded_extension_id(extension, user_data=base / "User Data")

            self.assertEqual(found, "aaaabbbbccccddddeeeeffffgggghhhh")

    def test_an_unreadable_or_absent_profile_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            extension = base / "extension"
            extension.mkdir()
            profile = base / "User Data" / "Default"
            profile.mkdir(parents=True)
            (profile / "Secure Preferences").write_text("{not json", encoding="utf-8")

            self.assertIsNone(
                loaded_extension_id(extension, user_data=base / "User Data")
            )
            self.assertIsNone(loaded_extension_id(extension, user_data=base / "gone"))

    def test_an_explicit_id_overrides_everything_and_still_reports_the_derivation(self):
        with tempfile.TemporaryDirectory() as temp:
            extension = Path(temp) / "extension"
            extension.mkdir()

            answer = resolve(extension, explicit="p" * 32)

            self.assertEqual(answer["id"], "p" * 32)
            self.assertEqual(answer["source"], "given")
            # Reported so a caller can see the two disagree.
            self.assertEqual(answer["derived"], derive_extension_id(extension))

    def test_the_derivation_is_used_when_chrome_has_never_seen_the_directory(self):
        """This is what lets the host be registered before anyone opens Chrome,
        which is what removes the ordering constraint from the install."""
        with tempfile.TemporaryDirectory() as temp:
            extension = Path(temp) / "extension"
            extension.mkdir()

            answer = resolve(extension)

            self.assertEqual(answer["source"], "derived")
            self.assertEqual(answer["id"], derive_extension_id(extension))


class PinnedManifestTests(unittest.TestCase):
    def test_the_rendered_host_manifest_is_read_through_its_bom(self):
        """PowerShell writes one, and reading strictly hid a real bug.

        `Set-Content -Encoding UTF8` prefixes a BOM, so the manifest this
        repository generates starts with one. Reading it as plain utf-8 raised,
        the caller took the exception as "nothing is pinned", and concluded the
        pin disagreed with Chrome — repinning an installation that was already
        correct. Chrome takes the BOM without complaint, which is why it went
        unnoticed until something else read the file.
        """
        setup = (ROOT / "scripts" / "setup.py").read_text(encoding="utf-8")
        self.assertIn('read_text(encoding="utf-8-sig")', setup)

        installed = ROOT / "native-host" / "com.sina.gptwebcall.json"
        if not installed.is_file():
            self.skipTest("no host manifest on this machine")
        # Whatever the encoding, the shipped reader must cope with the file the
        # shipped installer writes.
        value = json.loads(installed.read_text(encoding="utf-8-sig"))
        self.assertEqual(len(value["allowed_origins"]), 1)


class InstallDocumentationTests(unittest.TestCase):
    def test_one_command_installs_both_halves_and_the_extension(self):
        setup = (ROOT / "scripts" / "setup.py").read_text(encoding="utf-8")

        self.assertIn("install.ps1", setup)
        self.assertIn("install_skill.py", setup)
        # The extension step is walked through and then verified, not left as an
        # instruction the installer hopes was followed.
        self.assertIn("chrome://extensions", setup)
        self.assertIn("wait_for_extension", setup)
        self.assertIn("confirm_pinned_id", setup)
        self.assertIn("Restart Claude Code", setup)

    def test_the_readme_opens_on_the_link_and_the_one_command(self):
        """The entry point is a repository link handed to Claude, so the clone
        target is named rather than left as a decision."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        head = readme[:1200]

        self.assertIn("git clone https://github.com/Siriko404/GptWebCall.git", head)
        self.assertIn("python scripts/setup.py", head)
        self.assertIn("$HOME\\GptWebCall", head)

    def test_the_readme_points_a_reader_at_that_one_command(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("python scripts/setup.py", readme)
        # The transcription step is gone and must not creep back. Checked as an
        # instruction rather than a substring: the README is free to say the
        # string is never typed, which is the opposite of asking for it.
        self.assertNotIn("read back its", readme)
        self.assertNotIn("reading back its", readme)
        self.assertIn("You never read or type a 32-character string", readme)

    def test_the_installer_no_longer_demands_an_id(self):
        installer = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")

        self.assertNotIn("Mandatory = $true", installer)
        self.assertIn("extension_id.py", installer)

    def test_init_installs_without_asking_anyone_to_read_an_id(self):
        init = (
            ROOT / "skill" / "webcall" / "skills" / "init" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("scripts/setup.py", init)
        self.assertNotIn("read back the 32-character ID", init)


if __name__ == "__main__":
    unittest.main()
