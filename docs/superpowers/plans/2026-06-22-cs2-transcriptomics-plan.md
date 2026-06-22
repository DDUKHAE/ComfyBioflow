# CS2 ComfyTranscriptomics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** bulk RNA-seq(QC→정렬→정량→DE→pathway) + scRNA-seq(전처리→클러스터링→주석) 12개 workflow family를 ComfyUI 노드와 CS2 DomainPlugin으로 구현한다.

**Architecture:** 실행 로직은 `llm_interface/llm_core/transcriptomics/` 패키지에 집중하고, `py/RNASeq_*.py`와 `py/SingleCell_Objects.py`는 얇은 ComfyUI 래퍼다. 이 분리로 ComfyUI 런타임 없이 `pytest`가 로직을 직접 테스트할 수 있다. TSR은 이미 존재하는 `transcriptomics.yaml`을 완성하고, CS2DomainPlugin이 Foundation의 DomainPlugin ABC를 구현한다.

**Tech Stack:** Python 3.11+, pydeseq2 0.5.4, scanpy 1.7.2, anndata 0.12.17, fastp(CLI), STAR(CLI — index 필요), kallisto(CLI), salmon(CLI), pyyaml, pytest

## Global Constraints

- 신규 로직 파일: `llm_interface/llm_core/transcriptomics/` 하위
- 신규 ComfyUI 노드: `py/RNASeq_QC_Objects.py`, `py/RNASeq_Align_Objects.py`, `py/RNASeq_DE_Objects.py`, `py/SingleCell_Objects.py`
- 테스트: `tests/llm_core/test_cs2_*.py`
- 테스트 실행: `cd /tmp && PYTHONPATH= python -m pytest /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py -v`
- `comfy_api`는 노드 파일에서만 import — 로직 파일에서 금지
- edgeR 미사용(R 없음) — DE는 pydeseq2 단독
- featureCounts 미사용 — 정량은 kallisto/salmon
- STAR 정렬 노드는 index가 없어 integration test 제외, subprocess 구성만 검증
- import style: `from llm_core.transcriptomics.X import ...` (절대 경로)

---

## File Structure

```
llm_interface/llm_core/transcriptomics/
  __init__.py          # 패키지 선언 + 주요 함수 re-export
  de.py                # run_deseq2() — pydeseq2 기반 DE 분석
  sc.py                # run_sc_preprocess(), run_sc_cluster(), run_sc_annotate()
  qc.py                # run_fastp() — subprocess wrapper
  align.py             # run_kallisto_quant(), run_star_align() — subprocess wrappers

py/
  RNASeq_DE_Objects.py       # DESeq2_run ComfyUI 노드
  SingleCell_Objects.py      # SC_load, SC_preprocess, SC_cluster, SC_annotate 노드
  RNASeq_QC_Objects.py       # Fastp_trim ComfyUI 노드
  RNASeq_Align_Objects.py    # STAR_align, Kallisto_quant, Salmon_quant 노드

llm_interface/llm_core/tsr/domains/
  transcriptomics.yaml       # 기존 파일 확장 (12 step 완성)

llm_interface/llm_core/benchmark/
  cs2_transcriptomics_plugin.py  # CS2DomainPlugin

llm_interface/llm_core/gold/domains/transcriptomics/
  de_analysis_001.yaml       # DE family gold criteria
  sc_clustering_001.yaml     # sc_clustering family gold criteria

tests/
  fixtures/transcriptomics/
    counts_small.tsv          # 20 genes × 8 samples synthetic count matrix
    metadata.tsv              # 8 samples × 2 cols (sample_id, condition)
    reads_R1.fastq            # 500 synthetic short reads
  llm_core/
    test_cs2_core.py          # de.py + sc.py + qc.py + align.py 단위 테스트
    test_cs2_tsr.py           # transcriptomics.yaml 12-step 검증
    test_cs2_plugin.py        # CS2DomainPlugin + Gold criteria 테스트
```

---

### Task 1: Core 패키지 scaffold + 테스트 픽스처 생성

**Files:**
- Create: `llm_interface/llm_core/transcriptomics/__init__.py`
- Create: `llm_interface/llm_core/transcriptomics/de.py` (stub)
- Create: `llm_interface/llm_core/transcriptomics/sc.py` (stub)
- Create: `llm_interface/llm_core/transcriptomics/qc.py` (stub)
- Create: `llm_interface/llm_core/transcriptomics/align.py` (stub)
- Create: `tests/fixtures/transcriptomics/counts_small.tsv`
- Create: `tests/fixtures/transcriptomics/metadata.tsv`
- Create: `tests/fixtures/transcriptomics/reads_R1.fastq`
- Test: `tests/llm_core/test_cs2_core.py` (import test only)

**Interfaces:**
- Produces: `llm_core.transcriptomics` 패키지 importable, 픽스처 파일 3개

- [ ] **Step 1: 테스트 — import 실패 확인**

`tests/llm_core/test_cs2_core.py` (초기 버전):
```python
import pytest


def test_transcriptomics_package_importable():
    from llm_core.transcriptomics import de, sc, qc, align
    assert de is not None
    assert sc is not None
    assert qc is not None
    assert align is not None


def test_fixtures_exist():
    from pathlib import Path
    base = Path("/home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/fixtures/transcriptomics")
    assert (base / "counts_small.tsv").exists()
    assert (base / "metadata.tsv").exists()
    assert (base / "reads_R1.fastq").exists()
```

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_transcriptomics_package_importable -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 2: `__init__.py` + 4개 stub 모듈 생성**

`llm_interface/llm_core/transcriptomics/__init__.py`:
```python
from .de import run_deseq2
from .sc import run_sc_preprocess, run_sc_cluster, run_sc_annotate
from .qc import run_fastp
from .align import run_kallisto_quant, run_star_align

__all__ = [
    "run_deseq2",
    "run_sc_preprocess", "run_sc_cluster", "run_sc_annotate",
    "run_fastp",
    "run_kallisto_quant", "run_star_align",
]
```

