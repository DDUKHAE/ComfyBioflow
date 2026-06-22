"""
llm_runner.py — Async LLM runner for Biopython workflow generation.
"""
from __future__ import annotations
import asyncio
import uuid

from llm_core import exec_log, workflow_history
from llm_core.biopython_comfy_adapter import load_registry
from llm_core.biopython_prompts import get_biopython_workflow_prompt
from llm_core.llm_adapters import get_adapter
from llm_core.llm_contracts import LLMContractError, parse_and_validate_llm_output
from llm_core.workflow_guidance import (
    classify_intent,
    get_template_for_intent,
    normalize_workflow_spec,
    repair_workflow_spec,
    score_workflow_against_template,
)

# Active jobs: job_id -> asyncio.Task
active_jobs: dict[str, asyncio.Task] = {}
VALID_MODES = {"free", "normalized", "hybrid"}




def normalize_mode(mode: str | None) -> str:
    value = (mode or "").strip().lower()
    return value if value in VALID_MODES else "hybrid"


def create_job_id() -> str:
    return str(uuid.uuid4())


def cancel_job(job_id: str) -> bool:
    if job_id in active_jobs:
        active_jobs[job_id].cancel()
        del active_jobs[job_id]
        return True
    return False


async def _run_with_tracking(job_id: str, coro):
    task = asyncio.current_task()
    active_jobs[job_id] = task
    try:
        return await coro
    finally:
        active_jobs.pop(job_id, None)


async def generate_biopython_workflow(
    provider: str,
    goal: str,
    input_path: str = "",
    output_dir: str = "./output",
    job_id: str | None = None,
    model: str | None = None,
    mode: str = "hybrid",
) -> dict:
    if not job_id:
        job_id = create_job_id()

    mode = normalize_mode(mode)

    exec_log.clear()
    exec_log.write("INFO", f"Provider: {provider}" + (f"  |  Model: {model}" if model else ""))
    exec_log.write("INFO", f"Mode: {mode}")
    exec_log.write("INFO", f"Goal: {goal[:120]}{'…' if len(goal) > 120 else ''}")

    similar = workflow_history.find_similar(goal, limit=1)
    similar_workflow = similar[0] if similar else None
    if similar_workflow:
        exec_log.write(
            "INFO",
            "Similar workflow found: "
            f"{similar_workflow.get('query', '')[:100]} "
            f"(score {similar_workflow.get('similarity', 0):.2f}); adapting it for this request",
        )

    prompt = get_biopython_workflow_prompt(goal, input_path, output_dir, similar_workflow=similar_workflow)
    adapter = get_adapter(provider)
    registry = load_registry()

    async def _run() -> dict:
        import inspect

        sig = inspect.signature(adapter.generate)
        kwargs: dict = {"expected_type": "biopython_workflow_spec"}
        if "model" in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        ):
            kwargs["model"] = model

        exec_log.write("INFO", "Sending request to LLM...")
        try:
            raw = await adapter.generate(prompt, **kwargs)
            _, raw_spec = parse_and_validate_llm_output(raw, expected_type="biopython_workflow_spec")
            exec_log.write(
                "INFO",
                f"Raw spec parsed: {len(raw_spec.get('nodes', []))} node(s), {len(raw_spec.get('edges', []))} edge(s)",
            )

            normalized_spec = normalize_workflow_spec(raw_spec, registry)
            exec_log.write(
                "INFO",
                f"Normalized spec: {len(normalized_spec.get('nodes', []))} node(s), {len(normalized_spec.get('edges', []))} edge(s)",
            )

            intent = classify_intent(goal)
            template = get_template_for_intent(intent)
            template_id = template.get("template_id", "") if template else ""
            exec_log.write("INFO", f"Intent classified: {intent}")
            if template_id:
                exec_log.write("INFO", f"Template selected: {template_id}")

            equivalence_score = 0.0
            repair_applied = False
            repair_summary: list[str] = []
            final_spec = raw_spec if mode == "free" else normalized_spec

            if template:
                initial_eval = score_workflow_against_template(normalized_spec, template)
                equivalence_score = initial_eval["score"]
                exec_log.write("INFO", f"Equivalence score: {equivalence_score:.2f}")
                if mode == "hybrid":
                    repaired_spec, repair_meta = repair_workflow_spec(normalized_spec, template, registry)
                    final_spec = repaired_spec
                    repair_applied = repair_meta.get("repair_applied", False)
                    repair_summary = repair_meta.get("repair_summary", [])
                    equivalence_score = repair_meta.get("equivalence_score", equivalence_score)
                    if repair_applied:
                        exec_log.write("INFO", f"Repair applied: {'; '.join(repair_summary)}")
            elif mode != "free":
                final_spec = normalized_spec

            if mode == "free":
                final_spec = raw_spec

            return {
                "raw_spec": raw_spec,
                "normalized_spec": normalized_spec,
                "final_spec": final_spec,
                "intent": intent,
                "template_id": template_id,
                "equivalence_score": equivalence_score,
                "repair_applied": repair_applied,
                "repair_summary": repair_summary,
                "mode": mode,
            }
        except LLMContractError as exc:
            exec_log.write("ERROR", f"LLM contract error [{exc.code}]: {exc.message}")
            raise
        except Exception as exc:
            exec_log.write("ERROR", f"Unexpected error: {exc}")
            raise

    return await _run_with_tracking(job_id, _run())
