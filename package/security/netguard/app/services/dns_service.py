"""DNS 解析 + 子域名枚举服务"""

import asyncio
from datetime import datetime, timezone

import dns.resolver


class DNSService:
    """DNS 查询服务"""

    RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]

    async def lookup(self, domain: str, record_types: list[str] | None = None) -> dict:
        """DNS 解析"""
        types = record_types or ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]
        results = {}
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 10

        for rtype in types:
            try:
                answers = resolver.resolve(domain, rtype)
                results[rtype] = [str(r) for r in answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout):
                results[rtype] = []
            except Exception:
                results[rtype] = []

        return {
            "domain": domain,
            "records": results,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    async def reverse_lookup(self, ip: str) -> dict:
        """反向 DNS 解析"""
        try:
            import socket
            hostname = socket.gethostbyaddr(ip)
            return {"ip": ip, "hostname": hostname[0], "aliases": hostname[1]}
        except Exception as e:
            return {"ip": ip, "hostname": None, "error": str(e)}

    async def subdomain_enum(self, domain: str, wordlist: list[str] | None = None) -> dict:
        """子域名枚举（字典爆破）"""
        if wordlist is None:
            wordlist = [
                "www", "mail", "ftp", "smtp", "pop", "imap", "ns1", "ns2",
                "dns", "dns1", "dns2", "mx", "mx1", "mx2", "webmail",
                "admin", "panel", "cpanel", "api", "dev", "staging", "test",
                "blog", "shop", "app", "mobile", "cdn", "static", "media",
                "vpn", "remote", "gateway", "proxy", "load", "lb",
                "db", "database", "mysql", "postgres", "redis", "mongo",
                "git", "gitlab", "jenkins", "ci", "cd", "jira", "confluence",
                "monitor", "grafana", "prometheus", "kibana", "elastic",
                "s3", "aws", "gcp", "azure", "cloud", "storage",
                "login", "auth", "sso", "oauth", "id",
                "m", "w", "beta", "alpha", "canary", "edge",
                "backup", "bak", "old", "new", "v2", "v3",
                "internal", "intranet", "corp", "office", "hr",
                "support", "help", "docs", "wiki", "kb",
                "forum", "community", "status", "health",
            ]

        found = []
        resolver = dns.resolver.Resolver()
        resolver.timeout = 2
        resolver.lifetime = 3

        sem = asyncio.Semaphore(30)

        async def check_subdomain(sub: str):
            fqdn = f"{sub}.{domain}"
            async with sem:
                try:
                    answers = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: resolver.resolve(fqdn, "A")
                    )
                    ips = [str(r) for r in answers]
                    found.append({"subdomain": fqdn, "ips": ips})
                except Exception:
                    pass

        await asyncio.gather(*[check_subdomain(s) for s in wordlist])

        return {
            "domain": domain,
            "total_checked": len(wordlist),
            "found_count": len(found),
            "subdomains": sorted(found, key=lambda x: x["subdomain"]),
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }
