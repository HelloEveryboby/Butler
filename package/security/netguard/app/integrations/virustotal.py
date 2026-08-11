"""VirusTotal API 集成"""

from app.integrations.base import ExternalAPIClient


class VirusTotalClient(ExternalAPIClient):
    BASE_URL = "https://www.virustotal.com/api/v3"

    def is_available(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0

    async def lookup(self, target: str) -> dict:
        cached = self._cache_get(f"vt:{target}")
        if cached:
            return cached

        if not self.is_available():
            return {"source": "virustotal", "available": False, "error": "API key not configured"}

        try:
            # 检测目标类型
            if self._is_ip(target):
                url = f"{self.BASE_URL}/ip_addresses/{target}"
            elif self._is_domain(target):
                url = f"{self.BASE_URL}/domains/{target}"
            else:
                url = f"{self.BASE_URL}/urls/{target}"

            resp = await self._http.get(url, headers={"x-apikey": self.api_key})

            if resp.status_code == 200:
                data = resp.json()
                attrs = data.get("data", {}).get("attributes", {})
                stats = attrs.get("last_analysis_stats", {})
                malicious = stats.get("malicious", 0)
                suspicious = stats.get("suspicious", 0)
                total = sum(stats.values()) or 1

                result = {
                    "source": "virustotal",
                    "available": True,
                    "score": round((malicious + suspicious * 0.5) / total, 3),
                    "is_malicious": malicious > 0,
                    "malicious_count": malicious,
                    "suspicious_count": suspicious,
                    "total_engines": total,
                    "categories": self._extract_categories(attrs),
                    "reputation": attrs.get("reputation", 0),
                }
            elif resp.status_code == 404:
                result = {"source": "virustotal", "available": True, "score": 0.0, "is_malicious": False, "note": "Not found in VT database"}
            else:
                result = {"source": "virustotal", "available": True, "error": f"HTTP {resp.status_code}"}

        except Exception as e:
            result = {"source": "virustotal", "available": True, "error": str(e)}

        self._cache_set(f"vt:{target}", result)
        return result

    @staticmethod
    def _is_ip(target: str) -> bool:
        import re
        return bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", target))

    @staticmethod
    def _is_domain(target: str) -> bool:
        return "." in target and not target.startswith(("http://", "https://"))

    @staticmethod
    def _extract_categories(attrs: dict) -> list[str]:
        cats = attrs.get("categories", {})
        if isinstance(cats, dict):
            return list(set(cats.values()))
        return []