`llm_interface/llm_core/transcriptomics/de.py` (stub):
```python
from __future__ import annotations


def run_deseq2(
    counts_path: str,
    metadata_path: str,
    condition_col: str = "condition",
    reference_level: str = "control",
    output_path: str | None = None,
) -> str:
    raise NotImplementedError
```

`llm_interface/llm_core/transcriptomics/sc.py` (stub):
```python
from __future__ import annotations


def run_sc_preprocess(
    input_path: str,
    min_genes: int = 200,
    min_cells: int = 3,
    n_top_genes: int = 2000,
    output_path: str | None = None,
) -> str:
    raise NotImplementedError


def run_sc_cluster(
    input_path: str,
    resolution: float = 0.5,
    algorithm: str = "leiden",
    output_path: str | None = None,
) -> str:
    raise NotImplementedError


def run_sc_annotate(
    input_path: str,
    marker_genes: dict[str, list[str]],
    output_path: str | None = None,
) -> str:
    raise NotImplementedError
```

`llm_interface/llm_core/transcriptomics/qc.py` (stub):
```python
from __future__ import annotations


def run_fastp(
    r1_path: str,
    r2_path: str | None = None,
    output_dir: str | None = None,
    thread: int = 4,
) -> dict:
    raise NotImplementedError
```

`llm_interface/llm_core/transcriptomics/align.py` (stub):
```python
from __future__ import annotations


def run_kallisto_quant(
    r1_path: str,
    index_path: str,
    output_dir: str | None = None,
    single_end: bool = True,
    fragment_length: float = 200.0,
    sd: float = 20.0,
    threads: int = 4,
) -> str:
    raise NotImplementedError


def run_star_align(
    r1_path: str,
    genome_dir: str,
    output_dir: str | None = None,
    r2_path: str | None = None,
    threads: int = 4,
) -> str:
    raise NotImplementedError
```

- [ ] **Step 3: 픽스처 파일 생성**

`tests/fixtures/transcriptomics/counts_small.tsv` (20 genes × 8 samples, ctrl 4 / treated 4):
```
gene_id	ctrl_1	ctrl_2	ctrl_3	ctrl_4	treat_1	treat_2	treat_3	treat_4
GENE_001	120	135	110	128	241	258	230	247
GENE_002	85	92	78	88	170	181	163	175
GENE_003	200	215	195	208	402	418	390	408
GENE_004	55	61	50	58	108	115	102	111
GENE_005	310	325	298	315	623	640	608	630
GENE_006	450	462	438	455	452	465	440	458
GENE_007	180	192	175	185	183	195	177	188
GENE_008	90	98	85	93	92	100	87	95
GENE_009	270	281	262	274	273	284	265	277
GENE_010	140	151	135	144	142	153	137	146
GENE_011	60	67	55	63	61	68	56	64
GENE_012	320	335	310	325	325	338	313	328
GENE_013	75	82	70	78	76	83	71	79
GENE_014	195	208	188	200	198	210	190	203
GENE_015	410	425	398	415	415	428	402	418
GENE_016	100	110	95	104	101	111	96	105
GENE_017	240	255	232	248	243	258	235	250
GENE_018	30	35	28	32	31	36	29	33
GENE_019	510	528	495	515	515	532	500	520
GENE_020	165	178	158	170	167	180	160	172
```

`tests/fixtures/transcriptomics/metadata.tsv`:
```
sample_id	condition
ctrl_1	control
ctrl_2	control
ctrl_3	control
ctrl_4	control
treat_1	treated
treat_2	treated
treat_3	treated
treat_4	treated
```

`tests/fixtures/transcriptomics/reads_R1.fastq` (500개 synthetic reads — Python으로 생성):
```python
# 이 코드를 한 번 실행해 파일 생성
import random, pathlib
random.seed(42)
bases = "ACGT"
out = pathlib.Path("/home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/fixtures/transcriptomics/reads_R1.fastq")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w") as f:
    for i in range(500):
        seq = "".join(random.choices(bases, k=50))
        qual = "I" * 50
        f.write(f"@READ_{i:04d}\n{seq}\n+\n{qual}\n")
```

- [ ] **Step 4: import 테스트 통과 확인**

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add llm_interface/llm_core/transcriptomics/ \
        tests/fixtures/transcriptomics/ \
        tests/llm_core/test_cs2_core.py
git commit -m "feat(cs2): add transcriptomics core package scaffold and test fixtures"
```

---

### Task 2: DE Analysis — pydeseq2 구현 + ComfyUI 노드

**Files:**
- Modify: `llm_interface/llm_core/transcriptomics/de.py`
- Create: `py/RNASeq_DE_Objects.py`
- Modify: `tests/llm_core/test_cs2_core.py` (테스트 추가)

**Interfaces:**
- Consumes: `tests/fixtures/transcriptomics/counts_small.tsv`, `tests/fixtures/transcriptomics/metadata.tsv`
- Produces: `run_deseq2(counts_path, metadata_path, condition_col, reference_level, output_path) -> str` — 결과 TSV 경로 반환

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/llm_core/test_cs2_core.py`에 추가:
```python
import tempfile
from pathlib import Path

_FIXTURES = Path("/home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/fixtures/transcriptomics")


def test_run_deseq2_produces_result_tsv():
    from llm_core.transcriptomics.de import run_deseq2
    with tempfile.TemporaryDirectory() as tmp:
        out = run_deseq2(
            counts_path=str(_FIXTURES / "counts_small.tsv"),
            metadata_path=str(_FIXTURES / "metadata.tsv"),
            condition_col="condition",
            reference_level="control",
            output_path=str(Path(tmp) / "results.tsv"),
        )
        assert Path(out).exists()
        import pandas as pd
        df = pd.read_csv(out, sep="\t", index_col=0)
        assert "log2FoldChange" in df.columns
        assert "padj" in df.columns
        assert len(df) == 20  # 20 genes


def test_run_deseq2_detects_upregulated_genes():
    from llm_core.transcriptomics.de import run_deseq2
    import pandas as pd
    with tempfile.TemporaryDirectory() as tmp:
        out = run_deseq2(
            counts_path=str(_FIXTURES / "counts_small.tsv"),
            metadata_path=str(_FIXTURES / "metadata.tsv"),
            output_path=str(Path(tmp) / "results.tsv"),
        )
        df = pd.read_csv(out, sep="\t", index_col=0)
        # GENE_001~005는 2배 발현: log2FC ≈ 1
        sig = df[(df["padj"] < 0.05) & (df["log2FoldChange"] > 0.5)]
        assert len(sig) >= 3
```

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_run_deseq2_produces_result_tsv -v
```
Expected: FAIL `NotImplementedError`

- [ ] **Step 2: `de.py` 구현**

`llm_interface/llm_core/transcriptomics/de.py`:
```python
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd


