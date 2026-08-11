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

## Entry 07 — Fix search function: SQLite FTS5 và tiếng Việt

**Thời điểm:** Ngày 2, Phần B — debug KB  
**Công cụ AI:** Kiro  
**Mục tiêu:** Search trả 0 kết quả cho hầu hết query tiếng Việt multi-word

**Vấn đề phát hiện:**
Chạy eval 10 câu → 4/10 PASS. FTS5 phrase match thất bại với multi-word tiếng Việt ("sao lưu 23:30" → 0 results) vì tokenizer mặc định `unicode61` không handle compound phrase tiếng Việt như mong đợi.

**Prompt gửi AI:**
> SQLite FTS5 trả 0 kết quả cho query "sao lưu 23:30" nhưng cùng nội dung đó có trong DB. Nguyên nhân và cách fix mà không cần thêm dependency ngoài?

**AI trả lời:**
Giải thích tokenizer unicode61 split theo whitespace nhưng phrase match `"sao lưu 23:30"` yêu cầu exact token sequence. Đề xuất 2-tier: FTS5 → fallback multi-keyword AND LIKE (tách query thành keywords, tất cả phải xuất hiện trong content).

**Kiểm chứng:**
Implement fallback, chạy lại eval → 9/10 PASS. Verify logic với case Q10 (version trap) — fallback vẫn giữ `active=1` filter, không leak superseded content.

**Kết quả dùng:**
Search function trong `kb_builder.py` và `run_eval.py` — 2-tier: FTS5 phrase → multi-keyword LIKE fallback, cả hai tầng đều lọc `active=1`.

---

## Entry 08 — Thiết kế cơ chế conflict resolution cho POL-01 v1 vs v2

**Thời điểm:** Ngày 2, Phần B2  
**Công cụ AI:** Kiro  
**Mục tiêu:** Tìm và xử lý mâu thuẫn trong bộ tài liệu

**Prompt gửi AI:**
> Đọc 8 tài liệu docs. Tìm các cặp nội dung mâu thuẫn nhau. Với mỗi cặp: chỉ rõ mâu thuẫn là gì và đề xuất cơ chế để KB luôn trả lời theo bản đúng.

**AI trả lời:**
Phát hiện POL-01 v1 vs v2 với 4 điểm mâu thuẫn: giờ backup (22:00 vs 23:30), thời gian lưu giữ (7 vs 30 ngày), nơi lưu trữ, yêu cầu phê duyệt khôi phục. Đề xuất dùng `active` flag + `superseded_by` pointer.

**Kiểm chứng:**
Đọc kỹ cả hai file POL-01. Xác nhận tất cả 4 điểm mâu thuẫn đều chính xác. V2 có dòng "Thay thế phiên bản trước" xác nhận v2 là bản hiệu lực.

**Test version trap:**
Query "22:00" → 0 active results (v1 với active=0 bị block).  
Query "23:30" → POL-01 v2.0 active=1 được trả về. ✓

**Kết quả dùng:**
`DOC_CATALOG` trong `kb_builder.py` với `active=False` cho v1, cơ chế `WHERE active=1` trong tất cả search queries.



---

## Entry 09 — Viết review Task A: phát hiện 6 lỗi trong câu trả lời AI

**Thời điểm:** Ngày 2, Bài 2 Task A  
**Công cụ AI:** Kiro  
**Mục tiêu:** Xác định và giải thích đầy đủ tất cả lỗi kỹ thuật trong đoạn trả lời AI đề bài cho

**Prompt gửi AI:**
> Đọc đoạn trả lời AI trong đề Bài 2. Liệt kê tất cả điểm sai kỹ thuật, giải thích vì sao sai, đề xuất sửa lại. Phân loại mức độ nghiêm trọng.

**AI trả lời:**
Phát hiện đúng 6 lỗi: S3 Standard-IA cho hot data, Glue đọc RDS production mỗi 5 phút, Parquet mô tả là row-based, Lambda timeout 15 phút, chunk cố định 4.000 token, không version KB.

**Kiểm chứng từng lỗi:**
- Lỗi 1 (S3 Standard-IA): Xác nhận từ AWS S3 Pricing page — Standard-IA có phí retrieval $0.01/GB, không miễn phí như Standard
- Lỗi 2 (Glue đọc RDS production): Từ Accelerator — đây là anti-pattern, sẽ tạo load lên production DB
- Lỗi 3 (Parquet row-based): Xác nhận từ Apache Parquet docs — Parquet là columnar, không phải row-based
- Lỗi 4 (Lambda 15 phút): Xác nhận từ AWS Lambda docs — hard limit 900 seconds (15 minutes)
- Lỗi 5 (chunk 4.000 token): Từ `reading/01_chunking_basics.md` — "không có con số đúng cho mọi trường hợp"
- Lỗi 6 (không version KB): Từ `reading/01_chunking_basics.md` Mục 3 — đây là "rủi ro vận hành số một của hệ thống RAG"; verify bằng chính thực tế POL-01 v1 vs v2 trong data pack

**Kết quả dùng:** `ai_review.md` — review đầy đủ 6 lỗi với nguồn kiểm chứng cụ thể cho từng lỗi.

---

## Entry 10 — Thiết kế prompt extraction JSON từ message log

**Thời điểm:** Ngày 2, Bài 2 Task B  
**Công cụ AI:** Kiro  
**Mục tiêu:** Viết prompt có cấu trúc, xử lý được edge case, không hallucinate error_code

**Prompt gửi AI:**
> Viết system prompt cho LLM trích xuất message log thành JSON: error_code, error_type, component, parameters, is_error, confidence. Xử lý đủ ca: ERROR rõ, INFO bình thường, WARN mơ hồ, message thiếu thông tin. KHÔNG được bịa thông tin không có trong message.

**AI trả lời:**
Draft system prompt với schema JSON, 3 few-shot examples, và 5 rule rõ ràng về null vs hallucination.

**Kiểm chứng:**
Đọc kỹ prompt và test thủ công 5 case từ data pack thực:
- TC2 (INFO "Session created"): phát hiện ban đầu AI không có rule rõ ràng cho INFO → `is_error` có thể trả `true` → thêm rule #2 rõ ràng "INFO → is_error=false, error_code=null"
- TC3 (WARN "Queue depth high"): phát hiện WARN mơ hồ cần được xử lý riêng → thêm rule #3
- TC5 (ERR NullPointer không có tham số số học): phát hiện prompt ban đầu trả `confidence="high"` cho ca ít thông tin → thêm rule #4 về confidence

**Điểm AI sai / tôi điều chỉnh:**
- Prompt ban đầu thiếu rule về `confidence` → thêm rule #4
- Rule về "không bịa" trong version đầu không đủ rõ → viết lại thành "Chỉ trích xuất thông tin CÓ TRONG message. KHÔNG suy diễn, KHÔNG bịa thêm." (tường minh hơn)

**Kết quả dùng:** `prompt_design.md` — prompt hoàn chỉnh + 5 test case + phương pháp đánh giá trên 3.000 dòng thật.
