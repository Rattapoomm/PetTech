import os, secrets, hashlib, datetime as dt
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, ForeignKey, DateTime, Index, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from sqlalchemy.exc import IntegrityError

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(engine, expire_on_commit=False)
SLOTS = [f"{h:02d}:00" for h in range(9, 17)]
SERVICES = ["ตรวจสุขภาพ", "วัคซีน", "ทำหมัน", "ทำความสะอาดฟัน"]

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    salt: Mapped[str] = mapped_column(String(32))
    pw_hash: Mapped[str] = mapped_column(String(128))
    token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

class Pet(Base):
    __tablename__ = "pets"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    species: Mapped[str] = mapped_column(String(50))

class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"))
    slot: Mapped[dt.datetime] = mapped_column(DateTime)
    service: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="booked")
    # กันจองซ้ำระดับ DB: ช่วงเวลาเดียวกันมีได้เพียง 1 นัดที่ status=booked (แม้จองพร้อมกัน)
    __table_args__ = (Index("uq_active_slot", "slot", unique=True,
                            sqlite_where=(status == "booked"), postgresql_where=(status == "booked")),)

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title="PetTech Vet Booking", lifespan=lifespan)

def get_db():
    with SessionLocal() as db:
        yield db

def hash_pw(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 100_000).hex()

def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    token = authorization.removeprefix("Bearer ").strip()
    user = db.scalar(select(User).where(User.token == token)) if token else None
    if not user:
        raise HTTPException(401, "กรุณาเข้าสู่ระบบ")
    return user

class Cred(BaseModel):
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=6, max_length=100)

class PetIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    species: str = Field(min_length=1, max_length=50)

class BookingIn(BaseModel):
    pet_id: int
    date: dt.date
    time: str
    service: str

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}

@app.post("/api/register", status_code=201)
def register(c: Cred, db: Session = Depends(get_db)):
    salt = secrets.token_hex(16)
    db.add(User(email=c.email.lower(), salt=salt, pw_hash=hash_pw(c.password, salt)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "อีเมลนี้ถูกใช้แล้ว")
    return {"ok": True}

@app.post("/api/login")
def login(c: Cred, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == c.email.lower()))
    if not u or not secrets.compare_digest(u.pw_hash, hash_pw(c.password, u.salt)):
        raise HTTPException(401, "อีเมลหรือรหัสผ่านไม่ถูกต้อง")  # ไม่บอกว่าผิดช่องใด
    u.token = secrets.token_hex(24)
    db.commit()
    return {"token": u.token}

@app.get("/api/pets")
def list_pets(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": p.id, "name": p.name, "species": p.species} for p in db.scalars(select(Pet).where(Pet.owner_id == u.id))]

@app.post("/api/pets", status_code=201)
def add_pet(p: PetIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    pet = Pet(owner_id=u.id, name=p.name, species=p.species)
    db.add(pet); db.commit()
    return {"id": pet.id, "name": pet.name, "species": pet.species}

def free_slots(db, day: dt.date):
    taken = {b.slot.strftime("%H:%M") for b in db.scalars(
        select(Booking).where(Booking.status == "booked",
                              Booking.slot >= dt.datetime.combine(day, dt.time.min),
                              Booking.slot < dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min)))}
    return [{"time": t, "available": t not in taken} for t in SLOTS]

@app.get("/api/services")
def services(): return SERVICES

@app.get("/api/slots")
def slots(date: dt.date, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return free_slots(db, date)

@app.post("/api/bookings", status_code=201)
def book(b: BookingIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if b.time not in SLOTS or b.service not in SERVICES:
        raise HTTPException(422, "ช่วงเวลาหรือบริการไม่ถูกต้อง")
    slot = dt.datetime.combine(b.date, dt.datetime.strptime(b.time, "%H:%M").time())
    if slot <= dt.datetime.now():
        raise HTTPException(400, "ไม่สามารถจองเวลาที่ผ่านมาแล้ว")
    pet = db.get(Pet, b.pet_id)
    if not pet or pet.owner_id != u.id:
        raise HTTPException(404, "ไม่พบสัตว์เลี้ยงของคุณ")
    bk = Booking(owner_id=u.id, pet_id=pet.id, slot=slot, service=b.service)
    db.add(bk)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        alts = [s["time"] for s in free_slots(db, b.date) if s["available"]]
        raise HTTPException(409, {"message": "ช่วงเวลานี้เพิ่งถูกจอง", "alternatives": alts})
    return {"id": bk.id, "code": f"BK-{bk.id:05d}", "slot": slot.isoformat(), "status": bk.status}

@app.get("/api/bookings")
def my_bookings(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Booking, Pet).join(Pet, Pet.id == Booking.pet_id)
                      .where(Booking.owner_id == u.id).order_by(Booking.slot)).all()
    return [{"id": b.id, "code": f"BK-{b.id:05d}", "slot": b.slot.isoformat(), "service": b.service,
             "status": b.status, "pet": p.name} for b, p in rows]

@app.delete("/api/bookings/{bid}")
def cancel(bid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    b = db.get(Booking, bid)
    if not b or b.owner_id != u.id:
        raise HTTPException(404, "ไม่พบนัดหมาย")
    b.status = "cancelled"   # คืนช่วงเวลาให้จองใหม่ได้ (partial unique index)
    db.commit()
    return {"id": b.id, "status": b.status}

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
