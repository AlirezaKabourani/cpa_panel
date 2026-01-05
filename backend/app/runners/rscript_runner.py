import os
import subprocess
import traceback
from pathlib import Path
from typing import Optional
import json

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = PROJECT_ROOT / "data" / "runs"
R_RUNNER = PROJECT_ROOT / "r" / "runners" / "run_campaign.R"

def ensure_runs_dir():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

def run_r_campaign(
    *,
    mode: str,
    rubica_token: str,
    snapshot_path: str,
    service_id: str,
    file_id: Optional[str],
    message_text: str,
    test_number: Optional[str],
    batch_size: int = 1000,
    workers: int = 5,
    sleep_sec: float = 0.2,
    run_id: str,
) -> dict:
    """
    Always creates run_dir and run.log.
    Token passed only via env var.
    Returns returncode + paths even on failure.
    """
    ensure_runs_dir()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / "run.log"
    log_csv = run_dir / "rubika_message_log.csv"
    message_path = run_dir / "message.txt"
    message_path.write_text(message_text, encoding="utf-8")


    # Allow configuring Rscript path via env var on Windows
    rscript_bin = os.environ.get("RSCRIPT_PATH", "Rscript")

    cmd = [
        rscript_bin,
        str(R_RUNNER),
        "--mode", mode,
        "--snapshot", str(snapshot_path),
        "--service_id", str(service_id),
        "--message_file", str(message_path),
        "--log_csv", str(log_csv),
        "--batch_size", str(batch_size),
        "--workers", str(workers),
        "--sleep_sec", str(sleep_sec),
    ]
    if file_id:
        cmd += ["--file_id", str(file_id)]
    if mode == "test" and test_number:
        cmd += ["--test_number", str(test_number)]

    env = os.environ.copy()
    env["RUBICA_TOKEN"] = rubica_token

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("COMMAND:\n" + " ".join(cmd) + "\n\n")
            f.flush()

            proc = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )

        return {
            "returncode": proc.returncode,
            "run_dir": str(run_dir),
            "log_path": str(log_path),
            "log_csv": str(log_csv),
        }

    except Exception as e:
        # Always write the error to log so you can read it from /runs/{id}/log
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n\n=== PYTHON RUNNER ERROR ===\n")
            f.write(str(e) + "\n")
            f.write(traceback.format_exc() + "\n")

        return {
            "returncode": 999,
            "run_dir": str(run_dir),
            "log_path": str(log_path),
            "log_csv": str(log_csv),
            "error": str(e),
        }



def run_r_upload_media(
    *,
    rubica_token: str,
    media_path: str,
    media_type: str,  # "Image" or "Video"
    run_id: str,
) -> dict:
    """
    Upload media to Rubica, return file_id. Token via env var only.
    Writes logs to data/runs/{run_id}/ and result.json for parsing.
    """
    ensure_runs_dir()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / "run.log"
    result_path = run_dir / "result.json"

    rscript_bin = os.environ.get("RSCRIPT_PATH", "Rscript")

    cmd = [
        rscript_bin,
        str(R_RUNNER),
        "--mode", "upload_media",
        "--media_path", str(media_path),
        "--media_type", str(media_type),
        "--result_json", str(result_path),
    ]

    env = os.environ.copy()
    env["RUBICA_TOKEN"] = rubica_token

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("COMMAND:\n" + " ".join(cmd) + "\n\n")
        f.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

    result = None
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            result = {"ok": False, "error": "Could not parse result.json"}

    return {
        "returncode": proc.returncode,
        "run_dir": str(run_dir),
        "log_path": str(log_path),
        "result_path": str(result_path),
        "result": result,
    }
