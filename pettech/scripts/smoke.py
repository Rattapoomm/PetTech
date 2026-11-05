"""Smoke test หลัง Deploy ใช้ระบบจริงผ่าน HTTP  ใช้: python scripts/smoke.py http://localhost:8000"""
import json, sys, time, urllib.request, urllib.error
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

def call(method, path, body=None, token=None):
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(urllib.request.Request(URL + path, data=data, headers=h, method=method)) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")

def check(name, ok):
    print(("[ok] " if ok else "[FAIL] ") + name)
    if not ok: sys.exit(1)

check("health", call("GET", "/health")[0] == 200)
email = f"smoke{int(time.time())}@test.com"
cred = {"email": email, "password": "secret1"}
check("register", call("POST", "/api/register", cred)[0] == 201)
token = call("POST", "/api/login", cred)[1]["token"]
pet = call("POST", "/api/pets", {"name": "Mango", "species": "dog"}, token)[1]["id"]
b = {"pet_id": pet, "date": "2031-03-10", "time": "10:00", "service": "วัคซีน"}
check("booking -> 201", call("POST", "/api/bookings", b, token)[0] == 201)
check("double booking -> 409", call("POST", "/api/bookings", b, token)[0] == 409)
print("SMOKE PASSED")