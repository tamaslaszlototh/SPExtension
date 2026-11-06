"""Atomic JSON files: write a temp file next to the target, then ``os.replace``."""

import json
import os
import shutil
from pathlib import Path


def dumps(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_text_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_json_atomic(path, data):
    write_text_atomic(path, dumps(data))


def copy_atomic(source, target):
    target = Path(target)
    tmp = target.with_name(target.name + ".tmp")
    shutil.copyfile(source, tmp)
    os.replace(tmp, target)
