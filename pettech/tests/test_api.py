import os, datetime as dt
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
if os.path.exists("test.db"): os.remove("test.db")
import pytest
from fastapi.testclient import TestClient
from app.main import app

DAY = (dt.date.today() + dt.timedelta(days=3)).isoformat()

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def make_user(c, email):
    c.post("/api/register", json={"email": email, "password": "secret1"})
    t = c.post("/api/login", json={"email": email, "password": "secret1"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    pet = c.post("/api/pets", json={"name": "มะม่วง", "species": "สุนัข"}, headers=h).json()
    return h, pet["id"]

def body(pet, time="10:00"):
    return {"pet_id": pet, "date": DAY, "time": time, "service": "วัคซีน"}

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}

def test_login_wrong_password_generic(client):
    make_user(client, "a@x.com")
    r = client.post("/api/login", json={"email": "a@x.com", "password": "wrong11"})
    assert r.status_code == 401 and "ไม่ถูกต้อง" in r.json()["detail"]

def test_requires_auth(client):
    assert client.get("/api/bookings").status_code == 401

def test_book_success_and_listed(client):
    h, pet = make_user(client, "b@x.com")
    r = client.post("/api/bookings", json=body(pet, "09:00"), headers=h)
    assert r.status_code == 201 and r.json()["code"].startswith("BK-")
    assert any(b["id"] == r.json()["id"] for b in client.get("/api/bookings", headers=h).json())

def test_double_booking_conflict_with_alternatives(client):
    h1, p1 = make_user(client, "c1@x.com"); h2, p2 = make_user(client, "c2@x.com")
    assert client.post("/api/bookings", json=body(p1, "11:00"), headers=h1).status_code == 201
    r = client.post("/api/bookings", json=body(p2, "11:00"), headers=h2)
    assert r.status_code == 409 and "11:00" not in r.json()["detail"]["alternatives"]
    slots = client.get(f"/api/slots?date={DAY}", headers=h2).json()
    assert [s for s in slots if s["time"] == "11:00"][0]["available"] is False

def test_cancel_frees_slot(client):
    h, pet = make_user(client, "d@x.com")
    bid = client.post("/api/bookings", json=body(pet, "14:00"), headers=h).json()["id"]
    assert client.delete(f"/api/bookings/{bid}", headers=h).status_code == 200
    assert client.post("/api/bookings", json=body(pet, "14:00"), headers=h).status_code == 201

def test_cannot_touch_others(client):
    h1, p1 = make_user(client, "e1@x.com"); h2, p2 = make_user(client, "e2@x.com")
    bid = client.post("/api/bookings", json=body(p1, "15:00"), headers=h1).json()["id"]
    assert client.delete(f"/api/bookings/{bid}", headers=h2).status_code == 404
    assert client.post("/api/bookings", json=body(p1, "16:00"), headers=h2).status_code == 404

def test_invalid_input(client):
    h, pet = make_user(client, "f@x.com")
    assert client.post("/api/bookings", json=body(pet, "03:00"), headers=h).status_code == 422
    past = {**body(pet), "date": "2020-01-01"}
    assert client.post("/api/bookings", json=past, headers=h).status_code == 400
