import pytest


def test_imports():
    """Verify that the key core modules of Butler can be imported without errors."""
    try:
        from package.document.file_converter import convert_file

        assert convert_file is not None
    except ImportError as e:
        pytest.fail(f"Failed to import convert_file: {e}")


def test_app_import():
    """Verify that butler_app main can be imported."""
    try:
        from butler.butler_app import main

        assert main is not None
    except ImportError as e:
        pytest.fail(f"Failed to import butler_app: {e}")