def run_deseq2(
    counts_path: str,
    metadata_path: str,
    condition_col: str = "condition",
    reference_level: str = "control",
    output_path: str | None = None,
) -> str:
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.default_inference import DefaultInference
    from pydeseq2.ds import DeseqStats

    counts = pd.read_csv(counts_path, sep="\t", index_col=0).T
    metadata = pd.read_csv(metadata_path, sep="\t", index_col=0)

    # align sample order
    common = counts.index.intersection(metadata.index)
    counts = counts.loc[common]
    metadata = metadata.loc[common]

    dds = DeseqDataSet(
        counts=counts,
        metadata=metadata,
        design_factors=condition_col,
        ref_level=[condition_col, reference_level],
        refit_cooks=True,
        inference=DefaultInference(n_cpus=1),
    )
    dds.deseq2()

    stat_res = DeseqStats(dds, inference=DefaultInference(n_cpus=1))
    stat_res.summary()
    results = stat_res.results_df

    if output_path is None:
        tmp = tempfile.mkdtemp()
        output_path = str(Path(tmp) / "deseq2_results.tsv")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, sep="\t")
    return output_path
```

- [ ] **Step 3: ComfyUI 노드 생성**

`py/RNASeq_DE_Objects.py`:
```python
from __future__ import annotations

from typing_extensions import override
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class DESeq2_run(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DESeq2_run",
            display_name="DESeq2 run",
            category="Transcriptomics/DifferentialExpression",
            inputs=[
                io.String.Input("counts_path", multiline=False, default=""),
                io.String.Input("metadata_path", multiline=False, default=""),
                io.String.Input("condition_col", multiline=False, default="condition"),
                io.String.Input("reference_level", multiline=False, default="control"),
                io.String.Input("output_path", multiline=False, default=""),
            ],
            outputs=[
                io.String.Output("results_path"),
            ],
        )

    @classmethod
    def execute(
        cls, counts_path, metadata_path, condition_col, reference_level, output_path
    ) -> io.NodeOutput:
        from llm_core.transcriptomics.de import run_deseq2
        out = run_deseq2(
            counts_path=counts_path,
            metadata_path=metadata_path,
            condition_col=condition_col,
            reference_level=reference_level,
            output_path=output_path or None,
        )
        return io.NodeOutput(out)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_run_deseq2_produces_result_tsv \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_run_deseq2_detects_upregulated_genes -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add llm_interface/llm_core/transcriptomics/de.py \
        py/RNASeq_DE_Objects.py \
        tests/llm_core/test_cs2_core.py
git commit -m "feat(cs2): implement pydeseq2 DE analysis and ComfyUI node"
```

---

### Task 3: Single-cell — scanpy 구현 + ComfyUI 노드

**Files:**
- Modify: `llm_interface/llm_core/transcriptomics/sc.py`
- Create: `py/SingleCell_Objects.py`
- Modify: `tests/llm_core/test_cs2_core.py` (테스트 추가)

**Interfaces:**
- Produces: `run_sc_preprocess(input_path, ...) -> str`, `run_sc_cluster(input_path, ...) -> str`, `run_sc_annotate(input_path, marker_genes, ...) -> str` — 모두 .h5ad 경로 반환

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/llm_core/test_cs2_core.py`에 추가:
```python
def _make_synthetic_adata(tmp_dir: str) -> str:
    """100 cells × 200 genes synthetic AnnData."""
    import numpy as np
    import anndata as ad

    rng = np.random.default_rng(42)
    X = rng.negative_binomial(5, 0.3, size=(100, 200)).astype(float)
    obs = pd.DataFrame({"cell_type": ["unknown"] * 100}, index=[f"cell_{i}" for i in range(100)])
    var = pd.DataFrame(index=[f"GENE_{i:04d}" for i in range(200)])
    adata = ad.AnnData(X=X, obs=obs, var=var)
    path = str(Path(tmp_dir) / "synthetic.h5ad")
    adata.write_h5ad(path)
    return path


def test_run_sc_preprocess_adds_normalized_layer():
    from llm_core.transcriptomics.sc import run_sc_preprocess
    import anndata as ad
    with tempfile.TemporaryDirectory() as tmp:
        input_path = _make_synthetic_adata(tmp)
        out = run_sc_preprocess(
            input_path=input_path,
            min_genes=5,
            min_cells=3,
            n_top_genes=100,
            output_path=str(Path(tmp) / "preprocessed.h5ad"),
        )
        assert Path(out).exists()
        adata = ad.read_h5ad(out)
        assert "highly_variable" in adata.var.columns


def test_run_sc_cluster_adds_cluster_column():
    from llm_core.transcriptomics.sc import run_sc_preprocess, run_sc_cluster
    import anndata as ad
    with tempfile.TemporaryDirectory() as tmp:
        input_path = _make_synthetic_adata(tmp)
        pre = run_sc_preprocess(input_path=input_path, min_genes=5, min_cells=3,
                                n_top_genes=100, output_path=str(Path(tmp) / "pre.h5ad"))
        out = run_sc_cluster(
            input_path=pre,
            resolution=0.3,
            algorithm="leiden",
            output_path=str(Path(tmp) / "clustered.h5ad"),
        )
        assert Path(out).exists()
        adata = ad.read_h5ad(out)
        assert "leiden" in adata.obs.columns
        assert adata.obs["leiden"].nunique() >= 1
```

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_run_sc_preprocess_adds_normalized_layer -v
```
Expected: FAIL `NotImplementedError`

- [ ] **Step 2: `sc.py` 구현**

`llm_interface/llm_core/transcriptomics/sc.py`:
```python
from __future__ import annotations

