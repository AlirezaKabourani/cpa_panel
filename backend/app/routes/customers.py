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
def list_customers(platform: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Customer)

    p = (platform or "").strip().lower()
    if p:
        if p not in ("rubika", "splus"):
            raise HTTPException(status_code=400, detail="platform must be rubika or splus")
        if p == "splus":
            query = query.filter(Customer.default_splus_token.isnot(None)).filter(Customer.default_splus_token != "")

    rows = query.order_by(Customer.created_at.desc()).all()
    if p == "rubika":
        rows = [r for r in rows if isinstance(r.service_id, str) and re.fullmatch(r"[0-9A-Fa-f]{24}", r.service_id or "")]
    return [{
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "service_id": r.service_id,
        "default_splus_token": r.default_splus_token,
        "created_at": r.created_at,
    } for r in rows]

@router.post("/customers")
def create_customer(payload: dict, db: Session = Depends(get_db)):
    name = (payload.get("name") or "").strip()
    service_id = (payload.get("service_id") or "").strip()
    default_splus_token = (payload.get("default_splus_token") or "").strip() or None
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

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
        service_id=service_id or "",
        default_splus_token=default_splus_token,
        created_at=now_iso(),
    )
    db.add(c)
    db.commit()
    return {"id": c.id, "code": c.code}

@router.put("/customers/{customer_id}")
def update_customer(customer_id: str, payload: dict, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="customer not found")

    name = payload.get("name")
    service_id = payload.get("service_id")
    default_splus_token = payload.get("default_splus_token")

    if isinstance(name, str):
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        existing = db.query(Customer).filter(Customer.name == name, Customer.id != customer_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="customer name already exists")
        c.name = name

    if isinstance(service_id, str):
        c.service_id = service_id.strip()

    if default_splus_token is None:
        c.default_splus_token = None
    elif isinstance(default_splus_token, str):
        c.default_splus_token = default_splus_token.strip() or None

    db.commit()
    return {"ok": True}

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

@router.put("/customers/{customer_id}/messages/{message_id}")
def update_customer_message(customer_id: str, message_id: str, payload: dict, db: Session = Depends(get_db)):
    m = (
        db.query(CustomerMessage)
        .filter(CustomerMessage.id == message_id)
        .filter(CustomerMessage.customer_id == customer_id)
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="message not found")

    text = payload.get("text_template")
    if isinstance(text, str):
        t = text.strip()
        if not t:
            raise HTTPException(status_code=400, detail="text_template cannot be empty")
        m.text_template = t

    if "title" in payload:
        title = payload.get("title")
        m.title = title.strip() if isinstance(title, str) and title.strip() else None

    db.commit()
    return {"ok": True}

@router.delete("/customers/{customer_id}/messages/{message_id}")
def delete_customer_message(customer_id: str, message_id: str, db: Session = Depends(get_db)):
    m = (
        db.query(CustomerMessage)
        .filter(CustomerMessage.id == message_id)
        .filter(CustomerMessage.customer_id == customer_id)
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="message not found")
    db.delete(m)
    db.commit()
    return {"ok": True}

@router.get("/customers/{customer_id}/media")
def list_customer_media(customer_id: str, platform: str = "rubika", db: Session = Depends(get_db)):
    p = str(platform or "rubika").strip().lower()
    if p not in ("rubika", "splus"):
        raise HTTPException(status_code=400, detail="platform must be rubika or splus")

    rows = (
        db.query(CustomerMedia)
        .filter(CustomerMedia.customer_id == customer_id)
        .filter(CustomerMedia.platform == p)
        .order_by(CustomerMedia.created_at.desc())
        .all()
    )
    return [{
        "id": r.id,
        "platform": r.platform,
        "file_id": r.file_id,
        "file_name": r.file_name,
        "file_type": r.file_type,
        "created_at": r.created_at,
    } for r in rows]
