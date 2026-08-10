"""
Part A — Log Pipeline
=====================
Ingest → Validate → Clean → Transform → Export

Xử lý file app_logs_7days.jsonl từ Công ty Tài chính Sao Đỏ.
Dữ liệu gốc KHÔNG bị sửa; toàn bộ xử lý xảy ra trong pipeline này.

Chạy: python part_a/pipeline.py
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT.parent / "Xbrain_Assessment_DE_DataPack" / "data" / "app_logs_7days.jsonl"
OUTPUT_DIR = ROOT / "pipeline" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CLEAN_PARQUET = OUTPUT_DIR / "clean_logs.parquet"
CLEAN_CSV = OUTPUT_DIR / "clean_logs.csv"
DQ_REPORT = OUTPUT_DIR / "data_quality_report.json"

# ---------------------------------------------------------------------------
# Step 1: Ingest — đọc từng dòng JSONL, bắt lỗi parse
# ---------------------------------------------------------------------------

def ingest(filepath: Path) -> tuple[list[dict], list[dict]]:
    """
    Đọc file JSONL dòng-by-dòng.
    Trả về:
        records   — list các dict JSON hợp lệ (kèm metadata dòng)
        bad_lines — list các dòng parse thất bại
    """
    records = []
    bad_lines = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                obj["_line_no"] = line_no        # metadata nội bộ để trace-back
                records.append(obj)
            except json.JSONDecodeError as e:
                bad_lines.append({
                    "line_no": line_no,
                    "raw": line[:120],           # cắt để tránh quá dài
                    "error": str(e),
                    "issue_type": "json_parse_error"
                })

    print(f"[INGEST] Đọc {line_no} dòng: {len(records)} JSON hợp lệ, {len(bad_lines)} dòng lỗi parse")
    return records, bad_lines


# ---------------------------------------------------------------------------
# Step 2: Validate — kiểm tra từng record hợp lệ
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"timestamp", "service", "message", "request_id"}
VALID_LEVELS = {"INFO", "WARN", "ERROR"}
VALID_SERVICES = {"auth-service", "payment-api", "web-portal", "batch-report", "notification-worker"}

def validate_and_tag(records: list[dict]) -> pd.DataFrame:
    """
    Với mỗi record:
      - Kiểm tra timestamp có parse được không
      - Kiểm tra field `level` có tồn tại / hợp lệ không
      - Phát hiện service không nằm trong danh sách chuẩn
      - Thêm cột flag để downstream xử lý
    Trả về DataFrame với các cột gốc + cột chất lượng.
    """
    rows = []

    for r in records:
        row = dict(r)  # copy để không mutate gốc

        # --- Timestamp ---
        ts_raw = row.get("timestamp", "")
        ts_parsed = None
        ts_invalid = False
        ts_anomaly = False

        try:
            ts_parsed = pd.Timestamp(ts_raw, tz="UTC")
        except Exception:
            ts_invalid = True

        row["_ts_invalid"] = ts_invalid
        row["_ts_parsed"] = ts_parsed  # None nếu invalid

        # --- Level ---
        level = row.get("level", None)
        level_missing = level is None
        level_unknown = (not level_missing) and (level not in VALID_LEVELS)

        row["_level_missing"] = level_missing
        row["_level_unknown"] = level_unknown

        # Điền giá trị mặc định nếu thiếu
        if level_missing:
            row["level"] = "UNKNOWN"
            row["_level_imputed"] = True
        else:
            row["_level_imputed"] = False

        # --- Service ---
        service = row.get("service", "")
        row["_service_unknown"] = service not in VALID_SERVICES

        rows.append(row)

    df = pd.DataFrame(rows)

    # Thêm cột is_timestamp_anomaly: timestamp nằm ngoài khoảng 27/07–02/08/2026
    if "_ts_parsed" in df.columns:
        expected_start = pd.Timestamp("2026-07-27", tz="UTC")
        expected_end   = pd.Timestamp("2026-08-02 23:59:59", tz="UTC")
        df["_ts_anomaly"] = df["_ts_parsed"].apply(
            lambda t: (t is not None) and not (expected_start <= t <= expected_end)
        )

    return df


# ---------------------------------------------------------------------------
# Step 3: Deduplicate
# ---------------------------------------------------------------------------

def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Xác định duplicate dựa trên (request_id, timestamp, message).
    Giữ bản đầu tiên.
    """
    key_cols = ["request_id", "timestamp", "message"]
    # Chỉ xét các cột tồn tại
    key_cols = [c for c in key_cols if c in df.columns]

    before = len(df)
    df_dedup = df.drop_duplicates(subset=key_cols, keep="first")
    n_removed = before - len(df_dedup)
    print(f"[DEDUP]  Loại {n_removed} bản ghi trùng lặp ({before} → {len(df_dedup)})")
    return df_dedup.reset_index(drop=True), n_removed


