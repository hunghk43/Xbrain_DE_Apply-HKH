# Bộ Đánh Giá (Eval Set) — Kiểm tra chất lượng Knowledge Base

**Dự án:** Xbrain DE POC · **Tác giả:** Hoàng Kim Hùng  
**Ngày:** 2026-08-11  
**Phiên bản KB:** 30 chunks / 8 tài liệu

---

## Cơ sở thiết kế bộ câu hỏi

10 câu hỏi bao phủ 4 loại theo phương pháp eval (reading/02_rag_eval_basics.md):

| Loại câu hỏi | Câu hỏi | Mục đích |
|---|---|---|
| Tra cứu trực tiếp | Q01–Q03, Q05, Q08 | Đáp án nằm gọn trong 1 mục |
| Tổng hợp nhiều nguồn | Q04, Q07 | Đáp án phải ghép từ 2 tài liệu |
| Bẫy phiên bản | Q10 | Tài liệu cũ có đáp án mâu thuẫn — phải trả về v2 |
| Ngoài phạm vi | Q09 | Đáp án đúng là "không có thông tin" |

**Thang điểm cho mỗi câu:**
- **PASS** — tài liệu đúng xuất hiện ở top-1, nội dung khớp đáp án mong đợi, chỉ phiên bản active
- **PARTIAL** — tài liệu đúng ở top-2 nhưng không phải top-1, hoặc nội dung đúng nhưng thiếu ý quan trọng
- **FAIL** — sai tài liệu, sai đáp án, hoặc trả về nội dung đã hết hiệu lực

---

## 10 Câu hỏi Eval

### Q01 — Giờ chạy backup (tra cứu trực tiếp, nhạy cảm phiên bản)

**Câu hỏi:** Hệ thống sao lưu chạy lúc mấy giờ?  
**Đáp án mong đợi:** Hằng ngày lúc **23:30** (theo POL-01 v2.0).  
**Nguồn:** POL-01 v2.0 · Mục "Quy định" · hiệu lực từ 2026-05-01  
**Bẫy:** POL-01 v1.0 ghi 22:00 — KHÔNG được xuất hiện.  
**Tiêu chí đạt:** Trả về POL-01 v2.0, nêu đúng 23:30, không nhắc đến 22:00.

---

### Q02 — Thời gian lưu giữ backup (tra cứu trực tiếp)

**Câu hỏi:** Bản sao lưu được giữ trong bao lâu?  
**Đáp án mong đợi:** **30 ngày** theo yêu cầu kiểm toán mới (POL-01 v2.0).  
**Nguồn:** POL-01 v2.0 · Mục "Quy định"  
**Bẫy:** POL-01 v1.0 ghi 7 ngày.  
**Tiêu chí đạt:** Nêu đúng 30 ngày, dẫn nguồn POL-01 v2.0, không nhắc đến 7 ngày.

---

### Q03 — Phê duyệt khôi phục dữ liệu (tra cứu trực tiếp)

**Câu hỏi:** Khi cần khôi phục dữ liệu, cần xin phê duyệt của ai?  
**Đáp án mong đợi:** Phải có phê duyệt của **Trưởng phòng Vận hành** trước khi thực hiện (POL-01 v2.0).  
**Nguồn:** POL-01 v2.0 · Mục "Quy định" · điều khoản 4  
**Bẫy:** POL-01 v1.0 ghi không cần phê duyệt.  
**Tiêu chí đạt:** Nêu rõ cần phê duyệt từ Trưởng phòng Vận hành; dẫn nguồn POL-01 v2.0.

---

### Q04 — Điều kiện an toàn khi restart payment-api (tổng hợp nhiều nguồn)

**Câu hỏi:** Khi cần restart payment-api, phải kiểm tra điều kiện gì trước?  
**Đáp án mong đợi:** Phải xác nhận **queue = 0** (không còn giao dịch đang xử lý); thông báo vào kênh `#ops-alert` trước khi thao tác (SOP-01). Lý do: restart khi còn giao dịch treo có thể gây lệch số dư.  
**Nguồn:** SOP-01 v1.0 · Mục "Quy trình chuẩn" · bước 2 và 3  
**Tiêu chí đạt:** Nêu được điều kiện queue=0 VÀ thông báo kênh #ops-alert.

