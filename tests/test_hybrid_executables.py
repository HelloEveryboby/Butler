import os
import unittest
import json
from butler.code_execution_manager import CodeExecutionManager


class TestHybridExecutablesIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = CodeExecutionManager()
        cls.registered = cls.manager.scan_and_register()

    def test_scan_and_register_returns_dict(self):
        self.assertIsInstance(self.registered, dict)
        self.assertGreater(len(self.registered), 0, "Registered programs map should not be empty")

    def test_manifest_schema_normalization(self):
        norm = self.manager._normalize_manifest(
            "/dummy/path",
            "test_proj",
            {
                "id": "test_id",
                "language": "cpp",
                "description": "Test module",
                "entry": {"source": "main.cpp", "executable": "test_bin"},
                "build": {"command": "g++ main.cpp -o test_bin", "auto_build": True}
            }
        )
        self.assertEqual(norm['name'], "test_id")
        self.assertEqual(norm['language'], "cpp")
        self.assertEqual(norm['executable_name'], "test_bin")
        self.assertEqual(norm['build_command'], "g++ main.cpp -o test_bin")

    def test_active_executables_invocation(self):
        """
        Tests invocation of active programs registered in CodeExecutionManager.
        """
        active_programs = {
            name: info for name, info in self.registered.items()
            if info.get('status') == 'ACTIVE'
        }
        self.assertGreater(len(active_programs), 0, "At least one hybrid program should be ACTIVE")

        # Test trial execution of active programs
        for name, info in active_programs.items():
            with self.subTest(program=name):
                if name == 'word_counter':
                    success, output = self.manager.execute_program(name, ['sample.txt'])
                    self.assertTrue(success, f"Failed executing {name}: {output}")
                    self.assertIn("sample.txt", output)
                elif name == 'hybrid_compute':
                    success, output = self.manager.execute_program(name, ['1000000007'])
                    self.assertTrue(success, f"Failed executing {name}: {output}")
                elif name == 'hybrid_sysutil':
                    success, output = self.manager.execute_program(name, [])
                    self.assertTrue(success, f"Failed executing {name}: {output}")
                elif name == 'hybrid_crypto':
                    success, output = self.manager.execute_program(name, ['hash', 'hello'])
                    self.assertTrue(success, f"Failed executing {name}: {output}")
                elif name == 'hybrid_net':
                    success, output = self.manager.execute_program(name, ['ping', '127.0.0.1'])
                    self.assertTrue(success, f"Failed executing {name}: {output}")

    def test_degraded_program_handling(self):
        """
        Tests that degraded programs return false with informative status messages when executed.
        """
        degraded_programs = {
            name: info for name, info in self.registered.items()
            if info.get('status') == 'DEGRADED'
        }
        for name in degraded_programs:
            with self.subTest(degraded_program=name):
                success, output = self.manager.execute_program(name, [])
                self.assertFalse(success)
                self.assertIn("unavailable", output)

    def test_unknown_program_execution(self):
        success, output = self.manager.execute_program("non_existent_program_xyz", [])
        self.assertFalse(success)
        self.assertIn("not found", output)


if __name__ == '__main__':
    unittest.main()
