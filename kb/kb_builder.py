"""
Part B — Knowledge Base Builder
================================
Đọc 8 tài liệu từ data/docs/, chia chunk theo cấu trúc (structure-based),
lưu vào SQLite FTS5 index kèm đầy đủ metadata.

Chạy: python kb/kb_builder.py

Output: kb/output/kb.db
"""

import re
import sqlite3
import json
from pathlib import Path
from datetime import date

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT     = Path(__file__).parent.parent
DOCS_DIR = ROOT.parent / "Xbrain_Assessment_DE_DataPack" / "data" / "docs"
OUTPUT_DIR = ROOT / "kb" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH  = OUTPUT_DIR / "kb.db"

# ---------------------------------------------------------------------------
# Metadata catalog — khai báo thủ công cho 8 tài liệu
# Mỗi tài liệu: doc_id, version, effective_date, owner, superseded_by
# ---------------------------------------------------------------------------
DOC_CATALOG = {
    "FAQ-01_loi_thuong_gap.md": {
        "doc_id": "FAQ-01",
        "title": "Các lỗi thường gặp và cách xử lý",
        "doc_type": "FAQ",
        "version": "1.0",
        "effective_date": "2026-07-01",
        "owner": "Phòng CNTT",
        "superseded_by": None,
        "active": True,
    },
    "GUIDE-01_giam_sat_he_thong.md": {
        "doc_id": "GUIDE-01",
        "title": "Hướng dẫn giám sát hệ thống",
        "doc_type": "GUIDE",
        "version": "1.0",
        "effective_date": "2026-06-01",
        "owner": "Phòng CNTT",
        "superseded_by": None,
        "active": True,
    },
    "POL-01_chinh_sach_backup_v1.md": {
        "doc_id": "POL-01",
        "title": "Chính sách sao lưu dữ liệu",
        "doc_type": "POLICY",
        "version": "1.0",
        "effective_date": "2025-06-01",
        "owner": "Phòng CNTT",
        "superseded_by": "POL-01-v2",   # ← bị thay thế bởi v2
        "active": False,                 # ← KHÔNG còn hiệu lực
    },
    "POL-01_chinh_sach_backup_v2.md": {
        "doc_id": "POL-01",
        "title": "Chính sách sao lưu dữ liệu",
        "doc_type": "POLICY",
        "version": "2.0",
        "effective_date": "2026-05-01",
        "owner": "Phòng CNTT",
        "superseded_by": None,
        "active": True,                  # ← bản hiệu lực
    },
    "POL-02_chinh_sach_truy_cap.md": {
        "doc_id": "POL-02",
        "title": "Chính sách truy cập hệ thống",
        "doc_type": "POLICY",
        "version": "1.1",
        "effective_date": "2026-02-01",
        "owner": "Phòng CNTT",
        "superseded_by": None,
        "active": True,
    },
    "RUN-01_runbook_batch_report.md": {
        "doc_id": "RUN-01",
        "title": "Runbook job báo cáo cuối ngày",
        "doc_type": "RUNBOOK",
        "version": "1.0",
        "effective_date": "2026-05-01",
        "owner": "Phòng CNTT",
        "superseded_by": None,
        "active": True,
    },
    "SOP-01_khoi_dong_lai_dich_vu.md": {
        "doc_id": "SOP-01",
        "title": "Quy trình khởi động lại dịch vụ",
        "doc_type": "SOP",
        "version": "1.0",
        "effective_date": "2026-03-01",
        "owner": "Trưởng phòng Vận hành",
        "superseded_by": None,
        "active": True,
    },
    "SOP-02_quy_trinh_escalation.md": {
        "doc_id": "SOP-02",
        "title": "Quy trình escalation sự cố",
        "doc_type": "SOP",
        "version": "1.0",
        "effective_date": "2026-04-01",
        "owner": "Phòng CNTT",
        "superseded_by": None,
        "active": True,
    },
}

# ---------------------------------------------------------------------------
# Chunking — structure-based: cắt theo heading H2 (##)
# ---------------------------------------------------------------------------

