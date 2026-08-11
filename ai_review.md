# Bài 2 — Task A: Review câu trả lời AI

**Tác giả:** Hoàng Kim Hùng  
**Ngày:** 2026-08-11

---

## Câu trả lời AI cần review

> *"Bạn nên lưu toàn bộ log vào S3 Standard-IA vì đây là lựa chọn mặc định rẻ nhất cho data lake. Để thu dữ liệu, cấu hình một Glue job đọc trực tiếp từ database RDS production của khách mỗi 5 phút — đây là pattern chuẩn cho near-real-time. Dữ liệu nên chuyển sang Parquet, một format lưu theo hàng (row-based) nên ghi rất nhanh, phù hợp cho analytics. Với các bước transform nặng chạy khoảng 30–45 phút, dùng AWS Lambda là phù hợp nhất vì không phải quản lý server. Về knowledge base cho RAG, hãy chia tài liệu thành các chunk cố định 4.000 token — kích thước này luôn tốt nhất cho mọi loại tài liệu. Cuối cùng, không cần đánh version cho knowledge base, vì bản mới nhất luôn là bản đúng — cứ ghi đè là được."*

---

## Tổng đánh giá

Câu trả lời chứa **6 lỗi kỹ thuật**, trong đó 3 lỗi nghiêm trọng có thể gây mất dữ liệu hoặc chi phí ngoài kiểm soát nếu triển khai thật. Phong cách trả lời tự tin ("luôn tốt nhất", "pattern chuẩn") mà không có cảnh báo là dấu hiệu điển hình của AI hallucination tự tin.

---

## Chi tiết 6 lỗi

---

### Lỗi 1 — S3 Standard-IA không phải lựa chọn rẻ nhất cho data lake

**Câu AI nói:** *"lưu toàn bộ log vào S3 Standard-IA vì đây là lựa chọn mặc định rẻ nhất cho data lake"*

**Sai ở đâu:**
S3 Standard-IA (Infrequent Access) có **phí retrieval $0.01/GB** mỗi lần đọc. Log dùng cho analytics bị query thường xuyên — mỗi lần Athena scan hoặc Glue đọc đều tính phí retrieval. Với data lake log hằng ngày được query thường xuyên trong 30 ngày đầu, Standard-IA đắt hơn Standard-IA nghe có vẻ.

**Sửa lại:**
- Dữ liệu **hot (0–30 ngày):** dùng **S3 Standard** — không phí retrieval, phù hợp data được query thường xuyên
- Dữ liệu **cold (30+ ngày):** chuyển sang S3 Standard-IA hoặc S3 Glacier qua **Lifecycle Policy**
- "Rẻ nhất" phụ thuộc pattern truy cập: Standard-IA chỉ rẻ hơn khi dữ liệu thật sự ít được truy cập

**Nguồn kiểm chứng:** AWS S3 Pricing page — Standard-IA có mục "Data Retrieval: $0.01 per GB"

---

### Lỗi 2 — Glue job đọc trực tiếp từ RDS production mỗi 5 phút là anti-pattern nguy hiểm

**Câu AI nói:** *"cấu hình một Glue job đọc trực tiếp từ database RDS production của khách mỗi 5 phút — đây là pattern chuẩn cho near-real-time"*

**Sai ở đâu:**
Đây là **anti-pattern nghiêm trọng**, không phải "pattern chuẩn":
1. Glue job chạy mỗi 5 phút liên tục đọc RDS production → tạo tải thêm trực tiếp lên production DB, ảnh hưởng đến performance của ứng dụng đang chạy
2. Mỗi lần Glue khởi động tốn 1–2 phút warm-up — chạy mỗi 5 phút là không hợp lý về chi phí
3. Glue được thiết kế cho **batch ETL**, không phải near-real-time streaming

**Sửa lại:**
- Cho use case **log hằng ngày (batch):** log nên được **ghi ra file / stream lên S3 Raw** từ ứng dụng — Glue chỉ xử lý file từ S3, không đọc trực tiếp production DB
- Nếu cần **near-real-time:** dùng **Amazon Kinesis Data Firehose** hoặc **AWS DMS** để stream, rồi Glue/Lambda xử lý downstream — không đụng trực tiếp production DB

**Nguồn kiểm chứng:** Kiến thức từ Accelerator + AWS Glue documentation (Glue là batch ETL service, không phải streaming)

---

### Lỗi 3 — Parquet là format lưu theo cột (columnar), không phải row-based

**Câu AI nói:** *"Dữ liệu nên chuyển sang Parquet, một format lưu theo hàng (row-based) nên ghi rất nhanh"*

**Sai ở đâu:**
Parquet là định dạng **columnar (lưu theo cột)**, ngược hoàn toàn với mô tả của AI. Đây là lỗi kỹ thuật cơ bản:
- **Row-based** (CSV, JSON, Avro): ghi nhanh, phù hợp OLTP — đọc toàn bộ cột của mọi hàng khi query
- **Columnar** (Parquet, ORC): phù hợp analytics/OLAP — Athena chỉ đọc đúng cột cần query, bỏ qua phần còn lại → **giảm chi phí và tăng tốc**

Lý do chọn Parquet là đúng, nhưng mô tả kỹ thuật sai hoàn toàn. Nếu dùng mô tả này để giải thích với khách thì tạo ra hiểu lầm nghiêm trọng.

**Sửa lại:** *"Parquet là định dạng lưu theo cột (columnar), phù hợp cho analytics vì Athena chỉ scan đúng cột cần query, giảm lượng dữ liệu đọc và chi phí."*

**Nguồn kiểm chứng:** Apache Parquet documentation chính thức; AWS Athena docs giải thích tại sao nên dùng Parquet/ORC

