# Bài 2 — Task B: Thiết kế Prompt Trích xuất Dữ liệu có Cấu trúc

**Tác giả:** Hoàng Kim Hùng  
**Ngày:** 2026-08-11

---

## 1. Bài toán

Các dòng log có trường `message` là văn bản tự do. Khách muốn dùng LLM để trích xuất thành JSON có cấu trúc để phân tích tự động.

Ví dụ message thô:
```
"ERR ConnTimeout db-primary after 30s retry=3"
"Slow query 1200ms table=tx_history"
"Session created uid=u2746"
```

---

## 2. Prompt hoàn chỉnh

### System Prompt

```
Bạn là một công cụ trích xuất dữ liệu có cấu trúc từ log hệ thống. Nhiệm vụ duy nhất của bạn là phân tích trường "message" trong một dòng log và trả về JSON theo schema quy định. KHÔNG được thêm giải thích, không được thêm markdown, không được trả lời gì ngoài JSON.

## Schema đầu ra

{
  "error_code": string | null,       // Mã lỗi nếu có (ví dụ: "ERR_CONN_TIMEOUT", "ERR_HTTP_502"). null nếu không phải ERROR.
  "error_type": string | null,       // Loại lỗi ngắn gọn (ví dụ: "connection_timeout", "slow_query"). null nếu không phải ERROR.
  "component": string | null,        // Thành phần/hệ thống bị ảnh hưởng (ví dụ: "db-primary", "payment-api"). null nếu không xác định được.
  "parameters": object | null,       // Các tham số kỹ thuật có trong message (ví dụ: {"retry": 3, "duration_ms": 1200}). null nếu không có.
  "is_error": boolean,               // true nếu message mô tả một lỗi/sự cố, false nếu là INFO bình thường hoặc WARN chưa thành lỗi.
  "confidence": "high" | "medium" | "low"  // Mức độ chắc chắn của kết quả trích xuất.
}

## Quy tắc bắt buộc

1. Chỉ trích xuất thông tin CÓ TRONG message. KHÔNG suy diễn, KHÔNG bịa thêm.
2. Nếu message là INFO thông thường (ví dụ: "Session created", "Email sent"): is_error=false, error_code=null, error_type=null.
3. Nếu message là WARN nhưng không phải lỗi rõ ràng (ví dụ: "Slow query", "Queue depth high"): is_error=false, error_code=null, error_type="slow_query" hoặc tương tự, component điền nếu có.
4. Nếu message mơ hồ, không đủ thông tin để xác định chắc chắn: điền confidence="low", điền null cho các trường không rõ.
5. KHÔNG hallucinate error_code nếu message không có mã lỗi rõ ràng.

## Ví dụ

Input: "ERR ConnTimeout db-primary after 30s retry=3"
Output: {"error_code": "ERR_CONN_TIMEOUT", "error_type": "connection_timeout", "component": "db-primary", "parameters": {"duration_s": 30, "retry": 3}, "is_error": true, "confidence": "high"}

Input: "Session created uid=u2746"
Output: {"error_code": null, "error_type": null, "component": null, "parameters": {"uid": "u2746"}, "is_error": false, "confidence": "high"}

Input: "Slow query 1200ms table=tx_history"
Output: {"error_code": null, "error_type": "slow_query", "component": "tx_history", "parameters": {"duration_ms": 1200}, "is_error": false, "confidence": "high"}
```

### User Prompt (mẫu, gọi mỗi dòng)

```
Trích xuất thông tin từ message log sau:

message: "{MESSAGE}"
```

---

## 3. Bộ test 5 message từ data pack

### Test Case 1 — ERROR rõ ràng với nhiều tham số

**Input:**
```json
{"level": "ERROR", "message": "ERR ConnTimeout db-primary after 30s retry=3"}
```

**Đầu ra kỳ vọng:**
```json
{
  "error_code": "ERR_CONN_TIMEOUT",
  "error_type": "connection_timeout",
  "component": "db-primary",
  "parameters": {"duration_s": 30, "retry": 3},
  "is_error": true,
  "confidence": "high"
}
```

**Lý do chọn:** Ca chuẩn — ERROR có mã lỗi rõ, có component rõ, có tham số số học → phải parse đúng hết.

---

### Test Case 2 — INFO bình thường, không phải lỗi

**Input:**
```json
{"level": "INFO", "message": "Session created uid=u2746"}
```

**Đầu ra kỳ vọng:**
```json
{
  "error_code": null,
  "error_type": null,
  "component": null,
  "parameters": {"uid": "u2746"},
  "is_error": false,
  "confidence": "high"
}
```

**Lý do chọn:** Kiểm tra prompt không hallucinate lỗi cho message INFO. `is_error` phải là `false`.

---

### Test Case 3 — WARN, có số liệu nhưng không phải lỗi

**Input:**
```json
{"level": "WARN", "message": "Queue depth high depth=2656"}
```

**Đầu ra kỳ vọng:**
```json
{
  "error_code": null,
  "error_type": "queue_depth_high",
  "component": null,
  "parameters": {"depth": 2656},
  "is_error": false,
  "confidence": "high"
}
```

**Lý do chọn:** WARN có thể gây nhầm lẫn — prompt phải hiểu đây không phải ERROR, nhưng vẫn trích được tham số `depth`.

---

### Test Case 4 — ERROR với HTTP status code (ca khó: component là service name)