def chunk_document(filepath: Path, meta: dict) -> list[dict]:
    """
    Chia tài liệu thành các chunk theo heading H2 (##).
    Mỗi chunk = 1 section (heading + nội dung bên dưới).
    Chunk đầu tiên = phần header trước H2 đầu tiên (nếu có).

    Trả về list các dict chunk với đầy đủ metadata.
    """
    text = filepath.read_text(encoding="utf-8")
    filename = filepath.name

    chunks = []
    # Tách theo ## heading
    # Pattern: bắt đầu dòng có ##, lấy đến ## tiếp theo hoặc hết file
    sections = re.split(r'\n(?=## )', text)

    # Section 0 thường là title doc + thông tin header — giữ lại như 1 chunk
    for idx, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue

        # Lấy heading làm section title
        first_line = section.split('\n')[0].strip()
        section_title = re.sub(r'^#+\s*', '', first_line)  # bỏ dấu #

        chunk_id = f"{meta['doc_id']}-v{meta['version'].replace('.', '_')}-s{idx}"

        chunks.append({
            "chunk_id":       chunk_id,
            "doc_id":         meta["doc_id"],
            "doc_title":      meta["title"],
            "doc_type":       meta["doc_type"],
            "version":        meta["version"],
            "effective_date": meta["effective_date"],
            "owner":          meta["owner"],
            "active":         1 if meta["active"] else 0,
            "superseded_by":  meta["superseded_by"] or "",
            "filename":       filename,
            "section_index":  idx,
            "section_title":  section_title,
            "content":        section,
        })

    return chunks


# ---------------------------------------------------------------------------
# SQLite FTS5 setup
# ---------------------------------------------------------------------------

def init_db(db_path: Path) -> sqlite3.Connection:
    """Tạo SQLite DB với FTS5 table và metadata table."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Bảng metadata (structured, để filter)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id       TEXT PRIMARY KEY,
            doc_id         TEXT,
            doc_title      TEXT,
            doc_type       TEXT,
            version        TEXT,
            effective_date TEXT,
            owner          TEXT,
            active         INTEGER,   -- 1 = hiệu lực, 0 = đã superseded
            superseded_by  TEXT,
            filename       TEXT,
            section_index  INTEGER,
            section_title  TEXT,
            content        TEXT
        )
    """)

    # FTS5 virtual table — index nội dung để full-text search (standalone, không dùng content=)
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
        USING fts5(
            chunk_id,
            doc_id,
            section_title,
            content
        )
    """)

    conn.commit()
    return conn


def insert_chunks(conn: sqlite3.Connection, chunks: list[dict]) -> None:
    cur = conn.cursor()
    for c in chunks:
        cur.execute("""
            INSERT OR REPLACE INTO chunks
            (chunk_id, doc_id, doc_title, doc_type, version, effective_date,
             owner, active, superseded_by, filename, section_index, section_title, content)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            c["chunk_id"], c["doc_id"], c["doc_title"], c["doc_type"],
            c["version"], c["effective_date"], c["owner"], c["active"],
            c["superseded_by"], c["filename"], c["section_index"],
            c["section_title"], c["content"],
        ))
        # Insert vào FTS table
        cur.execute("""
            INSERT INTO chunks_fts (chunk_id, doc_id, section_title, content)
            VALUES (?, ?, ?, ?)
        """, (c["chunk_id"], c["doc_id"], c["section_title"], c["content"]))
    conn.commit()


# ---------------------------------------------------------------------------
# Search — chỉ trả kết quả từ tài liệu ACTIVE
# ---------------------------------------------------------------------------

