# §10 의미적 소켓 타입 도입 — 직접 구현 가이드 (상세)

- **작성일**: 2026-06-04
- **대상 문제**: 리뷰 §10 — 출력 포트 330개 중 245개가 `STRING`이라, `validate_workflow_spec`의 `src.type == tgt.type` 타입 검사가 도메인 객체(SeqRecord/Alignment/Tree/BLAST…)를 구분하지 못함. Tree 출력을 Sequence 입력에 연결해도 통과.
- **목표**: 생물학적 객체마다 별도 io_type을 부여해, **GUI 연결과 워크플로우 검증 양쪽에서** 의미가 맞는 연결만 허용.
- **검증 환경**: 일부 단계는 실행 중인 ComfyUI에서 눈으로 확인해야 하므로 직접 진행.

---

## 0. 큰 그림 — 무엇이 바뀌고 어디에 영향을 주나

핵심은 노드 정의에서 **객체를 나르는 포트의 타입 문자열만** `STRING` → `BIO_*`로 바꾸는 것이다. 그 한 줄이 다음을 자동으로 작동시킨다.

```
[노드 정의 io.Custom("BIO_SEQRECORD")]
        │  (AST 파싱)
        ▼
[node_registry.json: outputs[].type = "BIO_SEQRECORD"]
        │
        ├─► biopython_comfy_adapter: 링크 type 자동 반영 (수정 불필요)
        ├─► workflow_validator: src.type==tgt.type 가 비로소 의미를 가짐 (수정 불필요)
        ├─► biopython_prompts: 카탈로그에 타입이 노출 → 프롬프트 문구만 손봄
        └─► ComfyUI GUI: io_type 일치 소켓끼리만 연결 (자동)
```

**직접 손대야 하는 곳은 4군데뿐이다.**

| # | 파일 | 변경 | 난이도 |
|---|------|------|--------|
| A | `py/*.py` 노드 정의 | 객체 포트의 `io.String` → `io.Custom("BIO_*")` | 양 많음(반복) |
| B | `llm_interface/harness_core/build_registry.py` | AST 파서가 `io.Custom("X")` 패턴 인식 | 한 번 |
| C | `node_registry.json` | 재생성(스크립트 실행) | 명령 1회 |
| D | `llm_interface/harness_core/biopython_prompts.py` | 카탈로그 범례 + "S→S로 연결" 문구 수정 | 작음 |

검사기(validator)·어댑터(comfy_adapter)는 **수정 불필요** — 레지스트리 타입을 그대로 읽기 때문. 다만 동작을 테스트로 고정해야 한다(§5).

---

## 1. 가장 중요한 구분 — "객체 포트" vs "파라미터 포트"

> 이 구분을 틀리면 GUI에서 정상 입력(파일 경로·옵션)까지 연결이 막힌다. **여기가 제일 실수하기 쉽다.**

- **객체 포트(→ 의미적 타입으로 변경)**: 노드 사이를 흐르는 Biopython 객체. 현재 `io.String`이고 내용이 `bio_serialize`로 직렬화된 것. 예: `records`(SeqRecord 리스트), `alignment`, `tree`, `record`(BLAST), `structure`(PDB), `chain`, `alignments`(Pairwise).
- **파라미터/원시 포트(→ 그대로 둠)**: 사용자가 GUI에서 채우는 값.
  - 파일 경로 입력 `source` / `file_path` / `output_path` → **`io.String` 유지** (사용자가 타이핑).
  - 옵션 `format`, `source_kind` 등 `io.Combo` → 유지.
  - 개수·점수 `count:INT`, `score:FLOAT`, 불리언 → 유지.

**판별 규칙**: "이 포트가 다른 노드의 출력을 받아 객체를 들고 다니는가?" → 예면 의미적 타입. "사용자가 직접 입력하는 스칼라/경로/옵션인가?" → 아니오, 그대로.

> 주의: `build_registry._detect_io_flags`는 입력 이름 `source`/`file_path`/`output_path`의 **존재**로 is_input/output_node를 판단한다. 이 입력들의 타입을 STRING으로 유지하므로 판정 로직은 영향받지 않는다.

---

## 2. 타입 목록 설계 (먼저 종이에 정의)

카테고리별로 흐르는 객체를 열거해 io_type 이름을 확정한다. 출발점 예시(실제 포트명을 보고 보강):