import tempfile
from pathlib import Path


def run_sc_preprocess(
    input_path: str,
    min_genes: int = 200,
    min_cells: int = 3,
    n_top_genes: int = 2000,
    output_path: str | None = None,
) -> str:
    import scanpy as sc

    adata = sc.read_h5ad(input_path)
    sc.pp.filter_cells(adata, min_genes=min_genes)
    sc.pp.filter_genes(adata, min_cells=min_cells)
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=min(n_top_genes, adata.n_vars))

    out = output_path or str(Path(tempfile.mkdtemp()) / "preprocessed.h5ad")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(out)
    return out


def run_sc_cluster(
    input_path: str,
    resolution: float = 0.5,
    algorithm: str = "leiden",
    output_path: str | None = None,
) -> str:
    import scanpy as sc

    adata = sc.read_h5ad(input_path)
    use_hvg = "highly_variable" in adata.var.columns
    sc.pp.pca(adata, use_highly_variable=use_hvg)
    sc.pp.neighbors(adata, n_neighbors=min(10, adata.n_obs - 1))

    if algorithm == "leiden":
        sc.tl.leiden(adata, resolution=resolution)
    elif algorithm == "louvain":
        sc.tl.louvain(adata, resolution=resolution)
    else:
        raise ValueError(f"Unknown clustering algorithm: {algorithm!r}. Use 'leiden' or 'louvain'.")

    out = output_path or str(Path(tempfile.mkdtemp()) / "clustered.h5ad")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(out)
    return out


def run_sc_annotate(
    input_path: str,
    marker_genes: dict[str, list[str]],
    output_path: str | None = None,
) -> str:
    """Assign cell type labels to clusters based on marker gene expression."""
    import numpy as np
    import scanpy as sc

    adata = sc.read_h5ad(input_path)
    cluster_col = "leiden" if "leiden" in adata.obs.columns else "louvain"

    cell_types: list[str] = []
    for cluster in adata.obs[cluster_col]:
        best_type = "Unknown"
        best_score = -1.0
        for cell_type, markers in marker_genes.items():
            present = [g for g in markers if g in adata.var_names]
            if not present:
                continue
            score = float(np.mean(adata[adata.obs[cluster_col] == cluster, present].X.mean(axis=0)))
            if score > best_score:
                best_score = score
                best_type = cell_type
        cell_types.append(best_type)

    adata.obs["cell_type"] = cell_types

    out = output_path or str(Path(tempfile.mkdtemp()) / "annotated.h5ad")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(out)
    return out
```

- [ ] **Step 3: ComfyUI 노드 생성**

`py/SingleCell_Objects.py`:
```python
from __future__ import annotations

import json
from typing_extensions import override
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class SC_preprocess(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SC_preprocess",
            display_name="SC preprocess",
            category="Transcriptomics/SingleCell",
            inputs=[
                io.String.Input("input_path", multiline=False, default=""),
                io.Int.Input("min_genes", default=200),
                io.Int.Input("min_cells", default=3),
                io.Int.Input("n_top_genes", default=2000),
                io.String.Input("output_path", multiline=False, default=""),
            ],
            outputs=[io.String.Output("output_path")],
        )

    @classmethod
    def execute(cls, input_path, min_genes, min_cells, n_top_genes, output_path) -> io.NodeOutput:
        from llm_core.transcriptomics.sc import run_sc_preprocess
        out = run_sc_preprocess(input_path, min_genes, min_cells, n_top_genes, output_path or None)
        return io.NodeOutput(out)


class SC_cluster(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SC_cluster",
            display_name="SC cluster",
            category="Transcriptomics/SingleCell",
            inputs=[
                io.String.Input("input_path", multiline=False, default=""),
                io.Float.Input("resolution", default=0.5),
                io.Combo.Input("algorithm", options=["leiden", "louvain"], default="leiden"),
                io.String.Input("output_path", multiline=False, default=""),
            ],
            outputs=[io.String.Output("output_path")],
        )

    @classmethod
    def execute(cls, input_path, resolution, algorithm, output_path) -> io.NodeOutput:
        from llm_core.transcriptomics.sc import run_sc_cluster
        out = run_sc_cluster(input_path, resolution, algorithm, output_path or None)
        return io.NodeOutput(out)


class SC_annotate(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SC_annotate",
            display_name="SC annotate",
            category="Transcriptomics/SingleCell",
            inputs=[
                io.String.Input("input_path", multiline=False, default=""),
                io.String.Input("marker_genes_json", multiline=True, default='{"T cell": ["CD3D", "CD3E"]}'),
                io.String.Input("output_path", multiline=False, default=""),
            ],
            outputs=[io.String.Output("output_path")],
        )

    @classmethod
    def execute(cls, input_path, marker_genes_json, output_path) -> io.NodeOutput:
        from llm_core.transcriptomics.sc import run_sc_annotate
        marker_genes = json.loads(marker_genes_json)
        out = run_sc_annotate(input_path, marker_genes, output_path or None)
        return io.NodeOutput(out)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_run_sc_preprocess_adds_normalized_layer \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_run_sc_cluster_adds_cluster_column -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add llm_interface/llm_core/transcriptomics/sc.py \
        py/SingleCell_Objects.py \
        tests/llm_core/test_cs2_core.py
