#!/bin/sh
# Smoke test หลัง Deploy: ใช้ระบบจริงผ่าน HTTP  ใช้: ./scripts/smoke.sh http://localhost:8080
set -e
URL=${1:-http://localhost:8080}; E="smoke$(date +%s)@test.com"; D=2031-03-10
H='Content-Type: application/json'
curl -fsS "$URL/health" >/dev/null && echo "[ok] health"
curl -fsS -X POST "$URL/api/register" -H "$H" -d "{\"email\":\"$E\",\"password\":\"secret1\"}" >/dev/null
T=$(curl -fsS -X POST "$URL/api/login" -H "$H" -d "{\"email\":\"$E\",\"password\":\"secret1\"}" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
A="Authorization: Bearer $T"
P=$(curl -fsS -X POST "$URL/api/pets" -H "$H" -H "$A" -d '{"name":"Mango","species":"dog"}' | grep -o '"id":[0-9]*' | cut -d: -f2)
B="{\"pet_id\":$P,\"date\":\"$D\",\"time\":\"10:00\",\"service\":\"วัคซีน\"}"
C1=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL/api/bookings" -H "$H" -H "$A" -d "$B")
C2=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL/api/bookings" -H "$H" -H "$A" -d "$B")
[ "$C1" = 201 ] && echo "[ok] booking 201" || { echo "[FAIL] first booking=$C1"; exit 1; }
[ "$C2" = 409 ] && echo "[ok] double booking 409" || { echo "[FAIL] second booking=$C2"; exit 1; }
echo "SMOKE PASSED"
