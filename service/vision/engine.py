import io
import logging
import os
from PIL import Image, ImageFile
import numpy as np
from service.core.config import settings
from service.utils.pillow_heif_support import enable_heif_support

log = logging.getLogger(__name__)
enable_heif_support(log)


def _clear_bad_proxy():
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(key, "")
        if val.startswith("http://127.0.0.1:9") or val.startswith("https://127.0.0.1:9"):
            os.environ.pop(key, None)


class VisionEngine:
    def __init__(self, model_name: str, pretrained: str, use_gpu: bool):
        self.model_name = model_name
        self.pretrained = pretrained
        self.use_gpu = use_gpu
        self.device = None
        self.model = None
        self.preprocess = None
        self._init_model()

    def _init_model(self):
        try:
            import torch  # type: ignore
            import open_clip  # type: ignore
        except Exception as exc:
            raise RuntimeError("open_clip_torch/torch not available") from exc

        _clear_bad_proxy()
        device = "cuda" if self.use_gpu and torch.cuda.is_available() else "cpu"
        self.device = device
        model, _, preprocess = open_clip.create_model_and_transforms(self.model_name, pretrained=self.pretrained)
        model.eval()
        self.model = model.to(device)
        self.preprocess = preprocess

    def _center_crop(self, img: Image.Image, scale: float = 0.7, y_shift: float = 0.0) -> Image.Image:
        w, h = img.size
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        left = max(0, (w - new_w) // 2)
        top = max(0, int((h - new_h) // 2 + h * y_shift))
        if top + new_h > h:
            top = max(0, h - new_h)
        return img.crop((left, top, left + new_w, top + new_h))

    def _center_strip(self, img: Image.Image, *, axis: str, ratio: float) -> Image.Image:
        w, h = img.size
        if axis == "vertical":
            strip_w = max(1, int(w * ratio))
            left = max(0, (w - strip_w) // 2)
            return img.crop((left, 0, left + strip_w, h))
        strip_h = max(1, int(h * ratio))
        top = max(0, (h - strip_h) // 2)
        return img.crop((0, top, w, top + strip_h))

    def _cross_focus(self, img: Image.Image, *, ratio: float = 0.38) -> Image.Image:
        arr = np.array(img.convert("RGB"), copy=True)
        h, w = arr.shape[:2]
        if h <= 0 or w <= 0:
            return img
        vx = max(1, int(w * ratio))
        hy = max(1, int(h * ratio))
        left = max(0, (w - vx) // 2)
        top = max(0, (h - hy) // 2)
        mask = np.zeros((h, w), dtype=bool)
        mask[:, left:left + vx] = True
        mask[top:top + hy, :] = True
        result = np.full_like(arr, 128)
        result[mask] = arr[mask]
        return Image.fromarray(result, mode="RGB")

    def _prepare_image(self, img: Image.Image, mode: str) -> Image.Image:
        mode = str(mode or "scene").strip().lower()
        if mode in ("scene", "location"):
            return img
        if mode in ("object", "center", "focus_center"):
            return self._center_crop(img, scale=0.7)
        if mode in ("building", "vertical", "focus_vertical"):
            return self._center_strip(img, axis="vertical", ratio=0.45)
        if mode in ("horizontal", "focus_horizontal"):
            return self._center_strip(img, axis="horizontal", ratio=0.45)
        if mode in ("cross", "focus_cross"):
            return self._cross_focus(img, ratio=0.36)
        return img

    def embed_image_bytes(self, image_bytes: bytes, mode: str = "scene") -> np.ndarray:
        try:
            import torch  # type: ignore
        except Exception as exc:
            raise RuntimeError("torch not available") from exc

        # Some chat-export thumbnails are slightly truncated; retry with tolerant decode.
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except OSError as exc:
            prev = ImageFile.LOAD_TRUNCATED_IMAGES
            try:
                ImageFile.LOAD_TRUNCATED_IMAGES = True
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            except Exception:
                raise exc
            finally:
                ImageFile.LOAD_TRUNCATED_IMAGES = prev
        img = self._prepare_image(img, mode)
        image_tensor = self.preprocess(img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            feats = self.model.encode_image(image_tensor)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].detach().cpu().numpy().astype("float32")


    def embed_text(self, text: str) -> np.ndarray:
        import torch
        import open_clip
        from threading import RLock
        if not hasattr(self, "_text_lock"):
            self._text_lock = RLock()
        with self._text_lock, torch.no_grad():
            if settings.vision.text_model:
                if self.model_name != "ViT-B-32" or self.pretrained != "openai":
                    raise RuntimeError("当前多语言文字编码器只适配OpenAI ViT-B-32图片索引")
                if not hasattr(self, "_multilingual_text_model"):
                    from service.vision.multilingual_text import encode_text
                    self._multilingual_text_model = encode_text
                return self._multilingual_text_model(text, settings.vision.text_model)
            else:
                if any('\u3400' <= char <= '\u9fff' for char in text):
                    from fastapi import HTTPException
                    raise HTTPException(503, detail="中文描述模型尚未准备，请先运行准备中文描述模型.py。也可先使用参考图找相似画面。")
                tokens = open_clip.get_tokenizer(self.model_name)([text]).to(self.device)
                feats = self.model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
            result = feats[0].detach().cpu().numpy().astype("float32")
            if result.size != settings.vision.embedding_dim:
                raise RuntimeError("文字向量维度与图片索引不一致")
            return result


_engine = None
_engine_failed = False


def get_vision_engine() -> VisionEngine:
    global _engine, _engine_failed
    if _engine is None:
        if _engine_failed:
            raise RuntimeError("vision engine disabled due to previous init failure")
        try:
            _engine = VisionEngine(
                model_name=settings.vision.model_name,
                pretrained=settings.vision.pretrained,
                use_gpu=settings.face.use_gpu,
            )
        except Exception:
            _engine_failed = True
            raise
    return _engine
