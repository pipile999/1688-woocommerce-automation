"""Exact, non-semantic cache for verified 1688 processing artifacts.

Cache identity is deliberately content-addressed.  There is no similarity,
embedding, fuzzy, or GPTCache lookup in this module.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".codex" / "skills" / "1688-woocommerce-profit-import"
EVENTS_PATH = ROOT / "output" / "strict-cache-events.jsonl"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def rules_version(skill_dir: Path = SKILL_DIR) -> str:
    """Hash the active Skill and rules, so any rule change invalidates cache."""
    digest = hashlib.sha256()
    paths = [skill_dir / "SKILL.md", *sorted((skill_dir / "rules").glob("*.md"))]
    for path in paths:
        digest.update(path.relative_to(skill_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def specification_hash(source: dict) -> str:
    """Hash supplier specification text and verified SKU option text."""
    payload = {
        "title": source.get("title"),
        "description": source.get("description"),
        "attributes": source.get("attributes"),
        "skus": [
            {
                "attributes": sku.get("attributes"),
                "spec_id": sku.get("spec_id"),
                "variation_id": sku.get("variation_id"),
            }
            for sku in source.get("skus", [])
        ],
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def cache_key(*, offer_id: str, source_url: str, image_hash: str, spec_hash: str, rules_ver: str) -> str:
    payload = {
        "offer_id": str(offer_id),
        "source_url": str(source_url),
        "image_hash": str(image_hash),
        "spec_hash": str(spec_hash),
        "rules_version": str(rules_ver),
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


class StrictCache:
    """SQLite exact-match cache.  Lookup compares one complete key only."""

    def __init__(self, path: Path, events_path: Path = EVENTS_PATH):
        self.path = path
        self.events_path = events_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    offer_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    image_hash TEXT NOT NULL,
                    spec_hash TEXT NOT NULL,
                    rules_version TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS cache_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    offer_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _event(self, event: str, key: str, offer_id: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connection() as db:
            db.execute("INSERT INTO cache_events(event, cache_key, offer_id, created_at) VALUES(?,?,?,?)", (event, key, str(offer_id), timestamp))
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(_canonical({"event": event, "cache_key": key, "offer_id": str(offer_id), "created_at": timestamp}) + "\n")

    def lookup(self, *, key: str, offer_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT result_json FROM cache_entries WHERE cache_key = ? AND offer_id = ?", (key, str(offer_id))).fetchone()
        if row is None:
            self._event("CACHE_MISS", key, offer_id)
            return None
        self._event("CACHE_HIT", key, offer_id)
        return json.loads(row[0])


    def store(self, *, key: str, offer_id: str, source_url: str, image_hash: str, spec_hash: str, rules_ver: str, result: dict) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = _canonical(result)
        with self.connection() as db:
            db.execute(
                """INSERT INTO cache_entries(cache_key, offer_id, source_url, image_hash, spec_hash, rules_version, result_json, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(cache_key) DO UPDATE SET result_json=excluded.result_json, updated_at=excluded.updated_at""",
                (key, str(offer_id), source_url, image_hash, spec_hash, rules_ver, payload, timestamp, timestamp),
            )


def product_identity(source: dict, raw_dir: Path, version: str) -> dict:
    images = [(p.name, hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(raw_dir.iterdir()) if p.is_file()]
    return dict(offer_id=str(source['offer_id']), source_url=source['source_url'],
                image_hash=hashlib.sha256(_canonical(images).encode()).hexdigest(),
                spec_hash=specification_hash(source), rules_ver=version)


def validate_prices(source: dict) -> list[dict]:
    """Always read current source prices; this intentionally bypasses cache."""
    from decimal import Decimal, ROUND_HALF_UP

    checked = []
    for sku in source.get("skus", []):
        expected = (Decimal(str(sku["source_price"])) / Decimal("0.7") / Decimal("6.7")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        checked.append({"sku": str(sku.get("sku")), "source_price": str(sku["source_price"]), "sale_price": str(expected)})
    return checked
