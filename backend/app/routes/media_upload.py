import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Customer, CustomerMedia
from ..runners.rscript_runner import run_r_upload_media

PROJECT_ROOT = Path(__file__).resolve().parents[3]
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"

router = APIRouter()

def ensure_uploads_dir():
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/customers/{customer_id}/media/upload")
async def upload_customer_media(
    customer_id: str,
    token: str = Form(...),                      # NOT stored
    file_type: str = Form(...),                  # "Image" or "Video"
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file_type not in ("Image", "Video"):
        raise HTTPException(status_code=400, detail="file_type must be Image or Video")

    cust = db.query(Customer).filter(Customer.id == customer_id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="customer not found")

    if not token or not token.strip():
        raise HTTPException(status_code=400, detail="token is required")

    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")

    ensure_uploads_dir()

    ext = Path(file.filename).suffix.lower()
    local_id = str(uuid.uuid4())
    local_path = UPLOADS_DIR / f"{local_id}{ext}"

    # Save upload to disk (local media file)
    with open(local_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    run_id = str(uuid.uuid4())
    out = run_r_upload_media(
        rubica_token=token.strip(),
        media_path=str(local_path),
        media_type=file_type,
        run_id=run_id,
    )

    result = out.get("result") or {}
    if not result.get("ok"):
        raise HTTPException(
            status_code=500,
            detail={
                "message": "media upload failed",
                "runner": out,
            },
        )

    file_id = result["file_id"]

    media = CustomerMedia(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        file_id=file_id,
        file_name=file.filename,
        file_type=file_type,
        created_at=__import__("datetime").datetime.utcnow().isoformat() + "Z",
    )
    db.add(media)
    db.commit()

    return {
        "media_id": media.id,
        "file_id": file_id,
        "file_name": media.file_name,
        "file_type": media.file_type,
    }
