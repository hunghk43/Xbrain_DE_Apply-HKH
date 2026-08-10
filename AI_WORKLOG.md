# AI Work Log — Xbrain DE Assessment

**Ứng viên:** Hoang Kim Hung  
**Thời gian làm bài:** 08/2026

> Log trung thực các lần dùng AI có ảnh hưởng đến bài nộp. Chọn 8–15 entry có ý nghĩa nhất.
> Format mỗi entry: Mục tiêu → Prompt → AI trả lời gì → Tôi kiểm chứng ra sao → Đã dùng/sửa gì.

---

## Entry 01 — Phân tích data quality issues trong JSONL

**Thời điểm:** Ngày 1, bước Ingest  
**Công cụ AI:** Kiro (Claude)  
**Mục tiêu:** Hiểu nhanh các loại vấn đề dữ liệu trong file log trước khi viết pipeline

**Prompt gửi AI:**
> Đọc 80 dòng đầu của app_logs_7days.jsonl và liệt kê các loại vấn đề data quality bạn thấy.

**AI trả lời:**
Liệt kê được 5 vấn đề: invalid timestamp (`not-a-date`), out-of-order timestamp, missing `level` field, truncated JSON, duplicate record — và đề xuất cách xử lý từng loại.

**Kiểm chứng:**
Chạy thủ công `grep` một số pattern, đọc thêm 200 dòng ngẫu nhiên để xác nhận các loại lỗi có xuất hiện đều xuyên suốt file. Confirm đủ 5 loại.

**Kết quả dùng:**
Logic xử lý 5 loại vấn đề trong `pipeline.py` — đặc biệt cách xử lý truncated JSON (try/except JSONDecodeError per line) và duplicate key (request_id + timestamp + message).

---

## Entry 02 — Thiết kế schema output Parquet

**Thời điểm:** Ngày 1, bước Transform  
**Công cụ AI:** Kiro  
**Mục tiêu:** Quyết định schema cuối cho clean dataset

**Prompt gửi AI:**
> Với log data gồm timestamp, service, level, message, request_id — schema Parquet tốt nhất cho bước downstream query bằng Athena là gì? Cần thêm partition columns nào?

**AI trả lời:**
Đề xuất thêm cột `date` (string partition) và `hour` (int) để Athena partition pruning. Giữ timestamp dạng `datetime64[ns, UTC]`. Đề xuất kiểu dữ liệu cụ thể.

**Kiểm chứng:**
Đọc AWS Athena docs về partition projection — confirm rằng partition theo `date` string (YYYY-MM-DD) là pattern chuẩn. Đọc thêm pyarrow docs để đảm bảo timezone-aware timestamp được serialize đúng.

**Kết quả dùng:**
Schema trong hàm `transform()` của pipeline.py — thêm `date`, `hour`, giữ `datetime64[ns, UTC]`.

**Điểm AI sai / tôi điều chỉnh:**
AI ban đầu đề xuất dùng `category` dtype cho `service` và `level` để tiết kiệm bộ nhớ. Tôi giữ `str` vì với 3,000 records POC thì không cần optimize sớm, và category dtype đôi khi gây surprise behavior khi filter.

---

## Entry 03 — Review câu trả lời AI có lỗi (Bài 2 Part 2)

**Thời điểm:** Ngày 1, buổi chiều  
**Công cụ AI:** Kiro  
**Mục tiêu:** Phân tích đoạn text AI sai để viết phần review trong bài 2

**Prompt gửi AI:**
> Đọc đoạn trả lời sau của AI về AWS pipeline. Liệt kê tất cả điểm sai hoặc gây hiểu nhầm kỹ thuật, giải thích vì sao sai.

**AI trả lời:**
Phát hiện 6 lỗi với giải thích rõ từng lỗi (xem `part_b/ai_review.md`).

