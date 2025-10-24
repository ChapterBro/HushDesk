from __future__ import annotations
import json, os
from hashlib import sha256
from pathlib import Path
from typing import List, Dict
from hushdesk.core.privacy_runtime import ensure_private_dir, secure_open_for_write

def write_records(path: str, records: List[dict], meta: Dict) -> str:
    p = Path(path)
    ensure_private_dir(str(p.parent))
    blob = {"meta": meta, "records": records}
    data = json.dumps(blob, indent=2).encode("utf-8")
    fd = secure_open_for_write(str(p))
    with os.fdopen(fd, "wb", closefd=True) as fh:
        fh.write(data)
    return str(p)

def file_sha256(path: str) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()
