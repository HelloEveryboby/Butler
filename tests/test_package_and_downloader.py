import pytest
import skills.downloader as downloader
from package.vision import PictureRecognition
from package.security import SecureVault, SymmetricCrypto
from package.network import ImageSearchTool
from package.document import DocumentInterpreter
from package.core_utils import LogManager
from butler.core.skill_manager import SkillManager

def test_package_direct_imports():
    """Test that package core components can be directly imported."""
    pic_rec = PictureRecognition()
    assert pic_rec is not None

    log = LogManager.get_logger("test_logger")
    assert log is not None

    tool = ImageSearchTool()
    assert tool is not None

    doc = DocumentInterpreter()
    assert doc is not None

def test_downloader_lazy_loading():
    """Test that Downloader service does not start on get_status and starts lazily on demand."""
    downloader.scheduler_running = False

    status = downloader.handle_request("get_status")
    assert status["status"] == "ok"
    assert status["service_active"] is False

    start_res = downloader.handle_request("start_service")
    assert start_res["status"] == "ok"
    assert start_res["service_active"] is True

    status_after = downloader.handle_request("get_status")
    assert status_after["service_active"] is True

def test_skill_manager_isolation():
    """Test that SkillManager does not load package modules as dynamic skills."""
    sm = SkillManager()
    sm.load_skills()
    assert not any(k.startswith("package.") for k in sm.manifests.keys())
