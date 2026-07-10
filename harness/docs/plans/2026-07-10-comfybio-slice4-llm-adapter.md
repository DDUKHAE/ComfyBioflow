# ComfyBIO Slice 4 — Claude LLM Brief Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Claude-backed `AnalysisBrief` extractor that replaces the deterministic `parse_prompt` call in the two server handlers, with the deterministic parser as a graceful fallback — feeding the existing registry/TSR planner unchanged.

**Architecture:** New additive package `bioflow_harness/llm/` (`claude_extractor.py` + `brief_extractor.py`). The Claude call uses `output_config.format` structured outputs, is reached through an `extract_brief` orchestrator that falls back to `parse_prompt` on any failure, and is wired into `handlers.py` by swapping two call-sites. Everything else (planner, builder, nodes, registry, DTOs, `AnalysisBrief`, `parse_prompt`) is untouched.

**Tech Stack:** Python, `anthropic` SDK (optional, lazy-imported), pytest. `output_config.format` structured outputs on `claude-opus-4-8` / `claude-sonnet-5` / `claude-haiku-4-5`.

## Global Constraints

- **Minimize changes to the pre-built structure.** New code is additive under `bioflow_harness/llm/`. Do NOT modify `parser/prompt_parser.py`, `planner/*`, `comfy/*`, `models/*`, the registry YAML, `nodes/*`, or `server/dto.py`. The only edits to existing files are: two call-sites + the import in `server/handlers.py`, and the `PROVIDER_MODELS.claude` list in `web/js/comfybio_panel.js`.
- **`anthropic` is optional** — import it lazily *inside* a method, never at module top. Importing `bioflow_harness` and running the full test suite must not require `anthropic` to be installed.
- **No real network in tests** — every test injects a fake `client`; no test calls the live API.
- **Fallback is total** — any failure in the Claude path (missing SDK, missing credential, API error, refusal, malformed output) is caught and degrades to `parse_prompt`. A route must always get a usable brief.
- **`AnalysisBrief` contract is fixed** — fields: `analysis_type: str`, `domain: str`, `input_assets: list[str]`, `organism: str | None`, `expected_outputs: list[str]`, `constraints: list[str] = []`, `preferred_tools: list[str] = []`, `confidence_notes: list[str] = []`, `submission_source: str = "text_prompt"`, `data_characteristics: dict[str, str] = {}`.
- **pytest config** (already in `pyproject.toml`): `pythonpath = ["harness/src", "."]`, `testpaths = ["tests"]`. Run tests from the repo root `/home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow`.
- **Commit identity:** commit as `ddukhae <dongjoon69@gmail.com>` (`git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com`). End commit messages with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

---

### Task 1: Claude extractor module

**Files:**
- Create: `harness/src/bioflow_harness/llm/__init__.py` (empty)
- Create: `harness/src/bioflow_harness/llm/claude_extractor.py`
- Test: `tests/test_comfybio_llm_adapter.py`

**Interfaces:**
- Produces: `ClaudeBriefExtractor(model, *, client=None)` with `.extract(request_text) -> AnalysisBrief`; module constants `DEFAULT_MODEL = "claude-opus-4-8"`, `BRIEF_SCHEMA`, `SYSTEM_PROMPT`; exception `BriefExtractionError(RuntimeError)`. Task 2 imports `ClaudeBriefExtractor` and `DEFAULT_MODEL`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_comfybio_llm_adapter.py`:
```python
import json
from dataclasses import dataclass

import pytest

from bioflow_harness.llm.claude_extractor import (
    BriefExtractionError,
    ClaudeBriefExtractor,
    DEFAULT_MODEL,
)
from bioflow_harness.models.prompt_contract import AnalysisBrief


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Response:
    content: list
    stop_reason: str = "end_turn"


class _FakeClient:
    """Stands in for anthropic.Anthropic(); client.messages.create(...)."""

    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc is not None:
            raise self._exc
        return self._response


