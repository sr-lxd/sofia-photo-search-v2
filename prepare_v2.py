"""Prepare an independent metadata/index snapshot. Source photos stay read-only."""
import configparser
from datetime import datetime
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time

import pymysql
from pymysql.cursors import SSCursor

PROJECT = Path(__file__).resolve().parent
DB_NAME = "photo_search_v2"


def parser(path):
    result = configparser.ConfigParser()
    result.read(path, encoding="utf-8-sig")
    return result


def connection(db, database=None):
    return pymysql.connect(host=db.get("host", "127.0.0.1"), port=int(db.get("port", 3306)), user=db.get("user", "root"), password=db.get("password", ""), database=database, charset="utf8mb4", autocommit=True)


def main():
    if not PROJECT.name.endswith("v2"):
        raise RuntimeError("Run this entry point only from the v2 project directory")
    original = parser(PROJECT / "db2.ini")
    source_db = original["db1"] if original.has_section("db1") else original["database"]
    source_name = source_db["database"]
    if source_name == DB_NAME or not re.fullmatch(r"[A-Za-z0-9_]+", source_name):
        raise RuntimeError("Invalid source database")
    marker = PROJECT / "runtime" / "isolation_ready.json"
    if marker.exists():
        print("v2 snapshot already prepared; existing v2 data preserved.", flush=True)
        return
    source = connection(source_db, source_name)
    target = connection(source_db)
    with target.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM mysql.user WHERE user='photo_search_v2' AND host='127.0.0.1'")
        if cur.fetchone()[0]:
            raise RuntimeError("The v2 database account already exists; refusing to replace its credentials")
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s", (DB_NAME,))
        if cur.fetchone()[0]:
            raise RuntimeError("Target database already contains tables; refusing to overwrite it")
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    with source.cursor() as cur:
        cur.execute("SHOW TABLES")
        tables = [row[0] for row in cur.fetchall() if re.fullmatch(r"[A-Za-z0-9_]+", row[0])]
        if "scan_progress" in tables:
            cur.execute("SELECT COUNT(*) FROM scan_progress WHERE status IN ('running','paused')")
            if cur.fetchone()[0]:
                raise RuntimeError("The original scan is active. Wait for it to finish before making the snapshot.")
    # Schema inspection is read-only on the original database; all DDL targets v2.
    counts = {}
    with source.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cur.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
    for table in tables:
        with target.cursor() as cur:
            cur.execute(f"CREATE TABLE `{DB_NAME}`.`{table}` LIKE `{source_name}`.`{table}`")
        with source.cursor(SSCursor) as stream:
            stream.execute(f"SELECT * FROM `{table}`")
            columns = [item[0] for item in stream.description]
            names = ",".join("`" + name.replace("`", "``") + "`" for name in columns)
            sql = f"INSERT INTO `{DB_NAME}`.`{table}` ({names}) VALUES (" + ",".join(["%s"] * len(columns)) + ")"
            count = 0
            with target.cursor() as cur:
                while True:
                    rows = stream.fetchmany(2000)
                    if not rows:
                        break
                    cur.executemany(sql, rows)
                    count += len(rows)
            counts[table] = count
            print(f"Copied table {table}: {count} records", flush=True)
    source.commit()
    runtime = PROJECT / "runtime"
    runtime.mkdir(exist_ok=True)
    original_index = Path(original["paths"]["index_dir"])
    new_index = runtime / "index"
    if new_index.exists() and any(new_index.iterdir()):
        raise RuntimeError("Target index is not empty; refusing to overwrite it")
    before = {str(path.relative_to(original_index)): (path.stat().st_size, path.stat().st_mtime_ns) for path in original_index.rglob("*") if path.is_file()}
    shutil.copytree(original_index, new_index, dirs_exist_ok=True)
    after = {str(path.relative_to(original_index)): (path.stat().st_size, path.stat().st_mtime_ns) for path in original_index.rglob("*") if path.is_file()}
    if before != after:
        raise RuntimeError("Source index changed during copy; snapshot not marked ready")
    with target.cursor() as cur:
        cur.execute(f"USE `{DB_NAME}`")
        cur.execute("CREATE TABLE ui_library_version (id INT PRIMARY KEY,revision BIGINT NOT NULL)")
        cur.execute("INSERT INTO ui_library_version VALUES (1,1)")
        for event in ["INSERT", "UPDATE", "DELETE"]:
            cur.execute(f"CREATE TRIGGER ui_photos_{event.lower()} AFTER {event} ON photos FOR EACH ROW UPDATE ui_library_version SET revision=revision+1 WHERE id=1")
        for index_name, expression in [("idx_v2_added", "status,created_at,id"), ("idx_v2_faces", "status,face_count,id")]:
            cur.execute(f"CREATE INDEX {index_name} ON photos ({expression})")
        # Dedicated account can only access the independent v2 database.
        account = "photo_search_v2"
        db_password = secrets.token_urlsafe(32)
        cur.execute("CREATE USER 'photo_search_v2'@'127.0.0.1' IDENTIFIED BY %s", (db_password,))
        cur.execute(f"GRANT ALL PRIVILEGES ON `{DB_NAME}`.* TO 'photo_search_v2'@'127.0.0.1'")
    configuration = configparser.ConfigParser()
    for section in original.sections():
        if section not in ("db1", "database", "paths", "auth", "server"):
            configuration[section] = dict(original[section])
    configuration["database"] = {"host": "127.0.0.1", "port": source_db.get("port", "3306"), "user": account, "password": db_password, "database": DB_NAME, "charset": "utf8mb4"}
    configuration["paths"] = {"photo_roots": original["paths"]["photo_roots"], "index_dir": str(new_index), "thumb_dir": str(runtime / "thumbs"), "export_dir": str(runtime / "export"), "source_read_only": "true"}
    policies_source = Path(original.get("auth", "policies_json", fallback="config/auth_policies.json"))
    if not policies_source.is_absolute():
        policies_source = PROJECT / policies_source
    policies_target = PROJECT / "config" / "auth_policies_v2.json"
    shutil.copy2(policies_source, policies_target)
    configuration["auth"] = {"password": original.get("auth", "password", fallback=""), "session_secret": secrets.token_urlsafe(48), "policies_json": str(policies_target), "cookie_name": "photo_search_v2_auth"}
    configuration["server"] = {"port": "5091"}
    if not configuration.has_section("face"):
        configuration["face"] = {}
    configuration["face"]["use_gpu"] = "false"
    if not configuration.has_section("vision"):
        configuration["vision"] = {"enabled": "true", "model_name": "ViT-B-32", "pretrained": "openai"}
    with (PROJECT / "db2_v2.ini").open("w", encoding="utf-8") as handle:
        configuration.write(handle)
    if not (PROJECT / ".venv" / "Scripts" / "python.exe").exists():
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(PROJECT / ".venv")], check=True)
    marker.write_text(json.dumps({"created_at": datetime.now().isoformat(), "database": DB_NAME, "port": 5091, "tables": counts, "source_read_only": True, "index_files": len(before)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("v2 isolation prepared. Source photos are read-only. Port: 5091", flush=True)


if __name__ == "__main__":
    main()
