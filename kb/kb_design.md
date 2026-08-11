# Thiết kế Knowledge Base — Mini KB cho Trợ lý AI

**Dự án:** Xbrain DE POC · **Tác giả:** Hoàng Kim Hùng  
**Ngày:** 2026-08-11

---

## 1. Chiến lược chia chunk (Chunking Strategy)

### Tại sao chọn chia theo cấu trúc tài liệu?

8 tài liệu nguồn đều là tài liệu vận hành/chính sách (SOP, FAQ, GUIDE, POLICY, RUNBOOK) với cấu trúc heading Markdown rõ ràng. Người dùng trợ lý AI trong ngữ cảnh này thường hỏi những câu tập trung như "backup chạy lúc mấy giờ?" hay "restart payment-api thì phải làm gì?" — mỗi câu hỏi ánh xạ đúng vào một mục của một tài liệu cụ thể.

| Chiến lược | Đã cân nhắc? | Quyết định |
|---|---|---|
| Cố định theo số ký tự/token (fixed-size) | Có | ✗ Loại bỏ — sẽ cắt ngang giữa các bước trong SOP, cắt ngang bảng trong GUIDE |
| **Theo cấu trúc heading H2** | Có | **✓ Chọn** — giữ trọn ngữ nghĩa từng mục, không mất ngữ cảnh quy trình |
| Theo ngữ nghĩa (embedding-based split) | Có | ✗ Phức tạp không cần thiết với 8 tài liệu nhỏ; thêm dependency mà không có lợi ích rõ |

### Cách hoạt động

Mỗi tài liệu được cắt tại mỗi heading `##` (H2). Phần header trước H2 đầu tiên (tiêu đề tài liệu + dòng metadata) được giữ lại là chunk index 0.

```
# POL-01 — Chính sách sao lưu dữ liệu       ← chunk 0 (header)
## Quy định                                   ← chunk 1
## Trách nhiệm                                ← chunk 2
```

Kết quả: **30 chunks** từ 8 tài liệu (trung bình 3–6 chunk/tài liệu), kích thước từ ~100 đến ~500 ký tự. Kích thước chunk không đều là cố ý — một section SOP 3 bước được giữ nguyên thay vì cắt để đạt ngưỡng token nhất định.

### Lý do về kích thước chunk

Chunk lớn nhất là "Quy trình chuẩn" của SOP-01 (~450 ký tự, 6 bước). Toàn bộ quy trình này phải được trả về cùng nhau — nếu cắt ra thì AI chỉ đọc được một nửa quy trình. Đây là đánh đổi phù hợp với KB vận hành có tài liệu nhỏ như thế này.

---

## 2. Metadata cho mỗi Chunk

Mỗi chunk lưu các trường sau:

| Trường | Kiểu | Mục đích |
|---|---|---|
| `chunk_id` | TEXT PK | ID duy nhất: `{DOC_ID}-v{VERSION}-s{IDX}` |
| `doc_id` | TEXT | Mã tài liệu (ví dụ: `POL-01`) |
| `doc_title` | TEXT | Tên tài liệu dạng đọc được |
| `doc_type` | TEXT | `SOP`, `FAQ`, `GUIDE`, `POLICY`, `RUNBOOK` |
| `version` | TEXT | Phiên bản tài liệu (ví dụ: `2.0`) |
| `effective_date` | TEXT | Ngày tài liệu có hiệu lực (ISO date) |
| `owner` | TEXT | Đội/người chịu trách nhiệm |
| `active` | INTEGER | **1 = đang hiệu lực, 0 = đã bị thay thế** — trường chính để xử lý mâu thuẫn |
| `superseded_by` | TEXT | ID tài liệu thay thế tài liệu này |
| `filename` | TEXT | Tên file nguồn để truy vết |
| `section_index` | INTEGER | Thứ tự section trong tài liệu |
| `section_title` | TEXT | Nội dung heading H2 |
| `content` | TEXT | Toàn bộ nội dung markdown của section |

Trường `active` là cốt lõi của cơ chế xử lý mâu thuẫn (xem Mục 4).

---

## 3. Công nghệ Index / Tìm kiếm

### Lựa chọn: SQLite FTS5 + fallback multi-keyword LIKE

**Tại sao chọn SQLite FTS5:**
- Không cần infrastructure — một file `.db` duy nhất, chạy offline, dễ tái tạo
- FTS5 cung cấp inverted index với ranking kiểu BM25 (`ORDER BY f.rank`)
- Đủ dùng với KB quy mô này (<50 chunks, <100KB text)
- Tiêu chí bài thi nhấn mạnh: lý do chọn công cụ quan trọng hơn bản thân công cụ

