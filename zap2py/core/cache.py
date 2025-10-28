from pathlib import Path
import gzip, io, json

class Cache:
    def __init__(self, base: Path):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.base / name

    def write_gz_bytes(self, path: Path, data: bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(gzip.compress(data))

    def write_gz_json(self, path: Path, obj):
        data = json.dumps(obj).encode("utf-8")
        self.write_gz_bytes(path, data)

    def read_gz_json(self, path: Path):
        with gzip.open(path, "rb") as f:
            try:
                return json.load(io.TextIOWrapper(f, encoding="utf-8"))
            except Exception:
                raw = f.read().decode("utf-8", errors="ignore")
                import json as _json
                return _json.loads(raw)
