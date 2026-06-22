from __future__ import annotations

import datetime
import json
import re
import uuid
from pathlib import Path
from typing import Any

from llm_core.paths import get_comfyui_output_dir

_HISTORY_DIRNAME = "comfybio_biopython"
_HISTORY_FILENAME = "workflow_history.jsonl"
_MAX_QUERY_RESULTS = 20
_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "by", "for", "from", "in", "into",
    "is", "of", "on", "or", "the", "to", "use", "using", "with", "workflow",
    "analysis", "analyze", "create", "generate", "make", "run",
}


def history_path() -> Path:
    root = get_comfyui_output_dir() / _HISTORY_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root / _HISTORY_FILENAME


def normalize_query(query: str) -> str:
    return " ".join(_tokens(query))


def _tokens(text: str) -> list[str]:
    return [tok for tok in _TOKEN_RE.findall((text or "").lower()) if tok not in _STOP_WORDS]


def _score(query: str, candidate_query: str) -> float:
    q_tokens = set(_tokens(query))
    c_tokens = set(_tokens(candidate_query))
    if not q_tokens or not c_tokens:
        return 0.0
    overlap = q_tokens & c_tokens
    union = q_tokens | c_tokens
    jaccard = len(overlap) / len(union)
    coverage = len(overlap) / min(len(q_tokens), len(c_tokens))
    return round((jaccard * 0.6) + (coverage * 0.4), 4)


def append_record(record: dict[str, Any]) -> dict[str, Any]:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    final_spec = record.get("final_workflow_spec") or record.get("workflow_spec")
    saved = {
        "id": record.get("id") or str(uuid.uuid4()),
        "created_at": record.get("created_at") or now,
        "query": record.get("query") or "",
        "normalized_query": normalize_query(record.get("query") or ""),
        "input_path": record.get("input_path") or "",
        "output_dir": record.get("output_dir") or "",
        "provider": record.get("provider") or "",
        "model": record.get("model") or "",
        "mode": record.get("mode") or "",
        "status": record.get("status") or "unknown",
        "workflow_json": record.get("workflow_json"),
        "workflow_spec": final_spec,
        "raw_workflow_spec": record.get("raw_workflow_spec"),
        "normalized_workflow_spec": record.get("normalized_workflow_spec"),
        "final_workflow_spec": final_spec,
        "intent": record.get("intent") or "",
        "template_id": record.get("template_id") or "",
        "equivalence_score": record.get("equivalence_score") or 0.0,
        "repair_applied": bool(record.get("repair_applied", False)),
        "repair_summary": record.get("repair_summary") or [],
        "repair_actions": record.get("repair_actions") or [],
        "node_count": record.get("node_count") or 0,
        "edge_count": record.get("edge_count") or 0,
        "error_message": record.get("error_message") or "",
    }
    path = history_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(saved, ensure_ascii=False, separators=(",", ":")) + "\n")
    return saved


def iter_records() -> list[dict[str, Any]]:
    path = history_path()
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def list_recent(limit: int = _MAX_QUERY_RESULTS, include_workflow: bool = False) -> list[dict[str, Any]]:
    records = list(reversed(iter_records()))[:max(1, limit)]
    if include_workflow:
        return records
    return [_summary(r) for r in records]


def get_record(record_id: str) -> dict[str, Any] | None:
    for record in reversed(iter_records()):
        if record.get("id") == record_id:
            return record
    return None


def find_similar(query: str, limit: int = 3, min_score: float = 0.42) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for record in iter_records():
        if record.get("status") != "success":
            continue
        if not record.get("final_workflow_spec") and not record.get("workflow_spec") and not record.get("workflow_json"):
            continue
        score = _score(query, record.get("query") or "")
        if score >= min_score:
            item = dict(record)
            item["similarity"] = score
            matches.append(item)
    matches.sort(key=lambda r: (r.get("similarity", 0), r.get("created_at", "")), reverse=True)
    return matches[:max(1, limit)]


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "created_at": record.get("created_at"),
        "query": record.get("query"),
        "input_path": record.get("input_path"),
        "output_dir": record.get("output_dir"),
        "provider": record.get("provider"),
        "model": record.get("model"),
        "mode": record.get("mode"),
        "intent": record.get("intent"),
        "template_id": record.get("template_id"),
        "equivalence_score": record.get("equivalence_score"),
        "repair_applied": record.get("repair_applied"),
        "repair_actions": record.get("repair_actions"),
        "status": record.get("status"),
        "node_count": record.get("node_count"),
        "edge_count": record.get("edge_count"),
        "error_message": record.get("error_message"),
    }
