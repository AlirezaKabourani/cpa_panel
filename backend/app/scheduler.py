import uuid
from queue import Empty, Queue
from threading import Event, Lock, Thread
from datetime import datetime, timezone
import json
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import ScheduledRun, Campaign, Customer, AudienceSnapshot, Run
from .runners.rscript_runner import run_r_campaign
from .runners.splus_runner import run_splus_campaign

scheduler = BackgroundScheduler()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "data" / "runs"
_dispatch_queue: Queue[str] = Queue()
_enqueued_ids: set[str] = set()
_enqueue_lock = Lock()
_poll_lock = Lock()
_worker_stop = Event()
_worker_thread: Thread | None = None

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def parse_iso(dt_str: str) -> datetime:
    # accepts "2026-01-04T10:00:00Z" or "+00:00"
    s = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(s)

def _create_run_row(db: Session, campaign_id: str) -> Run:
    rid = str(uuid.uuid4())
    run_dir = RUNS_DIR / rid
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "run.log"
    if not log_path.exists():
        log_path.write_text("Run started...\n", encoding="utf-8")
    r = Run(
        id=rid,
        campaign_id=campaign_id,
        status="running",
        started_at=now_iso(),
        finished_at=None,
        log_path=str(log_path),
        artifacts_path=str(run_dir),
        result_json=None,
    )
    db.add(r)
    db.commit()
    return r

def _mark_scheduled_failed(db: Session, sr: ScheduledRun, reason: str):
    sr.status = "failed"
    sr.updated_at = now_iso()
    db.commit()


def _run_single_scheduled(scheduled_run_id: str):
    db = SessionLocal()
    try:
        sr = db.query(ScheduledRun).filter(ScheduledRun.id == scheduled_run_id).first()
        if not sr:
            return

        # Skip if user canceled/changed state before worker picked it up.
        if sr.status != "scheduled":
            return

        sr.updated_at = now_iso()
        sr.status = "running"
        db.commit()

        c = db.query(Campaign).filter(Campaign.id == sr.campaign_id).first()
        if not c:
            _mark_scheduled_failed(db, sr, "campaign not found")
            return

        cust = db.query(Customer).filter(Customer.id == c.customer_id).first()
        snap = db.query(AudienceSnapshot).filter(AudienceSnapshot.id == c.audience_snapshot_id).first()
        if not cust or not snap:
            _mark_scheduled_failed(db, sr, "campaign missing customer or snapshot")
            return

        run_row = _create_run_row(db, c.id)
        sr.last_run_id = run_row.id
        db.commit()

        try:
            if c.platform == "splus":
                out = run_splus_campaign(
                    mode="send",
                    splus_bot_id=sr.token_plain,
                    snapshot_path=snap.stored_path,
                    file_id=c.selected_file_id,
                    message_text=c.message_text,
                    test_number=None,
                    run_id=run_row.id,
                    scenario_name=c.name or c.id,
                )
            else:
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
        except Exception as e:
            out = {"returncode": 999, "error": str(e)}

        run_row.log_path = out.get("log_path")
        run_row.artifacts_path = out.get("run_dir")
        run_row.finished_at = now_iso()

        if out.get("returncode") == 0:
            run_row.status = "success"
            sr.status = "success"
            run_row.result_json = json.dumps({"ok": True}, ensure_ascii=False)
        else:
            run_row.status = "failed"
            sr.status = "failed"
            run_row.result_json = json.dumps({"ok": False, "returncode": out.get("returncode"), "error": out.get("error")}, ensure_ascii=False)

        sr.updated_at = now_iso()
        db.commit()

    finally:
        db.close()


def _worker_loop():
    while not _worker_stop.is_set():
        try:
            scheduled_run_id = _dispatch_queue.get(timeout=1.0)
        except Empty:
            continue

        with _enqueue_lock:
            _enqueued_ids.discard(scheduled_run_id)

        try:
            _run_single_scheduled(scheduled_run_id)
        finally:
            _dispatch_queue.task_done()


def process_due_scheduled_runs():
    """
    Poll DB for due scheduled_runs and enqueue them for background processing.
    This function must stay lightweight to avoid APScheduler max_instances skips.
    """
    if not _poll_lock.acquire(blocking=False):
        return

    db = SessionLocal()
    try:
        due = db.query(ScheduledRun).filter(ScheduledRun.status == "scheduled").all()
        now_dt = datetime.now(timezone.utc)
        due = [x for x in due if parse_iso(x.run_at) <= now_dt]

        for sr in due:
            with _enqueue_lock:
                if sr.id in _enqueued_ids:
                    continue
                _enqueued_ids.add(sr.id)
            _dispatch_queue.put(sr.id)
    finally:
        db.close()
        _poll_lock.release()


def start_scheduler():
    global _worker_thread
    if not scheduler.running:
        _worker_stop.clear()
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = Thread(target=_worker_loop, name="scheduled-run-worker", daemon=True)
            _worker_thread.start()

        scheduler.add_job(
            process_due_scheduled_runs,
            "interval",
            seconds=20,
            id="poll_scheduled_runs",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
