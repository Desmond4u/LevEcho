"""Small JSON I/O helpers used by local scripts and the Streamlit app."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path, default: Any = None) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        return default
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, value: Any) -> None:
    """Write JSON atomically so a failed run cannot leave a partial snapshot."""

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = file_path.with_name(f"{file_path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(file_path)