| io_type | 의미 | 주로 나오는 포트 |
|---------|------|------------------|
| `BIO_SEQRECORD` | 단일 SeqRecord | `record`, `seqrecord` |
| `BIO_SEQRECORD_LIST` | SeqRecord 묶음 | `records` (SeqIO_parse 출력) |
| `BIO_SEQ` | Seq 객체(서열 문자열과 구분 필요 시) | `seq` |
| `BIO_ALIGNMENT` | 다중 정렬 | `alignment` |
| `BIO_ALIGNMENT_LIST` | 정렬 묶음/pairwise 결과 | `alignments` |
| `BIO_TREE` | 계통수 | `tree` |
| `BIO_BLAST` | BLAST/Search 결과 레코드 | `record`(BLAST), `qresults` |
| `BIO_STRUCTURE` | PDB 구조 | `structure` |
| `BIO_CHAIN` | PDB 체인 | `chain` |
| `BIO_MOTIF` | 모티프 | `motif` |
| `BIO_KEGG` / `BIO_UNIPROT` / `BIO_PHENOTYPE` … | 도메인 레코드 | 각 카테고리 출력 |

> 팁: **너무 잘게 쪼개지 말 것.** 같은 객체를 받는 입력·출력은 반드시 같은 io_type이어야 연결된다. `records`(리스트)와 `record`(단일)를 섞어 쓰는 노드가 있으면 둘을 어떻게 구분/변환할지(예: "리스트→단일" 인덱싱 노드의 입력=LIST, 출력=단일) 미리 정한다.

io_type 문자열을 **한곳에 상수로 모아두면 오타를 줄인다**(단, §A의 AST 제약 때문에 노드 파일에는 리터럴로 적는다 — 아래 참조).

---

## 3-A. 노드 파일 수정 (`py/*.py`)

각 노드의 `io.Schema(... inputs=[...], outputs=[...])`에서 **객체 포트만** 바꾼다.

```python
# Before
outputs=[
    io.String.Output("records"),     # ← SeqRecord 리스트 (객체)
    io.Int.Output("count"),          # 스칼라 → 유지
    io.String.Output("ids"),         # 문자열 결과 → 유지(또는 판단)
],
inputs=[
    io.String.Input("source", default=""),   # 파일 경로 → 유지
    io.Combo.Input("format", ...),            # 옵션 → 유지
],

# After
outputs=[
    io.Custom("BIO_SEQRECORD_LIST").Output("records"),   # ← 변경
    io.Int.Output("count"),
    io.String.Output("ids"),
],
inputs=[
    io.String.Input("source", default=""),   # 그대로
    io.Combo.Input("format", ...),            # 그대로
],
```

그리고 다른 노드에서 이 `records`를 받는 입력도 **같은 타입**으로:

```python
# SeqIO_records_info 같은 소비 노드
inputs=[io.Custom("BIO_SEQRECORD_LIST").Input("records")],
```

> **왜 `io.Custom("문자열")`을 인라인으로 쓰나** — build_registry는 ComfyUI를 import하지 않고 **AST(소스 텍스트)** 로만 타입을 읽는다. `SeqRecordList = io.Custom("BIO_SEQRECORD_LIST")` 같은 별칭을 만들어 `SeqRecordList.Output(...)`로 쓰면, 파서는 변수명 `SeqRecordList`만 볼 뿐 io_type 문자열 `"BIO_SEQRECORD_LIST"`를 알 수 없다(import를 해석하지 않으므로). 따라서 **노드 소스에는 `io.Custom("리터럴")` 형태로 직접** 쓴다. 오타 방지를 위해 문자열 목록을 docstring/주석으로 한곳에 적어두고 복붙한다.

런타임에는 `bio_serialize`로 직렬화한 값을 그대로 `io.NodeOutput(...)`에 넣으면 된다 — **execute 본문은 바꿀 필요 없다.** 소켓 타입은 "연결 계약"일 뿐 페이로드 인코딩과 무관하다.

---

## 3-B. build_registry AST 파서 확장 (필수)

`_parse_io_call`이 `io.Custom("X").Input/Output` 패턴을 인식하도록 고친다. 현재는 `func.value`가 `ast.Attribute`(`io.String`)일 때만 처리하고, `io.Custom("X")`(= `ast.Call`)면 `None`을 반환해 **포트를 누락**한다.

`llm_interface/harness_core/build_registry.py`의 `_parse_io_call`에서 타입 판별부를 다음처럼 교체:

```python
    type_node = func.value

    # Case 1: io.String / io.Int / ... (ast.Attribute)
    if isinstance(type_node, ast.Attribute):
        registry_type = _TYPE_MAP.get(type_node.attr, "STRING")
    # Case 2: io.Custom("BIO_XXX") (ast.Call)
    elif (
        isinstance(type_node, ast.Call)
        and isinstance(type_node.func, ast.Attribute)
        and type_node.func.attr == "Custom"
        and type_node.args
        and _get_str(type_node.args[0]) is not None
    ):
        registry_type = _get_str(type_node.args[0])   # "BIO_SEQRECORD_LIST"
    else:
        return None
```

