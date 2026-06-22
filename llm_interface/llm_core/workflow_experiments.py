from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from llm_core import workflow_history
from llm_core.llm_runner import generate_biopython_workflow


QueryInput = str | dict[str, Any]


def _spec_signature(spec: dict[str, Any] | None) -> str:
    if not spec:
        return ""
    nodes = sorted(
        (
            {"id": node.get("id", ""), "class_type": node.get("class_type", "")}
            for node in spec.get("nodes", [])
        ),
        key=lambda item: (item["id"], item["class_type"]),
    )
    edges = sorted(
        (
            {"from": edge.get("from", ""), "to": edge.get("to", "")}
            for edge in spec.get("edges", [])
        ),
        key=lambda item: (item["from"], item["to"]),
    )
    return json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True, ensure_ascii=False)


def _normalize_query_input(item: QueryInput) -> dict[str, Any]:
    if isinstance(item, str):
        query = item.strip()
        return {
            "query": query,
            "expected_intent": "",
            "expected_template_id": "",
            "label": query,
        }
    query = str(item.get("query") or "").strip()
    label = str(item.get("label") or query).strip() or query
    return {
        "query": query,
        "expected_intent": str(item.get("expected_intent") or "").strip(),
        "expected_template_id": str(item.get("expected_template_id") or "").strip(),
        "label": label,
    }


