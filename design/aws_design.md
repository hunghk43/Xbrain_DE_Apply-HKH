# AWS Architecture Design — Daily Log Pipeline

**Công ty Tài chính Sao Đỏ — Xbrain POC**

> Sơ đồ kiến trúc: `Xbrain_DE_Apply_HKH.drawio.png`

---

## Services sử dụng

| Service | Vai trò |
|---------|---------|
| **S3 Raw** | Lưu log gốc (.jsonl) từ 5 service của khách hàng — immutable, không sửa |
| **AWS EventBridge** | Scheduler kích hoạt Glue Job hằng ngày lúc 01:00 |
| **AWS Glue** | ETL job: validate, clean, deduplicate, convert sang Parquet |
| **S3 Quarantine** | Lưu các record bị lỗi (bad records) để review và reprocess sau |
| **S3 Processed** | Dataset sạch định dạng Parquet, partition theo `year/month/day` |
| **Glue Data Catalog** | Schema registry — Athena cần để biết cấu trúc file Parquet trên S3 |
| **AWS Athena** | Query SQL trực tiếp trên S3 Processed, pay-per-query |
| **QuickSight** | Dashboard visualization cho đội vận hành |
| **AWS CloudWatch** | Thu thập data quality metrics từ Glue Job, theo dõi error rate |
| **Lambda Alert** | Trigger khi error rate vượt ngưỡng → gửi thông báo qua SNS |
| **SNS** | Gửi email alert tới đội vận hành khi có sự cố |

---

## Lý do chọn format Parquet

Parquet là định dạng **columnar** (lưu theo cột) — phù hợp cho analytics vì:
- Athena chỉ scan đúng cột cần query, không đọc toàn bộ file → giảm chi phí và tăng tốc độ
- Nén tốt hơn JSON/CSV từ 5–10 lần
- Hỗ trợ partition pruning theo `date` → query ngày cụ thể chỉ đọc đúng partition đó

---

## S3 Lifecycle Policy (S3 Processed)

- **0–30 ngày:** S3 Standard — truy cập thường xuyên để query
- **30+ ngày:** S3 Standard-IA — ít truy cập, tiết kiệm ~40% chi phí lưu trữ

---

## IAM — Least-privilege

| Role | Quyền |
|------|-------|
| GlueJobRole | Read S3 Raw · Write S3 Processed · Write S3 Quarantine · Write CloudWatch |
| LambdaRole | Read CloudWatch · Publish SNS |
| AthenaRole | Read S3 Processed · Read Glue Data Catalog |
| QuickSightRole | Read Athena query results |

---

## Điểm còn chưa chắc

1. **Ingest method:** hiện dùng S3 batch upload (phù hợp log cuối ngày). Nếu cần near-realtime thì nên dùng **Kinesis Data Firehose** thay thế — chưa có kinh nghiệm thực tế với Firehose.
2. **EventBridge + Glue trigger:** biết về mặt lý thuyết, chưa cấu hình thực tế. Chưa rõ cách xử lý retry khi Glue Job fail giữa chừng.
3. **QuickSight:** chưa dùng thực tế — chưa rõ chi phí licensing per-user và cách setup SPICE cache.
4. **S3 Quarantine reprocessing:** thiết kế lưu bad records nhưng chưa có quy trình reprocess cụ thể khi đã fix lỗi nguồn.