_VALID_PAYLOAD = {
    "analysis_type": "differential_expression",
    "domain": "bulk_rna_seq",
    "input_assets": ["fastq", "sample_metadata"],
    "organism": "Homo sapiens",
    "expected_outputs": ["salmon_quantification", "deseq2_results"],
    "constraints": [],
    "preferred_tools": ["salmon", "deseq2"],
    "data_characteristics": [{"key": "layout", "value": "paired"}],
}


def _ok_client(payload=None):
    body = json.dumps(payload or _VALID_PAYLOAD)
    return _FakeClient(response=_Response(content=[_Block(text=body)]))


def test_extract_parses_structured_response_into_brief():
    extractor = ClaudeBriefExtractor("claude-opus-4-8", client=_ok_client())
    brief = extractor.extract("Analyze this bulk RNA-seq FASTQ folder, human, treated vs control")
    assert isinstance(brief, AnalysisBrief)
    assert brief.domain == "bulk_rna_seq"
    assert brief.organism == "Homo sapiens"
    assert brief.input_assets == ["fastq", "sample_metadata"]
    assert brief.preferred_tools == ["salmon", "deseq2"]
    assert brief.data_characteristics == {"layout": "paired"}
    assert brief.submission_source == "text_prompt"


def test_empty_organism_maps_to_none():
    payload = dict(_VALID_PAYLOAD, organism="")
    extractor = ClaudeBriefExtractor("claude-opus-4-8", client=_ok_client(payload))
    brief = extractor.extract("some request")
    assert brief.organism is None


def test_default_model_used_when_blank():
    client = _ok_client()
    ClaudeBriefExtractor("", client=client).extract("x")
    assert client.calls[0]["model"] == DEFAULT_MODEL


def test_refusal_raises_extraction_error():
    client = _FakeClient(response=_Response(content=[], stop_reason="refusal"))
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", client=client).extract("x")


def test_malformed_json_raises_extraction_error():
    client = _FakeClient(response=_Response(content=[_Block(text="not json{")]))
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", client=client).extract("x")


def test_schema_invalid_payload_raises_extraction_error():
    client = _FakeClient(response=_Response(content=[_Block(text=json.dumps({"domain": "bulk_rna_seq"}))]))
    with pytest.raises(BriefExtractionError):
        ClaudeBriefExtractor("claude-opus-4-8", client=client).extract("x")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow && python -m pytest tests/test_comfybio_llm_adapter.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bioflow_harness.llm'`.

- [ ] **Step 3: Create the package marker**

Create `harness/src/bioflow_harness/llm/__init__.py` as an empty file.

- [ ] **Step 4: Write the implementation**

