"""Download the pinned multilingual text encoder; never sends photos or queries."""
import configparser
import hashlib
import json
from pathlib import Path
import shutil


def main():
    from huggingface_hub import HfApi, snapshot_download, hf_hub_download
    project = Path(__file__).resolve().parent
    folder = project / "runtime" / "models" / "mclip-vit-b32"
    folder.mkdir(parents=True, exist_ok=True)
    repo = "M-CLIP/XLM-Roberta-Large-Vit-B-32"
    info = HfApi().model_info(repo)
    print("Downloading multilingual text weights, revision:", info.sha, flush=True)
    snapshot_download(repo, revision=info.sha, local_dir=str(folder), allow_patterns=["config.json", "pytorch_model.bin", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "sentencepiece.bpe.model"])
    cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    base_repo = cfg["modelBase"]
    base_info = HfApi().model_info(base_repo)
    source = hf_hub_download(base_repo, "config.json", revision=base_info.sha)
    shutil.copy2(source, folder / "base_config.json")
    digest = hashlib.sha256()
    with (folder / "pytorch_model.bin").open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    (folder / "model_origin.json").write_text(json.dumps({"repo": repo, "revision": info.sha, "base_repo": base_repo, "base_revision": base_info.sha, "image_space": "openai/ViT-B-32", "weights_sha256": digest.hexdigest()}, ensure_ascii=False, indent=2), encoding="utf-8")
    parser = configparser.ConfigParser()
    config = project / "db2_v2.ini"
    parser.read(config, encoding="utf-8")
    parser["vision"]["text_model"] = str(folder)
    with config.open("w", encoding="utf-8") as handle:
        parser.write(handle)
    print("Model files prepared. Restart v2 to enable Chinese description search.", flush=True)


if __name__ == "__main__":
    main()
