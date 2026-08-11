"""
run_eval.py — chạy 10 eval queries lên KB, in kết quả để ghi vào eval_set.md
Dùng cùng search logic 2 tầng như kb_builder.py:
  1. FTS5 phrase match
  2. LIKE fallback (xử lý multi-word tiếng Việt)
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "output" / "kb.db"


def search_active(conn, query, top_k=3):
    """
    FTS5 + multi-keyword LIKE fallback, chỉ trả active chunks.

    Tầng 1: FTS5 phrase match — nhanh, cho ASCII/từ đơn.
    Tầng 2: Multi-keyword AND LIKE — tách query thành các keyword,
            yêu cầu content chứa TẤT CẢ keyword (thứ tự bất kỳ).
            Xử lý được multi-word tiếng Việt mà FTS5 tokenizer bỏ sót.
    """
    cur = conn.cursor()

    # Tầng 1: FTS5
    safe_q = f'"{query}"'
    cur.execute("""
        SELECT c.chunk_id, c.doc_id, c.version, c.section_title,
               c.content, c.active
        FROM chunks_fts f
        JOIN chunks c ON c.chunk_id = f.chunk_id
        WHERE chunks_fts MATCH ?
          AND c.active = 1
        ORDER BY f.rank
        LIMIT ?
    """, (safe_q, top_k))
    rows = cur.fetchall()

    # Tầng 2: Multi-keyword LIKE fallback
    if not rows:
        keywords = [kw.strip() for kw in query.split() if len(kw.strip()) > 1]
        if keywords:
            # Build: content LIKE %kw1% AND content LIKE %kw2% ...
            conditions = " AND ".join(
                ["(content LIKE ? OR section_title LIKE ?)"] * len(keywords)
            )
            params = []
            for kw in keywords:
                params.extend([f"%{kw}%", f"%{kw}%"])
            params.append(top_k)
            cur.execute(f"""
                SELECT chunk_id, doc_id, version, section_title,
                       content, active
                FROM chunks
                WHERE {conditions}
                  AND active = 1
                ORDER BY effective_date DESC
                LIMIT ?
            """, params)
            rows = cur.fetchall()

    return rows


def search_all_versions(conn, query, top_k=5):
    """Tìm tất cả kể cả superseded — dùng để kiểm tra version trap."""
    cur = conn.cursor()
    like_p = f"%{query}%"
    cur.execute("""
        SELECT chunk_id, doc_id, version, section_title, content, active
        FROM chunks
        WHERE content LIKE ? OR section_title LIKE ?
        ORDER BY active DESC, effective_date DESC
        LIMIT ?
    """, (like_p, like_p, top_k))
    return cur.fetchall()


def fmt(text, n=200):
    return text[:n].replace("\n", " ") + ("..." if len(text) > n else "")


EVAL_QUERIES = [
    # (id, query, expected_doc, expected_section_hint, is_out_of_scope, is_version_trap)
    ("Q01", "sao lưu 23:30",            "POL-01 v2.0", "Quy định",            False, False),
    ("Q02", "lưu giữ 30 ngày",          "POL-01 v2.0", "Quy định",            False, False),
    ("Q03", "khôi phục phê duyệt",      "POL-01 v2.0", "Quy định",            False, False),
    ("Q04", "payment-api restart queue","SOP-01 v1.0", "Quy trình chuẩn",     False, False),
    ("Q05", "ERR ConnTimeout",          "FAQ-01 v1.0", "ERR ConnTimeout",      False, False),
    ("Q06", "P1 thời hạn phản ứng",     "SOP-02 v1.0", "Phân mức sự cố",      False, False),
    ("Q07", "NullPointer ReportBuilder","RUN-01 v1.0", "Khi job lỗi",         False, False),
    ("Q08", "mật khẩu 90 ngày",         "POL-02 v1.1", "Quy định chung",      False, False),
    ("Q09", "lương thưởng phúc lợi",    "NONE",        "out-of-scope",         True,  False),
    ("Q10", "22:00",                    "BLOCKED",     "version trap",         False, True),
]


def main():
    if not DB_PATH.exists():
        print(f"[ERROR] KB not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    print("=" * 72)
    print("  EVAL RUN — Xbrain KB  (10 queries)")
    print("=" * 72)

    pass_count = 0
    results_log = []

    for qid, query, expected_doc, expected_section, is_oos, is_vt in EVAL_QUERIES:
        print(f"\n[{qid}] query: {repr(query)}")
        print(f"       expected: {expected_doc} | {expected_section}")

        hits = search_active(conn, query)

        if is_oos:
            # Đúng khi KHÔNG tìm thấy gì
            if not hits:
                verdict = "PASS"
                print("  → NO RESULTS  ✓ (correct: out-of-scope)")
            else:
                verdict = "FAIL"
                print(f"  → UNEXPECTED HIT: [{hits[0][1]} v{hits[0][2]}] {hits[0][3][:50]}")
        elif is_vt:
            # Version trap: "22:00" chỉ có trong v1 (inactive) → phải trả rỗng
            blocked = search_all_versions(conn, query)
            inactive_hits = [r for r in blocked if r[5] == 0]
            if not hits and inactive_hits:
                verdict = "PASS"
                print(f"  → NO RESULTS (active=1)  ✓ version trap blocked correctly")
                for r in inactive_hits:
                    print(f"     blocked: [{r[1]} v{r[2]}] active=0  ← BLOCKED ✓")
            elif hits:
                verdict = "FAIL"
                print(f"  → UNEXPECTED: returned active result for superseded content")
            else:
                verdict = "PARTIAL"
                print("  → NO RESULTS but no inactive doc found either (check data)")
        else:
            if hits:
                top = hits[0]
                hit_doc = f"{top[1]} v{top[2]}"
                verdict = "PASS" if expected_doc in hit_doc or hit_doc in expected_doc else "PARTIAL"
                mark = "✓" if verdict == "PASS" else "~"
                print(f"  hit1: [{top[1]} v{top[2]}] section='{top[3][:55]}' {mark}")
                print(f"  snippet: {fmt(top[4])}")
                if len(hits) > 1:
                    print(f"  hit2: [{hits[1][1]} v{hits[1][2]}] section='{hits[1][3][:55]}'")
            else:
                verdict = "FAIL"
                print("  → NO RESULTS  ✗")

        print(f"  verdict: {verdict}")
        results_log.append((qid, query, expected_doc, verdict))
        if verdict == "PASS":
            pass_count += 1

    print("\n" + "=" * 72)
    print(f"  RESULT: {pass_count}/{len(EVAL_QUERIES)} PASS")
    partial = sum(1 for r in results_log if r[3] == "PARTIAL")
    fail    = sum(1 for r in results_log if r[3] == "FAIL")
    print(f"  PASS={pass_count}  PARTIAL={partial}  FAIL={fail}")
    print("=" * 72)

    conn.close()


if __name__ == "__main__":
    main()
