import hashlib
import os
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic", ".heif"}
SKIP_DIR_NAMES = {
    "__MACOSX",
    "$RECYCLE.BIN",
    "System Volume Information",
    "@eaDir",
    ".git",
    ".svn",
    ".idea",
}
SKIP_FILE_PREFIXES = ("._",)


def compute_md5(path: Path, chunk_size: int = 1024 * 1024) -> str:
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES


def _should_skip_file(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in SKIP_FILE_PREFIXES)


def iter_image_files(roots):
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        stack = [root_path]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        name = entry.name
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if _should_skip_dir(name):
                                    continue
                                stack.append(Path(entry.path))
                                continue
                            if not entry.is_file(follow_symlinks=False):
                                continue
                        except OSError:
                            continue
                        if _should_skip_file(name):
                            continue
                        suffix = Path(name).suffix.lower()
                        if suffix in IMAGE_EXTS:
                            yield Path(entry.path)
            except OSError:
                continue
