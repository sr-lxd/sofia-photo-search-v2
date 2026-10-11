import io
import logging
from typing import List
import numpy as np
from PIL import Image
from service.core.config import settings
from service.utils.pillow_heif_support import enable_heif_support

log = logging.getLogger(__name__)
enable_heif_support(log)


class FaceEngine:
    def __init__(self, engine_name: str, use_gpu: bool, model_name: str):
        self.engine_name = engine_name
        self.use_gpu = use_gpu
        self.model_name = model_name
        self._engine = None
        self._init_engine()

    def _init_engine(self):
        if self.engine_name == "insightface":
            try:
                from insightface.app import FaceAnalysis  # type: ignore

                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if self.use_gpu else ["CPUExecutionProvider"]
                self._engine = FaceAnalysis(name=self.model_name, providers=providers)
                self._engine.prepare(ctx_id=0 if self.use_gpu else -1)
                return
            except Exception as exc:
                log.warning("insightface init failed, fallback to face_recognition: %s", exc)
                # fall through to face_recognition

        if self.engine_name == "face_recognition" or self._engine is None:
            try:
                import face_recognition  # type: ignore
            except Exception as exc:
                raise RuntimeError("face_recognition not available") from exc
            self._engine = face_recognition
            self.engine_name = "face_recognition"
            return

        raise RuntimeError("Unsupported face engine")

    def _load_image(self, image_bytes: bytes):
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.array(img)

    def detect_and_embed_bytes(self, image_bytes: bytes) -> List[dict]:
        img = self._load_image(image_bytes)
        if self.engine_name == "insightface":
            faces = self._engine.get(img)
            results = []
            for idx, face in enumerate(faces):
                bbox = [int(v) for v in face.bbox.tolist()]
                results.append(
                    {
                        "face_index": idx,
                        "bbox": bbox,
                        "embedding": face.embedding.astype("float32"),
                        "quality_score": float(getattr(face, "det_score", 0.0)),
                    }
                )
            return results

        if self.engine_name == "face_recognition":
            boxes = self._engine.face_locations(img)
            encodings = self._engine.face_encodings(img, boxes)
            results = []
            for idx, (box, enc) in enumerate(zip(boxes, encodings)):
                top, right, bottom, left = box
                results.append(
                    {
                        "face_index": idx,
                        "bbox": [left, top, right, bottom],
                        "embedding": np.asarray(enc, dtype="float32"),
                        "quality_score": None,
                    }
                )
            return results

        return []


def get_face_engine() -> FaceEngine:
    global _engine
    try:
        _engine
    except NameError:
        _engine = None
    if _engine is None:
        _engine = FaceEngine(settings.face.engine, settings.face.use_gpu, settings.face.model_name)
    return _engine