(기존의 `if not isinstance(type_node, ast.Attribute): return None` 두 줄을 위 블록으로 대체.)

> 주의: `_parse_io_call`의 Input 분기에서 `default` 폴백이 `{"STRING":..,"INT":..}.get(registry_type, "")`로 되어 있다. 새 `BIO_*` 타입은 여기 없으니 `""`가 폴백으로 들어가는데, **객체 입력에는 보통 default가 무의미**하므로 그대로 둬도 된다(객체 입력은 링크로 채워지므로 widget default를 안 씀). 신경 쓰이면 객체 타입일 때 `default`를 빼도록 분기 추가.

---

## 3-C. 레지스트리 재생성

```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython
python llm_interface/harness_core/build_registry.py
# → node_registry.json 갱신, "159 nodes" 출력 확인
```

재생성 후 `node_registry.json`에서 바뀐 포트의 `"type"`이 `"BIO_*"`로 들어갔는지 눈으로 확인.

---

## 3-D. 프롬프트 문구 수정 (`biopython_prompts.py`)

지금 프롬프트는 **거짓이 될 문장**을 담고 있다:
> "Biopython objects (SeqRecord, …) are serialised as STRING. Connect them S→S."

이걸 의미적 타입에 맞게 고친다.

1. `_TYPE_ABBREV`에 새 타입을 추가하거나(예: `"BIO_SEQRECORD_LIST": "SeqRecList"`), 아예 **객체 타입은 약어 없이 풀네임**으로 카탈로그에 노출한다. `build_node_catalog`가 `_TYPE_ABBREV.get(t, "S")`로 처리하므로, 폴백 `"S"`를 그대로 두면 모든 BIO_* 가 `S`로 표시되어 LLM이 구분 못 한다 → **반드시 매핑 추가** 또는 폴백을 `t`(원본 타입명)로 변경:

```python
# build_node_catalog 내부
ins = ",".join(f"{i['name']}:{_TYPE_ABBREV.get(i['type'], i['type'])}" for i in ...)
#                                                          ^^^^^^^ 폴백을 원본 타입명으로
```

2. 연결 규칙 문구를 교체:
```
- 각 객체는 고유 타입(BIO_SEQRECORD_LIST, BIO_TREE 등)을 가진다.
- 출력→입력은 **타입이 정확히 일치할 때만** 연결한다(BIO_TREE→BIO_TREE 식).
- 파일 경로/옵션(STRING, COMBO 등)은 사용자가 GUI에서 채우므로 연결하지 않는다.
```

확장 프롬프트(`get_biopython_extension_prompt`)에도 같은 문구가 있으니 함께 수정.

---

## 4. 점진적 롤아웃 전략 (한 번에 159노드 다 바꾸지 말 것)

1. **파일럿 2카테고리**: `SeqIO_Objects.py` + `Phylo_Objects.py`만 의미적 타입으로 변경(서로 연결되면 안 되는 대표 쌍). `BIO_SEQRECORD_LIST`, `BIO_TREE` 정도만.
2. 파서(§3-B) 고치고 레지스트리 재생성(§3-C).
3. **검증**(§5) 통과 + GUI에서 "SeqIO 출력 → Phylo 입력 연결 거부" 눈으로 확인.
4. 패턴이 확정되면 카테고리별로 확장(Align → BLAST/SearchIO → PDB → Pairwise → 나머지). 카테고리 1개 끝낼 때마다 §5 반복.

이렇게 하면 실수 범위가 작고, §19 drift 테스트가 매 단계 안전망이 된다.

---

## 5. 검증 체크리스트 (각 단계마다)

