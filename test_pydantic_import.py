import unittest

class TestPydanticImport(unittest.TestCase):
    def test_can_import_pydantic(self):
        try:
            import pydantic
            print("Successfully imported pydantic")
        except ImportError as e:
            self.fail(f"Failed to import pydantic: {e}")

if __name__ == "__main__":
    unittest.main()