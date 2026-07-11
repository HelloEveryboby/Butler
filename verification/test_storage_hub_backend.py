import pytest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from skills.storage_hub.hub_manager import HubManager
from skills.storage_hub.adapters.base_adapter import BaseDriveAdapter

# A mock adapter class to test real integration flow
class MockDriveAdapter(BaseDriveAdapter):
    def __init__(self, drive_id):
        super().__init__(drive_id)
        self.files = [
            {"name": "test_file.iso", "id": "file_uuid_123", "size": 1024 * 1024 * 5, "is_dir": False, "path": "/test_file.iso"}
        ]

    def login_auth(self) -> bool:
        return True

    def list_files(self, remote_path: str = "/") -> list:
        return self.files

    def get_download_link(self, file_id: str) -> str:
        return f"https://mockdownload.com/{self.drive_id}/{file_id}"

    def get_quota(self) -> dict:
        return {"total": 1000, "used": 500}

    def get_upload_params(self, remote_path: str) -> dict:
        return {
            "url": f"https://mockupload.com/{self.drive_id}{remote_path}",
            "method": "PUT",
            "headers": {"Authorization": "Bearer mock_token"}
        }

@pytest.mark.asyncio
async def test_hub_manager_real_transfer_success():
    # 1. Instantiate HubManager
    manager = HubManager()

    # 2. Register mock adapters
    src_drv = MockDriveAdapter("src_mock")
    dst_drv = MockDriveAdapter("dst_mock")
    manager.register_adapter("src_mock", src_drv)
    manager.register_adapter("dst_mock", dst_drv)

    # 3. Mock the storage_bridge.transfer to return success
    from skills.storage_hub.bridge_client import storage_bridge

    with patch.object(storage_bridge, "transfer", new_callable=AsyncMock) as mock_transfer:
        mock_transfer.return_value = (True, "Transfer successful via Go Runner")

        # 4. Trigger transfer via handle_request
        response = manager.handle_request(
            "transfer",
            src_drive="src_mock",
            dst_drive="dst_mock",
            file_name="test_file.iso",
            file_id="file_uuid_123",
            file_size=1024 * 1024 * 5,
            source_path="/",
            dst_path="/"
        )

        assert response["status"] == "ok"
        task_id = response["task_id"]

        # 5. Wait for the background transfer thread to complete
        start_wait = time.time()
        completed = False
        while time.time() - start_wait < 5.0:
            status_resp = manager.handle_request("check_transfer_status", task_id=task_id)
            assert status_resp["status"] == "ok"
            task = status_resp["task"]
            if task["status"] in ["completed", "failed"]:
                completed = True
                assert task["status"] == "completed"
                assert task["progress"] == 100
                break
            time.sleep(0.1)

        assert completed, "Transfer task did not complete in time"

        # Verify storage_bridge.transfer was called with correct parameters
        mock_transfer.assert_called_once_with(
            src_url="https://mockdownload.com/src_mock/file_uuid_123",
            dst_url="https://mockupload.com/dst_mock/test_file.iso",
            method="PUT",
            src_headers={},
            dst_headers={"Authorization": "Bearer mock_token"}
        )

@pytest.mark.asyncio
async def test_hub_manager_real_transfer_failure():
    manager = HubManager()

    src_drv = MockDriveAdapter("src_mock")
    dst_drv = MockDriveAdapter("dst_mock")
    manager.register_adapter("src_mock", src_drv)
    manager.register_adapter("dst_mock", dst_drv)

    from skills.storage_hub.bridge_client import storage_bridge

    with patch.object(storage_bridge, "transfer", new_callable=AsyncMock) as mock_transfer:
        mock_transfer.return_value = (False, "Network error or connection timed out")

        response = manager.handle_request(
            "transfer",
            src_drive="src_mock",
            dst_drive="dst_mock",
            file_name="test_file.iso",
            file_id="file_uuid_123",
            file_size=1024 * 1024 * 5,
            source_path="/",
            dst_path="/"
        )

        assert response["status"] == "ok"
        task_id = response["task_id"]

        start_wait = time.time()
        completed = False
        while time.time() - start_wait < 5.0:
            status_resp = manager.handle_request("check_transfer_status", task_id=task_id)
            assert status_resp["status"] == "ok"
            task = status_resp["task"]
            if task["status"] in ["completed", "failed"]:
                completed = True
                assert task["status"] == "failed"
                assert "Network error" in task["message"]
                break
            time.sleep(0.1)

        assert completed, "Transfer task did not fail as expected"