**자동(터미널, ComfyUI 불필요):**
```bash
# 1) 노드 파일 구문
python -m py_compile py/*.py
# 2) 레지스트리 재생성 후 drift 테스트 통과 (소스=커밋 JSON 일치)
cd /tmp && PYTHONPATH= python -m pytest \
  /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests -q
```
- §19 `test_registry_in_sync`가 통과해야 한다(재생성을 빼먹으면 실패하며 알려줌).
- **새 타입 검증 테스트를 추가**(권장, TDD): 합성 registry로 "BIO_TREE 출력 → BIO_SEQRECORD 입력" edge가 `validate_workflow_spec`에서 **type mismatch로 거부**되는지. 기존 `test_workflow_validator_graph.py`에 케이스 추가:
```python
def test_semantic_type_mismatch_rejected():
    reg = {
        "T": {"inputs": [], "outputs": [{"name": "tree", "type": "BIO_TREE"}]},
        "S": {"inputs": [{"name": "recs", "type": "BIO_SEQRECORD_LIST"}], "outputs": []},
    }
    spec = {"goal": "x",
            "nodes": [{"id": "n1", "class_type": "T"}, {"id": "n2", "class_type": "S"}],
            "edges": [{"from": "n1.tree", "to": "n2.recs"}]}
    with pytest.raises(WorkflowValidationError, match="type mismatch"):
        validate_workflow_spec(spec, reg)
```
(이 테스트는 코드 수정 없이도 통과한다 — 검사기가 이미 타입 동등성을 보기 때문. 즉 §10의 "검사기 수정 불필요"를 증명하는 회귀 테스트다.)

**수동(실행 ComfyUI에서 눈으로):**
- [ ] 변경 노드를 캔버스에 올렸을 때 객체 소켓 색/모양이 STRING과 구분되는가.
- [ ] 의미가 맞는 연결(같은 BIO_* 끼리)은 **연결됨**.
- [ ] 의미가 틀린 연결(Tree→SeqRecord)은 **드래그해도 안 붙음**.
- [ ] 파일 경로/옵션 입력(STRING/COMBO)은 종전처럼 위젯으로 입력 가능.
- [ ] LLM 생성 워크플로우(생성 패널)에서 만든 그래프가 정상 로드·연결됨.

---

## 6. 함정 / 반드시 알아둘 것

1. **기존에 저장된 워크플로우 호환성**: 예전 `.json`(또는 history)에는 링크 type이 `"STRING"`으로 박혀 있다. 출력 타입을 `BIO_*`로 바꾸면 옛 그래프를 GUI에서 열 때 타입 불일치로 링크가 끊겨 보일 수 있다. → 파일럿 단계에서 옛 그래프는 **다시 생성**하는 것을 전제로 하고, 필요하면 "마이그레이션 안내"를 남긴다.
2. **직렬화는 손대지 않는다**: `bio_serialize.serialize/deserialize`는 그대로. 소켓 타입은 연결 계약일 뿐, 페이로드(base64 pickle)와 독립.
3. **같은 객체의 입력·출력 io_type을 반드시 통일**: 한 노드는 `records`를 `BIO_SEQRECORD_LIST`로 내보내는데 받는 노드가 `BIO_SEQRECORD`(단수)면 안 붙는다. §2의 단수/복수 정책을 일관되게.
4. **COMBO/STRING 위젯 입력은 건드리지 말 것**(§1). 특히 `source`/`file_path`/`output_path`는 STRING 유지 — 안 그러면 파일 경로를 못 넣고 is_input/output_node 판정도 흔들린다.
5. **프롬프트 범례 폴백**(§3-D): `_TYPE_ABBREV` 폴백이 `"S"`면 모든 새 타입이 `S`로 뭉개져 LLM이 구분 못 한다. 폴백을 원본 타입명으로 바꾸거나 매핑을 추가.
6. **AST 파서를 먼저 고치고 노드를 바꾸면**(또는 그 반대로 하면) drift 테스트가 빨간불로 순서를 잡아준다 — 둘 다 끝나고 재생성하면 초록불.
7. **프론트 색상(선택)**: ComfyUI는 미등록 타입에 기본색을 준다. 색을 지정하려면 `llm_interface/harness_nodes/web`의 JS에서 litegraph 링크 색 맵에 `BIO_*`를 등록(기능과 무관, 가독성용).

---

## 7. 작업 순서 요약 (체크리스트)

1. [ ] §2 타입 목록을 종이에 확정(단수/복수 정책 포함).
2. [ ] §3-B build_registry 파서에 `io.Custom` 분기 추가.
3. [ ] §5 자동 테스트에 시맨틱 mismatch 케이스 추가(먼저, RED 의도).
4. [ ] §3-A 파일럿 2카테고리(SeqIO, Phylo) 객체 포트만 `io.Custom("BIO_*")`로.
5. [ ] §3-C 레지스트리 재생성.
6. [ ] §3-D 프롬프트 범례·문구 수정.
7. [ ] §5 자동 검증(py_compile + pytest, drift 통과) → 수동 GUI 검증.
8. [ ] 통과하면 카테고리 단위로 §3-A~§5 반복 확장.
9. [ ] 완료 후 `docs/2026-06-04-engineering-fixes-applied.md`의 §10 행을 "해결 완료"로 갱신.
```
