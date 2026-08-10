# Thiết kế AWS — Log Pipeline Production

**Công ty Tài chính Sao Đỏ — Xbrain POC**  
*Nếu triển khai pipeline này lên AWS để chạy hằng ngày*

---

## Sơ đồ kiến trúc

```
[Hệ thống khách hàng]
  5 services (on-premise / EC2)
        │
        │  Log files / API push
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                         INGEST LAYER                            │
│                                                                 │
│  ┌─────────────────┐        ┌──────────────────────────┐        │
│  │  Amazon Kinesis │  hoặc  │  AWS Lambda (HTTP ingest)│        │
│  │  Data Firehose  │        │  trigger từ S3 upload    │        │
│  └────────┬────────┘        └────────────┬─────────────┘        │
└───────────┼─────────────────────────────┼────────────────────── ┘
            │                             │
            ▼                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER (S3)                      │
│                                                                 │
│  s3://saodo-datalake/                                           │
│  ├── raw/logs/year=YYYY/month=MM/day=DD/    ← file gốc .jsonl  │
│  ├── clean/logs/year=YYYY/month=MM/day=DD/  ← Parquet đã clean │
│  └── reports/date=YYYY-MM-DD/               ← báo cáo CSV/JSON │
└─────────────────────────────────────────────────────────────────┘
            │
            │  trigger hằng ngày (EventBridge Scheduler 01:00)
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PROCESS LAYER                             │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    AWS Glue Job (PySpark)                │   │
│  │                                                          │   │
│  │  1. Đọc raw/ partition ngày hôm trước                   │   │
│  │  2. Validate + clean (logic từ pipeline.py)             │   │
│  │  3. Deduplicate                                         │   │
│  │  4. Write clean Parquet → clean/ partition              │   │
│  │  5. Ghi data quality metrics → CloudWatch               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │          AWS Lambda (Báo cáo nhẹ — trigger sau Glue)    │   │
│  │                                                          │   │
│  │  - Aggregate số lỗi, tỉ lệ ERROR                        │   │
│  │  - Push metrics → CloudWatch Dashboard                  │   │
│  │  - Gửi email alert nếu tỉ lệ lỗi > ngưỡng              │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        QUERY LAYER                              │
│                                                                 │
│  ┌─────────────────────────────────────┐                        │
│  │          AWS Glue Data Catalog      │                        │
│  │  (schema registry cho clean/logs/)  │                        │
│  └──────────────────┬──────────────────┘                        │
│                     │                                           │
│                     ▼                                           │
│  ┌──────────────────────────────────────────┐                   │
│  │            Amazon Athena                 │                   │
│  │  Query SQL trực tiếp trên S3 Parquet     │                   │
│  │  (ad-hoc + báo cáo định kỳ)             │                   │
│  └──────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SECURITY LAYER                             │
│                                                                 │
│  IAM Roles:                                                     │
│  • GlueJobRole     — đọc s3://raw/, ghi s3://clean/            │
│  • LambdaReportRole — đọc s3://clean/, ghi CloudWatch          │
│  • AthenaQueryRole  — đọc s3://clean/ + s3://reports/          │
│                                                                 │
│  S3 Bucket Policy:                                              │
│  • raw/   — write-only từ ingest, read-only từ Glue            │
│  • clean/ — write từ Glue, read từ Athena/Lambda               │
│  • Server-side encryption (SSE-S3 hoặc SSE-KMS)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Luồng dữ liệu hằng ngày

```
00:30 → Log files từ 5 service được đẩy lên S3 raw/
01:00 → EventBridge Scheduler kích hoạt Glue Job
01:00–01:30 → Glue Job: validate + clean + write Parquet
01:35 → Lambda trigger: tổng hợp metrics, gửi alert nếu cần
07:00 → Đội vận hành mở Athena / dashboard xem báo cáo
```

---

## Giải thích lựa chọn service

| Service | Vai trò | Lý do chọn |
|---------|---------|------------|
| **S3** | Data lake (raw + clean + reports) | Chi phí thấp, durable 99.999999999%, tích hợp tốt với toàn bộ ecosystem AWS |
| **AWS Glue** | ETL job | Managed Spark, tự scale, phù hợp transform nặng (≥15 phút) — Lambda bị giới hạn 15 phút, **không phù hợp** cho bước này |
| **AWS Lambda** | Báo cáo nhẹ / alert | Đủ cho aggregate nhỏ + gửi email, không cần server, chi phí gần 0 |
| **Amazon Athena** | Query on-demand | Query SQL trực tiếp trên Parquet trong S3, không cần database riêng, trả tiền theo lượng scan |
| **AWS Glue Data Catalog** | Schema registry | Tập trung quản lý schema, Athena đọc từ đây |
| **EventBridge Scheduler** | Điều phối lịch | Thay cron đơn giản, có retry policy, tích hợp với Glue |
| **IAM** | Phân quyền | Least-privilege: mỗi component chỉ có quyền đúng việc của nó |
| **CloudWatch** | Monitor + alert | Tập trung log Glue Job, dashboard tỉ lệ lỗi, alarm khi vượt ngưỡng |

### Về S3 storage class

- **S3 Standard** cho `raw/` và `clean/` trong 30 ngày đầu (truy cập thường xuyên)
- **S3 Intelligent-Tiering** hoặc **S3 Standard-IA** cho data cũ hơn 30 ngày (lưu trữ dài hạn, ít truy cập)
- Dùng S3 Lifecycle Policy tự động chuyển class sau N ngày

> **Lưu ý:** S3 Standard-IA *không* phải "lựa chọn mặc định rẻ nhất" — nếu truy cập thường xuyên, chi phí retrieval của IA có thể đắt hơn Standard. Phải chọn theo pattern truy cập thực tế.

---

## Các điểm tuân thủ chính sách (POL-02)

- Dữ liệu log **không chứa thông tin định danh khách hàng** (PII masking trước khi ingest)
- Mọi truy cập S3 được log qua **S3 Access Logs + CloudTrail**
- Không kết nối trực tiếp database production — log được push ra file, tách biệt hoàn toàn
- Môi trường POC hoàn toàn tách biệt production (separate AWS account hoặc VPC)
