# Xbrain Data Engineer Assessment — POC

**Candidate:** Hoang Kim Hung  
**Timeline:** 2 days (08/2026)  
**Simulated client:** Sao Do Financial Company (Công ty Tài chính Sao Đỏ)

---

## Overview

This POC covers two parts:
- **Part A** — Log pipeline: ingest → validate → clean → deduplicate → export Parquet/CSV + 4 business reports + AWS architecture design
- **Part B** — Mini knowledge base for an AI assistant: structure-based chunking, SQLite FTS5 index, version conflict resolution, 10-question eval set, KB update SOP

It also includes the required AI Proficiency deliverables (Assessment Part 2):
- `AI_WORKLOG.md` — honest log of every meaningful AI interaction
- `ai_review.md` — review of a flawed AI answer (Task A)
- `prompt_design.md` — structured extraction prompt + test cases + evaluation method (Task B)

---

## Repo Structure

```
xbrain-de-poc/
├── README.md                    # This file — EN overview, how to run, design decisions
├── AI_WORKLOG.md                # Honest AI usage log (Assessment Part 2 requirement)
├── ai_review.md                 # Part 2 Task A: review of AI answer with 6 errors
├── prompt_design.md             # Part 2 Task B: log extraction prompt + eval design
├── requirements.txt
├── pipeline/                    # Part A — pipeline code + 4 report outputs
│   ├── pipeline.py              # Ingest, validate, clean, transform, export
│   ├── reports.py               # 4 business reports per client requirements
│   └── output/
│       ├── clean_logs.parquet   # Clean dataset (generated)
│       ├── clean_logs.csv       # CSV copy for easy inspection
│       └── data_quality_report.json
├── kb/                          # Part B — KB code + eval + results
│   ├── kb_builder.py            # Chunking, indexing, and search function
│   ├── kb_design.md             # KB design rationale (chunking, metadata, conflict resolution)
│   ├── run_eval.py              # Runs 10 eval queries and prints pass/fail
│   ├── eval_set.md              # 10 eval questions + expected answers + actual results
│   └── output/
│       └── kb.db                # SQLite FTS5 index (generated)
├── design/                      # AWS architecture diagram + explanation
│   ├── aws_design.md
│   └── Xbrain_DE_Apply_HKH.drawio.png
└── sop/                         # KB update SOP
    └── sop_kb_update.md
```

---

## Part A — Log Pipeline

### How to run

```bash
# Step 1: Install dependencies
pip install -r requirements.txt

# Step 2: Run pipeline (ingest + validate + clean + deduplicate + export)
python pipeline/pipeline.py

# Step 3: Generate the 4 business reports
python pipeline/reports.py
```

**Outputs:**
- `pipeline/output/clean_logs.parquet` — clean dataset in Parquet format
- `pipeline/output/clean_logs.csv` — CSV copy for inspection
- `pipeline/output/data_quality_report.json` — per-issue counts and examples

### Data quality issues found and handled

| # | Issue | Example | Handling |
|---|-------|---------|----------|
| 1 | **Invalid timestamp** | `"not-a-date"` | Drop record; log to quality report |
| 2 | **Truncated JSON** | `{"timestamp": "2026-07-27T02:56:2` | Skip line; log as parse error |
| 3 | **Missing `level` field** | Line without `"level"` key | Fill with `"UNKNOWN"`; flag `level_imputed=True` |
| 4 | **Out-of-order timestamp** | Mid-file jump across dates | Keep value; add `is_timestamp_anomaly` column |
| 5 | **Duplicate record** | Same `request_id` + `timestamp` + `message` | Deduplicate; keep first occurrence |

> Raw data is never modified — all transformations happen inside the pipeline.

### 4 Business Reports (Q1–Q4)

| Report | Finding |
|---|---|
| Q1 — Service with most errors | **payment-api** — 139 ERROR events |
| Q2 — Abnormal day | **2026-07-30** — error rate 3.4× daily average |
| Q3 — Top 3 error types | ERR ConnTimeout (db-primary), ERR HTTP 502 (payment-api), ERR NullPointer (ReportBuilder) |
| Q4 — Data quality summary | 18 truncated JSON, 20 invalid timestamps, 28 duplicates, 18 missing level |

---

## Part B — Knowledge Base

### How to run

```bash
# Build the KB (reads 8 docs from DataPack, outputs kb/output/kb.db)
python kb/kb_builder.py

# Run the eval set (10 questions, prints pass/fail)
python kb/run_eval.py
```

**Output:** `kb/output/kb.db` — SQLite FTS5 full-text search index with metadata

### Eval results summary

**9/10 PASS · 1/10 PARTIAL · 0/10 FAIL** (run: 2026-08-11)

- Q01–Q03: Backup policy questions — all return POL-01 v2.0, never v1.0 ✓
- Q09: Out-of-scope question ("salary policy") — correctly returns no results ✓
- Q10: Version trap ("22:00" from superseded doc) — blocked, returns 0 active results ✓
- Q07: PARTIAL — FAQ-01 ranked above RUN-01 for NullPointer query; RUN-01 correct in hit-2

Full results in `kb/eval_set.md`.

---

## Key Design Decisions

### 1. Structure-based chunking (not fixed-size)

Source documents are SOPs, policies, and runbooks with clear `##` heading structure. Users ask focused questions ("what time does backup run?", "how do I restart payment-api?") that map to exactly one section. Splitting at H2 headings preserves full procedure context — a fixed-size split would cut mid-step through a 6-step SOP.

### 2. Metadata-first chunk design

Every chunk carries: `doc_id`, `version`, `effective_date`, `owner`, `active` flag, `superseded_by`. This makes version conflict resolution deterministic and auditable.

### 3. Version conflict resolution: active flag + superseded_by

POL-01 has two versions with direct contradictions (backup at 22:00 in v1 vs 23:30 in v2; 7-day retention in v1 vs 30-day in v2). The mechanism:
- v1 stored with `active=0` — never returned in search results
- v2 stored with `active=1` — the only version the AI sees
- Old versions kept (not deleted) for audit trail
- All search queries enforce `WHERE active = 1`

### 4. SQLite FTS5 + multi-keyword LIKE fallback

Chosen over vector embeddings because: 30 chunks / 8 docs — adding an embedding API, a vector store, and a chunking-to-embedding pipeline adds operational overhead with no benefit at this scale. The reason for the choice matters more than the tool.

Known limitation: SQLite FTS5's default tokenizer does not segment Vietnamese compound words optimally. Fixed with a 2-tier search: FTS5 phrase match first, then multi-keyword AND LIKE fallback. Both tiers enforce `active=1`.

### 5. Idempotent pipeline

Both `pipeline.py` and `kb_builder.py` delete previous output before rebuilding — running them multiple times produces identical results.

---

## What Was Not Done / Known Gaps

- AWS diagram is provided as `.drawio.png` — a live Terraform/CDK template was not in scope for a 2-day POC
- KB uses keyword search (SQLite FTS5), not semantic search (embeddings) — sufficient for 8-document POC; embedding layer is the natural next step
- No automated unit tests — test coverage is manual via `run_eval.py` eval set
- Vietnamese tokenization in FTS5 is imperfect — documented in `kb/kb_design.md` with mitigation
- Part 2 Task B prompt was not run against a live LLM (no API key available) — expected outputs were reasoned manually based on prompt structure