git commit -m "feat(cs2): implement scanpy single-cell processing and ComfyUI nodes"
```

---

### Task 4: QC + Alignment — CLI wrapper 구현 + ComfyUI 노드

**Files:**
- Modify: `llm_interface/llm_core/transcriptomics/qc.py`
- Modify: `llm_interface/llm_core/transcriptomics/align.py`
- Create: `py/RNASeq_QC_Objects.py`
- Create: `py/RNASeq_Align_Objects.py`
- Modify: `tests/llm_core/test_cs2_core.py` (테스트 추가)

**Interfaces:**
- Produces: `run_fastp(r1_path, ...) -> dict` (JSON stats), `run_kallisto_quant(...) -> str` (output dir), `run_star_align(...) -> str` (output dir)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/llm_core/test_cs2_core.py`에 추가:
```python
def test_run_fastp_returns_stats_dict():
    from llm_core.transcriptomics.qc import run_fastp
    with tempfile.TemporaryDirectory() as tmp:
        result = run_fastp(
            r1_path=str(_FIXTURES / "reads_R1.fastq"),
            output_dir=tmp,
            thread=1,
        )
    assert isinstance(result, dict)
    assert "summary" in result
    assert result["summary"]["before_filtering"]["total_reads"] == 500


def test_run_star_align_builds_correct_command(monkeypatch):
    import subprocess
    from llm_core.transcriptomics.align import run_star_align

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        # create fake output directory with required file
        import os
        out_dir = None
        for i, part in enumerate(cmd):
            if part == "--outFileNamePrefix":
                out_dir = cmd[i + 1]
                break
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            open(out_dir + "Aligned.sortedByCoord.out.bam", "w").close()
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with tempfile.TemporaryDirectory() as tmp:
        out = run_star_align(
            r1_path="/fake/reads.fastq",
            genome_dir="/fake/genome",
            output_dir=tmp,
            threads=2,
        )
    assert "STAR" in captured["cmd"][0]
    assert "--runThreadN" in captured["cmd"]
    assert "2" in captured["cmd"]
```

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_run_fastp_returns_stats_dict -v
```
Expected: FAIL `NotImplementedError`

- [ ] **Step 2: `qc.py` 구현**

`llm_interface/llm_core/transcriptomics/qc.py`:
```python
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


def run_fastp(
    r1_path: str,
    r2_path: str | None = None,
    output_dir: str | None = None,
    thread: int = 4,
) -> dict:
    out_dir = Path(output_dir or tempfile.mkdtemp())
    out_dir.mkdir(parents=True, exist_ok=True)

    r1_out = str(out_dir / "R1_trimmed.fastq.gz")
    json_out = str(out_dir / "fastp.json")
    html_out = str(out_dir / "fastp.html")

    cmd = [
        "fastp",
        "--in1", r1_path,
        "--out1", r1_out,
        "--json", json_out,
        "--html", html_out,
        "--thread", str(thread),
        "--disable_adapter_trimming",  # safe default for synthetic reads
    ]
    if r2_path:
        r2_out = str(out_dir / "R2_trimmed.fastq.gz")
        cmd += ["--in2", r2_path, "--out2", r2_out]

    subprocess.run(cmd, check=True, capture_output=True)
    return json.loads(Path(json_out).read_text())
```

- [ ] **Step 3: `align.py` 구현**

`llm_interface/llm_core/transcriptomics/align.py`:
```python
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def run_kallisto_quant(
    r1_path: str,
    index_path: str,
    output_dir: str | None = None,
    single_end: bool = True,
    fragment_length: float = 200.0,
    sd: float = 20.0,
    threads: int = 4,
) -> str:
    out_dir = str(output_dir or tempfile.mkdtemp())
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    cmd = [
        "kallisto", "quant",
        "--index", index_path,
        "--output-dir", out_dir,
        "--threads", str(threads),
    ]
    if single_end:
        cmd += ["--single", "--fragment-length", str(fragment_length), "--sd", str(sd)]
    cmd.append(r1_path)

    subprocess.run(cmd, check=True, capture_output=True)
    return out_dir


def run_star_align(
    r1_path: str,
    genome_dir: str,
    output_dir: str | None = None,
    r2_path: str | None = None,
    threads: int = 4,
) -> str:
    out_dir = str(output_dir or tempfile.mkdtemp())
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    prefix = str(Path(out_dir) / "")

    cmd = [
        "STAR",
        "--runThreadN", str(threads),
        "--genomeDir", genome_dir,
        "--readFilesIn", r1_path,
        "--outFileNamePrefix", prefix,
        "--outSAMtype", "BAM", "SortedByCoordinate",
        "--outSAMattributes", "NH", "HI", "AS", "NM",
    ]
    if r2_path:
        cmd.append(r2_path)

    subprocess.run(cmd, check=True, capture_output=True)
    return out_dir
```

- [ ] **Step 4: ComfyUI 노드 생성**

`py/RNASeq_QC_Objects.py`:
```python
from __future__ import annotations

import json
from typing_extensions import override
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class Fastp_trim(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Fastp_trim",
            display_name="fastp trim",
            category="Transcriptomics/QC",
            inputs=[
                io.String.Input("r1_path", multiline=False, default=""),
                io.String.Input("r2_path", multiline=False, default=""),
                io.String.Input("output_dir", multiline=False, default=""),
                io.Int.Input("thread", default=4),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("stats_json"),
            ],
        )

    @classmethod
    def execute(cls, r1_path, r2_path, output_dir, thread) -> io.NodeOutput:
        from llm_core.transcriptomics.qc import run_fastp
        stats = run_fastp(
            r1_path=r1_path,
            r2_path=r2_path or None,
            output_dir=output_dir or None,
            thread=thread,
        )
        return io.NodeOutput(output_dir, json.dumps(stats))
```

`py/RNASeq_Align_Objects.py`:
```python
from __future__ import annotations

from typing_extensions import override
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class STAR_align(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="STAR_align",
            display_name="STAR align",
            category="Transcriptomics/Alignment",
            inputs=[
                io.String.Input("r1_path", multiline=False, default=""),
                io.String.Input("r2_path", multiline=False, default=""),
                io.String.Input("genome_dir", multiline=False, default=""),
                io.String.Input("output_dir", multiline=False, default=""),
                io.Int.Input("threads", default=4),
            ],
            outputs=[io.String.Output("output_dir")],
        )

    @classmethod
    def execute(cls, r1_path, r2_path, genome_dir, output_dir, threads) -> io.NodeOutput:
        from llm_core.transcriptomics.align import run_star_align
        out = run_star_align(
            r1_path=r1_path,
            genome_dir=genome_dir,
            output_dir=output_dir or None,
            r2_path=r2_path or None,
            threads=threads,
        )
        return io.NodeOutput(out)