**Kiểm chứng:**
- Lỗi Parquet row-based: xác nhận từ Apache Parquet documentation chính thức
- Lỗi Lambda 15-phút timeout: xác nhận từ AWS Lambda docs (hard limit 15 min)
- Lỗi S3 Standard-IA: đọc AWS pricing page — Standard-IA có phí retrieval $0.01/GB
- Lỗi Glue đọc production DB: kiến thức từ Accelerator + common sense về DB load

**Điểm AI đúng:** Cả 6 lỗi đều legitimate, không phải false positive.  
**Điểm tôi bổ sung:** Lỗi #6 (không version KB) — AI phân tích đúng nhưng tôi bổ sung thêm ví dụ cụ thể từ POL-01 v1 vs v2 trong data pack.

---

## Entry 04 — Chunking strategy cho 8 tài liệu docs

**Thời điểm:** Ngày 2, Phần B  
**Công cụ AI:** Kiro  
**Mục tiêu:** Quyết định strategy chunking phù hợp với tập tài liệu SOP/chính sách

**Prompt gửi AI:**
> Tôi có 8 tài liệu vận hành (SOP, chính sách, FAQ, runbook) dạng Markdown với heading rõ ràng. Người dùng sẽ hỏi kiểu "backup lưu bao lâu?", "lỗi X xử lý thế nào?". Nên dùng chunking strategy nào?

**AI trả lời:**
Đề xuất structure-based chunking theo heading level 2 (##), giữ context của section header cha trong mỗi chunk, lưu metadata: doc_id, version, section_title, effective_date.

**Kiểm chứng:**
Đọc lại `reading/01_chunking_basics.md` — confirm cách suy luận từ "người hỏi thường hỏi đúng một mục" → structure-based phù hợp. Thử tay chunking 2 tài liệu để kiểm tra chunk size có hợp lý không (không quá to, không quá nhỏ).

**Kết quả dùng:**
Logic trong `kb_builder.py` — parse markdown theo `##` heading, mỗi section = 1 chunk.

---

## Entry 05 — Soạn eval set 10 câu hỏi

**Thời điểm:** Ngày 2, Phần B3  
**Công cụ AI:** Kiro  
**Mục tiêu:** Tạo bộ câu hỏi đa dạng, đủ các kiểu theo hướng dẫn trong reading/02

**Prompt gửi AI:**
> Từ 8 tài liệu này, soạn 10 câu hỏi eval cho KB, đảm bảo có đủ 4 loại: tra cứu trực tiếp, tổng hợp nhiều nguồn, bẫy phiên bản, ngoài phạm vi. Kèm đáp án mong đợi và tiêu chí chấm.

**AI trả lời:**
Đề xuất 10 câu hỏi với đáp án mong đợi, trích nguồn cụ thể.

**Kiểm chứng:**
Đọc lại từng tài liệu để verify đáp án đúng không. Phát hiện 1 câu AI dẫn nguồn nhầm (trích POL-01 v1 thay vì v2 cho câu hỏi về giờ backup hiện tại) — sửa lại.

**Điểm AI sai:** 1 câu dẫn nguồn sai phiên bản → đây là chính xác loại lỗi mà bộ eval phải bắt được (ironic).

---

## Entry 06 — Viết prompt extraction cho Bài 2 Part 3

**Thời điểm:** Ngày 2  
**Công cụ AI:** Kiro  
**Mục tiêu:** Thiết kế prompt trích xuất error_code, target từ message log

**Prompt gửi AI:**
> Viết system prompt cho LLM để trích xuất error_code và target từ message log dạng "ERR ConnTimeout db-primary after 30s retry=3". Output phải là JSON. Xử lý cả ca không có lỗi (INFO/WARN) và ca message mơ hồ.

**AI trả lời:**
Draft prompt với role, schema JSON, examples few-shot, và instruction xử lý edge case.

**Kiểm chứng:**
Test thủ công 5 case (xem phần Bài 2 P3), verify output JSON có đúng schema. Phát hiện prompt ban đầu hallucinate error_code cho WARN message → thêm instruction rõ hơn về "nếu không phải ERROR thì error_code = null".

---

*(Các entry 07–10 sẽ được thêm khi hoàn thiện Phần B và quá trình kiểm tra)*