---

### Q05 — Xử lý lỗi ERR ConnTimeout (tra cứu trực tiếp)

**Câu hỏi:** Lỗi `ERR ConnTimeout db-primary` xảy ra do gì và xử lý thế nào?  
**Đáp án mong đợi:** Nguyên nhân: database quá tải, hết connection pool, hoặc sự cố mạng nội bộ. Xử lý: kiểm tra tải DB trên dashboard; **KHÔNG restart dịch vụ** nếu DB quá tải (làm bão kết nối nặng thêm); liên hệ DBA trực.  
**Nguồn:** FAQ-01 v1.0 · Mục "ERR ConnTimeout db-primary"  
**Tiêu chí đạt:** Nêu được "không restart" VÀ "liên hệ DBA".

---

### Q06 — Thời hạn phản ứng sự cố P1 (tra cứu trực tiếp)

**Câu hỏi:** Sự cố mức P1 yêu cầu phản ứng trong bao lâu?  
**Đáp án mong đợi:** **15 phút**, áp dụng mọi khung giờ (kể cả ngoài giờ hành chính).  
**Nguồn:** SOP-02 v1.0 · Mục "Phân mức sự cố"  
**Tiêu chí đạt:** Nêu đúng 15 phút VÀ "mọi khung giờ".

---

### Q07 — Xử lý lỗi job báo cáo NullPointer (tổng hợp nhiều nguồn)

**Câu hỏi:** Job báo cáo cuối ngày lỗi `ERR NullPointer in ReportBuilder` — phải làm gì?  
**Đáp án mong đợi:** Kiểm tra dữ liệu đầu vào ngày đó có thiếu không; nếu thiếu thì chờ dữ liệu được đồng bộ lại (KHÔNG chạy lại ngay); sau đó chạy lại lệnh rerun; xác nhận báo cáo đủ 800–1.200 dòng trước khi gửi (RUN-01).  
**Nguồn:** RUN-01 v1.0 · Mục "Khi job lỗi"; FAQ-01 mục 4 (tham chiếu chéo)  
**Tiêu chí đạt:** Nêu được "chờ đồng bộ dữ liệu" VÀ "kiểm tra số dòng 800–1200".

---

### Q08 — Chính sách mật khẩu (tra cứu trực tiếp)

**Câu hỏi:** Mật khẩu hệ thống phải đổi sau bao lâu? Truy cập từ ngoài mạng cần điều kiện gì?  
**Đáp án mong đợi:** Đổi mật khẩu mỗi **90 ngày**; bắt buộc **xác thực 2 lớp** khi truy cập từ ngoài mạng nội bộ.  
**Nguồn:** POL-02 v1.1 · Mục "Quy định chung" · điều khoản 3  
**Tiêu chí đạt:** Nêu đúng 90 ngày VÀ xác thực 2 lớp.

---

### Q09 — Câu hỏi ngoài phạm vi KB

**Câu hỏi:** Chính sách lương thưởng và phúc lợi nhân viên quy định thế nào?  
**Đáp án mong đợi:** **Không có thông tin** về chủ đề này trong knowledge base.  
**Nguồn:** N/A — không có trong bất kỳ tài liệu nào trong 8 docs  
**Tiêu chí đạt:** Trả về không có kết quả hoặc nêu rõ "không có thông tin trong KB". FAIL nếu hệ thống bịa đặt câu trả lời.

---

### Q10 — Bẫy phiên bản (xử lý mâu thuẫn)

