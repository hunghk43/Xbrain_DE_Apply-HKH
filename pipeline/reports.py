"""
Part A — Báo cáo (4 câu hỏi khách hàng)
========================================
Chạy SAU khi pipeline.py đã tạo ra clean_logs.parquet.

Chạy: python pipeline/reports.py

4 câu hỏi theo đúng yêu cầu đề bài:
  Q1. Service nào có nhiều lỗi (level=ERROR) nhất trong 7 ngày?
  Q2. Số lượng lỗi theo ngày của toàn hệ thống — ngày nào bất thường?
  Q3. Top 3 loại lỗi (message/error code) phổ biến nhất, thuộc service nào?
  Q4. Có bao nhiêu bản ghi bị loại/sửa trong bước làm sạch, thuộc những loại vấn đề gì?
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
# Q1 — Service nào có nhiều ERROR nhất?
# ---------------------------------------------------------------------------

def q1_errors_by_service(df: pd.DataFrame):
    print("=" * 60)
    print("Q1 — Service nào có nhiều lỗi (ERROR) nhất trong 7 ngày?")
    print("=" * 60)

    error_df = df[df["level"] == "ERROR"]
    result = (
        error_df.groupby("service")
        .size()
        .reset_index(name="error_count")
        .sort_values("error_count", ascending=False)
    )

    print(tabulate(result, headers="keys", tablefmt="github", showindex=False))

    top_service = result.iloc[0]
    total_errors = error_df["level"].count()
    pct = top_service["error_count"] / total_errors * 100
    print(f"\n  → Service lỗi nhiều nhất: {top_service['service']} "
          f"({int(top_service['error_count'])} lỗi, {pct:.1f}% tổng ERROR)")
    print(f"  Tổng ERROR toàn hệ thống: {total_errors} / {len(df)} bản ghi "
          f"({total_errors/len(df)*100:.2f}%)")
    print()


# ---------------------------------------------------------------------------
# Q2 — Số lỗi theo ngày toàn hệ thống — ngày nào bất thường?
# ---------------------------------------------------------------------------

def q2_errors_by_day(df: pd.DataFrame):
    print("=" * 60)
    print("Q2 — Số lượng lỗi theo ngày toàn hệ thống (ngày nào bất thường?)")
    print("=" * 60)

    error_df = df[df["level"] == "ERROR"]

    # Lỗi theo ngày
    by_day = (
        error_df.groupby("date")
        .size()
        .reset_index(name="error_count")
        .sort_values("date")
    )

    # Tính ngưỡng bất thường: mean + 2*std
    mean_err = by_day["error_count"].mean()
    std_err  = by_day["error_count"].std()
    threshold = mean_err + 2 * std_err

    by_day["anomaly"] = by_day["error_count"].apply(
        lambda x: "⚠ BẤT THƯỜNG" if x > threshold else ""
    )

    # ASCII bar chart
    max_count = by_day["error_count"].max()
    BAR_WIDTH = 25
    print(f"\n  {'Ngày':<12}  {'Lỗi':>5}  {'Bar':<27}  Ghi chú")
    print(f"  {'------------':<12}  {'-----':>5}  {'-------------------------':<27}  -------")
    for _, row in by_day.iterrows():
        bar_len = int(row["error_count"] / max_count * BAR_WIDTH)
        bar = "█" * bar_len
        print(f"  {row['date']:<12}  {int(row['error_count']):>5}  {bar:<27}  {row['anomaly']}")

    print(f"\n  Trung bình: {mean_err:.1f} lỗi/ngày | Ngưỡng bất thường (mean+2σ): {threshold:.1f}")

    anomaly_days = by_day[by_day["anomaly"] != ""]
    if len(anomaly_days) > 0:
        for _, r in anomaly_days.iterrows():
            print(f"\n  ⚠ Ngày bất thường: {r['date']} — {int(r['error_count'])} lỗi "
                  f"({int(r['error_count'])/mean_err:.1f}x mức trung bình)")

        # Breakdown theo service cho ngày bất thường
        worst_date = anomaly_days.sort_values("error_count", ascending=False).iloc[0]["date"]
        print(f"\n  Phân tích ngày {worst_date} theo service:")
        breakdown = (
            error_df[error_df["date"] == worst_date]
            .groupby("service")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        print(tabulate(breakdown, headers="keys", tablefmt="github", showindex=False))
    print()


# ---------------------------------------------------------------------------
# Q3 — Top 3 loại lỗi phổ biến nhất, thuộc service nào?
# ---------------------------------------------------------------------------

def q3_top3_error_types(df: pd.DataFrame):
    print("=" * 60)
    print("Q3 — Top 3 loại lỗi (message) phổ biến nhất, thuộc service nào?")
    print("=" * 60)

    error_df = df[df["level"] == "ERROR"].copy()

    # Aggregate theo message (1 message có thể từ nhiều service)
    by_message = (
        error_df.groupby("message")
        .agg(
            count=("message", "count"),
            services=("service", lambda x: ", ".join(sorted(x.unique())))
        )
        .reset_index()
        .sort_values("count", ascending=False)
        .head(3)
        .reset_index(drop=True)
    )
    by_message.index += 1  # rank bắt đầu từ 1

    print(tabulate(by_message, headers="keys", tablefmt="github"))
    print()

    total_errors = len(error_df)
    cumulative = by_message["count"].sum()
    print(f"  Top 3 loại lỗi chiếm {cumulative}/{total_errors} = "
          f"{cumulative/total_errors*100:.1f}% tổng số ERROR")

    print("\n  Phân tích:")
    for rank, row in by_message.iterrows():
        print(f"\n  #{rank} {row['message']}")
        print(f"      Service: {row['services']}")
        print(f"      Số lần:  {int(row['count'])} ({row['count']/total_errors*100:.1f}% ERROR)")
    print()


# ---------------------------------------------------------------------------
# Q4 — Bao nhiêu bản ghi bị loại/sửa?
# ---------------------------------------------------------------------------

def q4_data_quality_summary():
    print("=" * 60)
    print("Q4 — Bản ghi bị loại/sửa trong bước làm sạch")
    print("=" * 60)

    if not DQ_REPORT.exists():
        print("  [WARN] Không tìm thấy data_quality_report.json")
        return

    with open(DQ_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)

    summary  = report["summary"]
    breakdown = report["issue_breakdown"]

    rows = []
    for issue_key, info in breakdown.items():
        rows.append({
            "Loại vấn đề": issue_key,
            "Số lượng": info["count"],
            "Hành động": info["action"],
        })

    print(tabulate(rows, headers="keys", tablefmt="github", showindex=False))
    print()

    rejected = summary["json_parse_errors"] + summary["invalid_timestamp_rejected"] + summary["duplicates_removed"]
    modified = summary["level_imputed_records"]
    flagged  = summary["timestamp_anomalies_flagged"]

    print(f"  Tổng bị LOẠI bỏ hoàn toàn : {rejected} bản ghi")
    print(f"  Tổng bị SỬA (imputed)      : {modified} bản ghi")
    print(f"  Tổng bị FLAG (giữ lại)     : {flagged} bản ghi")
    print(f"  Tổng bản ghi sạch cuối cùng: {summary['final_clean_records']}")
    print()

    print("  Chi tiết từng loại:")
    for issue_key, info in breakdown.items():
        if info["count"] > 0:
            print(f"\n  [{info['count']}] {issue_key}")
            print(f"      Mô tả  : {info['description']}")
            print(f"      Xử lý  : {info['action']}")
            if info.get("samples"):
                sample = info["samples"][0]
                print(f"      Ví dụ  : {str(sample)[:100]}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Xbrain DE POC — Báo cáo (Part A)")
    print("=" * 60 + "\n")

    df = load_data()

    q1_errors_by_service(df)
    q2_errors_by_day(df)
    q3_top3_error_types(df)
    q4_data_quality_summary()

    print("  Báo cáo hoàn tất.")