@pytest.mark.asyncio
async def test_baidu_adapter_flow():
    from butler.core.secret_vault import secret_vault
    # Initialize SecretVault for testing
    secret_vault.initialize("test_master_password_123")

    from skills.storage_hub.adapters.baidu import BaiduAdapter

    # Mock bypy's ByPy class
    mock_bypy_instance = MagicMock()
    # Mock the stdout list output
    def mock_list(remotepath, fmt=""):
        print("D\tMovies\t0")
        print("F\tphoto.jpg\t2048576")

    mock_bypy_instance.list.side_effect = mock_list

    from unittest.mock import mock_open as unittest_mock_open
    with patch("bypy.ByPy", return_value=mock_bypy_instance), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", unittest_mock_open(read_data='{"access_token": "mock_baidu_access_token_abc123"}')):

        adapter = BaiduAdapter("baidu_test")

        # 1. Test login_auth
        assert adapter.login_auth() is True

        # 2. Test list_files
        files = adapter.list_files("/")
        assert len(files) == 2
        assert files[0]["name"] == "Movies"
        assert files[0]["is_dir"] is True
        assert files[1]["name"] == "photo.jpg"
        assert files[1]["is_dir"] is False
        assert files[1]["size"] == 2048576

        # 3. Test get_download_link
        dl_link = adapter.get_download_link("photo.jpg")
        assert "access_token=mock_baidu_access_token_abc123" in dl_link
        assert "path=/apps/bypy/photo.jpg" in dl_link

        # 4. Test get_upload_params
        upload_params = adapter.get_upload_params("new_doc.pdf")
        assert "method=upload" in upload_params["url"]
        assert "access_token=mock_baidu_access_token_abc123" in upload_params["url"]
        assert "path=/apps/bypy/new_doc.pdf" in upload_params["url"]
        assert upload_params["method"] == "POST"


@pytest.mark.asyncio
async def test_global_search_and_duplicates():
    manager = HubManager()

    # Register adapters with overlapping files for duplicate testing
    src_drv = MockDriveAdapter("src_mock")
    dst_drv = MockDriveAdapter("dst_mock")
    manager.register_adapter("src_mock", src_drv)
    manager.register_adapter("dst_mock", dst_drv)

    # 1. Test search_all action
    res_search = manager.handle_request("search_all", query="test_file")
    assert res_search["status"] == "ok"
    results = res_search["results"]
    assert len(results) == 2
    assert results[0]["name"] == "test_file.iso"
    assert results[1]["name"] == "test_file.iso"

    # 2. Test find_duplicates action
    res_dup = manager.handle_request("find_duplicates")
    assert res_dup["status"] == "ok"
    duplicates = res_dup["duplicates"]
    assert "test_file.iso (5242880 bytes)" in duplicates
    occurrences = duplicates["test_file.iso (5242880 bytes)"]
    assert len(occurrences) == 2
    assert occurrences[0]["drive"] == "src_mock"
    assert occurrences[1]["drive"] == "dst_mock"


@pytest.mark.asyncio
async def test_smart_upload_drive():
    manager = HubManager()

    # Register adapters with different quota parameters
    drv1 = MockDriveAdapter("drive1")
    drv2 = MockDriveAdapter("drive2")

    # Mock quota: drv1 has 1000 - 500 = 500 free space
    # We override drv2 get_quota to return 2000 - 400 = 1600 free space
    drv2.get_quota = MagicMock(return_value={"total": 2000, "used": 400})

    manager.register_adapter("drive1", drv1)
    manager.register_adapter("drive2", drv2)

    res = manager.handle_request("smart_upload_drive")
    assert res["status"] == "ok"
    assert res["drive_id"] == "drive2"  # drive2 has more free space (1600 vs 500)
