import unittest
from butler.core.algorithms import HybridMatcher, dras_manager
from butler.core.skill_sdk import scrub_env
import os

class TestIronBackened(unittest.TestCase):
    def test_hybrid_matcher_low_power(self):
        manifests = {
            "weather": {"name": "Weather Skill", "keywords": ["rain", "sun"]},
            "music": {"name": "Music Player", "description": "Play some tunes"}
        }
        # Test Low Power (Regex/Keyword)
        matcher = HybridMatcher(manifests, hardware_low_power=True)
        self.assertEqual(matcher.match("Tell me the weather"), "weather")
        self.assertEqual(matcher.match("Play music"), "music")

    def test_scrub_env(self):
        os.environ["VAULT_TEST_KEY"] = "secret_value"
        self.assertIn("VAULT_TEST_KEY", os.environ)
        scrub_env("VAULT_TEST_KEY")
        self.assertNotIn("VAULT_TEST_KEY", os.environ)

    def test_dras_throttle_signal(self):
        # Simulate SIGUSR1
        import signal
        import sys
        if sys.platform != 'win32':
            os.kill(os.getpid(), signal.SIGUSR1)
            self.assertTrue(dras_manager.throttled)

if __name__ == "__main__":
    unittest.main()
