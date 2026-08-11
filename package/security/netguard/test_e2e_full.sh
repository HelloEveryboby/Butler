#!/bin/bash
# 端到端测试脚本 — 完整版（含所有新功能）
set -e

BASE="http://localhost:8000"
PASS="SecurePass123!"

echo "=== 1. Health ==="
curl -sf "$BASE/health" | python3 -m json.tool

echo ""
echo "=== 2. Register ==="
REG=$(curl -sf -X POST "$BASE/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"email\":\"admin@test.com\",\"password\":\"$PASS\"}")
TOKEN=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token: ${TOKEN:0:20}..."

echo ""
echo "=== 3. Get Me ==="
curl -sf "$BASE/api/v1/auth/me" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 4. Threat Lookup (malicious) ==="
curl -sf "$BASE/api/v1/threat-intel/lookup?target=192.168.1.100" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 5. Threat Lookup (clean) ==="
curl -sf "$BASE/api/v1/threat-intel/lookup?target=8.8.8.8" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 6. Protection — SQLi ==="
curl -sf -X POST "$BASE/api/v1/protection/analyze" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"source_ip":"10.0.0.1","payload":"1'\'' UNION SELECT * FROM users--"}' | python3 -m json.tool

echo ""
echo "=== 7. Protection — Clean ==="
curl -sf -X POST "$BASE/api/v1/protection/analyze" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"source_ip":"10.0.0.99"}' | python3 -m json.tool

echo ""
echo "=== 8. Blocked IPs ==="
curl -sf "$BASE/api/v1/protection/blocked-ips" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 9. Rules ==="
curl -sf "$BASE/api/v1/protection/rules" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 10. DNS Lookup ==="
curl -sf -X POST "$BASE/api/v1/dns/lookup" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"domain":"example.com"}' | python3 -m json.tool

echo ""
echo "=== 11. Reverse DNS ==="
curl -sf -X POST "$BASE/api/v1/dns/reverse" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ip":"8.8.8.8"}' | python3 -m json.tool

echo ""
echo "=== 12. Blacklist Fetch ==="
curl -sf -X POST "$BASE/api/v1/blacklist/fetch" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Sources: {len(d[\"sources\"])}')
for k,v in d['sources'].items():
    print(f'  {k}: {v.get(\"count\",0)} IPs, status={v.get(\"status\",v.get(\"error\",\"?\"))}')
print(f'Total IPs in store: {d[\"total_ips\"]}')
"

echo ""
echo "=== 13. Blacklist Check ==="
curl -sf "$BASE/api/v1/blacklist/check/8.8.8.8" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 14. Task List ==="
curl -sf "$BASE/api/v1/tasks/" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 15. Schedule Create ==="
curl -sf -X POST "$BASE/api/v1/schedules/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"target":"10.0.0.1","scan_type":"port_scan","cron_expr":"0 2 * * *"}' | python3 -m json.tool

echo ""
echo "=== 16. Schedule List ==="
curl -sf "$BASE/api/v1/schedules/" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 17. Report Export (CSV) ==="
curl -sf "$BASE/api/v1/reports/threats?format=csv" \
  -H "Authorization: Bearer $TOKEN" | head -5

echo ""
echo "=== 18. Report Export (JSON) ==="
curl -sf "$BASE/api/v1/reports/threats?format=json" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Records: {len(d)}')"

echo ""
echo "=== 19. Dashboard Stats ==="
curl -sf "$BASE/api/v1/stats/dashboard" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 20. Threat History ==="
curl -sf "$BASE/api/v1/threat-intel/history?limit=5" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Threat records: {len(d[\"records\"])}')"

echo ""
echo "=== 21. Protection History ==="
curl -sf "$BASE/api/v1/protection/history?limit=5" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Protection records: {len(d[\"records\"])}')"

echo ""
echo "=== 22. Endpoint Count ==="
curl -sf "$BASE/openapi.json" | python3 -c "
import sys,json
d=json.load(sys.stdin)
paths=d.get('paths',{})
total=sum(len(m) for m in paths.values())
print(f'Total API endpoints: {total}')
for p,methods in sorted(paths.items()):
    for m in methods:
        print(f'  {m.upper():6s} {p}')
"

echo ""
echo "✅ ALL 22 END-TO-END TESTS PASSED"