**Input:**
```json
{"level": "ERROR", "message": "ERR HTTP 502 upstream=payment-api"}
```

**Đầu ra kỳ vọng:**
```json
{
  "error_code": "ERR_HTTP_502",
  "error_type": "http_upstream_error",
  "component": "payment-api",
  "parameters": {"http_status": 502},
  "is_error": true,
  "confidence": "high"
}
```

**Lý do chọn:** Ca khó — "upstream=payment-api" là tham số nhưng cũng chính là component. Test xem prompt có nhận diện đúng component không.

---

### Test Case 5 — Ca mơ hồ: message không có thông tin kỹ thuật cụ thể

**Input:**
```json
{"level": "ERROR", "message": "ERR NullPointer in ReportBuilder"}
```

**Đầu ra kỳ vọng:**
```json
{
  "error_code": "ERR_NULL_POINTER",
  "error_type": "null_pointer_exception",
  "component": "ReportBuilder",
  "parameters": null,
  "is_error": true,
  "confidence": "medium"
}
```

**Lý do chọn:** Ca mơ hồ — không có tham số số học, chỉ có tên component. `confidence` nên là `"medium"` vì thiếu ngữ cảnh, không phải `"high"`.

---

## 4. Cách đánh giá prompt trên 3.000 dòng thật

### 4.1 Tiêu chí đo

| Tiêu chí | Công thức | Ngưỡng chấp nhận |
|---|---|---|
| **Schema compliance** | % JSON output đúng schema (parse được, đủ fields) | ≥ 98% |
| **is_error accuracy** | % dòng ERROR có `is_error=true` đúng (so với `level` field gốc) | ≥ 95% |
| **error_code precision** | Trong các dòng `is_error=true`: % có `error_code` khớp pattern message | ≥ 85% |
| **Hallucination rate** | % dòng INFO/WARN có `error_code != null` (bịa lỗi) | ≤ 2% |
| **Null rate hợp lý** | % dòng INFO có `error_code=null` | ≥ 98% |

### 4.2 Cách phát hiện hallucination

**Phương pháp 1 — Cross-check với `level` field:**
```python
# Dòng level=INFO nhưng LLM trả is_error=true → hallucination
hallucination_count = df[(df['level'] == 'INFO') & (df['llm_is_error'] == True)].shape[0]
hallucination_rate  = hallucination_count / df[df['level'] == 'INFO'].shape[0]
```

**Phương pháp 2 — Pattern matching trên error_code:**
Dùng regex kiểm tra `error_code` có khớp với pattern trong `message` không. Nếu message không chứa chuỗi khớp error_code → nghi bịa.
```python
import re
def check_error_code_grounded(row):
    if row['llm_error_code'] is None:
        return True  # null là hợp lệ
    # Kiểm tra error code có xuất hiện (dạng nào đó) trong message gốc
    code_hint = row['llm_error_code'].replace('_', ' ').lower()
    return code_hint[:8] in row['message'].lower()
```

**Phương pháp 3 — Sampling thủ công:**
Random sample 50–100 dòng, người review đọc message gốc và JSON output, đánh dấu đúng/sai. Tính precision thủ công. Bắt buộc với lần đánh giá đầu tiên trước khi tin vào automated metrics.

### 4.3 Khi nào cần người kiểm tra

- Hallucination rate > 2% → xem lại prompt, cụ thể hóa rule "không bịa"
- Schema compliance < 98% → LLM trả markdown hoặc text thừa → thêm instruction `"Chỉ trả về JSON, không có gì khác"`
- error_code precision < 85% → cần thêm few-shot examples cho các pattern hay gặp
- Sau mỗi lần update prompt → chạy lại bộ 5 test case + 50-dòng manual sample trước khi deploy

---

## 5. (Điểm cộng) Kết quả chạy thử — mô phỏng thủ công

*Lưu ý: Không có API key LLM trong môi trường này, nên phần này mô phỏng kết quả dự đoán dựa trên thực hành prompt engineering.*

| Test | Message | LLM output dự đoán | Đánh giá |
|---|---|---|---|
| TC1 | ERR ConnTimeout db-primary after 30s retry=3 | error_code="ERR_CONN_TIMEOUT", is_error=true, component="db-primary", params={duration_s:30, retry:3} | ✅ Đúng hết |
| TC2 | Session created uid=u2746 | error_code=null, is_error=false, params={uid:"u2746"} | ✅ Không hallucinate |
| TC3 | Queue depth high depth=2656 | error_code=null, is_error=false, error_type="queue_depth_high" | ✅ WARN xử lý đúng |
| TC4 | ERR HTTP 502 upstream=payment-api | error_code="ERR_HTTP_502", component="payment-api", params={http_status:502} | ✅ Component đúng |
| TC5 | ERR NullPointer in ReportBuilder | error_code="ERR_NULL_POINTER", component="ReportBuilder", confidence="medium" | ✅ confidence hạ đúng |

**Nhận xét:** Prompt few-shot 3 ví dụ trong system prompt đủ để hướng format. Rule rõ ràng về `is_error=false` cho INFO/WARN là quan trọng nhất để ngăn hallucination. Trên 3.000 dòng thật, cần đặc biệt chú ý các message có level=WARN vì ranh giới "là lỗi hay chưa" phụ thuộc ngữ cảnh mà prompt hiện tại chưa nắm được.
