import requests
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse, unquote, quote, urlunparse
import base64
from .base_adapter import BaseDriveAdapter

# Use defusedxml for security
try:
    from defusedxml import ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

logger = logging.getLogger("WebDAVAdapter")

class WebDAVAdapter(BaseDriveAdapter):
    def __init__(self, drive_id: str, base_url: str, username: Optional[str] = None, password: Optional[str] = None):
        super().__init__(drive_id)
        self.base_url = base_url.rstrip('/') + '/'
        self.username = username
        self.password = password
        self.auth = (username, password) if username and password else None

    def login_auth(self) -> bool:
        """Verify connectivity and credentials with a Depth 0 PROPFIND request."""
        try:
            resp = requests.request(
                "PROPFIND",
                self.base_url,
                auth=self.auth,
                headers={"Depth": "0"},
                timeout=10
            )
            return resp.status_code in [200, 207]
        except Exception as e:
            logger.error(f"WebDAV connectivity check failed for {self.drive_id}: {e}")
            return False

    def list_files(self, remote_path: str = "/") -> List[Dict[str, Any]]:
        """List files in the specified remote path."""
        # Ensure path starts with / and urljoin handles it
        if not remote_path.startswith('/'):
            remote_path = '/' + remote_path

        url = urljoin(self.base_url, remote_path.lstrip('/'))
        if not url.endswith('/') and remote_path != "/":
             # Some WebDAV servers are picky about trailing slash for collections
             pass

        headers = {"Depth": "1"}
        try:
            resp = requests.request(
                "PROPFIND",
                url,
                auth=self.auth,
                headers=headers,
                timeout=15
            )
            if resp.status_code != 207:
                logger.error(f"Failed to list WebDAV files: HTTP {resp.status_code}")
                return []

            return self._parse_multistatus(resp.content, url)
        except Exception as e:
            logger.error(f"Error listing WebDAV files at {remote_path}: {e}")
            return []

    def _parse_multistatus(self, xml_content: bytes, request_url: str) -> List[Dict[str, Any]]:
        """Parse WebDAV PROPFIND XML response."""
        try:
            root = ET.fromstring(xml_content)
        except Exception as e:
            logger.error(f"Failed to parse WebDAV XML: {e}")
            return []

        # WebDAV uses the DAV: namespace, often prefixed as 'd' or 'D'
        # We'll use a wildcard or handle common prefixes
        ns = {"d": "DAV:"}
        results = []

        parsed_request_url = urlparse(request_url)
        request_path = unquote(parsed_request_url.path).rstrip('/')

        for response in root.findall(".//d:response", ns):
            href_el = response.find("d:href", ns)
            if href_el is None or href_el.text is None:
                continue

            href = href_el.text
            decoded_href = unquote(href)

            # Normalize path for comparison
            item_path = urlparse(decoded_href).path.rstrip('/')

            # Skip the requested directory itself
            if item_path == request_path:
                continue

            prop = response.find(".//d:prop", ns)
            if prop is None:
                continue

            displayname_el = prop.find("d:displayname", ns)
            if displayname_el is not None and displayname_el.text:
                name = displayname_el.text
            else:
                # Fallback to last part of path
                name = decoded_href.rstrip('/').split('/')[-1]

            resourcetype = prop.find("d:resourcetype", ns)
            is_dir = resourcetype is not None and resourcetype.find("d:collection", ns) is not None

            size_el = prop.find("d:getcontentlength", ns)
            size = int(size_el.text) if (size_el is not None and size_el.text) else 0

            results.append({
                "name": name,
                "size": size,
                "is_dir": is_dir,
                "id": decoded_href,
                "path": decoded_href
            })
        return results

    def get_download_link(self, file_id: str) -> str:
        """Get the full absolute URL for the file, including Basic Auth if present."""
        # file_id is the decoded href. We need to re-quote path segments.
        # But wait, if file_id is absolute path like /dav/foo bar.txt
        # we should quote it properly.
        quoted_path = quote(file_id)

        parsed_base = urlparse(self.base_url)
        # Construct the URL with proper path
        if file_id.startswith('/'):
            # If absolute path, replace path in base
            url_parts = list(parsed_base)
            url_parts[2] = quoted_path
            url = urlunparse(url_parts)
        else:
            # If relative, join with base
            url = urljoin(self.base_url, quoted_path)

        if self.username and self.password:
            parsed = urlparse(url)
            # Reconstruct URL with URL-encoded credentials
            safe_user = quote(self.username)
            safe_pass = quote(self.password)
            netloc = f"{safe_user}:{safe_pass}@{parsed.netloc}"
            url = parsed._replace(netloc=netloc).geturl()
        return url

    def get_quota(self) -> Dict[str, int]:
        """Fetch storage quota if supported by the server."""
        headers = {"Depth": "0"}
        try:
            resp = requests.request(
                "PROPFIND",
                self.base_url,
                auth=self.auth,
                headers=headers,
                timeout=10
            )
            if resp.status_code == 207:
                root = ET.fromstring(resp.content)
                ns = {"d": "DAV:"}
                prop = root.find(".//d:prop", ns)
                if prop is not None:
                    available_el = prop.find("d:quota-available-bytes", ns)
                    used_el = prop.find("d:quota-used-bytes", ns)

                    available = int(available_el.text) if (available_el is not None and available_el.text) else None
                    used = int(used_el.text) if (used_el is not None and used_el.text) else None

                    if used is not None:
                        total = (available + used) if available is not None else -1
                        return {"total": total, "used": used}
        except Exception:
            pass
        return {"total": -1, "used": -1}

    def get_upload_params(self, remote_path: str) -> Dict[str, Any]:
        """Generate parameters for a PUT upload request."""
        if not remote_path.startswith('/'):
            remote_path = '/' + remote_path
        url = urljoin(self.base_url, remote_path.lstrip('/'))

        headers = {}
        if self.username and self.password:
            auth_str = f"{self.username}:{self.password}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_auth}"

        return {
            "url": url,
            "method": "PUT",
            "headers": headers
        }
