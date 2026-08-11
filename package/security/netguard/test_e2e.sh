#!/bin/bash
# 端到端测试脚本
set -e

BASE="http://localhost:8000"
PASS="SecurePass123!"

echo "=== 1. Health Check ==="
curl -sf "$BASE/health" | python3 -m json.tool

echo ""
echo "=== 2. Register ==="
REG=$(curl -sf -X POST "$BASE/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"email\":\"admin@test.com\",\"password\":\"$PASS\"}")
echo "$REG" | python3 -m json.tool
TOKEN=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
APIKEY=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")
echo "Token: ${TOKEN:0:20}..."
echo "API Key: ${APIKEY:0:20}..."

echo ""
echo "=== 3. Get Me (JWT) ==="
curl -sf "$BASE/api/v1/auth/me" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 4. Get Me (API Key) ==="
curl -sf "$BASE/api/v1/auth/me" -H "X-API-Key: $APIKEY" | python3 -m json.tool

echo ""
echo "=== 5. Threat Lookup — Malicious IP ==="
curl -sf "$BASE/api/v1/threat-intel/lookup?target=192.168.1.100" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 6. Threat Lookup — Clean IP ==="
curl -sf "$BASE/api/v1/threat-intel/lookup?target=8.8.8.8" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 7. Threat Lookup — Malicious Domain ==="
curl -sf "$BASE/api/v1/threat-intel/lookup?target=malware-c2.example.com" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 8. Protection — SQL Injection ==="
curl -sf -X POST "$BASE/api/v1/protection/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_ip":"10.0.0.1","payload":"1'\'' UNION SELECT * FROM users--"}' | python3 -m json.tool

echo ""
echo "=== 9. Protection — XSS ==="
curl -sf -X POST "$BASE/api/v1/protection/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_ip":"10.0.0.2","payload":"<script>alert(1)</script>"}' | python3 -m json.tool

echo ""
echo "=== 10. Protection — Clean Request ==="
curl -sf -X POST "$BASE/api/v1/protection/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_ip":"10.0.0.3"}' | python3 -m json.tool

echo ""
echo "=== 11. Blocked IPs ==="
curl -sf "$BASE/api/v1/protection/blocked-ips" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 12. Protection Rules ==="
curl -sf "$BASE/api/v1/protection/rules" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 13. Threat History ==="
curl -sf "$BASE/api/v1/threat-intel/history?limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 14. Protection History ==="
curl -sf "$BASE/api/v1/protection/history?limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 15. Dashboard Stats ==="
curl -sf "$BASE/api/v1/stats/dashboard" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 16. Unauthorized Access ==="
curl -s "$BASE/api/v1/auth/me" | python3 -m json.tool

echo ""
echo "=== 17. API Docs Endpoint Count ==="
curl -sf "$BASE/openapi.json" | python3 -c "
import sys,json
d=json.load(sys.stdin)
paths=d.get('paths',{})
print(f'Total endpoints: {sum(len(m) for m in paths.values())}')
for p,methods in sorted(paths.items()):
    for m in methods:
        print(f'  {m.upper():6s} {p}')
"

echo ""
echo "✅ ALL END-TO-END TESTS PASSED"
