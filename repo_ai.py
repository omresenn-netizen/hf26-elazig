"""AI response caching and payment-history access for the API."""
import copy
import hashlib
import json
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import db

ROOT = Path(__file__).resolve().parent
_AI_CACHE = {}
_AI_CACHE_LOCK = threading.Lock()


def _as_dicts(rows):
    return [dict(row) for row in rows]


def _load_payment_history():
    path = ROOT / "data" / "payment_history.json"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as source:
        records = json.load(source)
    if not isinstance(records, list):
        raise ValueError("data/payment_history.json must contain a JSON array.")
    return [row for row in records if isinstance(row, dict)]


def get_payment_history(vkn, limit=24):
    getter = getattr(db, "get_payment_history", None)
    if callable(getter):
        records = _as_dicts(getter(vkn, limit=limit) or [])
    else:
        records = [
            row for row in _load_payment_history()
            if str(row.get("company_vkn", "")) == str(vkn)
        ]
    records.sort(
        key=lambda row: (str(row.get("due_date") or ""), str(row.get("invoice_no") or "")),
        reverse=True,
    )
    return records[:limit]


def payment_stats(vkn):
    getter = getattr(db, "payment_stats", None)
    if callable(getter):
        stats = getter(vkn)
        if stats is not None:
            supplied = dict(stats)
            return {
                "invoice_count": supplied.get("invoice_count", 0),
                "on_time_ratio": supplied.get("on_time_ratio", 0.0),
                "avg_days_late": supplied.get("avg_days_late", 0.0),
                "max_days_late": supplied.get("max_days_late", 0),
                "volume_12m": supplied.get("volume_12m", 0.0),
            }

    records = _load_payment_history()
    rows = [
        row for row in records
        if str(row.get("company_vkn", "")) == str(vkn)
    ]
    late_days = [int(row.get("days_late") or 0) for row in rows]
    cutoff = date.today() - timedelta(days=365)
    volume_12m = 0.0
    for row in rows:
        try:
            due_date = date.fromisoformat(str(row.get("due_date", ""))[:10])
        except ValueError:
            continue
        if due_date >= cutoff:
            try:
                volume_12m += float(row.get("amount") or 0)
            except (TypeError, ValueError):
                continue

    return {
        "invoice_count": len(rows),
        "on_time_ratio": (
            sum(days <= 0 for days in late_days) / len(late_days) if late_days else 0.0
        ),
        "avg_days_late": sum(late_days) / len(late_days) if late_days else 0.0,
        "max_days_late": max(late_days, default=0),
        "volume_12m": round(volume_12m, 2),
    }


def cached_ai_result(namespace, object_id, content, generate):
    serialized = json.dumps(
        {"model": "gemma4", "content": content},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    content_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    cache_key = (namespace, str(object_id), content_hash)
    with _AI_CACHE_LOCK:
        cached = _AI_CACHE.get(cache_key)
        if cached is not None:
            return copy.deepcopy(cached)

    result = generate()
    if isinstance(result, dict):
        response = dict(result)
    else:
        response = {"result": result}
    response.setdefault("model", "gemma4")
    response.setdefault("generated_at", datetime.now(timezone.utc).isoformat())

    with _AI_CACHE_LOCK:
        for key in list(_AI_CACHE):
            if key[:2] == cache_key[:2] and key != cache_key:
                del _AI_CACHE[key]
        _AI_CACHE[cache_key] = copy.deepcopy(response)
    return response


def clear_ai_cache():
    with _AI_CACHE_LOCK:
        _AI_CACHE.clear()