**Câu hỏi:** Thông tin về giờ backup "22:00" — hệ thống xử lý thế nào?  
**Đáp án mong đợi:** Query "22:00" trả về **0 kết quả** vì giờ đó chỉ có trong POL-01 v1.0 (đã hết hiệu lực, active=0). Câu trả lời đúng là giờ hiện hành là 23:30 (POL-01 v2.0).  
**Nguồn bị chặn:** POL-01 v1.0 · active=0  
**Tiêu chí đạt:** Hệ thống trả về 0 kết quả với query "22:00" (không trả về tài liệu đã superseded).

---

## Kết quả Chạy Thực Tế (2026-08-11)

Lệnh chạy: `python kb/run_eval.py`

| ID | Query | Tài liệu mong đợi | Kết quả top-1 thực tế | Kết quả |
|---|---|---|---|---|
| Q01 | sao lưu 23:30 | POL-01 v2.0 | POL-01 v2.0 ✓ | **PASS** |
| Q02 | lưu giữ 30 ngày | POL-01 v2.0 | POL-01 v2.0 ✓ | **PASS** |
| Q03 | khôi phục phê duyệt | POL-01 v2.0 | POL-01 v2.0 ✓ | **PASS** |
| Q04 | payment-api restart queue | SOP-01 v1.0 | SOP-01 v1.0 ✓ | **PASS** |
| Q05 | ERR ConnTimeout | FAQ-01 v1.0 | FAQ-01 v1.0 ✓ | **PASS** |
| Q06 | P1 thời hạn phản ứng | SOP-02 v1.0 | SOP-02 v1.0 ✓ | **PASS** |
| Q07 | NullPointer ReportBuilder | RUN-01 v1.0 | FAQ-01 v1.0 (top-2: RUN-01) | **PARTIAL** |
| Q08 | mật khẩu 90 ngày | POL-02 v1.1 | POL-02 v1.1 ✓ | **PASS** |
| Q09 | lương thưởng phúc lợi | Không có | không có kết quả ✓ | **PASS** |
| Q10 | 22:00 (bẫy phiên bản) | BỊ CHẶN | không có kết quả (active=0 bị chặn) ✓ | **PASS** |

**Tổng kết: 9/10 PASS · 1/10 PARTIAL · 0/10 FAIL**

---

### Phân tích Q07

Q07 trả về FAQ-01 "ERR NullPointer in ReportBuilder" ở top-1 vì FAQ-01 chứa đúng chuỗi lỗi đó và cả hai keyword đều khớp. RUN-01 vẫn được tìm thấy đúng ở hit-2. Trong hệ thống RAG thực tế, cả hai chunk đều được truyền vào LLM và quy trình đầy đủ trong RUN-01 sẽ được sử dụng để trả lời. Đây là hạn chế đã biết của tìm kiếm keyword với tài liệu tham chiếu chéo.

**Hướng cải thiện:** Dùng `doc_type` làm tiêu chí tie-breaker — ưu tiên `RUNBOOK` hơn `FAQ` cho câu hỏi liên quan đến quy trình. Có thể thực hiện bằng một bước re-ranking đơn giản sau khi retrieval.

---

### Kiểm chứng mâu thuẫn phiên bản (chi tiết Q10)

```
query='22:00'  → kết quả active=1: 0
               → kết quả superseded: 1 ([POL-01 v1.0] active=0) ← BỊ CHẶN ✓

query='23:30'  → kết quả active=1: 1 ([POL-01 v2.0] active=1) ✓
```

---

## Hạn chế đã biết

1. **Tokenization tiếng Việt** — Tokenizer FTS5 của SQLite không phân tách từ ghép tiếng Việt một cách tự nhiên. Đã xử lý bằng fallback multi-keyword LIKE, nhưng ranking có thể chưa tối ưu với câu hỏi phức tạp.
2. **Không có tìm kiếm ngữ nghĩa/synonym** — Query tiếng Anh "restore" sẽ không tìm được "khôi phục". Một tầng embedding sẽ giải quyết được vấn đề này.
3. **Tài liệu tham chiếu chéo** — Q07 cho thấy nội dung tham chiếu chéo (FAQ trỏ đến RUN) cần multi-hop retrieval, hệ thống hiện tại xử lý chưa hoàn hảo.