def search(conn: sqlite3.Connection, query: str, top_k: int = 3) -> list[dict]:
    """
    Full-text search, CHỈ trả chunk từ tài liệu active=1.
    Đây là cơ chế xử lý mâu thuẫn phiên bản: POL-01 v1 (active=0)
    sẽ không bao giờ xuất hiện trong kết quả tìm kiếm.

    Chiến lược tìm kiếm 2 tầng:
    1. FTS5 phrase match — nhanh, chính xác (hoạt động tốt với từ đơn / ASCII)
    2. Nếu FTS5 trả rỗng → fallback sang LIKE trên bảng chunks (xử lý
       multi-word tiếng Việt mà SQLite unicode tokenizer chưa hỗ trợ tốt)
    Cả hai tầng đều lọc active=1.
    """
    cur = conn.cursor()

    # --- Tầng 1: FTS5 ---
    safe_query = f'"{query}"'
    cur.execute("""
        SELECT c.chunk_id, c.doc_id, c.version, c.section_title,
               c.content, c.effective_date, c.owner, c.active,
               f.rank
        FROM chunks_fts f
        JOIN chunks c ON c.chunk_id = f.chunk_id
        WHERE chunks_fts MATCH ?
          AND c.active = 1
        ORDER BY f.rank
        LIMIT ?
    """, (safe_query, top_k))
    rows = cur.fetchall()

    # --- Tầng 2: Multi-keyword LIKE fallback nếu FTS5 không trả kết quả ---
    if not rows:
        keywords = [kw.strip() for kw in query.split() if len(kw.strip()) > 1]
        if keywords:
            conditions = " AND ".join(
                ["(content LIKE ? OR section_title LIKE ?)"] * len(keywords)
            )
            params = []
            for kw in keywords:
                params.extend([f"%{kw}%", f"%{kw}%"])
            params.append(top_k)
            cur.execute(f"""
                SELECT chunk_id, doc_id, version, section_title,
                       content, effective_date, owner, active,
                       0 AS rank
                FROM chunks
                WHERE {conditions}
                  AND active = 1
                ORDER BY effective_date DESC
                LIMIT ?
            """, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        results.append({
            "chunk_id":       row[0],
            "doc_id":         row[1],
            "version":        row[2],
            "section_title":  row[3],
            "content":        row[4][:300] + "..." if len(row[4]) > 300 else row[4],
            "effective_date": row[5],
            "owner":          row[6],
            "active":         row[7],
        })
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_kb():
    print("=" * 55)
    print("  Xbrain DE POC — KB Builder")
    print(f"  Docs: {DOCS_DIR}")
    print(f"  Output: {DB_PATH}")
    print("=" * 55)

    if not DOCS_DIR.exists():
        print(f"[ERROR] Không tìm thấy thư mục docs: {DOCS_DIR}")
        return

    # Xóa DB cũ để rebuild sạch (idempotent)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = init_db(DB_PATH)

    all_chunks = []
    for filename, meta in DOC_CATALOG.items():
        filepath = DOCS_DIR / filename
        if not filepath.exists():
            print(f"[WARN]  Không tìm thấy: {filename}")
            continue

        chunks = chunk_document(filepath, meta)
        insert_chunks(conn, chunks)
        all_chunks.extend(chunks)

        status = "✓ active" if meta["active"] else "✗ superseded"
        print(f"[OK]    {filename:45s} → {len(chunks):2d} chunks  [{status}]")

    print()
    print(f"  Tổng: {len(all_chunks)} chunks từ {len(DOC_CATALOG)} tài liệu")

    # Thống kê active vs superseded
    active_count     = sum(1 for c in all_chunks if c["active"] == 1)
    superseded_count = sum(1 for c in all_chunks if c["active"] == 0)
    print(f"  Active (searchable): {active_count} chunks")
    print(f"  Superseded (hidden): {superseded_count} chunks")

    conn.close()
    print()
    print(f"  KB saved → {DB_PATH}")
    print("=" * 55)


if __name__ == "__main__":
    build_kb()

    # Chạy thử search để verify
    print()
    print("  Quick search test:")
    print("-" * 55)
    conn = sqlite3.connect(DB_PATH)
    test_queries = ["sao lưu", "khởi động lại", "escalation"]
    for q in test_queries:
        results = search(conn, q, top_k=1)
        if results:
            r = results[0]
            print(f"  Q: '{q}'")
            print(f"     → [{r['doc_id']} v{r['version']}] {r['section_title']}")
        else:
            print(f"  Q: '{q}' → no results")
    conn.close()
