from __future__ import annotations

from pathlib import Path
from typing import Any
import json


DEFAULT_ENCODING = "utf-8"
READ_ENCODING = "utf-8-sig"


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding=READ_ENCODING)


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding=DEFAULT_ENCODING, newline="\n")


def read_json(path: str | Path) -> Any:
    return json.loads(read_text(path))


def write_json(path: str | Path, data: Any, *, indent: int = 2) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=indent))


def read_yaml_text(path: str | Path) -> str:
    return read_text(path)
