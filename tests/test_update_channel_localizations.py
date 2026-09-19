import json
import tempfile
import unittest
from pathlib import Path

import update_channel_localizations as cli


def _entry(
    studio_locale="en_US",
    *,
    studio_name="English",
    api_language="en",
    title="Example channel",
    description="Example description",
):
    return {
        "studioLocale": studio_locale,
        "studioName": studio_name,
        "apiLanguage": api_language,
        "title": title,
        "description": description,
    }


def _payload(*entries, expected_count=None):
    data = {"schemaVersion": 1, "entries": list(entries)}
    if expected_count is not None:
        data["expectedStudioLocaleCount"] = expected_count
    return data


class ChannelLocalizationCliTests(unittest.TestCase):
    def _write_payload(self, payload):
        temporary = tempfile.TemporaryDirectory()
        path = Path(temporary.name) / "channel-localizations.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        self.addCleanup(temporary.cleanup)
        return path

    def test_load_catalog_accepts_local_fixture(self):
        path = self._write_payload(
            _payload(
                _entry(),
                _entry(
                    "fr_FR",
                    studio_name="French",
                    api_language="fr",
                    title="Chaîne exemple",
                    description="Description exemple",
                ),
                expected_count=2,
            )
        )
        loaded = cli.load_catalog(path)
        self.assertEqual(2, len(loaded["entries"]))

    def test_load_catalog_reports_missing_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.json"
            with self.assertRaisesRegex(
                cli.ChannelLocalizationError,
                "Create the local ignored file first",
            ):
                cli.load_catalog(path)

    def test_load_catalog_rejects_expected_count_mismatch(self):
        path = self._write_payload(_payload(_entry(), expected_count=2))
        with self.assertRaisesRegex(cli.ChannelLocalizationError, "Expected 2"):
            cli.load_catalog(path)

    def test_load_catalog_rejects_duplicate_studio_locale(self):
        path = self._write_payload(
            _payload(
                _entry(),
                _entry("en_US", studio_name="English duplicate"),
            )
        )
        with self.assertRaisesRegex(cli.ChannelLocalizationError, "Duplicate Studio locale"):
            cli.load_catalog(path)

    def test_desired_localizations_use_exact_studio_locale_keys(self):
        payload = _payload(
            _entry(),
            _entry(
                "sr_Latn_RS",
                studio_name="Serbian (Latin)",
                api_language="sr-Latn",
                title="Primer",
                description="Opis",
            ),
        )
        desired = cli.desired_localizations(payload)
        self.assertEqual(
            {"title": "Example channel", "description": "Example description"},
            desired["en_US"],
        )
        self.assertIn("sr_Latn_RS", desired)
        self.assertNotIn("en", desired)
        self.assertNotIn("sr-Latn", desired)

    def test_diff_and_merge_preserve_unrelated_existing_localizations(self):
        existing = {
            "de_DE": {"title": "Alt", "description": "Alt"},
            "xx_YY": {"title": "Keep", "description": "Keep"},
        }
        desired = {
            "de_DE": {"title": "Neu", "description": "Neu"},
            "fr_FR": {"title": "Nouveau", "description": "Nouveau"},
        }
        self.assertEqual(
            [("de_DE", "UPDATE"), ("fr_FR", "ADD")],
            cli.diff_localizations(existing, desired),
        )
        merged = cli.merged_localizations(existing, desired)
        self.assertEqual(existing["xx_YY"], merged["xx_YY"])
        self.assertEqual(desired["de_DE"], merged["de_DE"])
        self.assertEqual(desired["fr_FR"], merged["fr_FR"])

    def test_overlap_guard_allows_dry_run_but_blocks_apply(self):
        existing = {"af_ZA": {"title": "Old", "description": "Old"}}
        desired = {"en_US": {"title": "New", "description": "New"}}
        self.assertEqual(
            [],
            cli.ensure_safe_overlap(existing, desired, applying=False),
        )
        with self.assertRaisesRegex(
            cli.ChannelLocalizationError,
            "zero key overlap",
        ):
            cli.ensure_safe_overlap(existing, desired, applying=True)

    def test_overlap_guard_returns_matching_keys(self):
        existing = {
            "af_ZA": {"title": "Old", "description": "Old"},
            "en_US": {"title": "Old", "description": "Old"},
        }
        desired = {
            "en_US": {"title": "New", "description": "New"},
            "fr_FR": {"title": "Nouveau", "description": "Nouveau"},
        }
        self.assertEqual(
            ["en_US"],
            cli.ensure_safe_overlap(existing, desired, applying=True),
        )

    def test_write_backup_keeps_existing_channel_state(self):
        channel = {
            "id": "channel-1",
            "etag": "etag-1",
            "brandingSettings": {"channel": {"defaultLanguage": "en"}},
            "localizations": {
                "en_US": {
                    "title": "Example channel",
                    "description": "Example description",
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            backup = cli.write_backup(channel, Path(tmp))
            saved = json.loads(backup.read_text(encoding="utf-8"))
        self.assertEqual("channel-1", saved["channelId"])
        self.assertEqual("en", saved["defaultLanguage"])
        self.assertEqual(channel["localizations"], saved["localizations"])

    def test_verify_desired_reports_only_mismatches(self):
        desired = {
            "en_US": {"title": "Example channel", "description": "Example"},
            "ru_RU": {"title": "Пример", "description": "Описание"},
        }
        actual = {
            "en_US": desired["en_US"],
            "ru_RU": {"title": "Пример", "description": "wrong"},
        }
        self.assertEqual(["ru_RU"], cli.verify_desired(actual, desired))


if __name__ == "__main__":
    unittest.main()
