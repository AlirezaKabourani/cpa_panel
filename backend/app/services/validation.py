import re
import pandas as pd

REQUIRED_COLS = {"phone_number", "link"}
OPTIONAL_COLS = {"source"}

def normalize_phone(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s:
        return None
    s = re.sub(r"[^0-9]", "", s)
    return s or None

def validate_and_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []

    cols = {c.strip() for c in df.columns}
    missing = REQUIRED_COLS - cols
    if missing:
        errors.append(f"Missing required columns: {sorted(missing)}. Required: {sorted(REQUIRED_COLS)}")
        return df, errors

    # Keep only required + optional + any extra (we will keep extra for future)
    # But we normalize required columns
    df = df.copy()
    df["phone_number"] = df["phone_number"].apply(normalize_phone)
    df["link"] = df["link"].astype(str).str.strip()

    # drop invalid
    before = len(df)
    df = df[df["phone_number"].notna()]
    df = df[df["link"].notna() & (df["link"].str.len() > 0)]
    after = len(df)

    if after == 0:
        errors.append("No valid rows left after cleaning (phone_number/link).")
        return df, errors

    # duplicates by phone_number+link
    dup_count = int(df.duplicated(subset=["phone_number", "link"]).sum())

    # stats (not errors but useful)
    if after < before:
        errors.append(f"Removed {before - after} invalid rows (empty phone_number or link).")
    if dup_count > 0:
        errors.append(f"Found {dup_count} duplicate rows (phone_number+link). (We keep them for now.)")

    return df, errors
