# PetTech: ระบบจองนัดสัตวแพทย์
**ปัญหา:** คลินิกรับนัดด้วยมือ/แชท ทำให้จองซ้ำและเจ้าของไม่เห็นเวลาว่างจริง (ทีมต้องเติมหลักฐานจริง เช่น สัมภาษณ์/แบบสอบถาม ก่อนนำเสนอ)
**Stack:** FastAPI · PostgreSQL · HTML/JS · Docker Compose · Jenkins

## รัน (ใน Course Container `tuchsanai/devtools:2569_1`)
```
cp .env.example .env      # แล้วแก้รหัสผ่าน
docker compose up -d --build --wait
docker compose exec -T app python scripts/smoke.py http://localhost:8000
# เปิด http://localhost:8081  หยุด: docker compose down   (ล้างข้อมูล: down -v)
```
ทดสอบหน่วย: `pip install -r requirements.txt && python -m pytest -q`

## Traceability Matrix
| Requirement | Acceptance Criteria | ส่วนที่ทำ | วิธีตรวจ |
|---|---|---|---|
| R1 สมัคร/เข้าสู่ระบบ | รหัสผ่านผิดแจ้งข้อความกลางๆ ไม่บอกว่าผิดช่องใด | `/api/login` | test_login_wrong_password_generic |
| R2 เห็นเฉพาะข้อมูลตนเอง | ยกเลิก/จองให้สัตว์ของผู้อื่นไม่ได้ (404) | `current_user`, owner check | test_cannot_touch_others |
| R3 จองนัด | จองสำเร็จได้รหัส BK-xxxxx และเห็นในรายการ | `POST /api/bookings` | test_book_success_and_listed |
| R4 ไม่จองซ้ำ | ช่วงเวลาเดียวกันจองได้ 1 คน อีกคนได้ 409 + เวลาทดแทน | partial unique index | test_double_booking..., smoke.py |
| R5 ยกเลิกแล้วคืนเวลา | จองช่วงนั้นใหม่ได้ | `DELETE /api/bookings/{id}` | test_cancel_frees_slot |
| R6 ตรวจ Input | เวลา/วันที่ผิดถูกปฏิเสธ | validation | test_invalid_input |
| R7 ส่งมอบอัตโนมัติ | Build → Test → Deploy → Smoke | `Jenkinsfile` | Jenkins build log |

## Known limitations (เปิดเผยตามจริง)
Token ต่อผู้ใช้ 1 ชุด · ยังไม่มีมุมมองสัตวแพทย์/การแจ้งเตือน (Broker/Worker) · ยังไม่มี Monitoring · ช่วงเวลาคลินิกตายตัว 09:00–16:00