Create `harness/src/bioflow_harness/llm/claude_extractor.py`:
```python
from __future__ import annotations

import json

from bioflow_harness.models.prompt_contract import AnalysisBrief

DEFAULT_MODEL = "claude-opus-4-8"


class BriefExtractionError(RuntimeError):
    """Raised when Claude returns a refusal or an unusable payload."""


BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_type": {"type": "string"},
        "domain": {"type": "string", "enum": ["bulk_rna_seq", "scrna_seq", "unsupported"]},
        "input_assets": {"type": "array", "items": {"type": "string"}},
        "organism": {"type": "string"},
        "expected_outputs": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "preferred_tools": {"type": "array", "items": {"type": "string"}},
        "data_characteristics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "analysis_type",
        "domain",
        "input_assets",
        "organism",
        "expected_outputs",
        "constraints",
        "preferred_tools",
        "data_characteristics",
    ],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """You extract a structured bioinformatics analysis brief from a researcher's free-text request.

Supported domains:
- "bulk_rna_seq": bulk RNA sequencing (FASTQ reads, differential expression, salmon/DESeq2, etc.)
- "scrna_seq": single-cell RNA sequencing (10x, Cell Ranger, scanpy, clustering, UMAP, marker genes)
- "unsupported": anything that is neither of the above

Fields:
- analysis_type: short slug for the intent (e.g. "differential_expression", "single_cell_analysis", "workflow_generation")
- domain: one of the three values above
- input_assets: input data kinds mentioned (e.g. "fastq", "sample_metadata")
- organism: the species/genome if stated, else an empty string
- expected_outputs: artifacts wanted (e.g. "salmon_quantification", "deseq2_results", "visualization_artifacts", "report")
- constraints: any explicit constraints stated
- preferred_tools: tools named in the request
- data_characteristics: any stated properties as key/value pairs (e.g. key "layout", value "paired")

Classify domain as "unsupported" when the request is neither bulk nor single-cell RNA-seq."""


def _brief_from_payload(data: dict) -> AnalysisBrief:
    try:
        pairs = data["data_characteristics"]
        characteristics = {str(p["key"]): str(p["value"]) for p in pairs}
        return AnalysisBrief(
            analysis_type=str(data["analysis_type"]),
            domain=str(data["domain"]),
            input_assets=[str(x) for x in data["input_assets"]],
            organism=(str(data["organism"]) or None),
            expected_outputs=[str(x) for x in data["expected_outputs"]],
            constraints=[str(x) for x in data["constraints"]],
            preferred_tools=[str(x) for x in data["preferred_tools"]],
            data_characteristics=characteristics,
        )
    except (KeyError, TypeError) as exc:
        raise BriefExtractionError(f"Schema-invalid brief payload: {exc}") from exc


class ClaudeBriefExtractor:
    """Extracts an AnalysisBrief from free text via the Claude Messages API."""

    def __init__(self, model: str, *, client=None):
        self._model = model or DEFAULT_MODEL
        self._client = client

    def _resolve_client(self):
        if self._client is not None:
            return self._client
        import anthropic  # lazy; optional dependency

        return anthropic.Anthropic()

    def extract(self, request_text: str) -> AnalysisBrief:
        client = self._resolve_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": BRIEF_SCHEMA}},
            messages=[{"role": "user", "content": request_text}],
        )
        if getattr(response, "stop_reason", None) == "refusal":
            raise BriefExtractionError("Claude refused the extraction request")
        text = next(
            (b.text for b in response.content if getattr(b, "type", None) == "text"),
            None,
        )
        if text is None:
            raise BriefExtractionError("No text block in Claude response")
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise BriefExtractionError(f"Malformed JSON from Claude: {exc}") from exc
        return _brief_from_payload(data)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow && python -m pytest tests/test_comfybio_llm_adapter.py -q`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com add harness/src/bioflow_harness/llm/__init__.py harness/src/bioflow_harness/llm/claude_extractor.py tests/test_comfybio_llm_adapter.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add Claude brief extractor with structured outputs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Extraction orchestrator with fallback

**Files:**
- Create: `harness/src/bioflow_harness/llm/brief_extractor.py`
- Test: `tests/test_comfybio_llm_adapter.py` (append)

**Interfaces:**
- Consumes: `ClaudeBriefExtractor`, `DEFAULT_MODEL` from Task 1; `parse_prompt` from `bioflow_harness.parser.prompt_parser`; `AnalysisBrief` from `bioflow_harness.models.prompt_contract`.
- Produces: `BriefExtractor` Protocol; `ExtractionMeta(source, model, note)` frozen dataclass; `extract_brief(request_text, provider="codex", model="", *, client=None) -> tuple[AnalysisBrief, ExtractionMeta]`. Task 3 imports `extract_brief`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comfybio_llm_adapter.py`:
```python
from bioflow_harness.llm.brief_extractor import ExtractionMeta, extract_brief


def test_extract_brief_claude_success_annotates_provenance():
    brief, meta = extract_brief("bulk RNA-seq, human", provider="claude", client=_ok_client())
    assert meta.source == "claude"
    assert brief.domain == "bulk_rna_seq"
    assert any("claude" in note for note in brief.confidence_notes)


