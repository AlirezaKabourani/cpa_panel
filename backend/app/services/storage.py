import os
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"

def ensure_dirs():
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def new_snapshot_path(original_filename: str) -> Path:
    ensure_dirs()
    ext = Path(original_filename).suffix.lower()
    sid = str(uuid.uuid4())
    filename = f"{sid}{ext}"
    return SNAPSHOT_DIR / filename
