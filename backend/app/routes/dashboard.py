from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Run, Campaign, Customer

router = APIRouter()

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

    out = []
    for r, c, cust in rows:
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
        })

    return out
