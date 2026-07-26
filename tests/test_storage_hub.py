import pytest
from unittest.mock import patch, MagicMock
from skills.storage_hub.adapters.webdav import WebDAVAdapter
from skills.storage_hub.adapters.onedrive import OneDriveAdapter
from skills.storage_hub.adapters.baidu import BaiduAdapter
from skills.storage_hub.hub_manager import HubManager


def test_webdav_adapter_file_operations():
    adapter = WebDAVAdapter("test_webdav", "http://localhost:5244/dav", "admin", "password123")

    with patch("requests.request") as mock_request:
        # Mock DELETE
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_request.return_value = mock_resp

        assert adapter.delete_file("/test_folder/file.txt") is True
        mock_request.assert_called_with(
            "DELETE",
            "http://localhost:5244/dav/test_folder/file.txt",
            auth=("admin", "password123"),
            timeout=15
        )

        # Mock COPY
        mock_resp.status_code = 201
        assert adapter.copy_file("/src.txt", "/dst.txt") is True
        mock_request.assert_called_with(
            "COPY",
            "http://localhost:5244/dav/src.txt",
            auth=("admin", "password123"),
            headers={"Destination": "http://localhost:5244/dav/dst.txt", "Overwrite": "T"},
            timeout=15
        )

        # Mock MOVE
        mock_resp.status_code = 201
        assert adapter.move_file("/src.txt", "/dst.txt") is True
        mock_request.assert_called_with(
            "MOVE",
            "http://localhost:5244/dav/src.txt",
            auth=("admin", "password123"),
            headers={"Destination": "http://localhost:5244/dav/dst.txt", "Overwrite": "T"},
            timeout=15
        )

        # Mock MKCOL (create_directory)
        mock_resp.status_code = 201
        assert adapter.create_directory("/new_dir") is True
        mock_request.assert_called_with(
            "MKCOL",
            "http://localhost:5244/dav/new_dir/",
            auth=("admin", "password123"),
            timeout=15
        )


def test_onedrive_adapter_file_operations():
    adapter = OneDriveAdapter("test_onedrive", "client_id", "secret", "http://localhost:8421")

    with patch.object(OneDriveAdapter, "login_auth", return_value=True), \
         patch.object(OneDriveAdapter, "_get_stored_tokens", return_value={"access_token": "token_123"}), \
         patch("requests.delete") as mock_delete, \
         patch("requests.patch") as mock_patch, \
         patch("requests.post") as mock_post:

        # Mock Delete
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_delete.return_value = mock_resp

        assert adapter.delete_file("/folder/file.txt") is True
        mock_delete.assert_called_with(
            "https://graph.microsoft.com/v1.0/me/drive/root:/folder/file.txt",
            headers={"Authorization": "Bearer token_123"},
            timeout=15
        )

        # Mock Rename
        mock_resp.status_code = 200
        mock_patch.return_value = mock_resp
        assert adapter.rename_file("/folder/file.txt", "new_name.txt") is True
        mock_patch.assert_called_with(
            "https://graph.microsoft.com/v1.0/me/drive/root:/folder/file.txt",
            headers={"Authorization": "Bearer token_123", "Content-Type": "application/json"},
            json={"name": "new_name.txt"},
            timeout=15
        )


def test_hub_manager_actions():
    manager = HubManager()

    # Register mock WebDAV adapter
    mock_adapter = MagicMock()
    mock_adapter.delete_file.return_value = True
    mock_adapter.rename_file.return_value = True

    manager.register_adapter("test_drv", mock_adapter)

    # Test delete file handler
    res = manager.handle_request("delete_file", drive="test_drv", path="/foo/bar.txt")
    assert res == {"status": "ok"}
    mock_adapter.delete_file.assert_called_with("/foo/bar.txt")

    # Test rename file handler
    res = manager.handle_request("rename_file", drive="test_drv", path="/foo/bar.txt", new_name="baz.txt")
    assert res == {"status": "ok"}
    mock_adapter.rename_file.assert_called_with("/foo/bar.txt", "baz.txt")
