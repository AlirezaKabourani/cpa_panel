import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AudienceSnapshot
from ..services.storage import new_snapshot_path
from ..services.validation import validate_and_clean

router = APIRouter()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def read_file_to_df(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file type: {ext}")

@router.post("/audience/upload")
async def upload_audience(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="Only .csv, .xlsx, .xls are supported")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    stored_path = new_snapshot_path(file.filename)
    stored_path.write_bytes(raw)

    try:
        df = read_file_to_df(stored_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    df, notes = validate_and_clean(df)
    if df.empty:
        raise HTTPException(status_code=400, detail="No valid rows found. Check columns and values.")

    row_count = int(len(df))
    h = sha256_bytes(raw)

    sid = str(uuid.uuid4())
    snap = AudienceSnapshot(
        id=sid,
        original_filename=file.filename,
        stored_path=str(stored_path),
        row_count=row_count,
        hash=h,
        created_at=now_iso(),
    )
    db.add(snap)
    db.commit()

    preview = df.head(10).to_dict(orient="records")
    cols = list(df.columns)

    return {
        "snapshot_id": sid,
        "original_filename": file.filename,
        "stored_path": str(stored_path),
        "row_count": row_count,
        "hash": h,
        "columns": cols,
        "preview": preview,
        "notes": notes,
    }
