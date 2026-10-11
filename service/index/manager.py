import hashlib
import json
import logging
import os
import shutil
import threading
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np

from service.core.config import settings

log = logging.getLogger(__name__)


class IndexManager:
    MANIFEST_VERSION = 1
    MANIFEST_REFRESH_SECONDS = 600
    STALE_MTIME_SECONDS = 14 * 24 * 3600

    def __init__(self, index_path: str | None = None, dim: int | None = None, index_type: str | None = None):
        self.backend = settings.index.backend
        self.index_type = index_type or settings.index.index_type
        self.index_path = index_path or str(Path(settings.paths.index_dir) / "faiss.index")
        self.dim = dim or settings.face.embedding_dim
        self._lock = threading.RLock()
        self._index = None
        self._manifest_path = f"{self.index_path}.manifest.json"
        self._prev_path = f"{self.index_path}.prev"
        self._last_manifest_refresh = 0.0
        self._subset_cache = OrderedDict()
        self._subset_cache_max = 6
        self._health = {
            "status": "unknown",
            "warnings": [],
            "checked_at": 0.0,
            "index_path": self.index_path,
            "file_size": 0,
            "ntotal": 0,
        }

    def exists(self) -> bool:
        try:
            return os.path.exists(self.index_path) and os.path.getsize(self.index_path) > 0
        except Exception:
            return False

    def get_health(self) -> dict:
        with self._lock:
            if float(self._health.get("checked_at") or 0.0) <= 0.0:
                self._probe_disk_health()
            return dict(self._health)

    def _probe_disk_health(self) -> None:
        warnings: list[str] = []
        if not os.path.exists(self.index_path):
            self._health = {
                "status": "warn",
                "warnings": ["index file not found"],
                "checked_at": time.time(),
                "index_path": self.index_path,
                "file_size": 0,
                "ntotal": 0,
            }
            return
        try:
            st = os.stat(self.index_path)
            file_size = int(st.st_size)
            if file_size <= 0:
                warnings.append("index file is empty")
            age = time.time() - float(st.st_mtime)
            if age > self.STALE_MTIME_SECONDS:
                warnings.append(f"stale mtime ({int(age)}s)")
            ntotal = int(self._health.get("ntotal") or 0)
            manifest = self._read_manifest()
            if manifest is None:
                warnings.append("manifest missing")
            else:
                try:
                    ntotal = max(0, int(manifest.get("ntotal") or ntotal))
                except Exception:
                    warnings.append("manifest ntotal invalid")
                if self._manifest_is_stale(manifest, st):
                    warnings.append("manifest stale")
            self._health = {
                "status": "warn" if warnings else "ok",
                "warnings": warnings,
                "checked_at": time.time(),
                "index_path": self.index_path,
                "file_size": file_size,
                "ntotal": ntotal,
            }
        except Exception as exc:
            self._health = {
                "status": "error",
                "warnings": [f"probe failed: {exc}"],
                "checked_at": time.time(),
                "index_path": self.index_path,
                "file_size": 0,
                "ntotal": 0,
            }

    def _now_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _index_kind(self) -> str:
        name = Path(self.index_path).name.lower()
        return "vision" if "vision" in name else "face"

    def _model_meta(self) -> dict:
        if self._index_kind() == "vision":
            return {
                "engine": "open_clip",
                "model_name": settings.vision.model_name,
                "pretrained": settings.vision.pretrained,
                "embedding_dim": int(getattr(settings.vision, "embedding_dim", self.dim)),
            }
        return {
            "engine": settings.face.engine,
            "model_name": settings.face.model_name,
            "embedding_dim": int(settings.face.embedding_dim),
        }

    def _set_health(self, status: str, warnings: list[str] | None = None, **extra) -> None:
        payload = {
            "status": status,
            "warnings": list(warnings or []),
            "checked_at": time.time(),
            "index_path": self.index_path,
        }
        payload.update(extra)
        with self._lock:
            self._health = payload

    def _read_manifest(self) -> dict | None:
        if not os.path.exists(self._manifest_path):
            return None
        try:
            with open(self._manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except Exception as exc:
            log.warning("failed to read index manifest %s: %s", self._manifest_path, exc)
            return None

    def _write_manifest_atomic(self, payload: dict) -> None:
        tmp_path = f"{self._manifest_path}.tmp"
        Path(self._manifest_path).parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self._manifest_path)

    def _file_sha256(self, file_path: str, chunk_size: int = 4 * 1024 * 1024) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _build_manifest(self, index_obj, file_path: str, *, include_hash: bool = True) -> dict:
        st = os.stat(file_path)
        payload = {
            "version": self.MANIFEST_VERSION,
            "generated_at": self._now_iso(),
            "index_path": str(file_path),
            "index_kind": self._index_kind(),
            "index_type": self.index_type,
            "dimension": int(self.dim),
            "ntotal": int(getattr(index_obj, "ntotal", 0)),
            "file_size": int(st.st_size),
            "file_mtime": float(st.st_mtime),
            "model": self._model_meta(),
        }
        payload["sha256"] = self._file_sha256(file_path) if include_hash else ""
        return payload

    def _manifest_is_stale(self, manifest: dict, file_stat: os.stat_result) -> bool:
        if not isinstance(manifest, dict):
            return True
        manifest_mtime = float(manifest.get("file_mtime") or 0.0)
        return manifest_mtime + 1e-3 < float(file_stat.st_mtime)

    def _verify_manifest(self, index_obj, file_path: str, manifest: dict) -> tuple[bool, list[str]]:
        issues: list[str] = []
        if not isinstance(manifest, dict):
            return False, ["manifest missing"]
        file_stat = os.stat(file_path)
        if int(manifest.get("version") or 0) != self.MANIFEST_VERSION:
            issues.append("manifest version mismatch")
        if int(manifest.get("file_size") or -1) != int(file_stat.st_size):
            issues.append("manifest file_size mismatch")
        if int(manifest.get("ntotal") or -1) != int(getattr(index_obj, "ntotal", -1)):
            issues.append("manifest ntotal mismatch")
        expected_sha = str(manifest.get("sha256") or "").strip()
        if expected_sha:
            actual_sha = self._file_sha256(file_path)
            if actual_sha != expected_sha:
                issues.append("manifest sha256 mismatch")
        else:
            issues.append("manifest sha256 missing")
        return len(issues) == 0, issues

    def _create_empty_index(self, faiss_module):
        if self.index_type == "hnsw":
            base = faiss_module.IndexHNSWFlat(self.dim, settings.index.hnsw_m)
        elif self.index_type == "ivf_pq":
            quantizer = faiss_module.IndexFlatIP(self.dim)
            base = faiss_module.IndexIVFPQ(quantizer, self.dim, settings.index.nlist, settings.index.pq_m, 8)
        else:
            base = faiss_module.IndexFlatIP(self.dim)
        return faiss_module.IndexIDMap2(base)

    def _load_index_from_file(self, faiss_module, file_path: str, *, use_manifest: bool) -> object:
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        file_size = int(os.path.getsize(file_path))
        if file_size <= 0:
            raise RuntimeError(f"index file is empty: {file_path}")
        index_obj = faiss_module.read_index(file_path)
        ntotal = int(getattr(index_obj, "ntotal", 0))
        warnings: list[str] = []
        st = os.stat(file_path)
        age = time.time() - float(st.st_mtime)
        if age > self.STALE_MTIME_SECONDS:
            warnings.append(f"stale mtime ({int(age)}s)")
        if use_manifest:
            manifest = self._read_manifest()
            if manifest is None:
                warnings.append("manifest missing")
            elif self._manifest_is_stale(manifest, st):
                warnings.append("manifest stale")
            else:
                ok, issues = self._verify_manifest(index_obj, file_path, manifest)
                if not ok:
                    raise RuntimeError("manifest verification failed: " + "; ".join(issues))
                for issue in issues:
                    warnings.append(issue)
        self._set_health(
            "warn" if warnings else "ok",
            warnings=warnings,
            file_size=file_size,
            ntotal=ntotal,
            source_path=file_path,
        )
        return index_obj

    def _maybe_refresh_manifest(self, index_obj, *, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self._last_manifest_refresh) < self.MANIFEST_REFRESH_SECONDS:
            return
        payload = self._build_manifest(index_obj, self.index_path, include_hash=True)
        self._write_manifest_atomic(payload)
        self._last_manifest_refresh = now

    def _recover_from_prev(self, faiss_module, reason: str) -> bool:
        if not os.path.exists(self._prev_path):
            return False
        try:
            recovered = self._load_index_from_file(faiss_module, self._prev_path, use_manifest=False)
        except Exception as exc:
            log.warning("rollback load failed for %s: %s", self._prev_path, exc)
            return False
        self._index = recovered
        try:
            Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self._prev_path, self.index_path)
            self._maybe_refresh_manifest(recovered, force=True)
        except Exception as exc:
            log.warning("rollback restore copy failed (%s -> %s): %s", self._prev_path, self.index_path, exc)
        log.warning("index rollback applied from prev due to: %s", reason)
        return True

    def _load_faiss(self):
        try:
            import faiss  # type: ignore
        except Exception as exc:
            raise RuntimeError("faiss not available") from exc

        if os.path.exists(self.index_path):
            try:
                self._index = self._load_index_from_file(faiss, self.index_path, use_manifest=True)
                self._maybe_refresh_manifest(self._index, force=False)
                return
            except Exception as exc:
                log.warning("failed to load index %s: %s", self.index_path, exc)
                if self._recover_from_prev(faiss, str(exc)):
                    return
                ts = time.strftime("%Y%m%d_%H%M%S")
                corrupt_path = f"{self.index_path}.corrupt.{ts}"
                try:
                    os.replace(self.index_path, corrupt_path)
                    log.warning("unusable index moved to %s", corrupt_path)
                except Exception as move_exc:
                    log.warning("failed to move bad index %s: %s", self.index_path, move_exc)

        self._index = self._create_empty_index(faiss)
        self._set_health(
            "warn",
            warnings=["index rebuilt as empty"],
            file_size=0,
            ntotal=0,
            source_path=self.index_path,
        )

    def load(self):
        if self.backend != "faiss":
            raise RuntimeError("Only faiss backend is implemented in this build")
        if self._index is not None:
            return
        with self._lock:
            if self._index is not None:
                return
            self._load_faiss()

    def save(self):
        if self.backend != "faiss":
            return
        if self._index is None:
            return

        import faiss  # type: ignore

        with self._lock:
            tmp_path = f"{self.index_path}.tmp"
            Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)
            replaced_old = False
            try:
                faiss.write_index(self._index, tmp_path)
                probe = faiss.read_index(tmp_path)
                expected_ntotal = int(getattr(self._index, "ntotal", 0))
                actual_ntotal = int(getattr(probe, "ntotal", 0))
                if actual_ntotal != expected_ntotal:
                    raise RuntimeError(f"atomic save verification failed: ntotal {actual_ntotal} != {expected_ntotal}")

                if os.path.exists(self.index_path):
                    os.replace(self.index_path, self._prev_path)
                    replaced_old = True
                os.replace(tmp_path, self.index_path)
                self._set_health(
                    "ok",
                    warnings=[],
                    file_size=int(os.path.getsize(self.index_path)),
                    ntotal=actual_ntotal,
                    source_path=self.index_path,
                )
                try:
                    self._maybe_refresh_manifest(probe, force=not os.path.exists(self._manifest_path))
                except Exception as exc:
                    log.warning("manifest refresh failed: %s", exc)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                if replaced_old and (not os.path.exists(self.index_path)) and os.path.exists(self._prev_path):
                    try:
                        shutil.copy2(self._prev_path, self.index_path)
                    except Exception as restore_exc:
                        log.error("failed to restore index from prev after save error: %s", restore_exc)
                raise

    def add(self, vectors, ids):
        if len(vectors) == 0:
            return
        self.load()
        import faiss  # type: ignore

        vecs = np.asarray(vectors, dtype="float32")
        ids = np.asarray(ids, dtype="int64")
        if vecs.ndim == 1:
            vecs = vecs.reshape(1, -1)
        faiss.normalize_L2(vecs)

        with self._lock:
            if self.index_type == "ivf_pq" and not self._index.is_trained:
                if vecs.shape[0] < settings.index.nlist:
                    raise RuntimeError("Not enough vectors to train IVF index")
                self._index.train(vecs)
            self._index.add_with_ids(vecs, ids)
            self._subset_cache.clear()
            self.save()

    @staticmethod
    def _normalize_search_score(raw_score: float, metric_type: int, faiss_module) -> float:
        # All embeddings are unit-normalized before add/search.
        # For L2 metric, FAISS returns squared distance: d^2 = 2 - 2*cos.
        # Convert it to cosine-like similarity so callers can consistently use "higher is better".
        if metric_type == getattr(faiss_module, "METRIC_L2", 1):
            return max(-1.0, min(1.0, 1.0 - (float(raw_score) * 0.5)))
        return float(raw_score)

    def search(self, vector, topk=50):
        self.load()
        import faiss  # type: ignore

        vec = np.asarray(vector, dtype="float32")
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)
        faiss.normalize_L2(vec)
        with self._lock:
            scores, idx = self._index.search(vec, topk)
            metric_type = int(getattr(self._index, "metric_type", getattr(faiss, "METRIC_INNER_PRODUCT", 0)))
        results = []
        for i, raw_score in zip(idx[0], scores[0]):
            score = self._normalize_search_score(raw_score, metric_type, faiss)
            results.append((int(i), score))
        return results

    def _prepare_subset_vectors(self, candidate_ids) -> tuple[list[int], np.ndarray]:
        self.load()
        cleaned_ids: list[int] = []
        seen: set[int] = set()
        for raw in candidate_ids or []:
            try:
                eid = int(raw)
            except Exception:
                continue
            if eid < 0 or eid in seen:
                continue
            seen.add(eid)
            cleaned_ids.append(eid)
        if not cleaned_ids:
            return [], np.empty((0, int(self.dim)), dtype="float32")
        cache_key = hashlib.sha1(np.asarray(cleaned_ids, dtype="int64").tobytes()).hexdigest()
        with self._lock:
            cached = self._subset_cache.get(cache_key)
            if cached:
                self._subset_cache.move_to_end(cache_key, last=True)
                return list(cached["ids"]), cached["vecs"]
            reconstruct_batch = getattr(self._index, "reconstruct_batch", None)
            if callable(reconstruct_batch):
                try:
                    id_arr = np.asarray(cleaned_ids, dtype="int64")
                    vecs = np.asarray(reconstruct_batch(id_arr), dtype="float32")
                    if vecs.ndim == 1:
                        vecs = vecs.reshape(1, -1)
                    self._subset_cache[cache_key] = {"ids": tuple(cleaned_ids), "vecs": vecs}
                    self._subset_cache.move_to_end(cache_key, last=True)
                    while len(self._subset_cache) > self._subset_cache_max:
                        self._subset_cache.popitem(last=False)
                    return cleaned_ids, vecs
                except Exception:
                    pass
            vectors: list[np.ndarray] = []
            valid_ids: list[int] = []
            for eid in cleaned_ids:
                try:
                    vectors.append(np.asarray(self._index.reconstruct(int(eid)), dtype="float32"))
                    valid_ids.append(int(eid))
                except Exception:
                    continue
        if not vectors:
            return [], np.empty((0, int(self.dim)), dtype="float32")
        vecs = np.vstack(vectors).astype("float32", copy=False)
        with self._lock:
            self._subset_cache[cache_key] = {"ids": tuple(valid_ids), "vecs": vecs}
            self._subset_cache.move_to_end(cache_key, last=True)
            while len(self._subset_cache) > self._subset_cache_max:
                self._subset_cache.popitem(last=False)
        return valid_ids, vecs

    def prepare_subset(self, candidate_ids) -> tuple[list[int], np.ndarray]:
        return self._prepare_subset_vectors(candidate_ids)

    def search_prepared_subset(self, vector, subset_ids, subset_vecs, topk=None):
        vec = np.asarray(vector, dtype="float32")
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)
        query = vec.astype("float32", copy=True)
        norms = np.linalg.norm(query, axis=1, keepdims=True)
        query /= np.clip(norms, 1e-12, None)
        if not subset_ids or subset_vecs.size == 0:
            return []
        subset_norms = np.linalg.norm(subset_vecs, axis=1, keepdims=True)
        subset_vecs = subset_vecs / np.clip(subset_norms, 1e-12, None)
        scores = np.dot(subset_vecs, query[0])
        if scores.size == 0:
            return []
        limit = len(subset_ids) if topk is None else max(1, min(int(topk), len(subset_ids)))
        if limit >= len(subset_ids):
            order = np.argsort(-scores)
        else:
            order = np.argpartition(-scores, limit - 1)[:limit]
            order = order[np.argsort(-scores[order])]
        results = []
        for idx in order:
            results.append((int(subset_ids[int(idx)]), float(scores[int(idx)])))
        return results

    def search_subset(self, vector, candidate_ids, topk=None):
        subset_ids, subset_vecs = self.prepare_subset(candidate_ids)
        return self.search_prepared_subset(vector, subset_ids, subset_vecs, topk=topk)

    def reconstruct(self, embedding_id: int):
        self.load()
        with self._lock:
            return self._index.reconstruct(embedding_id)

    def _add_vectors_to_index(self, index_obj, vectors, ids, faiss_module) -> int:
        if not vectors:
            return 0
        vecs = np.asarray(vectors, dtype="float32")
        id_arr = np.asarray(ids, dtype="int64")
        if vecs.ndim == 1:
            vecs = vecs.reshape(1, -1)
        faiss_module.normalize_L2(vecs)
        if self.index_type == "ivf_pq" and not index_obj.is_trained:
            if vecs.shape[0] < settings.index.nlist:
                raise RuntimeError("Not enough vectors to train IVF index during compaction")
            index_obj.train(vecs)
        index_obj.add_with_ids(vecs, id_arr)
        return int(id_arr.shape[0])

    def compact_with_embedding_ids(
        self,
        embedding_ids: list[int],
        *,
        dry_run: bool = False,
        batch_size: int = 2048,
        progress_cb=None,
    ) -> dict:
        self.load()
        ids: list[int] = []
        seen = set()
        for raw in embedding_ids or []:
            try:
                eid = int(raw)
            except Exception:
                continue
            if eid < 0 or eid in seen:
                continue
            seen.add(eid)
            ids.append(eid)
        ids.sort()
        total = len(ids)
        source_ntotal = int(getattr(self._index, "ntotal", 0))
        result = {
            "requested_total": total,
            "source_ntotal": source_ntotal,
            "added_total": 0,
            "skipped_total": 0,
            "missing_total": 0,
            "new_ntotal": source_ntotal if dry_run else 0,
            "dry_run": bool(dry_run),
        }
        if dry_run or total <= 0:
            return result

        import faiss  # type: ignore

        target_index = self._create_empty_index(faiss)
        batch_vectors = []
        batch_ids = []
        added_total = 0
        skipped_total = 0
        safe_batch = max(64, int(batch_size or 2048))

        def _flush_batch() -> None:
            nonlocal batch_vectors, batch_ids, added_total
            if not batch_vectors:
                return
            added_total += self._add_vectors_to_index(target_index, batch_vectors, batch_ids, faiss)
            batch_vectors = []
            batch_ids = []

        for idx, eid in enumerate(ids, start=1):
            try:
                with self._lock:
                    vec = self._index.reconstruct(int(eid))
            except Exception:
                skipped_total += 1
                continue
            batch_vectors.append(np.asarray(vec, dtype="float32"))
            batch_ids.append(int(eid))
            if len(batch_ids) >= safe_batch:
                _flush_batch()
            if callable(progress_cb) and (idx == total or idx % 1000 == 0):
                progress_cb(
                    {
                        "phase": "reconstruct",
                        "processed": int(idx),
                        "total": int(total),
                        "added": int(added_total),
                        "skipped": int(skipped_total),
                    }
                )

        _flush_batch()
        new_ntotal = int(getattr(target_index, "ntotal", 0))

        with self._lock:
            old_index = self._index
            self._index = target_index
            try:
                self.save()
            except Exception:
                self._index = old_index
                raise

        result.update(
            {
                "added_total": int(added_total),
                "skipped_total": int(skipped_total),
                "missing_total": int(max(0, total - added_total)),
                "new_ntotal": int(new_ntotal),
            }
        )
        return result


_index_manager = None
_vision_index_manager = None


def get_index_manager() -> IndexManager:
    global _index_manager
    if _index_manager is None:
        _index_manager = IndexManager()
    return _index_manager


def get_vision_index_manager() -> IndexManager:
    global _vision_index_manager
    if _vision_index_manager is None:
        index_path = str(Path(settings.paths.index_dir) / "vision.index")
        dim = getattr(settings, "vision", None).embedding_dim if getattr(settings, "vision", None) else settings.face.embedding_dim
        _vision_index_manager = IndexManager(index_path=index_path, dim=dim)
    return _vision_index_manager
