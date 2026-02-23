import csv
import json
import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = PROJECT_ROOT / "data" / "runs"

DEFAULT_SPLUS_BASE_URL = "https://bui.splus.ir"
RETRYABLE_RESULT_CODES = {429, 500, 724, 730, 736, 738}
MAX_RETRIES = 5
SPLUS_MEDIA_MAX_SIZE = 8 * 1024 * 1024
ALLOWED_SPLUS_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "video/mp4",
}


def ensure_runs_dir():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_snapshot(snapshot_path: str) -> pd.DataFrame:
    p = Path(snapshot_path)
    ext = p.suffix.lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(p)
    elif ext == ".csv":
        df = pd.read_csv(p)
    else:
        raise ValueError(f"Unsupported snapshot extension: {ext}")

    for required_col in ("phone_number", "link"):
        if required_col not in df.columns:
            raise ValueError(f"snapshot missing required column: {required_col}")

    df["phone_number"] = (
        df["phone_number"]
        .astype(str)
        .str.replace(r"[^0-9]", "", regex=True)
        .str.strip()
    )
    df["link"] = df["link"].astype(str).str.strip()
    df = df[(df["phone_number"] != "") & (df["link"] != "")]
    return df[["phone_number", "link"]].reset_index(drop=True)


def _safe_json(resp: requests.Response) -> dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {}


def _is_retryable(resp: Optional[requests.Response], data: dict[str, Any], err: Optional[Exception]) -> bool:
    if err is not None:
        msg = str(err).lower()
        if "429" in msg or "too many requests" in msg:
            return True
        return False

    if resp is None:
        return False

    if resp.status_code == 429 or 500 <= resp.status_code <= 599:
        return True

    code = data.get("result_code")
    try:
        code_i = int(code)
    except Exception:
        return False
    return code_i in RETRYABLE_RESULT_CODES


def _message_text(template: str, link: str) -> str:
    if "%s" in template:
        return template % link
    return template.replace("🔗", link)


def _send_with_retry(
    *,
    base_url: str,
    bot_id: str,
    phone_number: str,
    text: str,
    file_id: Optional[str],
    timeout_sec: int,
):
    payload: dict[str, Any] = {
        "phone_number": str(phone_number),
        "text": text,
    }
    if file_id:
        payload["file_id"] = file_id

    url = f"{base_url}/v1/messages/send"
    headers = {
        "Authorization": bot_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    last_resp: Optional[requests.Response] = None
    last_data: dict[str, Any] = {}
    last_err: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout_sec)
            data = _safe_json(resp)
            err = None
        except Exception as ex:
            resp = None
            data = {}
            err = ex

        last_resp, last_data, last_err = resp, data, err
        if not _is_retryable(resp, data, err):
            break

        if attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)

    return last_resp, last_data, last_err


def _build_status(resp: Optional[requests.Response], data: dict[str, Any], err: Optional[Exception]) -> tuple[str, Optional[str], Optional[str]]:
    if err is not None:
        return f"SEND_ERROR: {err}", None, None

    result_code = data.get("result_code")
    result_message = data.get("result_message")
    message_id = data.get("message_id")
    request_id = data.get("request_id")
    message_id_str = str(message_id or request_id or "") or None

    try:
        rc = int(result_code)
    except Exception:
        rc = None

    if rc in (200, 202):
        return "Sent", message_id_str, None

    http_code = resp.status_code if resp is not None else "?"
    if result_message:
        return f"SEND_ERROR: http={http_code} rc={result_code} {result_message}", message_id_str, str(result_code) if result_code is not None else None
    return f"SEND_ERROR: http={http_code} rc={result_code}", message_id_str, str(result_code) if result_code is not None else None