async def run_experiment_batch(
    queries: list[QueryInput],
    providers: list[str],
    modes: list[str],
    *,
    models: dict[str, str] | None = None,
    repeats: int = 1,
    input_path: str = "",
    output_dir: str = "./output",
    persist_history: bool = False,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    models = models or {}

    for query_item in queries:
        query_meta = _normalize_query_input(query_item)
        query = query_meta["query"]
        if not query:
            continue
        for provider in providers:
            for mode in modes:
                for run_index in range(1, max(1, repeats) + 1):
                    model = models.get(provider)
                    record: dict[str, Any] = {
                        "query": query,
                        "query_label": query_meta["label"],
                        "normalized_query": workflow_history.normalize_query(query),
                        "expected_intent": query_meta["expected_intent"],
                        "expected_template_id": query_meta["expected_template_id"],
                        "intent_match": None,
                        "template_match": None,
                        "provider": provider,
                        "model": model or "",
                        "mode": mode,
                        "run_index": run_index,
                        "status": "error",
                        "workflow_json": None,
                        "raw_workflow_spec": None,
                        "normalized_workflow_spec": None,
                        "final_workflow_spec": None,
                        "intent": "",
                        "template_id": "",
                        "equivalence_score": 0.0,
                        "repair_applied": False,
                        "repair_summary": [],
                        "repair_actions": [],
                        "error_message": "",
                    }
                    try:
                        result = await generate_biopython_workflow(
                            provider,
                            query,
                            input_path,
                            output_dir,
                            model=model,
                            mode=mode,
                        )
                        final_spec = result.get("final_spec")
                        intent = result.get("intent", "")
                        template_id = result.get("template_id", "")
                        expected_intent = record.get("expected_intent") or ""
                        expected_template_id = record.get("expected_template_id") or ""
                        record.update({
                            "status": "success",
                            "raw_workflow_spec": result.get("raw_spec"),
                            "normalized_workflow_spec": result.get("normalized_spec"),
                            "final_workflow_spec": final_spec,
                            "workflow_spec": final_spec,
                            "intent": intent,
                            "template_id": template_id,
                            "intent_match": (intent == expected_intent) if expected_intent else None,
                            "template_match": (template_id == expected_template_id) if expected_template_id else None,
                            "equivalence_score": result.get("equivalence_score", 0.0),
                            "repair_applied": result.get("repair_applied", False),
                            "repair_summary": result.get("repair_summary", []),
                            "repair_actions": result.get("repair_actions", []),
                            "node_count": len(final_spec.get("nodes", [])) if final_spec else 0,
                            "edge_count": len(final_spec.get("edges", [])) if final_spec else 0,
                        })
                    except Exception as exc:
                        record["error_message"] = str(exc)

                    if persist_history:
                        workflow_history.append_record(record)
                    records.append(record)

    return records


def run_experiment_batch_sync(*args, **kwargs) -> list[dict[str, Any]]:
    return asyncio.run(run_experiment_batch(*args, **kwargs))


def compute_inter_model_agreement(records: list[dict[str, Any]]) -> float:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for record in records:
        query = record.get("normalized_query") or record.get("query") or ""
        mode = record.get("mode") or ""
        signature = _spec_signature(record.get("final_workflow_spec") or record.get("workflow_spec"))
        if not query or not signature:
            continue
        grouped[(query, mode)].append(signature)

    total_pairs = 0
    matching_pairs = 0
    for signatures in grouped.values():
        n = len(signatures)
        if n < 2:
            continue
        for i in range(n):
            for j in range(i + 1, n):
                total_pairs += 1
                if signatures[i] == signatures[j]:
                    matching_pairs += 1
    if total_pairs == 0:
        return 0.0
    return round(matching_pairs / total_pairs, 4)


def summarize_mode_metrics(records: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    by_mode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_mode[record.get("mode") or "unknown"].append(record)

    summary: dict[str, dict[str, float | int]] = {}
    for mode, items in by_mode.items():
        total = len(items)
        valid_json = sum(1 for item in items if item.get("raw_workflow_spec") or item.get("workflow_spec"))
        executable = sum(1 for item in items if item.get("status") == "success" and item.get("workflow_json"))
        repairs = sum(1 for item in items if item.get("repair_applied"))
        eq_scores = [float(item.get("equivalence_score", 0.0) or 0.0) for item in items if item.get("equivalence_score") is not None]
        intent_checks = [item.get("intent_match") for item in items if item.get("intent_match") is not None]
        template_checks = [item.get("template_match") for item in items if item.get("template_match") is not None]
        summary[mode] = {
            "record_count": total,
            "valid_json_rate": round(valid_json / total, 4) if total else 0.0,
            "executable_workflow_rate": round(executable / total, 4) if total else 0.0,
            "mean_equivalence_score": round(sum(eq_scores) / len(eq_scores), 4) if eq_scores else 0.0,
            "repair_frequency": round(repairs / total, 4) if total else 0.0,
            "intent_match_rate": round(sum(1 for item in intent_checks if item) / len(intent_checks), 4) if intent_checks else 0.0,
            "template_match_rate": round(sum(1 for item in template_checks if item) / len(template_checks), 4) if template_checks else 0.0,
        }

    summary["overall"] = {
        "record_count": len(records),
        "inter_model_agreement": compute_inter_model_agreement(records),
    }
    return summary


def summarize_provider_mode_metrics(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, float | int]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        provider = record.get("provider") or "unknown"
        mode = record.get("mode") or "unknown"
        grouped[provider][mode].append(record)

    summary: dict[str, dict[str, dict[str, float | int]]] = {}
    for provider, by_mode in grouped.items():
        summary[provider] = {}
        for mode, items in by_mode.items():
            mode_summary = summarize_mode_metrics(items).get(mode, {})
            summary[provider][mode] = mode_summary
    return summary


def render_experiment_report_markdown(
    records: list[dict[str, Any]],
    *,
    title: str = "Workflow Generation Experiment Report",
) -> str:
    mode_summary = summarize_mode_metrics(records)
    provider_summary = summarize_provider_mode_metrics(records)
    lines = [f"# {title}", ""]

    lines.extend([
        "## Overall",
        "",
        f"- record_count: {mode_summary['overall']['record_count']}",
        f"- inter_model_agreement: {mode_summary['overall']['inter_model_agreement']:.4f}",
        "",
        "## By Mode",
        "",
        "| mode | records | valid_json_rate | executable_workflow_rate | mean_equivalence_score | repair_frequency | intent_match_rate | template_match_rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for mode in sorted(key for key in mode_summary.keys() if key != "overall"):
        row = mode_summary[mode]
        lines.append(
            f"| {mode} | {row['record_count']} | {row['valid_json_rate']:.4f} | {row['executable_workflow_rate']:.4f} | {row['mean_equivalence_score']:.4f} | {row['repair_frequency']:.4f} | {row['intent_match_rate']:.4f} | {row['template_match_rate']:.4f} |"
        )

    lines.extend([
        "",
        "## By Provider and Mode",
        "",
        "| provider | mode | records | valid_json_rate | executable_workflow_rate | mean_equivalence_score | repair_frequency | intent_match_rate | template_match_rate |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for provider in sorted(provider_summary):
        for mode in sorted(provider_summary[provider]):
            row = provider_summary[provider][mode]
            lines.append(
                f"| {provider} | {mode} | {row['record_count']} | {row['valid_json_rate']:.4f} | {row['executable_workflow_rate']:.4f} | {row['mean_equivalence_score']:.4f} | {row['repair_frequency']:.4f} | {row['intent_match_rate']:.4f} | {row['template_match_rate']:.4f} |"
            )

    lines.extend([
        "",
        "## Records",
        "",
        "| label | query | provider | model | mode | run | status | expected_intent | intent | expected_template_id | template_id | intent_match | template_match | equivalence_score | repair_applied | error_message |",
        "|---|---|---|---|---|---:|---|---|---|---|---|---|---|---:|---|---|",
    ])
    for record in records:
        lines.append(
            "| {query_label} | {query} | {provider} | {model} | {mode} | {run_index} | {status} | {expected_intent} | {intent} | {expected_template_id} | {template_id} | {intent_match} | {template_match} | {equivalence_score:.4f} | {repair_applied} | {error_message} |".format(
                query_label=(record.get("query_label") or record.get("query") or "").replace("|", "\\|"),
                query=(record.get("query") or "").replace("|", "\\|"),
                provider=record.get("provider") or "",
                model=record.get("model") or "",
                mode=record.get("mode") or "",
                run_index=record.get("run_index") or 0,
                status=record.get("status") or "",
                expected_intent=record.get("expected_intent") or "",
                intent=record.get("intent") or "",
                expected_template_id=record.get("expected_template_id") or "",
                template_id=record.get("template_id") or "",
                intent_match="" if record.get("intent_match") is None else str(bool(record.get("intent_match"))).lower(),
                template_match="" if record.get("template_match") is None else str(bool(record.get("template_match"))).lower(),
                equivalence_score=float(record.get("equivalence_score", 0.0) or 0.0),
                repair_applied=str(bool(record.get("repair_applied", False))).lower(),
                error_message=(record.get("error_message") or "").replace("|", "\\|"),
            )
        )
    return "\n".join(lines) + "\n"


def write_experiment_report(
    output_path: str | Path,
    records: list[dict[str, Any]],
    *,
    title: str = "Workflow Generation Experiment Report",
) -> Path:
    out = Path(output_path)
    out.write_text(render_experiment_report_markdown(records, title=title), encoding="utf-8")
    return out
