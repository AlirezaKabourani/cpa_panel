from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Run
from fastapi.responses import FileResponse
import os


router = APIRouter()

@router.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    rows = db.query(Run).order_by(Run.started_at.desc()).limit(200).all()
    return [{
        "id": r.id,
        "campaign_id": r.campaign_id,
        "status": r.status,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
        "log_path": r.log_path,
        "artifacts_path": r.artifacts_path,
    } for r in rows]

@router.get("/runs/{run_id}/log/download")
def download_run_log(run_id: str, db: Session = Depends(get_db)):
    r = db.query(Run).filter(Run.id == run_id).first()
    if not r or not r.log_path:
        raise HTTPException(status_code=404, detail="log not found")

    if not os.path.exists(r.log_path):
        raise HTTPException(status_code=404, detail="log file missing")

    return FileResponse(
        path=r.log_path,
        media_type="text/plain",
        filename=f"run_{run_id}.log",
    )

@router.get("/runs/{run_id}/result/download")
def download_run_result(run_id: str, db: Session = Depends(get_db)):
    r = db.query(Run).filter(Run.id == run_id).first()
    if not r or not r.artifacts_path:
        raise HTTPException(status_code=404, detail="run not found")

    csv_path = os.path.join(r.artifacts_path, "rubika_message_log.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="result csv not found")

    return FileResponse(
        path=csv_path,
        media_type="text/csv",
        filename=f"rubika_message_log_{run_id}.csv",
    )



@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    r = db.query(Run).filter(Run.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "id": r.id,
        "campaign_id": r.campaign_id,
        "status": r.status,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
        "log_path": r.log_path,
        "artifacts_path": r.artifacts_path,
        "result_json": r.result_json,
    }

@router.get("/runs/{run_id}/log")
def get_run_log(run_id: str, db: Session = Depends(get_db)):
    r = db.query(Run).filter(Run.id == run_id).first()
    if not r or not r.log_path:
        raise HTTPException(status_code=404, detail="log not found")
    try:
        with open(r.log_path, "r", encoding="utf-8", errors="replace") as f:
            return {"log": f.read()}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="log file missing")