def run_splus_campaign(
    *,
    mode: str,
    splus_bot_id: str,
    snapshot_path: str,
    file_id: Optional[str],
    message_text: str,
    test_number: Optional[str],
    run_id: str,
    sleep_sec: float = 0.2,
    base_url: str = DEFAULT_SPLUS_BASE_URL,
    timeout_sec: int = 60,
) -> dict:
    ensure_runs_dir()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / "run.log"
    log_csv = run_dir / "splus_message_log.csv"

    with open(log_path, "w", encoding="utf-8") as lf:
        lf.write(f"mode={mode}\n")
        lf.write(f"snapshot_path={snapshot_path}\n")
        lf.write(f"file_id={file_id or ''}\n")
        lf.write(f"started_at={now_iso()}\n\n")

        try:
            if mode not in ("test", "send"):
                raise ValueError("mode must be test or send")
            if not splus_bot_id or not splus_bot_id.strip():
                raise ValueError("splus_bot_id is required")
            if not message_text or not str(message_text).strip():
                raise ValueError("message_text is required")

            df = _read_snapshot(snapshot_path)
            if df.empty:
                raise ValueError("No valid rows in snapshot after cleaning")

            if mode == "test":
                if not test_number:
                    raise ValueError("test_number required in test mode")
                link0 = str(df.iloc[0]["link"])
                send_df = pd.DataFrame(
                    [{"phone_number": str(test_number), "link": link0}]
                )
                scenario = "CPA_Panel_SPLUS_TEST"
            else:
                send_df = df
                scenario = "CPA_Panel_SPLUS_SEND"

            rows: list[dict[str, Any]] = []
            total = len(send_df.index)
            for idx, row in send_df.iterrows():
                phone = str(row["phone_number"])
                link = str(row["link"])
                text = _message_text(message_text, link)

                resp, data, err = _send_with_retry(
                    base_url=base_url.rstrip("/"),
                    bot_id=splus_bot_id.strip(),
                    phone_number=phone,
                    text=text,
                    file_id=file_id,
                    timeout_sec=timeout_sec,
                )

                status, message_id, error_code = _build_status(resp, data, err)
                ts = datetime.now()
                rows.append(
                    {
                        "phone_number": f"'{phone}",
                        "message_id": f"'{message_id}" if message_id else "",
                        "file_id": file_id or "",
                        "status": status,
                        "text": text,
                        "scenario": scenario,
                        "send_data": ts.strftime("%Y-%m-%d"),
                        "send_time": ts.strftime("%H:%M"),
                        "error_code": error_code or "",
                    }
                )

                if err:
                    lf.write(f"[{idx + 1}/{total}] phone={phone} error={err}\n")
                else:
                    lf.write(
                        f"[{idx + 1}/{total}] phone={phone} http={resp.status_code if resp else '?'} "
                        f"rc={data.get('result_code')} status={status}\n"
                    )
                lf.flush()

                if idx + 1 < total and sleep_sec > 0:
                    time.sleep(sleep_sec)

            with open(log_csv, "w", newline="", encoding="utf-8-sig") as cf:
                writer = csv.DictWriter(
                    cf,
                    fieldnames=[
                        "phone_number",
                        "message_id",
                        "file_id",
                        "status",
                        "text",
                        "scenario",
                        "send_data",
                        "send_time",
                        "error_code",
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)

            lf.write("\nOK: splus campaign completed\n")
            return {
                "returncode": 0,
                "run_dir": str(run_dir),
                "log_path": str(log_path),
                "log_csv": str(log_csv),
            }

        except Exception as ex:
            lf.write("\n=== PYTHON SPLUS RUNNER ERROR ===\n")
            lf.write(str(ex) + "\n")
            return {
                "returncode": 999,
                "run_dir": str(run_dir),
                "log_path": str(log_path),
                "log_csv": str(log_csv),
                "error": str(ex),
            }


def run_splus_upload_media(
    *,
    splus_bot_id: str,
    media_path: str,
    run_id: str,
    base_url: str = DEFAULT_SPLUS_BASE_URL,
    timeout_sec: int = 60,
) -> dict:
    ensure_runs_dir()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / "run.log"
    result_path = run_dir / "result.json"

    try:
        if not splus_bot_id or not splus_bot_id.strip():
            raise ValueError("splus_bot_id is required")
        if not media_path:
            raise ValueError("media_path is required")

        info = os.stat(media_path)
        if info.st_size > SPLUS_MEDIA_MAX_SIZE:
            raise ValueError("file size exceeds splus upload limit (8MB)")

        url = f"{base_url.rstrip('/')}/v1/file/upload"
        headers = {"Authorization": splus_bot_id.strip(), "Accept": "application/json"}

        media_name = Path(media_path).name
        content_type = mimetypes.guess_type(media_name)[0] or "application/octet-stream"
        if content_type == "image/jpg":
            content_type = "image/jpeg"

        if content_type not in ALLOWED_SPLUS_MIME_TYPES:
            raise ValueError(
                f"unsupported media MIME type for SPlus upload: {content_type} "
                f"(allowed: {', '.join(sorted(ALLOWED_SPLUS_MIME_TYPES))})"
            )

        with open(media_path, "rb") as f:
            files = {"file": (media_name, f, content_type)}
            resp = requests.post(url, files=files, headers=headers, timeout=timeout_sec)
            data = _safe_json(resp)

        file_id_val = str(data.get("file_id", "")).strip() if isinstance(data, dict) else ""
        result_code_raw = data.get("result_code") if isinstance(data, dict) else None

        # SPlus upload can return only {file_id: "..."} with HTTP 200.
        # Treat 2xx + non-empty file_id as success even when result_code is absent.
        rc_ok = False
        if result_code_raw is None:
            rc_ok = True
        else:
            try:
                rc_ok = int(result_code_raw) in (200, 202)
            except Exception:
                rc_ok = False

        ok = (
            200 <= resp.status_code < 300
            and isinstance(data, dict)
            and file_id_val != ""
            and rc_ok
        )

        result: dict[str, Any]
        if ok:
            result = {
                "ok": True,
                "file_id": file_id_val,
                "result_code": data.get("result_code"),
                "result_message": data.get("result_message"),
            }
        else:
            result = {
                "ok": False,
                "http_status": resp.status_code,
                "result_code": data.get("result_code"),
                "result_message": data.get("result_message"),
                "raw": data if data else resp.text,
            }

        with open(log_path, "w", encoding="utf-8") as lf:
            lf.write(f"POST {url}\n")
            lf.write(f"upload_file={media_name}\n")
            lf.write(f"content_type={content_type}\n")
            lf.write(f"http_status={resp.status_code}\n")
            lf.write(json.dumps(result, ensure_ascii=False, indent=2))
            lf.write("\n")

        with open(result_path, "w", encoding="utf-8") as rf:
            rf.write(json.dumps(result, ensure_ascii=False))

        return {
            "returncode": 0 if result.get("ok") else 1,
            "run_dir": str(run_dir),
            "log_path": str(log_path),
            "result_path": str(result_path),
            "result": result,
        }

    except Exception as ex:
        result = {"ok": False, "error": str(ex)}
        with open(log_path, "w", encoding="utf-8") as lf:
            lf.write("=== PYTHON SPLUS UPLOAD ERROR ===\n")
            lf.write(str(ex) + "\n")
        with open(result_path, "w", encoding="utf-8") as rf:
            rf.write(json.dumps(result, ensure_ascii=False))
        return {
            "returncode": 999,
            "run_dir": str(run_dir),
            "log_path": str(log_path),
            "result_path": str(result_path),
            "result": result,
            "error": str(ex),
        }