def test_extract_brief_falls_back_when_claude_raises():
    failing = _FakeClient(exc=RuntimeError("no credential"))
    brief, meta = extract_brief(
        "Analyze this bulk RNA-seq data with DESeq2",
        provider="claude",
        client=failing,
    )
    assert meta.source == "deterministic"
    assert brief.domain == "bulk_rna_seq"  # parse_prompt still classifies it
    assert any("deterministic" in note for note in brief.confidence_notes)


def test_extract_brief_non_claude_provider_uses_deterministic():
    brief, meta = extract_brief("Analyze bulk RNA-seq with DESeq2", provider="codex")
    assert meta.source == "deterministic"
    assert isinstance(meta, ExtractionMeta)
    assert any("not yet wired" in note for note in brief.confidence_notes)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow && python -m pytest tests/test_comfybio_llm_adapter.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bioflow_harness.llm.brief_extractor'`.

- [ ] **Step 3: Write the implementation**

Create `harness/src/bioflow_harness/llm/brief_extractor.py`:
```python
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Protocol

from bioflow_harness.llm.claude_extractor import DEFAULT_MODEL, ClaudeBriefExtractor
from bioflow_harness.models.prompt_contract import AnalysisBrief
from bioflow_harness.parser.prompt_parser import parse_prompt


class BriefExtractor(Protocol):
    def extract(self, request_text: str) -> AnalysisBrief: ...


@dataclass(frozen=True)
class ExtractionMeta:
    source: str
    model: str
    note: str


def _annotate(brief: AnalysisBrief, meta: "ExtractionMeta") -> AnalysisBrief:
    return dataclasses.replace(
        brief, confidence_notes=[*brief.confidence_notes, meta.note]
    )


def extract_brief(
    request_text: str,
    provider: str = "codex",
    model: str = "",
    *,
    client=None,
) -> tuple[AnalysisBrief, ExtractionMeta]:
    if provider == "claude":
        chosen = model or DEFAULT_MODEL
        try:
            brief = ClaudeBriefExtractor(chosen, client=client).extract(request_text)
            meta = ExtractionMeta(
                source="claude",
                model=chosen,
                note=f"brief extracted via claude/{chosen}",
            )
            return _annotate(brief, meta), meta
        except Exception as exc:  # noqa: BLE001 - any failure degrades to deterministic
            meta = ExtractionMeta(
                source="deterministic",
                model=chosen,
                note=f"claude extraction unavailable ({exc}); used deterministic parser",
            )
            return _annotate(parse_prompt(request_text), meta), meta
    meta = ExtractionMeta(
        source="deterministic",
        model=model,
        note=f"provider '{provider}' not yet wired; used deterministic parser",
    )
    return _annotate(parse_prompt(request_text), meta), meta
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow && python -m pytest tests/test_comfybio_llm_adapter.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com add harness/src/bioflow_harness/llm/brief_extractor.py tests/test_comfybio_llm_adapter.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: add brief extraction orchestrator with deterministic fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Wire the orchestrator into the server handlers

**Files:**
- Modify: `harness/src/bioflow_harness/server/handlers.py` (import line + two call-sites)
- Test: `tests/test_comfybio_llm_adapter.py` (append)

**Interfaces:**
- Consumes: `extract_brief` from Task 2.
- Produces: no new interface; `compile_spec` / `generate_workflow` now route the brief through `extract_brief`, behavior-preserving in the no-credential default.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_comfybio_llm_adapter.py`:
```python
from bioflow_harness.server.handlers import compile_spec, generate_workflow


def test_compile_spec_default_provider_still_produces_bulk_steps():
    payload = {
        "request_text": "Analyze this FASTQ folder as bulk RNA-seq, human, treated vs control with DESeq2",
        "provider": "codex",
        "model": "",
        "resources": [],
    }
    result = compile_spec(payload)
    assert result["status"] == "ok"
    assert result["domain"] == "bulk_rna_seq"
    assert len(result["steps"]) > 0


def test_generate_workflow_default_provider_returns_workflow():
    payload = {
        "request_text": "Analyze this FASTQ folder as bulk RNA-seq, human, treated vs control with DESeq2",
        "provider": "codex",
        "model": "",
        "resources": [],
        "steps": [],
    }
    result = generate_workflow(payload)
    assert result["status"] == "ok"
    assert result["workflow"] is not None
```

