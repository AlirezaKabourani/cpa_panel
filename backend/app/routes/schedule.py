import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ScheduledRun, Campaign, Customer

router = APIRouter()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

@router.get("/scheduled-runs")
def list_scheduled_runs(db: Session = Depends(get_db)):
    rows = db.query(ScheduledRun).order_by(ScheduledRun.run_at.desc()).limit(300).all()
    return [{
        "id": r.id,
        "campaign_id": r.campaign_id,
        "run_at": r.run_at,
        "status": r.status,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
        "last_run_id": r.last_run_id,
        "has_token": bool(r.token_plain),
        "customer_name": r.customer_name,
        "campaign_name": r.campaign_name,
    } for r in rows]

@router.post("/campaigns/{campaign_id}/schedule")
def schedule_campaign(campaign_id: str, payload: dict, db: Session = Depends(get_db)):
    run_at = payload.get("run_at")  # ISO UTC string
    if not run_at:
        raise HTTPException(status_code=400, detail="run_at is required (ISO UTC string)")

    token = payload.get("token")
    if not token or not str(token).strip():
        raise HTTPException(status_code=400, detail="token is required for scheduling")

    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="campaign not found")
    
    cust = db.query(Customer).filter(Customer.id == c.customer_id).first()
    customer_name = cust.name if cust else None
    campaign_name = c.name

    sid = str(uuid.uuid4())
    sr = ScheduledRun(
        id=sid,
        campaign_id=campaign_id,
        run_at=run_at,
        status="scheduled",
        token_plain=str(token).strip(),
        created_at=now_iso(),
        updated_at=now_iso(),
        last_run_id=None,
        customer_name=customer_name,
        campaign_name=campaign_name,
    )
    db.add(sr)
    db.commit()

    return {"scheduled_run_id": sid, "status": sr.status}

@router.post("/scheduled-runs/{scheduled_run_id}/run-now-with-token")
def run_scheduled_now_with_token(scheduled_run_id: str, payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    if not token or not str(token).strip():
        raise HTTPException(status_code=400, detail="token is required")

    sr = db.query(ScheduledRun).filter(ScheduledRun.id == scheduled_run_id).first()
    if not sr:
        raise HTTPException(status_code=404, detail="scheduled run not found")

    # set token temporarily (in DB) and mark scheduled (processor will pick it up quickly)
    sr.token_plain = str(token).strip()
    sr.status = "scheduled"
    sr.updated_at = now_iso()
    db.commit()

    return {"ok": True, "message": "Token saved for this scheduled run; it will execute shortly."}

@router.post("/scheduled-runs/{scheduled_run_id}/cancel")
def cancel_scheduled_run(scheduled_run_id: str, db: Session = Depends(get_db)):
    sr = db.query(ScheduledRun).filter(ScheduledRun.id == scheduled_run_id).first()
    if not sr:
        raise HTTPException(status_code=404, detail="scheduled run not found")
    if sr.status in ("success", "failed", "canceled"):
        return {"ok": True, "status": sr.status}

    sr.status = "canceled"
    sr.updated_at = now_iso()
    db.commit()
    return {"ok": True, "status": sr.status}
