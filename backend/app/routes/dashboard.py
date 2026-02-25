from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import os
import re
import csv

from ..db import get_db
from ..models import Run, Campaign, Customer, AudienceSnapshot

router = APIRouter()

PROGRESS_RE = re.compile(r"\[(\d+)\s*/\s*(\d+)\]")


def read_log_text_tail(log_path: str | None, max_bytes: int = 256 * 1024) -> str:
    if not log_path or not os.path.exists(log_path):
        return ""

    try:
        # Read only tail for performance; latest progress line is near file end.
        with open(log_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            tail = min(size, max_bytes)
            f.seek(-tail, os.SEEK_END)
            return f.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def read_log_text_head(log_path: str | None, max_bytes: int = 8 * 1024) -> str:
    if not log_path or not os.path.exists(log_path):
        return ""
    try:
        with open(log_path, "rb") as f:
            return f.read(max_bytes).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def is_test_run(log_path: str | None) -> bool:
    head = read_log_text_head(log_path)
    if not head:
        return False
    h = head.lower()
    return ("mode=test" in h) or ("--mode test" in h)


def extract_progress_from_log(log_path: str | None) -> tuple[int | None, int | None]:
    text = read_log_text_tail(log_path)
    if not text:
        return None, None

    matches = PROGRESS_RE.findall(text)
    if not matches:
        return None, None

    cur, total = matches[-1]
    try:
        return int(cur), int(total)
    except Exception:
        return None, None


def _csv_row_count(csv_path: str) -> int | None:
    if not csv_path or not os.path.exists(csv_path):
        return None
    try:
        # subtract header row if present
        with open(csv_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.reader(f)
            n = sum(1 for _ in reader)
        if n <= 0:
            return 0
        return max(0, n - 1)
    except Exception:
        return None


def infer_progress_from_artifacts(run: Run, campaign: Campaign, snapshot_row_count: int | None) -> tuple[int | None, int | None]:
    if not run.artifacts_path:
        return None, None

    splus_csv = os.path.join(run.artifacts_path, "splus_message_log.csv")
    rubika_csv = os.path.join(run.artifacts_path, "rubika_message_log.csv")
    sent = _csv_row_count(splus_csv)
    if sent is None:
        sent = _csv_row_count(rubika_csv)
    if sent is None:
        return None, None

    if run.status in ("success", "failed"):
        if snapshot_row_count and snapshot_row_count > 0:
            return sent, snapshot_row_count
        return sent, sent

    if snapshot_row_count and snapshot_row_count > 0:
        return sent, snapshot_row_count
    return sent, None

@router.get("/dashboard/runs")
def dashboard_runs(
    customer_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    Returns latest runs with campaign + customer info for dashboard.
    Filters:
      - customer_id (optional)
      - status: success|failed|running (optional)
      - q: substring search on campaign name or customer name (optional)
    """
    query = (
        db.query(Run, Campaign, Customer)
        .join(Campaign, Run.campaign_id == Campaign.id)
        .join(Customer, Campaign.customer_id == Customer.id)
    )

    if customer_id:
        query = query.filter(Customer.id == customer_id)
    if status:
        query = query.filter(Run.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((Campaign.name.like(like)) | (Customer.name.like(like)))

    rows = (
        query
        .order_by(Run.started_at.desc())
        .limit(max(1, min(limit, 1000)))
        .all()
    )

    snap_cache: dict[str, int] = {}
    out = []
    for r, c, cust in rows:
        # Hide test runs from dashboard.
        if is_test_run(r.log_path):
            continue

        progress_current, progress_total = extract_progress_from_log(r.log_path)

        if progress_current is None:
            snap_rows = None
            if c.audience_snapshot_id:
                if c.audience_snapshot_id not in snap_cache:
                    s = db.query(AudienceSnapshot).filter(AudienceSnapshot.id == c.audience_snapshot_id).first()
                    snap_cache[c.audience_snapshot_id] = int(s.row_count) if s else 0
                snap_rows = snap_cache.get(c.audience_snapshot_id) or None
            progress_current, progress_total = infer_progress_from_artifacts(r, c, snap_rows)

        progress_pct = None
        if progress_current is not None and progress_total and progress_total > 0:
            progress_pct = round((progress_current / progress_total) * 100, 2)

        out.append({
            "run_id": r.id,
            "campaign_id": c.id,
            "campaign_name": c.name,
            "customer_id": cust.id,
            "customer_name": cust.name,
            "status": r.status,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "artifacts_path": r.artifacts_path,  # not needed in UI but handy
            "has_log": bool(r.log_path),
            "has_result": bool(r.artifacts_path),
            "progress_current": progress_current,
            "progress_total": progress_total,
            "progress_pct": progress_pct,
        })

    return out
