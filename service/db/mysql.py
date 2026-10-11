from service.core.date_utils import end_exclusive, date_bounds
from contextlib import contextmanager
import logging
import math
import re
from pathlib import Path
import threading
import pymysql
from pymysql.cursors import DictCursor
from service.core.config import settings

log = logging.getLogger(__name__)
_thread_local = threading.local()
_schema_lock = threading.Lock()
_gps_schema_checked = False


def _new_conn():
    return pymysql.connect(
        host=settings.db.host,
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.database,
        port=settings.db.port,
        charset=settings.db.charset,
        cursorclass=DictCursor,
        autocommit=True,
    )


def get_conn():
    conn = getattr(_thread_local, "conn", None)
    if conn is None:
        conn = _new_conn()
        _thread_local.conn = conn
        return conn
    try:
        conn.ping(reconnect=True)
    except Exception:
        conn = _new_conn()
        _thread_local.conn = conn
    return conn


@contextmanager
def conn_ctx():
    conn = get_conn()
    try:
        yield conn
    finally:
        # keep per-thread connection open to avoid port exhaustion
        pass


def fetch_one(sql: str, params=None):
    with conn_ctx() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()


def fetch_all(sql: str, params=None):
    with conn_ctx() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()


def execute(sql: str, params=None):
    with conn_ctx() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.rowcount