# ---------------------------------------------------------------------------
# Step 4: Clean — tách bản ghi hợp lệ vs loại bỏ
# ---------------------------------------------------------------------------

def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Chia df thành:
      - df_clean   : bản ghi đủ điều kiện sử dụng
      - df_rejected: bản ghi bị loại (timestamp không parse được)
    Bản ghi timestamp anomaly được GIỮ LẠI nhưng đánh dấu flag.
    """
    mask_reject = df["_ts_invalid"] == True
    df_rejected = df[mask_reject].copy()
    df_clean = df[~mask_reject].copy()

    print(f"[CLEAN]  Loại {len(df_rejected)} bản ghi timestamp không hợp lệ")
    print(f"[CLEAN]  Giữ lại {len(df_clean)} bản ghi")

    anomaly_count = df_clean["_ts_anomaly"].sum() if "_ts_anomaly" in df_clean.columns else 0
    if anomaly_count:
        print(f"[CLEAN]  {anomaly_count} bản ghi có timestamp anomaly (ngoài range 27/07–02/08) — được giữ, đánh dấu flag")

    return df_clean, df_rejected


# ---------------------------------------------------------------------------
# Step 5: Transform — chuẩn hoá schema cho output
# ---------------------------------------------------------------------------

def transform(df_clean: pd.DataFrame) -> pd.DataFrame:
    """
    Chuẩn hoá về schema cuối:
      timestamp (datetime64[ns, UTC])
      service   (str)
      level     (str)
      message   (str)
      request_id (str)
      level_imputed (bool)
      is_ts_anomaly (bool)
    """
    out = pd.DataFrame()
    out["timestamp"]      = df_clean["_ts_parsed"]
    out["service"]        = df_clean["service"].astype(str)
    out["level"]          = df_clean["level"].astype(str)
    out["message"]        = df_clean["message"].astype(str)
    out["request_id"]     = df_clean["request_id"].astype(str)
    out["level_imputed"]  = df_clean["_level_imputed"].astype(bool)
    out["is_ts_anomaly"]  = df_clean["_ts_anomaly"].astype(bool) if "_ts_anomaly" in df_clean.columns else False

    # Sort theo timestamp
    out = out.sort_values("timestamp").reset_index(drop=True)

    # Thêm date/hour để tiện query
    out["date"]  = out["timestamp"].dt.date.astype(str)
    out["hour"]  = out["timestamp"].dt.hour

    return out


# ---------------------------------------------------------------------------
# Step 6: Export
# ---------------------------------------------------------------------------

def export(df: pd.DataFrame, bad_lines: list[dict], df_rejected: pd.DataFrame,
           n_dupes: int) -> None:
    """Lưu Parquet, CSV, và data quality report JSON."""

    # Parquet
    df.to_parquet(CLEAN_PARQUET, index=False, engine="pyarrow")
    print(f"[EXPORT] Parquet → {CLEAN_PARQUET}")

    # CSV (dễ kiểm tra bằng mắt)
    df.to_csv(CLEAN_CSV, index=False)
    print(f"[EXPORT] CSV     → {CLEAN_CSV}")

    # Data quality report
    ts_anomaly_records = df[df["is_ts_anomaly"] == True][["timestamp", "service", "message", "request_id"]].head(20).to_dict(orient="records")
    level_imputed_records = df[df["level_imputed"] == True][["timestamp", "service", "message", "request_id"]].head(20).to_dict(orient="records")

    # Convert timestamps to string for JSON serialization
    for rec in ts_anomaly_records:
        rec["timestamp"] = str(rec["timestamp"])
    for rec in level_imputed_records:
        rec["timestamp"] = str(rec["timestamp"])

    report = {
        "summary": {
            "total_raw_lines_attempted": "see below",
            "json_parse_errors": len(bad_lines),
            "invalid_timestamp_rejected": len(df_rejected),
            "duplicates_removed": n_dupes,
            "timestamp_anomalies_flagged": int(df["is_ts_anomaly"].sum()),
            "level_imputed_records": int(df["level_imputed"].sum()),
            "final_clean_records": len(df),
        },
        "issue_breakdown": {
            "json_parse_error": {
                "count": len(bad_lines),
                "description": "Dòng JSONL không parse được (JSON bị truncate hoặc malformed)",
                "action": "Bỏ qua hoàn toàn",
                "samples": bad_lines[:5]
            },
            "invalid_timestamp": {
                "count": len(df_rejected),
                "description": "Field timestamp không parse được thành datetime (vd: 'not-a-date')",
                "action": "Loại bỏ bản ghi",
                "samples": df_rejected[["_line_no", "timestamp", "service", "message"]].head(5).to_dict(orient="records")
            },
            "duplicate_record": {
                "count": n_dupes,
                "description": "Bản ghi trùng hoàn toàn (request_id + timestamp + message)",
                "action": "Giữ bản đầu tiên, loại bỏ bản sau"
            },
            "timestamp_anomaly": {
                "count": int(df["is_ts_anomaly"].sum()),
                "description": "Timestamp nằm ngoài khoảng 7 ngày kỳ vọng (27/07–02/08/2026)",
                "action": "Giữ lại, đánh flag is_ts_anomaly=True để phân tích riêng",
                "samples": ts_anomaly_records
            },
            "level_imputed": {
                "count": int(df["level_imputed"].sum()),
                "description": "Bản ghi thiếu field 'level'; điền giá trị 'UNKNOWN'",
                "action": "Giữ lại, đánh flag level_imputed=True",
                "samples": level_imputed_records
            },
        },
        "schema_output": {
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()}
        }
    }

    with open(DQ_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[EXPORT] DQ Report → {DQ_REPORT}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_pipeline():
    print("=" * 60)
    print("  Xbrain DE POC — Log Pipeline")
    print(f"  Input: {DATA_FILE}")
    print("=" * 60)

    if not DATA_FILE.exists():
        print(f"[ERROR] Không tìm thấy file: {DATA_FILE}")
        sys.exit(1)

    # 1. Ingest
    records, bad_lines = ingest(DATA_FILE)

    # 2. Validate & tag
    df_tagged = validate_and_tag(records)

    # 3. Deduplicate
    df_deduped, n_dupes = deduplicate(df_tagged)

    # 4. Clean (tách valid vs rejected)
    df_clean_raw, df_rejected = clean(df_deduped)

    # 5. Transform (chuẩn hoá schema)
    df_final = transform(df_clean_raw)

    # 6. Export
    export(df_final, bad_lines, df_rejected, n_dupes)

    print()
    print("=" * 60)
    print(f"  Pipeline hoàn thành. Records sạch: {len(df_final)}")
    print("=" * 60)

    return df_final


if __name__ == "__main__":
    run_pipeline()
