"""
Part A — Báo cáo (4 câu hỏi khách hàng)
========================================
Chạy SAU khi pipeline.py đã tạo ra clean_logs.parquet.

Chạy: python part_a/reports.py

4 câu hỏi:
  Q1. Có bao nhiêu bản ghi bị loại/sửa trong bước làm sạch, thuộc những loại vấn đề gì?
  Q2. Tổng số lỗi (ERROR) theo từng service trong 7 ngày?
  Q3. Phân bố lỗi theo giờ trong ngày (để phát hiện giờ cao điểm sự cố)?
  Q4. Những ngày nào payment-api có nhiều lỗi nhất?
"""

import json
import sys
from pathlib import Path

import pandas as pd
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
CLEAN_PARQUET = ROOT / "pipeline" / "output" / "clean_logs.parquet"
DQ_REPORT     = ROOT / "pipeline" / "output" / "data_quality_report.json"


def load_data() -> pd.DataFrame:
    if not CLEAN_PARQUET.exists():
        print("[ERROR] Chưa có clean_logs.parquet. Hãy chạy pipeline.py trước.")
        sys.exit(1)
    df = pd.read_parquet(CLEAN_PARQUET, engine="pyarrow")
    print(f"[LOAD]  {len(df)} records từ {CLEAN_PARQUET.name}\n")
    return df


# ---------------------------------------------------------------------------
# Q1 — Bản ghi bị loại / sửa
# ---------------------------------------------------------------------------

def q1_data_quality_summary():
    print("=" * 60)
    print("Q1 — Tóm tắt Data Quality: bản ghi bị loại / chỉnh sửa")
    print("=" * 60)

    if not DQ_REPORT.exists():
        print("  [WARN] Không tìm thấy data_quality_report.json")
        return

    with open(DQ_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)

    summary = report["summary"]
    breakdown = report["issue_breakdown"]

    rows = []
    for issue_key, info in breakdown.items():
        rows.append({
            "Loại vấn đề": issue_key,
            "Số lượng": info["count"],
            "Mô tả": info["description"],
            "Xử lý": info["action"]
        })

    print(tabulate(rows, headers="keys", tablefmt="github"))
    print()
    print(f"  ✓ Tổng số bản ghi sạch cuối cùng : {summary['final_clean_records']}")
    print(f"  ✗ JSON parse errors (bỏ qua)      : {summary['json_parse_errors']}")
    print(f"  ✗ Timestamp không hợp lệ (loại)   : {summary['invalid_timestamp_rejected']}")
    print(f"  ✗ Duplicate (loại)                 : {summary['duplicates_removed']}")
    print(f"  ⚠ Timestamp anomaly (giữ, flag)    : {summary['timestamp_anomalies_flagged']}")
    print(f"  ⚠ Level imputed → UNKNOWN (giữ)    : {summary['level_imputed_records']}")
    print()


# ---------------------------------------------------------------------------
# Q2 — Tổng số ERROR theo service
# ---------------------------------------------------------------------------

def q2_errors_by_service(df: pd.DataFrame):
    print("=" * 60)
    print("Q2 — Tổng số sự kiện ERROR theo service (7 ngày)")
    print("=" * 60)

    error_df = df[df["level"] == "ERROR"]
    result = (
        error_df.groupby("service")
        .size()
        .reset_index(name="error_count")
        .sort_values("error_count", ascending=False)
    )

    print(tabulate(result, headers="keys", tablefmt="github", showindex=False))
    print(f"\n  Tổng cộng: {error_df['level'].count()} lỗi ERROR trên {df['level'].count()} bản ghi")
    print(f"  Tỉ lệ lỗi toàn hệ thống: {error_df['level'].count() / df['level'].count() * 100:.2f}%")
    print()

    # Chi tiết loại lỗi
    print("  Top 10 message lỗi hay gặp nhất:")
    top_errors = (
        error_df.groupby("message")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(10)
    )
    print(tabulate(top_errors, headers="keys", tablefmt="github", showindex=False))
    print()


