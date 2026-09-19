import unittest

from ui.faq import FAQ_ENTRIES


class FaqTests(unittest.TestCase):
    def test_channel_profile_localization_is_documented(self):
        entries = dict(FAQ_ENTRIES)
        answer = entries["Can I localize the channel name and description too?"]
        self.assertIn("update_channel_localizations.py", answer)
        self.assertIn("data/channel-localizations.json", answer)
        self.assertIn("--apply", answer)


if __name__ == "__main__":
    unittest.main()
