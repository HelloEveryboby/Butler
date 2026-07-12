import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from butler.core.api import app
import butler.core.api as api_module
from butler.core.secret_vault import secret_vault

client = TestClient(app)

# Ensure the secret vault is always initialized for all tests
@pytest.fixture(autouse=True)
def setup_vault():
    if not secret_vault._master_key:
        secret_vault.initialize("testmasterpassword")

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_sensor_data_unauthorized():
    # Attempting to post sensor data without authorization header should fail with 401
    response = client.post("/sensor/data", json={"sensor": "distance", "value": 30})
    assert response.status_code == 401

def test_sensor_data_invalid_token():
    # Attempting to post with an invalid bearer token should fail with 401
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.post("/sensor/data", json={"sensor": "distance", "value": 30}, headers=headers)
    assert response.status_code == 401

def test_sensor_data_authorized(monkeypatch):
    # Get the token generated in vault
    token = secret_vault.get_secret("rest_api_bearer_token")
    assert token is not None

    # Mock SensingAPI and initialize
    mock_sensing_api = MagicMock()
    monkeypatch.setattr(api_module, "sensing_api", mock_sensing_api)

    # Post with valid token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/sensor/data", json={"sensor": "distance", "value": 45}, headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify that the sensing_api process_sensor_data was called
    mock_sensing_api.process_sensor_data.assert_called_once()