# ---------------------------------------------------------------------------
# Q3 — Phân bố lỗi theo giờ trong ngày
# ---------------------------------------------------------------------------

def q3_errors_by_hour(df: pd.DataFrame):
    print("=" * 60)
    print("Q3 — Phân bố ERROR theo giờ trong ngày (phát hiện giờ cao điểm)")
    print("=" * 60)

    error_df = df[df["level"] == "ERROR"].copy()
    by_hour = (
        error_df.groupby("hour")
        .size()
        .reset_index(name="error_count")
        .sort_values("hour")
    )

    # ASCII bar chart
    max_count = by_hour["error_count"].max()
    BAR_WIDTH = 30
    print(f"\n  {'Giờ':>4}  {'Lỗi':>5}  {'Bar':}")
    print(f"  {'----':>4}  {'-----':>5}  {'---':}")
    for _, row in by_hour.iterrows():
        bar_len = int(row["error_count"] / max_count * BAR_WIDTH)
        bar = "█" * bar_len
        peak_flag = " ◄ PEAK" if row["error_count"] == max_count else ""
        print(f"  {int(row['hour']):>4}  {int(row['error_count']):>5}  {bar}{peak_flag}")

    peak_hour = by_hour.loc[by_hour["error_count"].idxmax(), "hour"]
    print(f"\n  Giờ có nhiều lỗi nhất: {int(peak_hour)}:00 — {int(peak_hour)+1}:00")
    print()


# ---------------------------------------------------------------------------
# Q4 — payment-api: ngày nào nhiều lỗi nhất?
# ---------------------------------------------------------------------------

def q4_payment_api_errors_by_day(df: pd.DataFrame):
    print("=" * 60)
    print("Q4 — payment-api: số lỗi ERROR theo ngày")
    print("=" * 60)

    payment_errors = df[(df["service"] == "payment-api") & (df["level"] == "ERROR")]

    by_day = (
        payment_errors.groupby("date")
        .size()
        .reset_index(name="error_count")
        .sort_values("error_count", ascending=False)
    )

    print(tabulate(by_day, headers="keys", tablefmt="github", showindex=False))
    print()

    if len(by_day) > 0:
        worst_day = by_day.iloc[0]
        print(f"  Ngày nhiều lỗi nhất: {worst_day['date']} ({int(worst_day['error_count'])} lỗi ERROR)")
        print()

    # Breakdown loại lỗi payment-api theo ngày tệ nhất
    worst_date = by_day.iloc[0]["date"] if len(by_day) > 0 else None
    if worst_date:
        print(f"  Chi tiết lỗi ngày {worst_date}:")
        detail = (
            payment_errors[payment_errors["date"] == worst_date]
            .groupby("message")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        print(tabulate(detail, headers="keys", tablefmt="github", showindex=False))
    print()


# ---------------------------------------------------------------------------
# Bonus — service activity overview
# ---------------------------------------------------------------------------

def bonus_overview(df: pd.DataFrame):
    print("=" * 60)
    print("BONUS — Tổng quan hoạt động toàn hệ thống (7 ngày)")
    print("=" * 60)

    overview = (
        df.groupby(["service", "level"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    print(tabulate(overview, headers="keys", tablefmt="github", showindex=False))
    print()

    # Ngày bận nhất
    print("  Số sự kiện theo ngày:")
    daily = (
        df.groupby("date")
        .size()
        .reset_index(name="total_events")
        .sort_values("date")
    )
    print(tabulate(daily, headers="keys", tablefmt="github", showindex=False))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Xbrain DE POC — Báo cáo (Part A)")
    print("=" * 60 + "\n")

    df = load_data()

    q1_data_quality_summary()
    q2_errors_by_service(df)
    q3_errors_by_hour(df)
    q4_payment_api_errors_by_day(df)
    bonus_overview(df)

    print("  Báo cáo hoàn tất.")
