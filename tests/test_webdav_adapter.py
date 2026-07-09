import unittest
from unittest.mock import MagicMock, patch
import sys
from types import ModuleType

# Mock cryptography and secret_vault before importing adapters
mock_crypto = ModuleType("cryptography")
mock_crypto_hazmat = ModuleType("cryptography.hazmat")
mock_crypto_hazmat_primitives = ModuleType("cryptography.hazmat.primitives")
sys.modules["cryptography"] = mock_crypto
sys.modules["cryptography.hazmat"] = mock_crypto_hazmat
sys.modules["cryptography.hazmat.primitives"] = mock_crypto_hazmat_primitives
sys.modules["cryptography.hazmat.primitives.hashes"] = ModuleType("hashes")
sys.modules["cryptography.hazmat.primitives.kdf"] = ModuleType("kdf")
sys.modules["cryptography.hazmat.primitives.kdf.pbkdf2"] = ModuleType("pbkdf2")
sys.modules["cryptography.hazmat.primitives.ciphers"] = ModuleType("ciphers")
sys.modules["cryptography.hazmat.primitives.ciphers.aead"] = ModuleType("aead")

# Mock butler.core.secret_vault
mock_vault_mod = ModuleType("butler.core.secret_vault")
mock_vault_mod.secret_vault = MagicMock()
sys.modules["butler.core.secret_vault"] = mock_vault_mod

from skills.storage_hub.adapters.webdav import WebDAVAdapter

class TestWebDAVAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = WebDAVAdapter(
            drive_id="test_dav",
            base_url="http://example.com/dav",
            username="user",
            password="pass"
        )

    @patch("requests.request")
    def test_login_auth_success(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 207
        mock_request.return_value = mock_response

        self.assertTrue(self.adapter.login_auth())
        mock_request.assert_called_once()
        self.assertEqual(mock_request.call_args[1]["headers"]["Depth"], "0")

    @patch("requests.request")
    def test_list_files(self, mock_request):
        xml_payload = """<?xml version="1.0" encoding="utf-8" ?>
<d:multistatus xmlns:d="DAV:">
    <d:response>
        <d:href>/dav/</d:href>
        <d:propstat>
            <d:prop>
                <d:resourcetype><d:collection/></d:resourcetype>
            </d:prop>
            <d:status>HTTP/1.1 200 OK</d:status>
        </d:propstat>
    </d:response>
    <d:response>
        <d:href>/dav/test.txt</d:href>
        <d:propstat>
            <d:prop>
                <d:displayname>test.txt</d:displayname>
                <d:getcontentlength>1234</d:getcontentlength>
                <d:resourcetype/>
            </d:prop>
            <d:status>HTTP/1.1 200 OK</d:status>
        </d:propstat>
    </d:response>
</d:multistatus>"""
        mock_response = MagicMock()
        mock_response.status_code = 207
        mock_response.content = xml_payload.encode("utf-8")
        mock_request.return_value = mock_response

        files = self.adapter.list_files("/")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["name"], "test.txt")
        self.assertEqual(files[0]["size"], 1234)
        self.assertFalse(files[0]["is_dir"])

    def test_get_download_link(self):
        link = self.adapter.get_download_link("/dav/test.txt")
        self.assertEqual(link, "http://user:pass@example.com/dav/test.txt")

    def test_get_download_link_special_chars(self):
        self.adapter.username = "user@name"
        self.adapter.password = "pass:word"
        link = self.adapter.get_download_link("/dav/my file.txt")
        self.assertEqual(link, "http://user%40name:pass%3Aword@example.com/dav/my%20file.txt")

    def test_get_upload_params(self):
        params = self.adapter.get_upload_params("/test.txt")
        self.assertEqual(params["method"], "PUT")
        self.assertEqual(params["url"], "http://example.com/dav/test.txt")
        self.assertIn("Authorization", params["headers"])

if __name__ == "__main__":
    unittest.main()
