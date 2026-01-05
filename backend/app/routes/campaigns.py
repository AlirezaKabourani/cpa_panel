import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from datetime import datetime, timezone
from ..models import Run, Customer, AudienceSnapshot
from ..runners.rscript_runner import run_r_campaign

from ..db import get_db
from ..models import Campaign, Customer, AudienceSnapshot

router = APIRouter()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    rows = db.query(Campaign).order_by(Campaign.created_at.desc()).limit(200).all()
    return [{
        "id": r.id,
        "name": r.name,
        "customer_id": r.customer_id,
        "audience_snapshot_id": r.audience_snapshot_id,
        "selected_file_id": r.selected_file_id,
        "status": r.status,
        "created_at": r.created_at,
    } for r in rows]

@router.post("/campaigns")
def create_campaign(payload: dict, db: Session = Depends(get_db)):
    customer_id = payload.get("customer_id")
    snapshot_id = payload.get("audience_snapshot_id")
    name = payload.get("name")
    if isinstance(name, str): name = name.strip() or None
    message_text = payload.get("message_text")
    selected_file_id = payload.get("selected_file_id")
    test_number = payload.get("test_number")

    if not customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required")
    if not snapshot_id:
        raise HTTPException(status_code=400, detail="audience_snapshot_id is required")
    if not message_text or not str(message_text).strip():
        raise HTTPException(status_code=400, detail="message_text is required")

    # ensure customer exists
    if not db.query(Customer).filter(Customer.id == customer_id).first():
        raise HTTPException(status_code=404, detail="customer not found")

    # ensure snapshot exists
    if not db.query(AudienceSnapshot).filter(AudienceSnapshot.id == snapshot_id).first():
        raise HTTPException(status_code=404, detail="audience snapshot not found")

    cid = str(uuid.uuid4())
    c = Campaign(
        id=cid,
        name=name,
        customer_id=customer_id,
        audience_snapshot_id=snapshot_id,
        selected_file_id=selected_file_id,
        message_text=str(message_text),
        test_number=str(test_number) if test_number else None,
        status="draft",
        created_at=now_iso(),
    )
    db.add(c)
    db.commit()

    return {"campaign_id": cid, "status": c.status}

@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "id": c.id,
        "name": c.name,
        "customer_id": c.customer_id,
        "audience_snapshot_id": c.audience_snapshot_id,
        "selected_file_id": c.selected_file_id,
        "message_text": c.message_text,
        "test_number": c.test_number,
        "status": c.status,
        "created_at": c.created_at,
    }


@router.post("/campaigns/{campaign_id}/send-test")
def send_test(campaign_id: str, payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    test_number = payload.get("test_number")

    if not token or not str(token).strip():
        raise HTTPException(status_code=400, detail="token is required")

    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="campaign not found")

    cust = db.query(Customer).filter(Customer.id == c.customer_id).first()
    snap = db.query(AudienceSnapshot).filter(AudienceSnapshot.id == c.audience_snapshot_id).first()
    if not cust or not snap:
        raise HTTPException(status_code=400, detail="campaign missing customer or snapshot")

    rid = str(uuid.uuid4())
    r = Run(
        id=rid,
        campaign_id=c.id,
        status="running",
        started_at=now_iso(),
        finished_at=None,
        log_path=None,
        artifacts_path=None,
        result_json=None,
    )
    db.add(r)
    db.commit()

    try:
        out = run_r_campaign(
            mode="test",
            rubica_token=str(token),
            snapshot_path=snap.stored_path,
            service_id=cust.service_id,
            file_id=c.selected_file_id,
            message_text=c.message_text,
            test_number=str(test_number) if test_number else (c.test_number or "989024004940"),
            run_id=rid,
        )

        r.log_path = out["log_path"]
        r.artifacts_path = out["run_dir"]
        r.finished_at = now_iso()

        if out["returncode"] == 0:
            r.status = "success"
            r.result_json = json.dumps({"ok": True}, ensure_ascii=False)
        else:
            r.status = "failed"
            r.result_json = json.dumps({"ok": False, "returncode": out["returncode"]}, ensure_ascii=False)

        db.commit()
        return {"run_id": rid, "status": r.status, "log_url": f"/api/runs/{rid}/log"}

    except Exception as e:
        r.status = "failed"
        r.finished_at = now_iso()
        r.result_json = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/{campaign_id}/run-now")
def run_now(campaign_id: str, payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    if not token or not str(token).strip():
        raise HTTPException(status_code=400, detail="token is required")

    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="campaign not found")

    cust = db.query(Customer).filter(Customer.id == c.customer_id).first()
    snap = db.query(AudienceSnapshot).filter(AudienceSnapshot.id == c.audience_snapshot_id).first()
    if not cust or not snap:
        raise HTTPException(status_code=400, detail="campaign missing customer or snapshot")

    rid = str(uuid.uuid4())
    r = Run(
        id=rid,
        campaign_id=c.id,
        status="running",
        started_at=now_iso(),
        finished_at=None,
        log_path=None,
        artifacts_path=None,
        result_json=None,
    )
    db.add(r)
    db.commit()

    try:
        out = run_r_campaign(
            mode="send",
            rubica_token=str(token),
            snapshot_path=snap.stored_path,
            service_id=cust.service_id,
            file_id=c.selected_file_id,
            message_text=c.message_text,
            test_number=None,
            run_id=rid,
        )

        r.log_path = out["log_path"]
        r.artifacts_path = out["run_dir"]
        r.finished_at = now_iso()

        if out["returncode"] == 0:
            r.status = "success"
            r.result_json = json.dumps({"ok": True}, ensure_ascii=False)
        else:
            r.status = "failed"
            r.result_json = json.dumps({"ok": False, "returncode": out["returncode"]}, ensure_ascii=False)

        db.commit()
        return {"run_id": rid, "status": r.status, "log_url": f"/api/runs/{rid}/log"}

    except Exception as e:
        r.status = "failed"
        r.finished_at = now_iso()
        r.result_json = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
