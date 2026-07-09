import pytest
from unittest.mock import MagicMock, patch
from skills.storage_hub.hub_manager import HubManager
from skills.storage_hub.adapters.onedrive import OneDriveAdapter

@pytest.fixture
def hub_manager():
    return HubManager()

def test_hub_manager_init(hub_manager):
    config = {
        "drives": [
            {
                "id": "test_drive",
                "type": "onedrive",
                "client_id": "cid",
                "client_secret": "csec"
            }
        ]
    }
    result = hub_manager.handle_request("init", config=config)
    assert result["status"] == "ok"
    assert "test_drive" in hub_manager.adapters
    assert isinstance(hub_manager.adapters["test_drive"], OneDriveAdapter)

def test_hub_manager_list_drives(hub_manager):
    hub_manager.adapters = {"drive1": MagicMock(), "drive2": MagicMock()}
    result = hub_manager.handle_request("list_drives")
    assert "drive1" in result
    assert "drive2" in result

@patch("skills.storage_hub.hub_manager.storage_bridge")
def test_hub_manager_transfer_logic(mock_bridge, hub_manager):
    src_adapter = MagicMock()
    dst_adapter = MagicMock()
    src_adapter.get_download_link.return_value = "http://src"
    dst_adapter._get_stored_tokens.return_value = {"access_token": "token"}

    hub_manager.adapters = {"src": src_adapter, "dst": dst_adapter}

    # We need to mock asyncio.run or the bridge methods since they are async
    mock_bridge.transfer.return_value = (True, "Success")

    # In a real test environment, we'd use a pytest-asyncio plugin,
    # but here we'll just check if the call logic is sound.
    # Note: hub_manager.handle_request calls asyncio.run(storage_bridge.transfer(...))

    with patch("asyncio.run", return_value=(True, "Success")):
        result = hub_manager.handle_request("transfer",
                                           src_drive="src",
                                           dst_drive="dst",
                                           file_id="123",
                                           dst_path="/test.txt")
        assert result["status"] == "ok"
