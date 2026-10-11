import logging
import threading
import time
from service.core.config import settings
from service.db import mysql
from service.scan import scanner
from service.scan.idle import IdleController

log = logging.getLogger(__name__)


class ScanManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self._paused = False
        self._running = False
        self._last_message = ""
        self._progress_id = None
        self._progress_total = 0
        self._progress_last_count = 0
        self._progress_last_update = 0.0
        self._progress_last_path = None

    def _start_total_counter(self, progress_id: int):
        def _worker():
            total = 0
            try:
                total = scanner.count_image_files(settings.paths.photo_roots)
            except Exception as exc:
                log.warning("count image files failed: %s", exc)
            if self._progress_id != progress_id:
                return
            if self._running:
                mysql.update_scan_progress_meta(progress_id, total_photos=total, status="running")
            else:
                mysql.update_scan_progress_meta(progress_id, total_photos=total)
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _run(self, full: bool, resume_from: str | None = None, start_count: int = 0, progress_id: int | None = None):
        status = "completed"
        try:
            if progress_id:
                self._progress_id = progress_id
                self._progress_total = 0
                self._progress_last_count = start_count
                self._progress_last_update = 0.0
                self._progress_last_path = resume_from
                mysql.update_scan_progress_meta(progress_id, status="running")
            else:
                progress_id = mysql.create_scan_progress("full" if full else "incremental", 0, status="counting")
                self._progress_id = progress_id
                self._progress_total = 0
                self._progress_last_count = 0
                self._progress_last_update = 0.0
                self._progress_last_path = None
            if progress_id:
                self._start_total_counter(progress_id)
            # When scan_idle_only is disabled, do not block on idle checks.
            idle_controller = IdleController.from_settings() if settings.scan.scan_idle_only else None
            processed = scanner.scan_roots(
                settings.paths.photo_roots,
                on_progress=self._on_progress,
                should_pause=self._should_pause,
                stop_event=self._stop_event,
                batch_size=settings.scan.scan_batch_size,
                idle_controller=idle_controller,
                full=full,
                resume_from=resume_from,
                start_count=start_count,
            )
            if self._stop_event.is_set():
                status = "stopped"
                self._last_message = "scan stopped"
            else:
                self._last_message = "scan completed"
            if progress_id:
                mysql.update_scan_progress(progress_id, processed, self._progress_last_path)
        except Exception as exc:
            log.exception("scan failed")
            self._last_message = f"scan failed: {exc}"
            status = "failed"
        finally:
            if progress_id:
                mysql.finish_scan_progress(progress_id, status)
            self._running = False
            self._progress_id = None

    def _on_progress(self, info: dict):
        self._last_message = info.get("message", "")
        if not self._progress_id:
            return
        processed = int(info.get("processed", 0))
        path = info.get("path")
        if path:
            self._progress_last_path = path
        now = time.time()
        if (processed - self._progress_last_count) >= 20 or (now - self._progress_last_update) >= 2.0:
            mysql.update_scan_progress(self._progress_id, processed, self._progress_last_path)
            self._progress_last_count = processed
            self._progress_last_update = now

    def _should_pause(self):
        return self._paused

    def start(self, full: bool = False, resume: bool = False):
        with self._lock:
            if self._running:
                return {"running": True, "message": "scan already running"}
            resume_from = None
            start_count = 0
            progress_id = None
            if resume:
                row = mysql.get_latest_scan_progress()
                if not row:
                    return {"running": False, "message": "no previous scan progress to resume"}
                status = str(row.get("status") or "").lower()
                if status not in ("stopped", "failed", "running"):
                    return {"running": False, "message": f"scan status '{status}' not resumable"}
                resume_from = row.get("last_path")
                if not resume_from:
                    return {"running": False, "message": "no last_path to resume from"}
                scan_type = str(row.get("scan_type") or "").lower()
                full = scan_type == "full"
                start_count = int(row.get("processed_photos") or 0)
                progress_id = int(row.get("id"))
            self._stop_event.clear()
            self._paused = False
            self._running = True
            self._thread = threading.Thread(
                target=self._run,
                args=(full, resume_from, start_count, progress_id),
                daemon=True,
            )
            self._thread.start()
        return {"running": True, "message": "scan resumed" if resume else "scan started"}

    def pause(self):
        self._paused = True
        return {"paused": True}

    def resume(self):
        self._paused = False
        return {"paused": False}

    def stop(self):
        self._stop_event.set()
        return {"stopped": True}

    def status(self):
        return {
            "running": self._running,
            "paused": self._paused,
            "message": self._last_message,
        }


scan_manager = ScanManager()
