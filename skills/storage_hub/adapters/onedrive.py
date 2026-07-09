import requests
import time
import logging
from typing import List, Dict, Any, Optional
from .base_adapter import BaseDriveAdapter
from butler.core.secret_vault import secret_vault

logger = logging.getLogger("OneDriveAdapter")

class OneDriveAdapter(BaseDriveAdapter):
    AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    API_BASE = "https://graph.microsoft.com/v1.0/me"

    def __init__(self, drive_id: str, client_id: str, client_secret: str, redirect_uri: str):
        super().__init__(drive_id)
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = "files.readwrite.all offline_access"

    def _get_stored_tokens(self) -> Dict[str, str]:
        access_token = secret_vault.get_secret(f"onedrive_{self.drive_id}_access")
        refresh_token = secret_vault.get_secret(f"onedrive_{self.drive_id}_refresh")
        expires_at = secret_vault.get_secret(f"onedrive_{self.drive_id}_expires")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": float(expires_at) if expires_at else 0
        }

    def _save_tokens(self, data: Dict[str, Any]):
        secret_vault.set_secret(f"onedrive_{self.drive_id}_access", data["access_token"])
        if "refresh_token" in data:
            secret_vault.set_secret(f"onedrive_{self.drive_id}_refresh", data["refresh_token"])

        expires_at = time.time() + data.get("expires_in", 3600)
        secret_vault.set_secret(f"onedrive_{self.drive_id}_expires", str(expires_at))

    def login_auth(self) -> bool:
        tokens = self._get_stored_tokens()
        if tokens["access_token"] and tokens["expires_at"] > time.time() + 300:
            return True

        if tokens["refresh_token"]:
            return self.refresh_token(tokens["refresh_token"])

        return False

    def refresh_token(self, refresh_token: str) -> bool:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        resp = requests.post(self.TOKEN_URL, data=payload)
        if resp.status_code == 200:
            self._save_tokens(resp.json())
            return True
        logger.error(f"Failed to refresh OneDrive token: {resp.text}")
        return False

    def list_files(self, remote_path: str = "/") -> List[Dict[str, Any]]:
        if not self.login_auth():
            raise Exception("OneDrive not authenticated")

        tokens = self._get_stored_tokens()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Build path URL
        if remote_path == "/":
            url = f"{self.API_BASE}/drive/root/children"
        else:
            url = f"{self.API_BASE}/drive/root:{remote_path}:/children"

        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            logger.error(f"Failed to list OneDrive files: {resp.text}")
            return []

        children = resp.json().get("value", [])
        results = []
        for item in children:
            results.append({
                "name": item["name"],
                "size": item.get("size", 0),
                "is_dir": "folder" in item,
                "id": item["id"],
                "path": item.get("parentReference", {}).get("path", "") + "/" + item["name"]
            })
        return results

    def get_download_link(self, file_id: str) -> str:
        tokens = self._get_stored_tokens()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        url = f"{self.API_BASE}/drive/items/{file_id}"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json().get("@microsoft.graph.downloadUrl", "")
        return ""

    def get_quota(self) -> Dict[str, int]:
        tokens = self._get_stored_tokens()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        url = f"{self.API_BASE}/drive"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            quota = resp.json().get("quota", {})
            return {
                "total": quota.get("total", 0),
                "used": quota.get("used", 0)
            }
        return {"total": 0, "used": 0}

    def get_upload_params(self, remote_path: str) -> Dict[str, Any]:
        tokens = self._get_stored_tokens()
        url = f"{self.API_BASE}/drive/root:{remote_path}:/content"
        return {
            "url": url,
            "method": "PUT",
            "headers": {"Authorization": f"Bearer {tokens['access_token']}"}
        }
