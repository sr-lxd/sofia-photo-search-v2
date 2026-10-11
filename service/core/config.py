from dataclasses import dataclass
from pathlib import Path
import configparser
import os

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"


@dataclass
class PathsConfig:
    photo_roots: list
    index_dir: str
    thumb_dir: str
    export_dir: str
    source_read_only: bool = False


@dataclass
class FaceConfig:
    engine: str
    use_gpu: bool
    model_name: str
    embedding_dim: int = 512


@dataclass
class IndexConfig:
    backend: str
    index_type: str
    nlist: int
    pq_m: int
    hnsw_m: int


@dataclass
class ScanConfig:
    scan_idle_only: bool
    idle_minutes: int
    cpu_limit: int
    gpu_limit: int
    io_limit: int
    scan_batch_size: int


@dataclass
class ServerConfig:
    port: int


@dataclass
class AuthConfig:
    password: str
    session_secret: str
    policies_json: str
    cookie_name: str = "photo_search_auth"


@dataclass
class VisionConfig:
    enabled: bool
    model_name: str
    pretrained: str
    embedding_dim: int = 512
    text_model: str = ""


@dataclass
class Settings:
    db: DBConfig
    paths: PathsConfig
    face: FaceConfig
    vision: VisionConfig
    index: IndexConfig
    scan: ScanConfig
    server: ServerConfig
    auth: AuthConfig
    config_path: str


def _normalize_ini(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.replace("\ufeff", "")
        if line.lstrip().startswith("•"):
            line = line.replace("•", "", 1)
        lines.append(line)
    return "\n".join(lines)


def _load_parser(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if path.exists():
        text = _normalize_ini(path.read_text(encoding="utf-8", errors="ignore"))
        parser.read_string(text)
    return parser


def _split_paths(value: str) -> list:
    if not value:
        return []
    return [v.strip() for v in value.replace(",", ";").split(";") if v.strip()]


def load_settings() -> Settings:
    isolated = BASE_DIR.name.endswith("v2")
    config_path = Path(os.getenv("PHOTO_SEARCH_CONFIG", str(BASE_DIR / ("db2_v2.ini" if isolated else "db2.ini"))))
    if isolated and not config_path.is_file():
        raise RuntimeError("v2隔离配置缺失，请先运行准备照片搜索v2.py")
    parser = _load_parser(config_path)

    db_section = parser["db1"] if parser.has_section("db1") else parser["database"] if parser.has_section("database") else {}
    paths_section = parser["paths"] if parser.has_section("paths") else {}
    face_section = parser["face"] if parser.has_section("face") else {}
    index_section = parser["index"] if parser.has_section("index") else {}
    scan_section = parser["scan"] if parser.has_section("scan") else {}
    vision_section = parser["vision"] if parser.has_section("vision") else {}
    auth_section = parser["auth"] if parser.has_section("auth") else {}

    db = DBConfig(
        host=db_section.get("host", "127.0.0.1"),
        port=int(db_section.get("port", 3306)),
        user=db_section.get("user", "root"),
        password=db_section.get("password", ""),
        database=db_section.get("database", "photo_search"),
        charset=db_section.get("charset", "utf8mb4"),
    )

    photo_roots = _split_paths(paths_section.get("photo_roots", "")) or [r"D:\\homes", r"D:\\photo"]
    index_dir = paths_section.get("index_dir", str(BASE_DIR / "data" / "index"))
    thumb_dir = paths_section.get("thumb_dir", str(BASE_DIR / "data" / "thumbs"))
    export_dir = paths_section.get("export_dir", str(BASE_DIR / "data" / "export"))

    if isolated:
        if db.database == "photo_search" or not paths_section.get("photo_roots", "").strip():
            raise RuntimeError("v2不得使用生产数据库或默认照片根目录")
        original = _load_parser(BASE_DIR / "db2.ini")
        if original.has_section("paths"):
            for key, value in [("index_dir", index_dir), ("thumb_dir", thumb_dir), ("export_dir", export_dir)]:
                previous = original["paths"].get(key, "")
                if previous and Path(previous).resolve() == Path(value).resolve():
                    raise RuntimeError("v2缓存或索引尚未隔离: " + key)
        if str(paths_section.get("source_read_only", "false")).lower() != "true":
            raise RuntimeError("v2当前使用源照片只读模式，请设置source_read_only=true")

    paths = PathsConfig(
        photo_roots=photo_roots,
        index_dir=index_dir,
        thumb_dir=thumb_dir,
        export_dir=export_dir,
        source_read_only=str(paths_section.get("source_read_only", "false")).lower() == "true",
    )

    face = FaceConfig(
        engine=face_section.get("engine", "insightface"),
        use_gpu=str(face_section.get("use_gpu", "true")).lower() == "true",
        model_name=face_section.get("model_name", "antelopev2"),
        embedding_dim=int(face_section.get("embedding_dim", 512)),
    )

    vision = VisionConfig(
        enabled=str(vision_section.get("enabled", "true")).lower() == "true",
        model_name=vision_section.get("model_name", "ViT-B-32"),
        pretrained=vision_section.get("pretrained", "openai"),
        text_model=vision_section.get("text_model", ""),
        embedding_dim=int(vision_section.get("embedding_dim", 512)),
    )

    index = IndexConfig(
        backend=index_section.get("backend", "faiss"),
        index_type=index_section.get("index_type", "hnsw"),
        nlist=int(index_section.get("nlist", 4096)),
        pq_m=int(index_section.get("pq_m", 64)),
        hnsw_m=int(index_section.get("hnsw_m", 32)),
    )

    scan = ScanConfig(
        scan_idle_only=str(scan_section.get("scan_idle_only", "true")).lower() == "true",
        idle_minutes=int(scan_section.get("idle_minutes", 10)),
        cpu_limit=int(scan_section.get("cpu_limit", 40)),
        gpu_limit=int(scan_section.get("gpu_limit", 30)),
        io_limit=int(scan_section.get("io_limit", 60)),
        scan_batch_size=int(scan_section.get("scan_batch_size", 100)),
    )

    port_env = os.getenv("PHOTO_SEARCH_PORT")
    server = ServerConfig(port=int(port_env) if port_env else int(parser.get("server", "port", fallback="5091" if isolated else "5090")))
    auth = AuthConfig(
        cookie_name=auth_section.get("cookie_name", "photo_search_v2_auth" if isolated else "photo_search_auth"),
        password=auth_section.get("password", ""),
        session_secret=auth_section.get("session_secret", auth_section.get("password", "")),
        policies_json=auth_section.get("policies_json", str(BASE_DIR / "config" / "auth_policies.json")),
    )

    settings = Settings(
        db=db,
        paths=paths,
        face=face,
        vision=vision,
        index=index,
        scan=scan,
        server=server,
        auth=auth,
        config_path=str(config_path),
    )

    for d in (settings.paths.index_dir, settings.paths.thumb_dir, settings.paths.export_dir):
        Path(d).mkdir(parents=True, exist_ok=True)

    return settings


settings = load_settings()