---

### Lỗi 4 — Lambda không phù hợp cho job transform 30–45 phút

**Câu AI nói:** *"Với các bước transform nặng chạy khoảng 30–45 phút, dùng AWS Lambda là phù hợp nhất vì không phải quản lý server"*

**Sai ở đâu:**
AWS Lambda có **hard timeout 15 phút** — không thể chạy job 30–45 phút dù có muốn. Đây là giới hạn cứng của dịch vụ, không phải cấu hình.

**Sửa lại:**
Với batch transform **30–45 phút**, các lựa chọn đúng:
- **AWS Glue job** — serverless ETL, không giới hạn thời gian thực tế, thiết kế cho bài toán này
- **AWS Batch** — nếu cần container tùy chỉnh
- Lambda chỉ phù hợp với tác vụ nhẹ, nhanh: trigger event, validate nhanh, gửi notification — không phải ETL nặng

**Nguồn kiểm chứng:** AWS Lambda documentation — "Function timeout: 900 seconds (15 minutes) maximum"

---

### Lỗi 5 — Chunk cố định 4.000 token không "luôn tốt nhất cho mọi loại tài liệu"

**Câu AI nói:** *"hãy chia tài liệu thành các chunk cố định 4.000 token — kích thước này luôn tốt nhất cho mọi loại tài liệu"*

**Sai ở đâu:**
Không có kích thước chunk nào "luôn tốt nhất" — đây là quyết định thiết kế phụ thuộc vào:
- **Loại tài liệu:** SOP/quy trình nên cắt theo section (structure-based), không phải theo token count
- **Kiểu câu hỏi người dùng hỏi:** câu hỏi tra cứu từng mục vs câu hỏi tổng hợp toàn bộ tài liệu
- **Kích thước tài liệu gốc:** tài liệu ngắn như FAQ thì 4.000 token/chunk có thể bằng cả tài liệu

4.000 token/chunk trên tài liệu vận hành ngắn (SOP 500 từ) sẽ không cắt gì cả — toàn bộ tài liệu thành 1 chunk, mất granularity khi retrieval.

Đây là điểm được giải thích rõ trong `reading/01_chunking_basics.md`: *"Không có con số đúng cho mọi trường hợp"* và khuyến nghị structure-based cho tài liệu vận hành/chính sách.

**Sửa lại:** Cần phân tích loại tài liệu và kiểu câu hỏi trước khi chọn strategy. Với 8 tài liệu vận hành có heading rõ ràng, structure-based chunking theo H2 heading là lựa chọn phù hợp hơn.

**Nguồn kiểm chứng:** `reading/01_chunking_basics.md` trong data pack — Mục 2 "Ba chiến lược chia phổ biến"

---

### Lỗi 6 — Không version KB là rủi ro vận hành nghiêm trọng

**Câu AI nói:** *"không cần đánh version cho knowledge base, vì bản mới nhất luôn là bản đúng — cứ ghi đè là được"*

**Sai ở đâu:**
Đây là lỗi thiết kế nguy hiểm nhất trong cả câu trả lời, vì:

1. **"Bản mới nhất luôn là bản đúng" là sai** — trong bộ tài liệu POC này, POL-01 v1 (2025) và POL-01 v2 (2026) cùng tồn tại. Nếu ghi đè mà không version, hệ thống không phân biệt được bản nào hiệu lực khi có cả 2 file

2. **Ghi đè mất lịch sử kiểm toán** — tài liệu chính sách tài chính cần truy vết: "vào tháng 3/2026, chính sách backup quy định gì?" — ghi đè thì không trả lời được

3. **AI sẽ tự tin trả lời theo thông tin cũ nếu KB không cập nhật đúng** — đây là "rủi ro vận hành số một của hệ thống RAG" theo `reading/01_chunking_basics.md`

**Sửa lại:**
- Mỗi tài liệu cần metadata `version` + `effective_date` + flag `active`
- Khi có bản mới: bản cũ đổi `active=False` (giữ lại để audit), bản mới `active=True`
- Tất cả search query lọc `WHERE active = 1` — cơ chế này đảm bảo KB luôn trả lời theo bản hiệu lực

Ví dụ cụ thể từ POC này: POL-01 v1 nói backup lúc 22:00/giữ 7 ngày; POL-01 v2 nói 23:30/30 ngày. Nếu ghi đè hoặc không version, AI có thể trả lời theo bản sai với độ tự tin 100%.

**Nguồn kiểm chứng:** `reading/01_chunking_basics.md` Mục 3 — "Một knowledge base tốt... biết đoạn đó còn hiệu lực không"; thực tế xử lý trong `kb/kb_builder.py`

---

## Tóm tắt

| # | Lỗi | Mức độ | Hậu quả nếu triển khai |
|---|-----|--------|------------------------|
| 1 | S3 Standard-IA cho hot data | ⚠️ Trung bình | Chi phí retrieval tăng vọt |
| 2 | Glue đọc RDS production mỗi 5 phút | 🔴 Nghiêm trọng | Ảnh hưởng production DB, chi phí Glue cao |
| 3 | Parquet = row-based | ⚠️ Kỹ thuật | Giải thích sai cho khách, mất tin cậy |
| 4 | Lambda cho job 30–45 phút | 🔴 Nghiêm trọng | Job sẽ timeout sau 15 phút, không chạy được |
| 5 | Chunk 4.000 token "luôn tốt nhất" | ⚠️ Trung bình | KB có granularity kém, retrieval không chính xác |
| 6 | Không version KB | 🔴 Nghiêm trọng | AI trả lời theo tài liệu đã hết hiệu lực, không thể kiểm toán |
