"""Local M-CLIP inference, with its matching OpenAI ViT-B/32 image space."""
import json
from pathlib import Path
from threading import RLock

import numpy as np

_LOCK = RLock()
_CACHE = {}


def encode_text(text, model_dir):
    import torch
    from transformers import AutoConfig, AutoModel, AutoTokenizer
    folder = Path(model_dir)
    with _LOCK:
        if str(folder) not in _CACHE:
            if not (folder / "pytorch_model.bin").is_file():
                from fastapi import HTTPException
                raise HTTPException(503, detail="中文描述模型尚未准备，请运行准备中文描述模型.py")
            cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
            provenance = json.loads((folder / "model_origin.json").read_text(encoding="utf-8"))
            if provenance.get("image_space") != "openai/ViT-B-32" or int(cfg["numDims"]) != 512:
                raise RuntimeError("中文文字模型与图片向量空间不匹配")
            base_cfg = json.loads((folder / "base_config.json").read_text(encoding="utf-8"))
            model_type = base_cfg.pop("model_type")
            config = AutoConfig.for_model(model_type, **base_cfg)

            class Encoder(torch.nn.Module):
                def __init__(self):
                    super().__init__()
                    self.transformer = AutoModel.from_config(config)
                    self.LinearTransformation = torch.nn.Linear(int(cfg["transformerDimensions"]), int(cfg["numDims"]))

                def forward(self, tokens):
                    embs = self.transformer(**tokens)[0]
                    mask = tokens["attention_mask"]
                    return self.LinearTransformation((embs * mask.unsqueeze(2)).sum(dim=1) / mask.sum(dim=1)[:, None])

            model = Encoder()
            weights = torch.load(folder / "pytorch_model.bin", map_location="cpu", weights_only=True)
            incompatible = model.load_state_dict(weights, strict=False)
            optional = {"transformer.embeddings.position_ids", "transformer.embeddings.token_type_ids"}
            if set(incompatible.missing_keys + incompatible.unexpected_keys) - optional:
                raise RuntimeError("文字模型权重与本地架构不一致")
            model.eval()
            tokenizer = AutoTokenizer.from_pretrained(str(folder), local_files_only=True, trust_remote_code=False)
            _CACHE[str(folder)] = (model, tokenizer)
        model, tokenizer = _CACHE[str(folder)]
        tokens = tokenizer([text], padding=True, truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            features = model(tokens)
            features = features / features.norm(dim=-1, keepdim=True)
        return features[0].cpu().numpy().astype(np.float32)
