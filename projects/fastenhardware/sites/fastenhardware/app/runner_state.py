"""Small atomic, content-addressed primitives shared by the local runner."""
from __future__ import annotations

import hashlib
import copy
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path, default=None):
    from .site_guard import contained
    contained(path)
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def save(path, value):
    from .site_guard import contained
    contained(path)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class ReviewRequired(Exception):
    """A bounded product needs evidence, not a guessed PASS or an LLM call."""


class StageStore:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.path = self.folder / "checkpoint.json"
        self.state = read(self.path, {"version": 1, "stages": {}})

    def run(self, name, inputs, operation, *, fresh=False):
        key = digest(inputs)
        prior = self.state["stages"].get(name, {})
        if not fresh and prior.get("key") == key and prior.get("status") == "DONE":
            if all(Path(p).is_file() and file_hash(p) == h
                   for p, h in prior.get("artifact_hashes", {}).items()):
                return copy.deepcopy(prior["result"]), "CACHE_HIT"
        result = operation()
        artifacts = result.get("artifacts", []) if isinstance(result, dict) else []
        self.state["stages"][name] = dict(key=key, status="DONE", timestamp=now(), result=result,
                                         artifact_hashes={str(p): file_hash(p) for p in artifacts})
        save(self.path, self.state)
        return copy.deepcopy(result), "CACHE_MISS"


class ReviewQueue:
    def __init__(self, path):
        self.path = Path(path)
        self.items = read(path, [])

    def add(self, offer, stage, reason, evidence=None):
        item = dict(offer_id=str(offer), stage=stage, reason=str(reason), evidence=evidence or {})
        key = digest(item)
        if not any(x["key"] == key for x in self.items):
            self.items.append(dict(key=key, status="PENDING", created_at=now(), **item))
            save(self.path, self.items)
