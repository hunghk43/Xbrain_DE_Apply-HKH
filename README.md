# Xbrain Data Engineer Assessment — POC

**Ứng viên:** Hoang Kim Hung  
**Thời gian:** 2 ngày (08/2026)  
**Khách hàng giả lập:** Công ty Tài chính Sao Đỏ

---

## Tổng quan

POC gồm 2 phần:
- **Phần A** — Log pipeline: ingest → validate → transform → báo cáo → thiết kế AWS
- **Phần B** — Knowledge base cho RAG: chunking, indexing, eval set, SOP cập nhật

---

## Cấu trúc repo

```
xbrain-de-poc/
├── README.md                    # EN — tổng quan, cách chạy, quyết định thiết kế
├── AI_WORKLOG.md                # Nhật ký dùng AI (Bài 2)
├── requirements.txt
├── pipeline/                    # Phần A — code + kết quả 4 câu hỏi
│   ├── pipeline.py              # Ingest, validate, clean, transform, export
│   ├── reports.py               # 4 báo cáo theo yêu cầu khách hàng
│   └── output/
│       ├── clean_logs.parquet   # Dataset sạch (generated)
│       ├── clean_logs.csv       # Bản CSV để kiểm tra
│       └── data_quality_report.json
├── kb/                          # Phần B — code/cấu trúc KB + bộ eval + kết quả
│   ├── kb_builder.py            # Chunking + indexing
│   ├── kb_design.md             # Chiến lược thiết kế KB
│   ├── eval_set.md              # 10 câu hỏi + đáp án + tiêu chí chấm
│   └── output/
│       └── kb.db                # SQLite FTS index (generated)
├── design/                      # Sơ đồ AWS + giải thích
│   └── aws_design.md
└── sop/                         # SOP cập nhật KB
    └── sop_kb_update.md
```

---

## Phần A — Log Pipeline

### Cách chạy

```bash
# Bước 1: Cài dependencies
pip install -r requirements.txt

# Bước 2: Chạy pipeline (ingest + clean + export)
python pipeline/pipeline.py

# Bước 3: Chạy báo cáo
python pipeline/reports.py
```

**Output:**
- `pipeline/output/clean_logs.parquet` — dataset sạch định dạng Parquet
- `pipeline/output/clean_logs.csv` — bản CSV để dễ kiểm tra
- `pipeline/output/data_quality_report.json` — báo cáo chi tiết các vấn đề đã xử lý

### Các vấn đề data quality phát hiện & xử lý

| # | Vấn đề | Ví dụ | Xử lý |
|---|--------|-------|-------|
| 1 | **Timestamp không hợp lệ** | `"not-a-date"` | Loại bỏ bản ghi, ghi nhận vào quality report |
| 2 | **JSON bị truncate** | `{"timestamp": "2026-07-27T02:56:2` (cắt ngang) | Bỏ qua dòng, ghi nhận parse error |
| 3 | **Thiếu field `level`** | Dòng không có key `"level"` | Điền `"UNKNOWN"`, đánh dấu flag `level_imputed=True` |
| 4 | **Timestamp out-of-order** | Dòng giữa 27/07 nhảy sang 30/07 | Giữ nguyên giá trị, thêm cột `is_timestamp_anomaly` để phân tích |
| 5 | **Duplicate record** | Cùng `request_id` + `timestamp` + `message` | Deduplicate, giữ bản đầu tiên |

> Dữ liệu gốc **không bị sửa**. Toàn bộ xử lý xảy ra trong pipeline.

---

## Phần B — Knowledge Base

### Cách chạy

```bash
python kb/kb_builder.py
```

**Output:** `kb/output/kb.db` — SQLite full-text search index

---

## Quyết định thiết kế nổi bật

1. **Chunking theo cấu trúc (structure-based):** phù hợp với tài liệu SOP/chính sách có heading rõ ràng — giữ trọn ngữ nghĩa từng mục thay vì cắt cố định theo token.
2. **Metadata bắt buộc per chunk:** `doc_id`, `version`, `effective_date`, `section`, `owner` — giải quyết bài toán mâu thuẫn phiên bản (POL-01 v1 vs v2).
3. **Xử lý conflict:** khi có 2 bản cùng `doc_id`, KB ưu tiên bản có `effective_date` mới nhất; bản cũ được giữ lại với flag `superseded=True`.
4. **Pipeline idempotent:** chạy lại nhiều lần cho kết quả giống nhau.

---

## Những gì chưa làm kịp / còn hạn chế

- AWS diagram là dạng text/markdown, chưa có file ảnh vector
- KB chưa dùng embedding (vector search) — dùng SQLite FTS5 đủ dùng cho POC 8 tài liệu
- Chưa có unit test tự động cho pipeline