- [ ] **Step 2: Run the tests to verify current behavior (they should PASS already, then guard the swap)**

Run: `cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow && python -m pytest tests/test_comfybio_llm_adapter.py -q`
Expected: PASS — these assert the pre-existing behavior that the swap must preserve. (If they fail here, the payload/registry assumptions are wrong; stop and report.)

- [ ] **Step 3: Swap the import in `handlers.py`**

Find:
```python
from bioflow_harness.parser.prompt_parser import parse_prompt
```
Replace with:
```python
from bioflow_harness.llm.brief_extractor import extract_brief
```

- [ ] **Step 4: Swap both call-sites**

Both `compile_spec` and `generate_workflow` contain the identical line `    brief = parse_prompt(request.request_text)`. Use Edit with `replace_all: true`:

Find:
```python
    brief = parse_prompt(request.request_text)
```
Replace with:
```python
    brief, _meta = extract_brief(request.request_text, request.provider, request.model)
```

- [ ] **Step 5: Run the full suite to verify the swap is behavior-preserving**

Run: `cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow && python -m pytest -q`
Expected: PASS — the two new handler tests plus the entire pre-existing suite (no regression). Confirm the count is the prior total + 11 new tests from this plan.

- [ ] **Step 6: Commit**

```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com add harness/src/bioflow_harness/server/handlers.py tests/test_comfybio_llm_adapter.py
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "feat: route server handlers through the LLM brief extractor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Correct the panel's Claude model IDs

**Files:**
- Modify: `web/js/comfybio_panel.js` (`PROVIDER_MODELS.claude` only)

**Interfaces:**
- Consumes/Produces: nothing in Python; a cosmetic edit so the panel offers the real model IDs the backend accepts.

- [ ] **Step 1: Replace the fictional Claude model list**

Find:
```javascript
  claude: ["claude-opus-4.6", "claude-sonnet-5.0", "claude-haiku-4.5"],
```
Replace with:
```javascript
  claude: ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"],
```

- [ ] **Step 2: Verify the edit**

Run:
```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow
grep -n 'claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"' web/js/comfybio_panel.js; echo "new-exit:$?"
grep -n "claude-opus-4.6\|claude-sonnet-5.0\|claude-haiku-4.5" web/js/comfybio_panel.js; echo "old-exit:$?"
```
Expected: the first grep prints one line (`new-exit:0`); the second prints nothing (`old-exit:1`).

- [ ] **Step 3: Commit**

```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com add web/js/comfybio_panel.js
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "fix: use real Claude model IDs in ComfyBIO panel

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Manual Verification (human, optional — live LLM path)

Automated tests cover the logic with an injected fake client and never touch the network. To exercise the real Claude path, a human with an Anthropic credential:

1. `pip install anthropic` into the ComfyUI Python environment and set `ANTHROPIC_API_KEY` (or `ant auth login`).
2. Restart ComfyUI, open the panel, set provider = `claude`, model = `claude-opus-4-8`, enter a free-text request, and Submit.
3. Confirm the returned spec's steps match the request's domain, and (with no key) that clearing the credential still yields a working spec via the deterministic fallback.

## Notes / Risk

- **Behavior-preserving default:** with no credential the default (`provider="codex"` or a raising Claude client) falls back to `parse_prompt`, so an unconfigured deployment behaves exactly as today.
- **`output_config.format` model support:** valid on `claude-opus-4-8`, `claude-sonnet-5`, `claude-haiku-4-5` — the only models the panel offers.
- **Out of scope:** real codex/gemini adapters, streaming/caching, scRNA execution, route hardening, stale example JSONs.
