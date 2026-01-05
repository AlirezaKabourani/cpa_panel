import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Customer, CustomerMessage, CustomerMedia

router = APIRouter()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "customer"

@router.get("/customers")
def list_customers(db: Session = Depends(get_db)):
    rows = db.query(Customer).order_by(Customer.created_at.desc()).all()
    return [{
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "service_id": r.service_id,
        "created_at": r.created_at,
    } for r in rows]

@router.post("/customers")
def create_customer(payload: dict, db: Session = Depends(get_db)):
    name = (payload.get("name") or "").strip()
    service_id = (payload.get("service_id") or "").strip()
    if not name or not service_id:
        raise HTTPException(status_code=400, detail="name and service_id are required")

    code = payload.get("code")
    code = slugify(code) if code else slugify(name)

    # ensure unique code
    base = code
    i = 2
    while db.query(Customer).filter(Customer.code == code).first():
        code = f"{base}_{i}"
        i += 1

    # ensure unique name
    if db.query(Customer).filter(Customer.name == name).first():
        raise HTTPException(status_code=409, detail="customer name already exists")

    c = Customer(
        id=str(uuid.uuid4()),
        code=code,
        name=name,
        service_id=service_id,
        created_at=now_iso(),
    )
    db.add(c)
    db.commit()
    return {"id": c.id, "code": c.code}

@router.get("/customers/{customer_id}/messages")
def list_customer_messages(customer_id: str, db: Session = Depends(get_db)):
    rows = db.query(CustomerMessage).filter(CustomerMessage.customer_id == customer_id).order_by(CustomerMessage.created_at.desc()).all()
    return [{
        "id": r.id,
        "title": r.title,
        "text_template": r.text_template,
        "created_at": r.created_at,
        "is_active": bool(r.is_active),
    } for r in rows]

@router.post("/customers/{customer_id}/messages")
def create_customer_message(customer_id: str, payload: dict, db: Session = Depends(get_db)):
    text = payload.get("text_template")
    if not text or not str(text).strip():
        raise HTTPException(status_code=400, detail="text_template is required")

    title = payload.get("title")
    m = CustomerMessage(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        title=(title.strip() if isinstance(title, str) else None),
        text_template=str(text),
        created_at=now_iso(),
        is_active=1,
    )
    db.add(m)
    db.commit()
    return {"id": m.id}

@router.get("/customers/{customer_id}/media")
def list_customer_media(customer_id: str, db: Session = Depends(get_db)):
    rows = db.query(CustomerMedia).filter(CustomerMedia.customer_id == customer_id).order_by(CustomerMedia.created_at.desc()).all()
    return [{
        "id": r.id,
        "file_id": r.file_id,
        "file_name": r.file_name,
        "file_type": r.file_type,
        "created_at": r.created_at,
    } for r in rows]
