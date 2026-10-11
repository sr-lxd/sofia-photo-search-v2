# 3-File Handoff Path (Shortest)

Goal: read only 3 files and start development quickly.

## 1) API behavior entry: `service/api/v1/endpoints/search.py`
- Why first: this file defines the product-facing search behavior.
- Focus on:
  - `/search/multi` (multi-element main flow)
  - `/search/gps` and `/search/gps_multi` (GPS + element merge)
  - `/search/person` (face-id based recall)
- After this file, you understand request params, scoring merge, and result shape.

## 2) Data ingest and indexing entry: `service/scan/scanner.py`
- Why second: this file defines how raw photos become searchable data.
- Focus on:
  - `process_photo(...)` (EXIF/GPS extraction, face+vision embedding, DB upsert)
  - `scan_roots(...)` (incremental/full/resume flow, delete sync, failed-cache)
- After this file, you understand scan lifecycle and data freshness rules.

## 3) Persistence and query layer: `service/db/mysql.py`
- Why third: this file is the SQL truth for write/read behavior.
- Focus on:
  - `upsert_photo`, `insert_faces`, `reserve_embedding_ids*`
  - `fetch_photos_by_embedding_ids`, `fetch_photos_by_text_query`, `fetch_photos_by_gps_radius`
  - `scan_progress`, `scan_seen`, `scan_failed` helpers
- After this file, you can safely change queries, schema evolution, and scan consistency.

## 15-minute takeover checklist
- Run one API call from `search.py` path and confirm response fields.
- Trigger one incremental scan and watch progress/status.
- Trace one result end-to-end: API -> SQL function -> table fields.