class Kallisto_quant(_Base):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Kallisto_quant",
            display_name="kallisto quant",
            category="Transcriptomics/Alignment",
            inputs=[
                io.String.Input("r1_path", multiline=False, default=""),
                io.String.Input("index_path", multiline=False, default=""),
                io.String.Input("output_dir", multiline=False, default=""),
                io.Float.Input("fragment_length", default=200.0),
                io.Float.Input("sd", default=20.0),
                io.Int.Input("threads", default=4),
            ],
            outputs=[io.String.Output("output_dir")],
        )

    @classmethod
    def execute(cls, r1_path, index_path, output_dir, fragment_length, sd, threads) -> io.NodeOutput:
        from llm_core.transcriptomics.align import run_kallisto_quant
        out = run_kallisto_quant(
            r1_path=r1_path,
            index_path=index_path,
            output_dir=output_dir or None,
            single_end=True,
            fragment_length=fragment_length,
            sd=sd,
            threads=threads,
        )
        return io.NodeOutput(out)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_run_fastp_returns_stats_dict \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py::test_run_star_align_builds_correct_command -v
```
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add llm_interface/llm_core/transcriptomics/qc.py \
        llm_interface/llm_core/transcriptomics/align.py \
        py/RNASeq_QC_Objects.py \
        py/RNASeq_Align_Objects.py \
        tests/llm_core/test_cs2_core.py
git commit -m "feat(cs2): implement fastp/STAR/kallisto CLI wrappers and ComfyUI nodes"
```

---

### Task 5: TSR YAML 완성 — 12 step 전체 정의

**Files:**
- Modify: `llm_interface/llm_core/tsr/domains/transcriptomics.yaml`
- Create: `tests/llm_core/test_cs2_tsr.py`

**Interfaces:**
- Consumes: `TSREngine`, `load_domain_tsr` (Foundation)
- Produces: transcriptomics.yaml에 12개 step_id 모두 포함, 컨텍스트 기반 tool 선택 동작

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/llm_core/test_cs2_tsr.py`:
```python
from llm_core.tsr.loader import load_domain_tsr
from llm_core.tsr.engine import TSREngine

_REQUIRED_STEPS = [
    "raw_qc", "adapter_trimming", "genome_alignment", "pseudo_alignment",
    "read_quantification", "differential_expression", "pathway_enrichment",
    "sc_preprocessing", "sc_clustering", "sc_annotation",
    "sc_trajectory", "visualization",
]


def test_transcriptomics_tsr_has_all_12_steps():
    tsr = load_domain_tsr("transcriptomics")
    step_ids = {s.step_id for s in tsr.steps}
    for required in _REQUIRED_STEPS:
        assert required in step_ids, f"Missing step: {required}"


def test_adapter_trimming_canonical_is_fastp():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.canonical("adapter_trimming", {}) == "fastp"


def test_genome_alignment_short_read_canonical_is_star():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    ctx = {"data_type": "short_read", "read_length": 150}
    assert engine.canonical("genome_alignment", ctx) == "STAR"


def test_genome_alignment_long_read_star_is_invalid():
    from llm_core.tsr.schema import ToolValidity
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    ctx = {"data_type": "long_read"}
    assert engine.is_valid("genome_alignment", "STAR", ctx) == ToolValidity.INVALID


def test_de_small_sample_canonical_is_edger():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.canonical("differential_expression", {"n_samples_per_group": 3}) == "edgeR"


def test_de_large_sample_canonical_is_deseq2():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.canonical("differential_expression", {"n_samples_per_group": 8}) == "DESeq2"


def test_sc_clustering_leiden_canonical():
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.canonical("sc_clustering", {"assay": "scrna_seq"}) == "leiden"


def test_sc_clustering_kmeans_invalid():
    from llm_core.tsr.schema import ToolValidity
    tsr = load_domain_tsr("transcriptomics")
    engine = TSREngine(tsr)
    assert engine.is_valid("sc_clustering", "kmeans", {"assay": "scrna_seq"}) == ToolValidity.INVALID
```

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_tsr.py::test_transcriptomics_tsr_has_all_12_steps -v
```
Expected: FAIL (missing steps)

- [ ] **Step 2: transcriptomics.yaml 완성**

