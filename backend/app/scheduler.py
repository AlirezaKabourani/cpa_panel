import uuid
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import ScheduledRun, Campaign, Customer, AudienceSnapshot, Run
from .runners.rscript_runner import run_r_campaign

scheduler = BackgroundScheduler()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def parse_iso(dt_str: str) -> datetime:
    # accepts "2026-01-04T10:00:00Z" or "+00:00"
    s = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(s)

def _create_run_row(db: Session, campaign_id: str) -> Run:
    rid = str(uuid.uuid4())
    r = Run(
        id=rid,
        campaign_id=campaign_id,
        status="running",
        started_at=now_iso(),
        finished_at=None,
        log_path=None,
        artifacts_path=None,
        result_json=None,
    )
    db.add(r)
    db.commit()
    return r

def process_due_scheduled_runs():
    """
    Poll DB for due scheduled_runs and execute them.
    Runs every ~20 seconds (config in main.py).
    """
    db = SessionLocal()
    try:
        due = (
            db.query(ScheduledRun)
            .filter(ScheduledRun.status == "scheduled")
            .all()
        )

        # filter in python to avoid timezone quirks in sqlite string compare
        now_dt = datetime.now(timezone.utc)
        due = [x for x in due if parse_iso(x.run_at) <= now_dt]

        for sr in due:
            sr.updated_at = now_iso()

            # run it
            sr.status = "running"
            db.commit()

            c = db.query(Campaign).filter(Campaign.id == sr.campaign_id).first()
            if not c:
                sr.status = "failed"
                db.commit()
                continue

            cust = db.query(Customer).filter(Customer.id == c.customer_id).first()
            snap = db.query(AudienceSnapshot).filter(AudienceSnapshot.id == c.audience_snapshot_id).first()
            if not cust or not snap:
                sr.status = "failed"
                db.commit()
                continue

            run_row = _create_run_row(db, c.id)
            sr.last_run_id = run_row.id
            db.commit()

            out = run_r_campaign(
                mode="send",
                rubica_token=sr.token_plain,
                snapshot_path=snap.stored_path,
                service_id=cust.service_id,
                file_id=c.selected_file_id,
                message_text=c.message_text,
                test_number=None,
                run_id=run_row.id,
            )

            run_row.log_path = out.get("log_path")
            run_row.artifacts_path = out.get("run_dir")
            run_row.finished_at = now_iso()

            if out.get("returncode") == 0:
                run_row.status = "success"
                sr.status = "success"
            else:
                run_row.status = "failed"
                sr.status = "failed"

            sr.updated_at = now_iso()
            db.commit()

    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(process_due_scheduled_runs, "interval", seconds=20, id="poll_scheduled_runs", replace_existing=True)
        scheduler.start()
