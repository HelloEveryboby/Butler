"""AbuseIPDB API 集成"""

from app.integrations.base import ExternalAPIClient


class AbuseIPDBClient(ExternalAPIClient):
    BASE_URL = "https://api.abuseipdb.com/api/v2"

    def is_available(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0

    async def lookup(self, target: str) -> dict:
        cached = self._cache_get(f"aipdb:{target}")
        if cached:
            return cached

        if not self.is_available():
            return {"source": "abuseipdb", "available": False, "error": "API key not configured"}

        try:
            resp = await self._http.get(
                f"{self.BASE_URL}/check",
                params={"ipAddress": target, "maxAgeInDays": 90, "verbose": ""},
                headers={"Key": self.api_key, "Accept": "application/json"},
            )

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                abuse_score = data.get("abuseConfidenceScore", 0)
                result = {
                    "source": "abuseipdb",
                    "available": True,
                    "score": round(abuse_score / 100, 3),
                    "is_malicious": abuse_score > 50,
                    "abuse_confidence_score": abuse_score,
                    "total_reports": data.get("totalReports", 0),
                    "country_code": data.get("countryCode", ""),
                    "isp": data.get("isp", ""),
                    "domain": data.get("domain", ""),
                    "usage_type": data.get("usageType", ""),
                    "is_whitelisted": data.get("isWhitelisted", False),
                }
            else:
                result = {"source": "abuseipdb", "available": True, "error": f"HTTP {resp.status_code}"}

        except Exception as e:
            result = {"source": "abuseipdb", "available": True, "error": str(e)}

        self._cache_set(f"aipdb:{target}", result)
        return result
