# SOP-KB-01 — Quy trình cập nhật Knowledge Base

**Hệ thống:** Xbrain AI Assistant KB  
**Phiên bản:** 1.0 · Ban hành: 2026-08-11  
**Người duyệt:** Trưởng phòng Vận hành  
**Chu kỳ rà soát:** Hàng tháng và mỗi khi có tài liệu nguồn thay đổi

---

## Phạm vi

Áp dụng khi: (a) khách hàng/nội bộ gửi tài liệu mới, (b) tài liệu cũ được sửa đổi, (c) tài liệu cũ được thu hồi.

---

## Quy trình cập nhật (≤ 4 bước)

### Bước 1 — Tiếp nhận và phân loại (người nhận: DE/Ops)

| Tình huống | Hành động |
|---|---|
| Tài liệu mới (chưa có trong KB) | Thêm entry vào `DOC_CATALOG` trong `kb_builder.py` với `active=True` |
| Bản sửa đổi của tài liệu đã có | Thêm entry mới (`active=True`) + đổi bản cũ thành `active=False`, điền `superseded_by` |
| Tài liệu thu hồi hoàn toàn | Đổi entry hiện tại thành `active=False`, `superseded_by=""` |

**Lưu ý:** KHÔNG xóa entry cũ — giữ lại để tra cứu lịch sử kiểm toán.

Thời gian hoàn thành bước 1: ≤ 30 phút kể từ khi nhận tài liệu.

---

### Bước 2 — Rebuild và kiểm tra nhanh (người thực hiện: DE)

```bash
# 1. Đặt file tài liệu mới vào data/docs/
# 2. Rebuild KB
python kb/kb_builder.py

# 3. Kiểm tra output: số chunks tăng đúng, active/superseded đúng
```

Kiểm tra tối thiểu sau rebuild:
- [ ] Tổng số chunks tăng đúng với số section trong tài liệu mới
- [ ] Tài liệu mới hiển thị `[✓ active]` trong output
- [ ] Tài liệu cũ (nếu superseded) hiển thị `[✗ superseded]`

---

### Bước 3 — Chạy bộ eval để phát hiện regressions (người thực hiện: DE)

```bash
python kb/run_eval.py
```

Tiêu chí tiếp tục:
- **PASS ≥ 8/10** — tiến hành deploy
- **PASS 6–7/10** — xem xét query nào fail, quyết định có cần vá trước khi deploy
- **PASS < 6/10** — DỪNG, báo cáo lên Trưởng nhóm trước khi đưa vào production

Nếu tài liệu mới bổ sung nội dung hoàn toàn mới → **bổ sung ít nhất 1 câu hỏi eval mới** vào `eval_set.md` và chạy lại.

---

### Bước 4 — Xác nhận và ghi nhận (người kiểm tra: QA/Lead)

- [ ] Review diff của `DOC_CATALOG` trong pull request
- [ ] Xác nhận kết quả `run_eval.py` ≥ ngưỡng chấp nhận
- [ ] Merge và deploy `kb.db` mới lên môi trường production
- [ ] Ghi vào changelog KB: ngày, tài liệu thay đổi, lý do, người thực hiện

---

## Tần suất rà soát định kỳ

| Loại rà soát | Chu kỳ | Người chịu trách nhiệm |
|---|---|---|
| Kiểm tra tính hiệu lực của tài liệu trong KB | Hàng tháng | DE on-call |
| Chạy lại full eval set | Hàng tháng hoặc sau mỗi lần update | DE |
| Rà soát DOC_CATALOG với danh sách tài liệu chính thức | Hàng quý | Trưởng phòng Vận hành |

---

## Điểm liên hệ khi có vấn đề

- Tài liệu mới/sửa gửi đến: kênh `#kb-update` hoặc email ops-cntt@saodo.vn
- Vấn đề kỹ thuật KB: DE on-call
- Nội dung chính sách không rõ: chủ sở hữu tài liệu (field `owner` trong DOC_CATALOG)
