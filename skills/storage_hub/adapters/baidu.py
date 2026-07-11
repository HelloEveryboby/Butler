import os
import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from .base_adapter import BaseDriveAdapter
from butler.core.secret_vault import secret_vault

logger = logging.getLogger("BaiduAdapter")

class BaiduAdapter(BaseDriveAdapter):
    def __init__(self, drive_id: str):
        super().__init__(drive_id)
        # Ensure we backup or restore credentials at init
        self._restore_bypy_json()

    def _restore_bypy_json(self) -> bool:
        """Backup local bypy.json to SecretVault or restore it if missing."""
        auth_dir = os.path.expanduser('~/.bypy')
        auth_file = os.path.join(auth_dir, 'bypy.json')

        # Backup to SecretVault if it exists on disk
        if os.path.exists(auth_file):
            try:
                with open(auth_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.strip():
                    secret_vault.set_secret(f"bypy_{self.drive_id}_json", content)
                    logger.info(f"Backed up bypy credentials to SecretVault for {self.drive_id}.")
            except Exception as e:
                logger.error(f"Failed to backup bypy credentials: {e}")
            return True

        # Restore from SecretVault if missing on disk
        try:
            stored = secret_vault.get_secret(f"bypy_{self.drive_id}_json")
            if stored:
                os.makedirs(auth_dir, exist_ok=True)
                with open(auth_file, "w", encoding="utf-8") as f:
                    f.write(stored)
                logger.info(f"Restored bypy credentials from SecretVault to {auth_file}.")
                return True
        except Exception as e:
            logger.error(f"Failed to restore bypy credentials from SecretVault: {e}")

        return False

    def _get_access_token(self) -> str:
        """Get the current access token from SecretVault or raw config."""
        try:
            stored = secret_vault.get_secret(f"bypy_{self.drive_id}_json")
            if stored:
                data = json.loads(stored)
                return data.get("access_token", "")
        except Exception:
            pass

        auth_file = os.path.expanduser('~/.bypy/bypy.json')
        if os.path.exists(auth_file):
            try:
                with open(auth_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("access_token", "")
            except Exception:
                pass
        return ""

    def login_auth(self) -> bool:
        """Check if Baidu credentials are authenticated."""
        return bool(self._get_access_token())

    def list_files(self, remote_path: str = "/") -> List[Dict[str, Any]]:
        self._restore_bypy_json()
        from bypy import ByPy

        # Use /home/jules/.bypy as default config dir
        bp = ByPy(quit_when_fail=False)

        # Capture the tab-separated stdout
        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            try:
                bp.list(remote_path, fmt="$t\t$f\t$s")
            except Exception as e:
                logger.error(f"Baidu PCS list failed: {e}")

        output = f.getvalue()
        results = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 3:
                t, name, size_str = parts[0], parts[1], parts[2]
                is_dir = (t == 'D')
                try:
                    size = int(size_str)
                except ValueError:
                    size = 0

                path = f"{remote_path.rstrip('/')}/{name}"
                if not path.startswith('/'):
                    path = '/' + path

                results.append({
                    "name": name,
                    "size": size,
                    "is_dir": is_dir,
                    "id": path,
                    "path": path
                })
        return results

    def get_download_link(self, file_id: str) -> str:
        token = self._get_access_token()
        if not token:
            return ""

        pcs_path = f"/apps/bypy/{file_id.lstrip('/')}"
        quoted_path = quote(pcs_path)

        # Standard Baidu PCS direct download link
        return f"https://d.pcs.baidu.com/rest/2.0/pcs/file?method=download&access_token={token}&path={quoted_path}"

    def get_quota(self) -> Dict[str, int]:
        token = self._get_access_token()
        if not token:
            return {"total": -1, "used": -1}

        try:
            import requests
            url = f"https://pcs.baidu.com/rest/2.0/pcs/quota?method=info&access_token={token}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "total": data.get("quota", -1),
                    "used": data.get("used", -1)
                }
        except Exception as e:
            logger.error(f"Failed to query Baidu Netdisk quota: {e}")
        return {"total": -1, "used": -1}

    def get_upload_params(self, remote_path: str) -> Dict[str, Any]:
        token = self._get_access_token()
        pcs_path = f"/apps/bypy/{remote_path.lstrip('/')}"
        quoted_path = quote(pcs_path)

        url = f"https://c.pcs.baidu.com/rest/2.0/pcs/file?method=upload&access_token={token}&path={quoted_path}&ondup=overwrite"
        return {
            "url": url,
            "method": "POST",
            "headers": {}
        }