def _column_exists(table_name: str, column_name: str) -> bool:
    row = fetch_one(
        """
        SELECT COUNT(1) AS cnt
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return bool(row and int(row.get("cnt", 0)) > 0)


def _index_exists(table_name: str, index_name: str) -> bool:
    row = fetch_one(
        """
        SELECT COUNT(1) AS cnt
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND index_name = %s
        """,
        (table_name, index_name),
    )
    return bool(row and int(row.get("cnt", 0)) > 0)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if _index_exists(table_name, index_name):
        execute(f"ALTER TABLE {table_name} DROP INDEX {index_name}")


def _column_is_auto_increment(table_name: str, column_name: str) -> bool:
    row = fetch_one(
        """
        SELECT EXTRA AS extra_info
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    extra = ""
    if isinstance(row, dict):
        extra = str(row.get("extra_info") or row.get("EXTRA") or "")
    return "auto_increment" in extra.lower()


def _table_exists(table_name: str) -> bool:
    row = fetch_one(
        """
        SELECT COUNT(1) AS cnt
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
          AND table_name = %s
        """,
        (table_name,),
    )
    return bool(row and int(row.get("cnt", 0)) > 0)


def ensure_photo_gps_columns() -> None:
    global _gps_schema_checked
    if _gps_schema_checked:
        return
    with _schema_lock:
        if _gps_schema_checked:
            return
        if not _column_exists("photos", "gps_lat"):
            execute("ALTER TABLE photos ADD COLUMN gps_lat DECIMAL(10,7) NULL")
        if not _column_exists("photos", "gps_lon"):
            execute("ALTER TABLE photos ADD COLUMN gps_lon DECIMAL(10,7) NULL")
        if not _column_exists("photos", "gps_checked"):
            execute("ALTER TABLE photos ADD COLUMN gps_checked TINYINT(1) NOT NULL DEFAULT 0")
        if not _index_exists("photos", "idx_gps_lat_lon"):
            execute("ALTER TABLE photos ADD INDEX idx_gps_lat_lon (gps_lat, gps_lon)")
        execute(
            """
            UPDATE photos
            SET gps_checked=1
            WHERE gps_checked=0
              AND gps_lat IS NOT NULL
              AND gps_lon IS NOT NULL
            """
        )
        _gps_schema_checked = True


def _get_column_collation(table_name: str, column_name: str) -> str | None:
    row = fetch_one(
        """
        SELECT collation_name
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    if not row:
        return None
    if isinstance(row, dict):
        return row.get("collation_name") or row.get("COLLATION_NAME") or next(iter(row.values()), None)
    return None


def _ensure_scan_seen_collation() -> None:
    photos_collation = _get_column_collation("photos", "file_path")
    scan_seen_collation = _get_column_collation("scan_seen", "file_path")
    if not photos_collation or not scan_seen_collation:
        return
    if photos_collation == scan_seen_collation:
        return
    if not re.fullmatch(r"[A-Za-z0-9_]+", photos_collation):
        log.warning("skip scan_seen collation align, invalid target collation: %s", photos_collation)
        return
    execute(f"ALTER TABLE scan_seen CONVERT TO CHARACTER SET utf8mb4 COLLATE {photos_collation}")
    execute(
        f"""
        ALTER TABLE scan_seen
        MODIFY file_path VARCHAR(768)
        CHARACTER SET utf8mb4 COLLATE {photos_collation}
        NOT NULL
        """
    )
    log.info("aligned scan_seen.file_path collation to %s", photos_collation)


def ensure_scan_seen_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS scan_seen (
      file_path VARCHAR(768) PRIMARY KEY
    );
    """
    execute(sql)
    _ensure_scan_seen_collation()


def clear_scan_seen() -> None:
    execute("TRUNCATE TABLE scan_seen")


def count_scan_seen() -> int:
    row = fetch_one("SELECT COUNT(1) AS cnt FROM scan_seen")
    return int(row["cnt"]) if row else 0


def add_scan_seen_paths(paths: list[str]) -> int:
    if not paths:
        return 0
    sql = "INSERT IGNORE INTO scan_seen (file_path) VALUES (%s)"
    values = [(p,) for p in paths]
    with conn_ctx() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, values)
            return cur.rowcount


def ensure_scan_failed_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS scan_failed (
      file_path VARCHAR(768) PRIMARY KEY,
      file_size BIGINT NOT NULL,
      file_mtime DATETIME NOT NULL,
      error_type VARCHAR(64) NULL,
      error_message VARCHAR(255) NULL,
      failed_count INT NOT NULL DEFAULT 1,
      first_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      last_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_last_failed_at (last_failed_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    execute(sql)


def load_scan_failed_signatures() -> dict[str, tuple[int, str]]:
    ensure_scan_failed_table()
    rows = fetch_all("SELECT file_path, file_size, file_mtime FROM scan_failed") or ()
    result: dict[str, tuple[int, str]] = {}
    for row in rows:
        if not row:
            continue
        file_path = str(row.get("file_path") or "")
        if not file_path:
            continue
        file_size = int(row.get("file_size") or 0)
        file_mtime = str(row.get("file_mtime") or "")
        result[file_path] = (file_size, file_mtime)
    return result


def upsert_scan_failed_path(
    file_path: str,
    file_size: int,
    file_mtime: str,
    error_type: str | None = None,
    error_message: str | None = None,
) -> int:
    ensure_scan_failed_table()
    sql = """
    INSERT INTO scan_failed (file_path, file_size, file_mtime, error_type, error_message, failed_count)
    VALUES (%s, %s, %s, %s, %s, 1)
    ON DUPLICATE KEY UPDATE
      file_size=VALUES(file_size),
      file_mtime=VALUES(file_mtime),
      error_type=VALUES(error_type),
      error_message=VALUES(error_message),
      failed_count=failed_count+1,
      last_failed_at=CURRENT_TIMESTAMP
    """
    return execute(sql, (file_path, int(file_size), file_mtime, error_type, error_message))


def clear_scan_failed_path(file_path: str) -> int:
    ensure_scan_failed_table()
    return execute("DELETE FROM scan_failed WHERE file_path=%s", (file_path,))


def mark_missing_photos_deleted() -> int:
    ensure_scan_seen_table()
    sql = """
    UPDATE photos p
    LEFT JOIN scan_seen s ON p.file_path = s.file_path
    SET p.status='deleted'
    WHERE p.status='active' AND s.file_path IS NULL
    """
    return execute(sql)


def cleanup_deleted_records() -> None:
    execute("DELETE f FROM faces f JOIN photos p ON p.id=f.photo_id WHERE p.status='deleted'")
    execute("DELETE e FROM photo_embeddings e JOIN photos p ON p.id=e.photo_id WHERE p.status='deleted'")
    execute("DELETE ff FROM favorite_faces ff LEFT JOIN faces f ON ff.face_id=f.id WHERE f.id IS NULL")


def get_photo_by_path(file_path: str):
    return fetch_one("SELECT * FROM photos WHERE file_path=%s LIMIT 1", (file_path,))


def get_photo_by_id(photo_id: int):
    return fetch_one("SELECT * FROM photos WHERE id=%s LIMIT 1", (int(photo_id),))


def _normalize_root_prefixes(roots: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in roots or []:
        text = str(raw or "").replace("\\", "/").rstrip("/")
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _append_path_roots_where(sql: str, params: list, roots: list[str] | None, *, column_expr: str) -> str:
    normalized = _normalize_root_prefixes(roots)
    if roots is None:
        return sql
    if not normalized:
        sql += " AND 1=0"
        return sql
    clauses = []
    for root in normalized:
        clauses.append(f"({column_expr} = %s OR {column_expr} LIKE %s)")
        params.extend([root, root + "/%"])
    sql += " AND (" + " OR ".join(clauses) + ")"
    return sql


def fetch_photos_by_ids(photo_ids: list[int]) -> list[dict]:
    cleaned = [int(pid) for pid in (photo_ids or []) if int(pid) > 0]
    if not cleaned:
        return []
    placeholders = ",".join(["%s"] * len(cleaned))
    return list(fetch_all(f"SELECT * FROM photos WHERE id IN ({placeholders})", tuple(cleaned)) or ())


def fetch_active_photo_ids_by_roots(
    roots: list[str] | None,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[int]:
    sql = """
    SELECT id AS photo_id
    FROM photos
    WHERE status='active'
    """
    params: list = []
    sql = _append_path_roots_where(sql, params, roots, column_expr="REPLACE(file_path, '\\\\', '/')")
    if date_from:
        sql += " AND COALESCE(exif_datetime, file_mtime) >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND COALESCE(exif_datetime, file_mtime) < %s"
        params.append(end_exclusive(date_to))
    rows = fetch_all(sql, params) or ()
    result: list[int] = []
    for row in rows:
        try:
            photo_id = int(row["photo_id"])
        except Exception:
            continue
        if photo_id > 0:
            result.append(photo_id)
    return result


def fetch_face_embedding_ids_by_photo_ids(photo_ids: list[int], chunk_size: int = 1000) -> list[int]:
    ids = [int(pid) for pid in (photo_ids or []) if int(pid) > 0]
    if not ids:
        return []
    ids = list(dict.fromkeys(ids))
    result: list[int] = []
    seen: set[int] = set()
    step = max(1, int(chunk_size))
    for start in range(0, len(ids), step):
        batch = ids[start:start + step]
        placeholders = ",".join(["%s"] * len(batch))
        rows = fetch_all(
            f"""
            SELECT embedding_id
            FROM faces
            WHERE photo_id IN ({placeholders})
            ORDER BY embedding_id ASC
            """,
            batch,
        ) or ()
        for row in rows:
            try:
                embedding_id = int(row["embedding_id"])
            except Exception:
                continue
            if embedding_id < 0 or embedding_id in seen:
                continue
            seen.add(embedding_id)
            result.append(embedding_id)
    return result


def fetch_photo_embedding_ids_by_photo_ids(photo_ids: list[int], chunk_size: int = 1000) -> list[int]:
    ids = [int(pid) for pid in (photo_ids or []) if int(pid) > 0]
    if not ids:
        return []
    ids = list(dict.fromkeys(ids))
    ensure_photo_embeddings_table()
    result: list[int] = []
    seen: set[int] = set()
    step = max(1, int(chunk_size))
    for start in range(0, len(ids), step):
        batch = ids[start:start + step]
        placeholders = ",".join(["%s"] * len(batch))
        rows = fetch_all(
            f"""
            SELECT embedding_id
            FROM photo_embeddings
            WHERE photo_id IN ({placeholders})
            ORDER BY embedding_id ASC
            """,
            batch,
        ) or ()
        for row in rows:
            try:
                embedding_id = int(row["embedding_id"])
            except Exception:
                continue
            if embedding_id < 0 or embedding_id in seen:
                continue
            seen.add(embedding_id)
            result.append(embedding_id)
    return result


def ensure_standard_photo_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS standard_photo (
      id BIGINT PRIMARY KEY AUTO_INCREMENT,
      policy_id VARCHAR(64) NOT NULL DEFAULT 'admin',
      photo_id BIGINT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      INDEX idx_standard_photo_photo_id (photo_id),
      CONSTRAINT fk_standard_photo_photos FOREIGN KEY (photo_id) REFERENCES photos(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    execute(sql)
    if not _column_is_auto_increment("standard_photo", "id"):
        execute("ALTER TABLE standard_photo MODIFY COLUMN id BIGINT NOT NULL AUTO_INCREMENT")
    if not _column_exists("standard_photo", "policy_id"):
        execute("ALTER TABLE standard_photo ADD COLUMN policy_id VARCHAR(64) NOT NULL DEFAULT 'admin'")
    execute("UPDATE standard_photo SET policy_id='admin' WHERE policy_id IS NULL OR policy_id=''")
    if not _index_exists("standard_photo", "idx_standard_photo_photo_id"):
        execute("ALTER TABLE standard_photo ADD INDEX idx_standard_photo_photo_id (photo_id)")
    _drop_index_if_exists("standard_photo", "uk_standard_photo_photo_id")
    if not _index_exists("standard_photo", "uk_standard_photo_policy_photo_id"):
        execute("ALTER TABLE standard_photo ADD UNIQUE INDEX uk_standard_photo_policy_photo_id (policy_id, photo_id)")
    if not _index_exists("standard_photo", "idx_standard_photo_policy_id"):
        execute("ALTER TABLE standard_photo ADD INDEX idx_standard_photo_policy_id (policy_id)")


def ensure_favorites_tables() -> None:
    execute(
        """
        CREATE TABLE IF NOT EXISTS favorites (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          policy_id VARCHAR(64) NOT NULL DEFAULT 'admin',
          name VARCHAR(128) NOT NULL,
          cover_face_id BIGINT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    )
    if not _column_exists("favorites", "policy_id"):
        execute("ALTER TABLE favorites ADD COLUMN policy_id VARCHAR(64) NOT NULL DEFAULT 'admin'")
    execute("UPDATE favorites SET policy_id='admin' WHERE policy_id IS NULL OR policy_id=''")
    if not _index_exists("favorites", "idx_favorites_policy_id"):
        execute("ALTER TABLE favorites ADD INDEX idx_favorites_policy_id (policy_id)")
    execute(
        """
        CREATE TABLE IF NOT EXISTS favorite_faces (
          favorite_id BIGINT NOT NULL,
          face_id BIGINT NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (favorite_id, face_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    )


def list_standard_photos(policy_id: str):
    ensure_standard_photo_table()
    execute(
        """
        DELETE sp FROM standard_photo sp
        LEFT JOIN photos p ON p.id = sp.photo_id
        WHERE p.id IS NULL OR p.status <> 'active'
        """
    )
    sql = """
    SELECT
      sp.photo_id,
      p.file_path,
      COALESCE(p.exif_datetime, p.file_mtime) AS exif_datetime
    FROM standard_photo sp
    JOIN photos p ON p.id = sp.photo_id
    WHERE p.status='active' AND sp.policy_id=%s
    ORDER BY sp.id DESC
    """
    return list(fetch_all(sql, (str(policy_id or "admin"),)) or ())


def add_standard_photo(policy_id: str, photo_id: int) -> None:
    ensure_standard_photo_table()
    execute(
        "INSERT IGNORE INTO standard_photo (policy_id, photo_id) VALUES (%s, %s)",
        (str(policy_id or "admin"), int(photo_id)),
    )


def clear_standard_photos(policy_id: str) -> None:
    ensure_standard_photo_table()
    execute("DELETE FROM standard_photo WHERE policy_id=%s", (str(policy_id or "admin"),))


def remove_standard_photos(policy_id: str, photo_ids: list[int]) -> int:
    ensure_standard_photo_table()
    cleaned = [int(pid) for pid in photo_ids if int(pid) > 0]
    if not cleaned:
        return 0
    placeholders = ",".join(["%s"] * len(cleaned))
    params = [str(policy_id or "admin")]
    params.extend(cleaned)
    return execute(
        f"DELETE FROM standard_photo WHERE policy_id=%s AND photo_id IN ({placeholders})",
        tuple(params),
    )


def create_favorite(policy_id: str, name: str):
    ensure_favorites_tables()
    execute(
        "INSERT INTO favorites (policy_id, name) VALUES (%s, %s)",
        (str(policy_id or "admin"), str(name or "").strip()),
    )
    return fetch_one(
        "SELECT * FROM favorites WHERE policy_id=%s AND name=%s ORDER BY id DESC LIMIT 1",
        (str(policy_id or "admin"), str(name or "").strip()),
    )


def list_favorites_by_policy(policy_id: str):
    ensure_favorites_tables()
    return fetch_all(
        "SELECT * FROM favorites WHERE policy_id=%s ORDER BY id DESC",
        (str(policy_id or "admin"),),
    ) or []


def get_favorite_by_policy(favorite_id: int, policy_id: str):
    ensure_favorites_tables()
    return fetch_one(
        "SELECT * FROM favorites WHERE id=%s AND policy_id=%s LIMIT 1",
        (int(favorite_id), str(policy_id or "admin")),
    )


def add_face_to_favorite(favorite_id: int, face_id: int) -> int:
    ensure_favorites_tables()
    sql = "INSERT IGNORE INTO favorite_faces (favorite_id, face_id) VALUES (%s,%s)"
    return execute(sql, (int(favorite_id), int(face_id)))


def get_favorite_embedding_row(favorite_id: int, policy_id: str):
    ensure_favorites_tables()
    return fetch_one(
        """
        SELECT f.embedding_id, fav.id AS favorite_id
        FROM favorites fav
        JOIN favorite_faces ff ON ff.favorite_id = fav.id
        JOIN faces f ON ff.face_id = f.id
        JOIN photos p ON p.id = f.photo_id
        WHERE fav.id=%s
          AND fav.policy_id=%s
          AND p.status='active'
        LIMIT 1
        """,
        (int(favorite_id), str(policy_id or "admin")),
    )


def upsert_photo(meta: dict) -> int:
    ensure_photo_gps_columns()
    sql = """
    INSERT INTO photos (file_path, file_name, parent_dir_name, file_hash, file_size, exif_datetime, file_mtime, width, height, gps_lat, gps_lon, gps_checked, face_count, status)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')
    ON DUPLICATE KEY UPDATE
        id=LAST_INSERT_ID(id),
        file_name=VALUES(file_name),
        parent_dir_name=VALUES(parent_dir_name),
        file_hash=VALUES(file_hash),
        file_size=VALUES(file_size),
        exif_datetime=VALUES(exif_datetime),
        file_mtime=VALUES(file_mtime),
        width=VALUES(width),
        height=VALUES(height),
        gps_lat=VALUES(gps_lat),
        gps_lon=VALUES(gps_lon),
        gps_checked=VALUES(gps_checked),
        face_count=VALUES(face_count),
        status='active'
    """
    params = (
        meta["file_path"],
        meta.get("file_name"),
        meta.get("parent_dir_name"),
        meta["file_hash"],
        meta["file_size"],
        meta.get("exif_datetime"),
        meta["file_mtime"],
        meta.get("width"),
        meta.get("height"),
        meta.get("gps_lat"),
        meta.get("gps_lon"),
        meta.get("gps_checked", 0),
        meta.get("face_count", 0),
    )
    with conn_ctx() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid


def get_photo_gps_info(photo_id: int):
    ensure_photo_gps_columns()
    return fetch_one(
        """
        SELECT id AS photo_id, file_path, gps_lat, gps_lon, COALESCE(exif_datetime, file_mtime) AS exif_datetime
        FROM photos
        WHERE id=%s AND status='active'
        LIMIT 1
        """,
        (photo_id,),
    )


def delete_faces_by_photo(photo_id: int) -> None:
    execute("DELETE FROM faces WHERE photo_id=%s", (photo_id,))


def mark_photos_deleted_and_cleanup(photo_ids: list[int]) -> int:
    cleaned = [int(pid) for pid in photo_ids if int(pid) > 0]
    if not cleaned:
        return 0
    cleaned = list(dict.fromkeys(cleaned))
    placeholders = ",".join(["%s"] * len(cleaned))
    params = tuple(cleaned)
    with conn_ctx() as conn:
        try:
            conn.begin()
            with conn.cursor() as cur:
                if _table_exists("standard_photo"):
                    cur.execute(f"DELETE FROM standard_photo WHERE photo_id IN ({placeholders})", params)
                if _table_exists("favorite_faces") and _table_exists("faces"):
                    cur.execute(
                        f"""
                        DELETE ff FROM favorite_faces ff
                        JOIN faces f ON ff.face_id = f.id
                        WHERE f.photo_id IN ({placeholders})
                        """,
                        params,
                    )
                if _table_exists("faces"):
                    cur.execute(f"DELETE FROM faces WHERE photo_id IN ({placeholders})", params)
                if _table_exists("photo_embeddings"):
                    cur.execute(f"DELETE FROM photo_embeddings WHERE photo_id IN ({placeholders})", params)
                affected = cur.execute(
                    f"UPDATE photos SET status='deleted' WHERE id IN ({placeholders}) AND status='active'",
                    params,
                )
            conn.commit()
            return int(affected or 0)
        except Exception:
            conn.rollback()
            raise


def rename_photo_file_record(photo_id: int, old_path: str, new_path: str, file_name: str, parent_dir_name: str, file_mtime: str | None) -> int:
    pid = int(photo_id)
    has_scan_failed = _table_exists("scan_failed")
    with conn_ctx() as conn:
        try:
            conn.begin()
            with conn.cursor() as cur:
                affected = cur.execute(
                    """
                    UPDATE photos
                    SET file_path=%s, file_name=%s, parent_dir_name=%s, file_mtime=%s
                    WHERE id=%s AND status='active'
                    """,
                    (new_path, file_name, parent_dir_name, file_mtime, pid),
                )
                if has_scan_failed and old_path and new_path and old_path != new_path:
                    cur.execute(
                        "UPDATE scan_failed SET file_path=%s WHERE file_path=%s",
                        (new_path, old_path),
                    )
            conn.commit()
            return int(affected or 0)
        except Exception:
            conn.rollback()
            raise


def insert_faces(photo_id: int, faces: list) -> int:
    if not faces:
        return 0
    sql = """
    INSERT INTO faces (photo_id, face_index, bbox_x1, bbox_y1, bbox_x2, bbox_y2, embedding_id, model_name, quality_score)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    values = []
    for face in faces:
        values.append(
            (
                photo_id,
                face["face_index"],
                face["bbox"][0],
                face["bbox"][1],
                face["bbox"][2],
                face["bbox"][3],
                face["embedding_id"],
                face["model_name"],
                face.get("quality_score"),
            )
        )
    with conn_ctx() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, values)
            return cur.rowcount


def fetch_photos_by_embedding_ids(
    ids: list,
    date_from: str | None = None,
    date_to: str | None = None,
    photo_ids: list | None = None,
):
    if not ids:
        return []
    if photo_ids is not None and len(photo_ids) == 0:
        return []
    placeholders = ",".join(["%s"] * len(ids))
    sql = f"""
    SELECT f.id AS face_id, f.embedding_id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2,
           p.id AS photo_id, p.file_path, COALESCE(p.exif_datetime, p.file_mtime) AS exif_datetime,
           p.gps_lat, p.gps_lon
    FROM faces f
    JOIN photos p ON p.id = f.photo_id
    WHERE f.embedding_id IN ({placeholders}) AND p.status='active'
    """
    params = list(ids)
    if date_from:
        sql += " AND COALESCE(p.exif_datetime, p.file_mtime) >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND COALESCE(p.exif_datetime, p.file_mtime) < %s"
        params.append(end_exclusive(date_to))
    if photo_ids is not None:
        photo_placeholders = ",".join(["%s"] * len(photo_ids))
        sql += f" AND p.id IN ({photo_placeholders})"
        params.extend([int(pid) for pid in photo_ids])
    rows = list(fetch_all(sql, params) or ())
    order = {eid: i for i, eid in enumerate(ids)}
    rows.sort(key=lambda r: order.get(r["embedding_id"], 10**9))
    return rows


def fetch_photos_by_text_query(
    query: str,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    photo_ids: list | None = None,
    roots: list[str] | None = None,
    scope: str = "parent",
    query_mode: str = "and",
):
    query = (query or "").strip()
    if not query:
        return []
    if photo_ids is not None and len(photo_ids) == 0:
        return []
    scope = (scope or "parent").lower()
    if scope not in ("parent", "any"):
        scope = "parent"
    query_mode = (query_mode or "and").lower()
    if query_mode not in ("and", "or"):
        query_mode = "and"
    keywords = [w for w in re.split(r"[\s,，;；、|]+", query) if w]
    if not keywords:
        return []
    sql = """
    SELECT id AS photo_id, file_path, COALESCE(exif_datetime, file_mtime) AS exif_datetime, gps_lat, gps_lon
    FROM photos
    WHERE status='active'
    """
    params = []
    sql = _append_path_roots_where(sql, params, roots, column_expr="REPLACE(file_path, '\\\\', '/')")
    keyword_clauses = []
    if scope == "any":
        for kw in keywords:
            keyword_clauses.append("(file_name LIKE %s OR parent_dir_name LIKE %s OR REPLACE(file_path, '\\\\', '/') LIKE %s)")
            # Match keyword anywhere in normalized full path to cover arbitrary ancestor folders.
            params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
    else:
        for kw in keywords:
            keyword_clauses.append("(file_name LIKE %s OR parent_dir_name LIKE %s)")
            params.extend([f"%{kw}%", f"%{kw}%"])
    joiner = " AND " if query_mode == "and" else " OR "
    sql += f" AND ({joiner.join(keyword_clauses)})"
    if photo_ids is not None:
        placeholders = ",".join(["%s"] * len(photo_ids))
        sql += f" AND id IN ({placeholders})"
        params.extend(photo_ids)
    if date_from:
        sql += " AND COALESCE(exif_datetime, file_mtime) >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND COALESCE(exif_datetime, file_mtime) < %s"
        params.append(end_exclusive(date_to))
    sql += " ORDER BY COALESCE(exif_datetime, file_mtime) DESC"
    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))
    return list(fetch_all(sql, params) or ())


def fetch_photos_by_gps_radius(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    date_from: str | None = None,
    date_to: str | None = None,
    photo_ids: list | None = None,
    roots: list[str] | None = None,
    limit: int | None = None,
):
    ensure_photo_gps_columns()
    radius_km = max(0.1, float(radius_km))
    center_lat = float(center_lat)
    center_lon = float(center_lon)
    lat_delta = radius_km / 111.0
    lon_scale = max(0.01, abs(math.cos(math.radians(center_lat))))
    lon_delta = radius_km / (111.0 * lon_scale)
    min_lat = center_lat - lat_delta
    max_lat = center_lat + lat_delta
    min_lon = center_lon - lon_delta
    max_lon = center_lon + lon_delta

    sql = """
    SELECT
      id AS photo_id,
      file_path,
      COALESCE(exif_datetime, file_mtime) AS exif_datetime,
      gps_lat,
      gps_lon,
      (
        6371.0 * 2 * ASIN(
          SQRT(
            POW(SIN(RADIANS(gps_lat - %s) / 2), 2) +
            COS(RADIANS(%s)) * COS(RADIANS(gps_lat)) *
            POW(SIN(RADIANS(gps_lon - %s) / 2), 2)
          )
        )
      ) AS distance_km
    FROM photos
    WHERE status='active'
      AND gps_lat IS NOT NULL
      AND gps_lon IS NOT NULL
      AND gps_lat BETWEEN %s AND %s
      AND gps_lon BETWEEN %s AND %s
    """
    params = [center_lat, center_lat, center_lon, min_lat, max_lat, min_lon, max_lon]
    sql = _append_path_roots_where(sql, params, roots, column_expr="REPLACE(file_path, '\\\\', '/')")
    if photo_ids is not None:
        if len(photo_ids) == 0:
            return []
        placeholders = ",".join(["%s"] * len(photo_ids))
        sql += f" AND id IN ({placeholders})"
        params.extend(photo_ids)
    if date_from:
        sql += " AND COALESCE(exif_datetime, file_mtime) >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND COALESCE(exif_datetime, file_mtime) < %s"
        params.append(end_exclusive(date_to))
    sql += " HAVING distance_km <= %s ORDER BY distance_km ASC, COALESCE(exif_datetime, file_mtime) DESC"
    params.append(radius_km)
    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))
    return list(fetch_all(sql, params) or ())


def count_photos() -> int:
    row = fetch_one("SELECT COUNT(1) AS cnt FROM photos WHERE status='active'")
    return int(row["cnt"]) if row else 0


def count_faces() -> int:
    row = fetch_one("SELECT COUNT(1) AS cnt FROM faces")
    return int(row["cnt"]) if row else 0


def fetch_active_face_embedding_ids() -> list[int]:
    rows = fetch_all(
        """
        SELECT f.embedding_id
        FROM faces f
        JOIN photos p ON p.id = f.photo_id
        WHERE p.status='active'
        ORDER BY f.embedding_id ASC
        """
    ) or ()
    ids: list[int] = []
    for row in rows:
        try:
            eid = int(row["embedding_id"])
        except Exception:
            continue
        if eid >= 0:
            ids.append(eid)
    return ids


def fetch_active_photo_embedding_ids() -> list[int]:
    ensure_photo_embeddings_table()
    rows = fetch_all(
        """
        SELECT e.embedding_id
        FROM photo_embeddings e
        JOIN photos p ON p.id = e.photo_id
        WHERE p.status='active'
        ORDER BY e.embedding_id ASC
        """
    ) or ()
    ids: list[int] = []
    for row in rows:
        try:
            eid = int(row["embedding_id"])
        except Exception:
            continue
        if eid >= 0:
            ids.append(eid)
    return ids


def fetch_face_counts_by_photo_ids(photo_ids: list, chunk_size: int = 1000) -> dict[int, int]:
    if not photo_ids:
        return {}
    ids = []
    for pid in photo_ids:
        try:
            value = int(pid)
        except Exception:
            continue
        if value > 0:
            ids.append(value)
    if not ids:
        return {}
    ids = list(dict.fromkeys(ids))
    counts: dict[int, int] = {}
    step = max(1, int(chunk_size))
    for start in range(0, len(ids), step):
        batch = ids[start:start + step]
        placeholders = ",".join(["%s"] * len(batch))
        sql = f"""
        SELECT photo_id, COUNT(1) AS face_count
        FROM faces
        WHERE photo_id IN ({placeholders})
        GROUP BY photo_id
        """
        rows = fetch_all(sql, batch) or ()
        for row in rows:
            counts[int(row["photo_id"])] = int(row.get("face_count") or 0)
    return counts


def count_photo_embeddings() -> int:
    ensure_photo_embeddings_table()
    row = fetch_one("SELECT COUNT(1) AS cnt FROM photo_embeddings")
    return int(row["cnt"]) if row else 0


def ensure_scan_progress_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS scan_progress (
      id BIGINT PRIMARY KEY AUTO_INCREMENT,
      scan_type VARCHAR(16) NOT NULL,
      processed_photos BIGINT NOT NULL DEFAULT 0,
      total_photos BIGINT NOT NULL DEFAULT 0,
      last_path VARCHAR(768) NULL,
      status VARCHAR(32) NOT NULL DEFAULT 'running',
      started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_status (status),
      INDEX idx_started (started_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    execute(sql)


def create_scan_progress(scan_type: str, total_photos: int, status: str = "running") -> int:
    ensure_scan_progress_table()
    sql = "INSERT INTO scan_progress (scan_type, processed_photos, total_photos, status) VALUES (%s,%s,%s,%s)"
    with conn_ctx() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (scan_type, 0, int(total_photos), status))
            return int(cur.lastrowid)


def update_scan_progress(progress_id: int, processed: int, last_path: str | None = None) -> int:
    ensure_scan_progress_table()
    sql = "UPDATE scan_progress SET processed_photos=%s, last_path=%s WHERE id=%s"
    return execute(sql, (int(processed), last_path, int(progress_id)))


def update_scan_progress_meta(progress_id: int, total_photos: int | None = None, status: str | None = None) -> int:
    ensure_scan_progress_table()
    fields = []
    params = []
    if total_photos is not None:
        fields.append("total_photos=%s")
        params.append(int(total_photos))
    if status is not None:
        fields.append("status=%s")
        params.append(status)
    if not fields:
        return 0
    sql = "UPDATE scan_progress SET " + ", ".join(fields) + " WHERE id=%s"
    params.append(int(progress_id))
    return execute(sql, tuple(params))


def finish_scan_progress(progress_id: int, status: str = "completed") -> int:
    ensure_scan_progress_table()
    return execute("UPDATE scan_progress SET status=%s WHERE id=%s", (status, int(progress_id)))


def get_latest_scan_progress():
    ensure_scan_progress_table()
    return fetch_one("SELECT * FROM scan_progress ORDER BY id DESC LIMIT 1")


def stop_active_scan_progress_rows() -> int:
    ensure_scan_progress_table()
    return execute(
        "UPDATE scan_progress SET status='stopped' WHERE status IN ('running', 'counting')"
    )


def ensure_photo_embeddings_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS photo_embeddings (
      id BIGINT PRIMARY KEY AUTO_INCREMENT,
      photo_id BIGINT NOT NULL UNIQUE,
      embedding_id BIGINT NOT NULL UNIQUE,
      model_name VARCHAR(64) NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      INDEX idx_embedding_id (embedding_id),
      INDEX idx_photo_id (photo_id),
      CONSTRAINT fk_photo_embeddings_photos FOREIGN KEY (photo_id) REFERENCES photos(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    execute(sql)


def ensure_index_state_vision() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS index_state_vision (
      id INT PRIMARY KEY AUTO_INCREMENT,
      index_path VARCHAR(1024) NOT NULL,
      index_type VARCHAR(64) NOT NULL,
      last_embedding_id BIGINT NOT NULL,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    execute(sql)


def get_photo_embedding(photo_id: int):
    ensure_photo_embeddings_table()
    return fetch_one("SELECT * FROM photo_embeddings WHERE photo_id=%s LIMIT 1", (photo_id,))


def upsert_photo_embedding(photo_id: int, embedding_id: int, model_name: str) -> int:
    ensure_photo_embeddings_table()
    sql = """
    INSERT INTO photo_embeddings (photo_id, embedding_id, model_name)
    VALUES (%s,%s,%s)
    ON DUPLICATE KEY UPDATE
        embedding_id=VALUES(embedding_id),
        model_name=VALUES(model_name)
    """
    return execute(sql, (photo_id, embedding_id, model_name))


def fetch_photos_by_photo_embedding_ids(
    ids: list,
    date_from: str | None = None,
    date_to: str | None = None,
    photo_ids: list | None = None,
):
    if not ids:
        return []
    if photo_ids is not None and len(photo_ids) == 0:
        return []
    ensure_photo_embeddings_table()
    placeholders = ",".join(["%s"] * len(ids))
    sql = f"""
    SELECT e.embedding_id, p.id AS photo_id, p.file_path, COALESCE(p.exif_datetime, p.file_mtime) AS exif_datetime, p.gps_lat, p.gps_lon
    FROM photo_embeddings e
    JOIN photos p ON p.id = e.photo_id
    WHERE e.embedding_id IN ({placeholders}) AND p.status='active'
    """
    params = list(ids)
    if date_from:
        sql += " AND COALESCE(p.exif_datetime, p.file_mtime) >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND COALESCE(p.exif_datetime, p.file_mtime) < %s"
        params.append(end_exclusive(date_to))
    if photo_ids is not None:
        photo_placeholders = ",".join(["%s"] * len(photo_ids))
        sql += f" AND p.id IN ({photo_placeholders})"
        params.extend([int(pid) for pid in photo_ids])
    rows = list(fetch_all(sql, params) or ())
    order = {eid: i for i, eid in enumerate(ids)}
    rows.sort(key=lambda r: order.get(r["embedding_id"], 10**9))
    return rows


def get_index_state():
    return fetch_one("SELECT * FROM index_state ORDER BY id DESC LIMIT 1")


def ensure_index_state(index_path: str = "", index_type: str = "") -> int:
    row = get_index_state()
    if row:
        return int(row["id"])
    if not index_path:
        index_path = str(Path(settings.paths.index_dir) / "faiss.index")
    if not index_type:
        index_type = settings.index.index_type
    sql = "INSERT INTO index_state (index_path, index_type, last_embedding_id) VALUES (%s,%s,%s)"
    execute(sql, (index_path, index_type, 0))
    row = get_index_state()
    return int(row["id"]) if row else 0


def reserve_embedding_ids(count: int) -> list:
    if count <= 0:
        return []
    state = get_index_state()
    if not state:
        ensure_index_state()
        state = get_index_state()
    last_id = int(state["last_embedding_id"]) if state else 0
    new_last = last_id + count
    execute("UPDATE index_state SET last_embedding_id=%s WHERE id=%s", (new_last, state["id"]))
    return list(range(last_id + 1, new_last + 1))


def get_index_state_vision():
    ensure_index_state_vision()
    return fetch_one("SELECT * FROM index_state_vision ORDER BY id DESC LIMIT 1")


def ensure_index_state_vision_row(index_path: str = "", index_type: str = "") -> int:
    ensure_index_state_vision()
    row = get_index_state_vision()
    if row:
        return int(row["id"])
    if not index_path:
        index_path = str(Path(settings.paths.index_dir) / "vision.index")
    if not index_type:
        index_type = settings.index.index_type
    sql = "INSERT INTO index_state_vision (index_path, index_type, last_embedding_id) VALUES (%s,%s,%s)"
    execute(sql, (index_path, index_type, 0))
    row = get_index_state_vision()
    return int(row["id"]) if row else 0


def reserve_embedding_ids_vision(count: int) -> list:
    if count <= 0:
        return []
    state = get_index_state_vision()
    if not state:
        ensure_index_state_vision_row()
        state = get_index_state_vision()
    last_id = int(state["last_embedding_id"]) if state else 0
    new_last = last_id + count
    execute("UPDATE index_state_vision SET last_embedding_id=%s WHERE id=%s", (new_last, state["id"]))
    return list(range(last_id + 1, new_last + 1))