**Hạn chế đã biết và cách xử lý:**
Tokenizer mặc định của FTS5 (`unicode61`) không phân tách từ ghép tiếng Việt như tiếng Anh. Query tiếng Việt nhiều từ truyền vào dưới dạng phrase đôi khi trả 0 kết quả vì tokenizer tách theo khoảng trắng nhưng phrase matching yêu cầu các token liền kề nhau chính xác.

**Giải pháp — Tìm kiếm 2 tầng:**
```
Tầng 1: FTS5 phrase match   → nhanh, hoạt động tốt với ASCII và từ đơn
Tầng 2: Multi-keyword AND LIKE fallback → nếu FTS5 trả 0 kết quả, tách query
         thành từng keyword riêng, yêu cầu TẤT CẢ keyword xuất hiện trong content (AND).
         Đánh đổi độ chính xác lấy độ bao phủ với text tiếng Việt.
```

Cả hai tầng đều áp dụng `active = 1` — bộ lọc xử lý mâu thuẫn không bao giờ bị bỏ qua.

**Những gì đã KHÔNG chọn và lý do:**
- OpenAI/HuggingFace embeddings: thêm chi phí API, độ trễ, và phụ thuộc vector store cho 30 chunks — không hợp lý
- Elasticsearch: overhead vận hành; quá mức cần thiết cho quy mô này
- BM25 (thư viện rank_bm25): cải thiện tìm kiếm tiếng Việt nhưng thêm dependency và cần re-index; ghi nhận là hướng cải thiện tương lai

---

## 4. Xử lý mâu thuẫn: POL-01 v1 vs v2

### Mâu thuẫn cụ thể

`POL-01_chinh_sach_backup_v1.md` và `POL-01_chinh_sach_backup_v2.md` mô tả cùng một chính sách với các giá trị trực tiếp mâu thuẫn:

| Nội dung | v1.0 (đã hết hiệu lực) | v2.0 (đang hiệu lực) |
|---|---|---|
| Giờ backup | **22:00** | **23:30** |
| Thời gian lưu giữ | **7 ngày** | **30 ngày** |
| Nơi lưu trữ | Server nội bộ phòng máy | Cloud mã hoá |
| Phê duyệt khôi phục | Không cần | **Phải có phê duyệt Trưởng phòng Vận hành** |
| Ngày hiệu lực | 2025-06-01 | 2026-05-01 |

Nếu cả hai phiên bản đều có thể tìm được, một câu hỏi về giờ backup có thể trả về cả hai đáp án — và AI sẽ tự tin trả lời theo thông tin đã lỗi thời.

### Cơ chế xử lý

**Metadata phiên bản + thời gian hiệu lực → flag `active`:**

```python
DOC_CATALOG = {
    "POL-01_chinh_sach_backup_v1.md": { ..., "active": False },   # đã bị thay thế
    "POL-01_chinh_sach_backup_v2.md": { ..., "active": True  },   # đang hiệu lực
}
```

Tất cả query tìm kiếm đều có `WHERE c.active = 1` — các chunk đã superseded được lưu lại (để tra cứu lịch sử) nhưng không bao giờ trả về cho AI. Kết quả:

- Query `"22:00"` → trúng POL-01 v1.0 (active=0) → **bị chặn, trả 0 kết quả** ✓
- Query `"23:30"` → trúng POL-01 v2.0 (active=1) → **trả về đúng** ✓
- Query `"sao lưu"` → chỉ trả POL-01 v2.0 ✓

Trường `superseded_by` cung cấp con trỏ tiến để người vận hành có thể truy vết lịch sử: v1 → `superseded_by: POL-01-v2`.

### Tại sao không xóa các phiên bản cũ?

Record đã xóa không thể kiểm toán được. Giữ lại với `active=0` đảm bảo:
1. **Lịch sử kiểm toán** — có thể tái dựng lại nội dung chính sách tại bất kỳ thời điểm nào trong quá khứ
2. **Re-index an toàn** — rebuild luôn cho ra trạng thái đúng từ DOC_CATALOG
3. **Xử lý mâu thuẫn tường minh** — không phải ghi đè ngầm, dễ kiểm tra và debug

---

## 5. Cấu trúc thư mục

```
kb/
├── kb_builder.py    # xây dựng kb.db từ docs; định nghĩa DOC_CATALOG + chunking + search
├── kb_design.md     # tài liệu này
├── run_eval.py      # chạy 10 câu hỏi eval và in kết quả pass/fail
├── eval_set.md      # câu hỏi eval + đáp án mong đợi + kết quả chạy thực tế
└── output/
    └── kb.db        # SQLite database đã tạo (trong production nên gitignore, commit để review)
```