`llm_interface/llm_core/tsr/domains/transcriptomics.yaml` (전체 교체):
```yaml
domain_id: transcriptomics
description: "Bulk RNA-seq and scRNA-seq analysis — CS2"
steps:
  - step_id: raw_qc
    step_name: Raw Quality Control
    condition: "True"
    tools:
      - tool_id: FastQC
        validity: canonical
        reason: "Industry standard QC report"
      - tool_id: MultiQC
        validity: alternative_valid
        reason: "Aggregates multiple FastQC reports"

  - step_id: adapter_trimming
    step_name: Adapter Trimming
    condition: "True"
    tools:
      - tool_id: fastp
        validity: canonical
        reason: "Fast, all-in-one quality control"
      - tool_id: trimmomatic
        validity: alternative_valid
        reason: "Highly configurable, widely used"
      - tool_id: cutadapt
        validity: alternative_valid
        reason: "Flexible adapter trimmer"

  - step_id: genome_alignment
    step_name: Genome Alignment
    condition: "data_type == 'short_read'"
    tools:
      - tool_id: STAR
        validity: canonical
        reason: "Splice-aware aligner, RNA-seq standard for short reads"
      - tool_id: HISAT2
        validity: alternative_valid
        reason: "Memory-efficient splice-aware aligner"

  - step_id: genome_alignment
    step_name: Genome Alignment
    condition: "data_type == 'long_read'"
    tools:
      - tool_id: minimap2
        validity: canonical
        reason: "Optimal for long-read RNA-seq (PacBio/Nanopore)"
      - tool_id: STAR
        validity: invalid
        reason: "Short-read aligner; fails on long-read error rates"

  - step_id: pseudo_alignment
    step_name: Pseudo-alignment / Quantification
    condition: "True"
    tools:
      - tool_id: kallisto
        validity: canonical
        reason: "Fast pseudo-alignment, sufficient when genome alignment not needed"
      - tool_id: salmon
        validity: alternative_valid
        reason: "Quasi-mapping with GC-bias correction"

  - step_id: read_quantification
    step_name: Read Quantification
    condition: "True"
    tools:
      - tool_id: featureCounts
        validity: canonical
        reason: "Fast, memory-efficient gene-level counting"
      - tool_id: HTSeq
        validity: alternative_valid
        reason: "Python-based, flexible counting"
      - tool_id: RSEM
        validity: alternative_valid
        reason: "Handles multi-mapping reads with EM algorithm"

  - step_id: differential_expression
    step_name: Differential Expression Analysis
    condition: "n_samples_per_group < 6"
    tools:
      - tool_id: edgeR
        validity: canonical
        reason: "Best performance with small sample sizes"
      - tool_id: DESeq2
        validity: alternative_valid
        reason: "Acceptable but less optimal for n<6"

  - step_id: differential_expression
    step_name: Differential Expression Analysis
    condition: "n_samples_per_group >= 6"
    tools:
      - tool_id: DESeq2
        validity: canonical
        reason: "Negative binomial model, well-validated for bulk RNA-seq"
      - tool_id: edgeR
        validity: alternative_valid
        reason: "Also valid for larger sample sizes"
      - tool_id: limma_voom
        validity: alternative_valid
        reason: "Good for large studies or complex designs"

  - step_id: pathway_enrichment
    step_name: Pathway Enrichment Analysis
    condition: "True"
    tools:
      - tool_id: clusterProfiler
        validity: canonical
        reason: "Comprehensive ORA and GSEA in R"
      - tool_id: fgsea
        validity: alternative_valid
        reason: "Fast GSEA implementation"
      - tool_id: GSEA
        validity: alternative_valid
        reason: "Original GSEA Java implementation"

  - step_id: sc_preprocessing
    step_name: Single-cell Preprocessing
    condition: "assay == 'scrna_seq'"
    tools:
      - tool_id: scanpy
        validity: canonical
        reason: "Python-native sc analysis, Leiden/Louvain built-in"
      - tool_id: seurat
        validity: alternative_valid
        reason: "R-based, widely used reference implementation"

  - step_id: sc_clustering
    step_name: Single-cell Clustering
    condition: "assay == 'scrna_seq'"
    tools:
      - tool_id: leiden
        validity: canonical
        reason: "Superior community detection; default in Scanpy"
      - tool_id: louvain
        validity: alternative_valid
        reason: "Predecessor to Leiden, still widely used"
      - tool_id: kmeans
        validity: invalid
        reason: "Assumes spherical clusters; inappropriate for single-cell embedding"

  - step_id: sc_annotation
    step_name: Cell Type Annotation
    condition: "assay == 'scrna_seq'"
    tools:
      - tool_id: SingleR
        validity: canonical
        reason: "Reference-based automated annotation"
      - tool_id: CellTypist
        validity: alternative_valid
        reason: "Machine learning-based annotation"

  - step_id: sc_trajectory
    step_name: Trajectory Analysis
    condition: "assay == 'scrna_seq'"
    tools:
      - tool_id: PAGA
        validity: canonical
        reason: "Graph-based trajectory in Scanpy"
      - tool_id: Monocle3
        validity: alternative_valid
        reason: "Pseudotime analysis in R"

  - step_id: visualization
    step_name: Visualization
    condition: "True"
    tools:
      - tool_id: ggplot2
        validity: canonical
        reason: "Flexible R-based publication-quality plots"
      - tool_id: seaborn
        validity: alternative_valid
        reason: "Python-based statistical visualization"
      - tool_id: matplotlib
        validity: alternative_valid
        reason: "General-purpose Python plotting"
```

- [ ] **Step 3: lru_cache 무효화 후 테스트 통과 확인**

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_tsr.py -v
```
Expected: `8 passed`

- [ ] **Step 4: Commit**

```bash
git add llm_interface/llm_core/tsr/domains/transcriptomics.yaml \
        tests/llm_core/test_cs2_tsr.py
git commit -m "feat(cs2): complete transcriptomics TSR YAML with all 12 workflow steps"
```

---

### Task 6: CS2 DomainPlugin + Gold Criteria

**Files:**
- Create: `llm_interface/llm_core/benchmark/cs2_transcriptomics_plugin.py`
- Create: `llm_interface/llm_core/gold/domains/transcriptomics/de_analysis_001.yaml`
- Create: `llm_interface/llm_core/gold/domains/transcriptomics/sc_clustering_001.yaml`
- Create: `tests/llm_core/test_cs2_plugin.py`

**Interfaces:**
- Consumes: `DomainPlugin` ABC (Foundation), `load_domain_tsr` (Foundation), `GoldEvaluator`, `TieredGold` (Foundation)
- Produces: `CS2TranscriptomicsPlugin` — `.domain_id == "transcriptomics"`, `.list_families()` 12개, `.load_gold(query_id) -> TieredGold`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/llm_core/test_cs2_plugin.py`:
```python
from llm_core.benchmark.cs2_transcriptomics_plugin import CS2TranscriptomicsPlugin
from llm_core.benchmark.domain_plugin import DomainPlugin


def test_cs2_plugin_is_domain_plugin():
    plugin = CS2TranscriptomicsPlugin()
    assert isinstance(plugin, DomainPlugin)


def test_cs2_plugin_domain_id():
    plugin = CS2TranscriptomicsPlugin()
    assert plugin.domain_id == "transcriptomics"


def test_cs2_plugin_lists_12_families():
    plugin = CS2TranscriptomicsPlugin()
    families = plugin.list_families()
    assert len(families) == 12
    assert "differential_expression" in families
    assert "sc_clustering" in families


def test_cs2_plugin_get_tsr_resolves_de_canonical():
    from llm_core.tsr.engine import TSREngine
    plugin = CS2TranscriptomicsPlugin()
    tsr = plugin.get_tsr()
    engine = TSREngine(tsr)
    assert engine.canonical("differential_expression", {"n_samples_per_group": 8}) == "DESeq2"


def test_cs2_plugin_load_gold_de_analysis():
    from llm_core.gold.schema import TieredGold
    plugin = CS2TranscriptomicsPlugin()
    gold = plugin.load_gold("de_analysis_001")
    assert isinstance(gold, TieredGold)
    assert gold.family == "differential_expression"
    assert "DESeq2" in gold.canonical.tools or "edgeR" in gold.canonical.tools


def test_gold_evaluator_correct_canonical_de():
    from llm_core.gold.evaluator import GoldEvaluator
    from llm_core.gold.schema import Verdict
    plugin = CS2TranscriptomicsPlugin()
    gold = plugin.load_gold("de_analysis_001")
    evaluator = GoldEvaluator(gold)
    output = {"top10_overlap_min": 1.0, "has_log2fc_column": True, "has_padj_column": True}
    verdict = evaluator.evaluate(gold.canonical.tools, output)
    assert verdict == Verdict.CORRECT_CANONICAL
```

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_plugin.py -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 2: Gold Criteria YAML 작성**

`llm_interface/llm_core/gold/domains/transcriptomics/de_analysis_001.yaml`:
```yaml
query_id: de_analysis_001
family: differential_expression
context:
  n_samples_per_group: 4
  data_type: bulk_rna_seq
  organism: homo_sapiens

gold:
  tier_1_canonical:
    tools: [edgeR]
    expected_output_criteria:
      top10_overlap_min: 1.0
      has_log2fc_column: true
      has_padj_column: true

  tier_2_alternative:
    tools: [DESeq2, limma_voom]
    functional_equivalence_criteria:
      top10_overlap_with_canonical: ">= 0.80"
      has_log2fc_column: ">= 1.0"
      has_padj_column: ">= 1.0"

  tier_3_invalid:
    tools: [kallisto, STAR, fastp, scanpy]
```

`llm_interface/llm_core/gold/domains/transcriptomics/sc_clustering_001.yaml`:
```yaml
query_id: sc_clustering_001
family: sc_clustering
context:
  assay: scrna_seq
  n_cells: 100

gold:
  tier_1_canonical:
    tools: [leiden]
    expected_output_criteria:
      has_cluster_column: true
      n_clusters_min: 1

  tier_2_alternative:
    tools: [louvain]
    functional_equivalence_criteria:
      has_cluster_column: ">= 1.0"
      n_clusters_min: ">= 1.0"

  tier_3_invalid:
    tools: [kmeans, DESeq2, STAR]
```

- [ ] **Step 3: CS2DomainPlugin 구현**

`llm_interface/llm_core/benchmark/cs2_transcriptomics_plugin.py`:
```python
from __future__ import annotations

from pathlib import Path

import yaml

from gold.schema import (
    AdversarialOverride,
    AlternativeGold,
    CanonicalGold,
    TieredGold,
)
from tsr.loader import load_domain_tsr
from tsr.schema import DomainTSR

from .domain_plugin import DomainPlugin
from .query_schema import HeldOutQuery

_GOLD_DIR = Path(__file__).resolve().parent.parent / "gold" / "domains" / "transcriptomics"

_FAMILIES = [
    "raw_qc", "adapter_trimming", "genome_alignment", "pseudo_alignment",
    "read_quantification", "differential_expression", "pathway_enrichment",
    "sc_preprocessing", "sc_clustering", "sc_annotation",
    "sc_trajectory", "visualization",
]


class CS2TranscriptomicsPlugin(DomainPlugin):

    @property
    def domain_id(self) -> str:
        return "transcriptomics"

    @property
    def domain_description(self) -> str:
        return "Bulk RNA-seq and scRNA-seq analysis — CS2"

    def get_tsr(self) -> DomainTSR:
        return load_domain_tsr("transcriptomics")

    def list_families(self) -> list[str]:
        return list(_FAMILIES)

    def load_gold(self, query_id: str) -> TieredGold:
        path = _GOLD_DIR / f"{query_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"No gold criteria for query '{query_id}': {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return _parse_gold(data)

    def run_workflow(self, query: HeldOutQuery) -> dict:
        raise NotImplementedError("run_workflow requires domain-specific execution environment")


def _parse_gold(data: dict) -> TieredGold:
    t1 = data["gold"]["tier_1_canonical"]
    t2 = data["gold"]["tier_2_alternative"]
    t3 = data["gold"].get("tier_3_invalid", {})
    adversarial = data["gold"].get("adversarial_override")

    return TieredGold(
        query_id=data["query_id"],
        family=data["family"],
        context=data.get("context", {}),
        canonical=CanonicalGold(
            tools=t1["tools"],
            expected_output_criteria=t1["expected_output_criteria"],
        ),
        alternatives=AlternativeGold(
            tools=t2["tools"],
            functional_equivalence_criteria=t2["functional_equivalence_criteria"],
        ),
        invalid_tools=t3.get("tools", []),
        adversarial_override=(
            AdversarialOverride(
                bad_hint_tool=adversarial["bad_hint_tool"],
                correct_behaviors=adversarial["correct_behaviors"],
            )
            if adversarial else None
        ),
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_plugin.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add llm_interface/llm_core/benchmark/cs2_transcriptomics_plugin.py \
        llm_interface/llm_core/gold/domains/ \
        tests/llm_core/test_cs2_plugin.py
git commit -m "feat(cs2): add CS2TranscriptomicsPlugin and gold criteria for DE/sc_clustering"
```

---

### Task 7: 전체 테스트 통과 확인

**Files:**
- (수정 없음 — 통합 확인)

- [ ] **Step 1: CS2 전체 테스트 실행**

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_core.py \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_tsr.py \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_cs2_plugin.py \
  -v 2>&1 | tail -20
```
Expected: `21 passed` (2 + 4 + 2 + 2 + 2 + 8 + 6 = 26 — 실제 카운트는 구현에 따라 변동)

- [ ] **Step 2: 기존 테스트 회귀 없음 확인**

```bash
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/ \
  --ignore=/home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_check_provider_readiness_script.py \
  --ignore=/home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests/llm_core/test_run_workflow_experiment_script.py \
  -q 2>&1 | tail -5
```
Expected: `95 + CS2 신규` passed, 0 failed

- [ ] **Step 3: git tag**

```bash
git tag cs2-v1.0
```
