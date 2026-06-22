# 엔지니어링 리뷰 지적 — 수정 적용 기록

- **작성일**: 2026-06-04
- **상위 문서**: `docs/2026-06-04-critical-review-detailed-explanation.md` (B. 엔지니어링 관점 §9~§20)
- **방식**: TDD (실패 테스트 먼저 → 최소 구현 → 검증). 테스트는 `tests/`에 신규 작성.
- **테스트 실행**: 프로젝트 루트의 `py/` 패키지가 pytest의 레거시 `py` 의존성을 가리므로 **루트가 아닌 cwd에서 실행**한다.
  ```bash
  cd /tmp && PYTHONPATH= python -m pytest \
      /home/ydj/main/ComfyUI/custom_nodes/ComfyBIO_biopython/tests -q
  ```
- **현재 상태**: 신규 테스트 **16개 전부 통과**, 노드/하니스 전체 `py_compile` 통과.

---

## 해결 완료

### §9 — pickle 역직렬화 RCE (최우선, 보안)
**문제**: 노드들이 Biopython 객체를 `base64.b64encode(pickle.dumps(...))`로 직렬화해 STRING 소켓으로 주고받고, 소비 측에서 `pickle.loads(base64.b64decode(노드입력))`를 호출 → 공유된 워크플로우(.json)에 악성 페이로드가 실리면 임의 코드 실행.

**수정**:
- 신규 `py/bio_serialize.py` — **제한된 unpickler**(`_RestrictedUnpickler`). `find_class`에서 `Bio`/`numpy`/`collections`/`datetime`/`decimal` 접두 모듈과 안전 builtin 화이트리스트만 허용하고, 그 외(`os`, `subprocess`, `builtins.eval` 등) 참조 시 `UnsafeDeserializationError`. **와이어 포맷은 base64(pickle) 그대로** 유지해 기존 저장 값·흐름과 호환.
- 노드 레이어 15개 파일(`Align/BLAST/Cluster/Graphics/KEGG/Motif/PDB/Pairwise/Phenotype/Phylo/PopGen/SearchIO/SeqIO/Sequence_Annotation/UniProt`)의 **모든** 사이트(`pickle.loads` 95곳 + `pickle.dumps` 72곳)를 `bio_serialize.deserialize` / `bio_serialize.serialize`로 치환. 미사용 `import pickle`/`import base64` 제거.
- `__init__.py`가 `py/`를 `sys.path`에 추가 → 파일 경로로 로드되는 노드 모듈이 `import bio_serialize` 가능.

**테스트**: `test_bio_serialize.py`(5) — 기본/SeqRecord 라운드트립, 레거시 포맷 호환, `os.system`·`builtins.eval` 페이로드 거부. `test_node_layer_no_unsafe_pickle.py`(3) — 노드 레이어에 raw `pickle.loads` 부재, `__init__.py`의 sys.path 보강.

> 참고: `dumps`(생성) 자체는 보안 위협이 아니지만, import 정리와 일관성을 위해 함께 `serialize`로 통일.

### §15 — 검증이 구조 검사에 그침 (사이클 검출 추가)
**문제**: `validate_workflow_spec`이 포트 존재·타입 일치만 보고 그래프 실행 가능성을 안 봄. LLM 확장이 사이클(`n1→n2→n1`)을 만들면 ComfyUI가 실행 불가인데 검증을 통과.

**수정**: `_ensure_acyclic`(Kahn 위상정렬) 추가, `validate_workflow_spec` 말미에서 호출. 사이클(자기 루프 포함) 발견 시 관련 노드를 적시해 `WorkflowValidationError`.

**테스트**: `test_workflow_validator_graph.py`(3) — 비순환 체인 통과, 2-노드 사이클·자기 루프 거부.

### §13 — JSON 추출 견고성 (다중 블록 거부 제거)
**문제**: LLM이 스키마 예시 블록과 최종 답을 둘 다 출력하면(흔한 패턴) 두 블록이 모두 유효해 `ambiguous_json_output`으로 **전체 거부**. (코드펜스/주변 산문 케이스는 기존에도 정상 처리됨을 실측 확인.)

**수정**: `parse_and_validate_llm_output`에서 유효 블록이 여러 개면 거부 대신 **마지막 유효 블록**을 반환(관례상 최종 답이 마지막). 확장·spec 양쪽 경로 동일 적용.

**테스트**: `test_llm_contracts_multiblock.py`(2) — 예시+최종답에서 최종답(마지막) 선택.

### §19 — AST 레지스트리 drift 미검출 (가드 테스트 추가)
**문제**: 노드 스키마가 바뀌어도 `node_registry.json`(=LLM이 보는 카탈로그) 재생성을 잊으면 카탈로그와 실제가 조용히 어긋남.

**수정**: `test_registry_in_sync.py`(1) — `build_registry`(AST, ComfyUI 비의존)로 즉석 재생성한 결과와 커밋된 `node_registry.json`을 비교. 누락/추가/스키마 변경 시 실패하며 "재생성 필요" 안내. (현재는 완전 동기 상태 → 통과. drift 주입 시 정상 검출 확인 완료.)

### §12 — 죽은 자유생성 경로
**판단**: 제거가 아니라 **유지**. §3(베이스라인/ablation)에서 "자유생성 vs 템플릿 그라운딩" 비교 arm으로 필요하기 때문. 다만 "미사용·미테스트로 썩는다"는 위험은 회귀 테스트로 차단.

**수정**: `test_freeform_generation_path.py`(2) — `get_biopython_workflow_prompt`가 목표/카탈로그/출력 포맷을 포함하는지, 그 포맷을 따른 spec이 스키마 검증·파싱 경로를 통과하는지 고정.

---

## 미해결 — 전용 설계/검증 사이클 필요 (이유 명시)

이 항목들은 **실행 중인 ComfyUI 서버/프론트엔드 없이는 안전하게 검증할 수 없거나**, 선행 메타데이터·평가 데이터가 필요하다. 검증 불가한 변경을 무리하게 가하면 동작 중인 기능을 깨뜨릴 위험이 커서 보류하고 별도 사이클로 분리한다.

| 항목 | 보류 이유 | 선행 조건 |
|------|-----------|-----------|
| **§10 의미적 소켓 타입** | 출력 245개가 `STRING`이라 타입 검증이 무력. 해결하려면 `comfy_api`의 커스텀 소켓 타입 설계 + ~245개 포트의 도메인별 타입 매핑 + **GUI 연결성 실검증**이 필요. | comfy_api 타입 API 조사, 실행 ComfyUI |
| **§14 e2e 실행 검증** | 생성 JSON이 실제 ComfyUI에서 로드·실행되는지는 헤드리스 서버 라운드트립이 있어야 측정 가능. | 헤드리스 ComfyUI 기동 + `/prompt` API |
| **§17 per-job 로그 격리** | `exec_log`가 llm_runner·전 adapter·공개 API(`/comfybio/execution_log`)·프론트엔드 SSE까지 관통. job_id 스레딩은 공개 API/프론트 변경을 수반하고 실행 환경 없이는 검증 불가. | 실행 ComfyUI + 프론트엔드 |
| **§15 필수입력/도달성 검증** | "필수 입력 미연결" 판정에 입력의 optional 여부 메타데이터가 필요하나 현재 레지스트리에 없음. (사이클 검출은 완료) | `build_registry`에 optional 플래그 추출 추가 |
| **§16 history 임계값/성능** | 0.42 임계값 변경은 §16에서 스스로 지적한 "근거 없는 매직넘버 튜닝"에 해당 — 재사용 효과의 평가 데이터가 선행되어야 함. O(N) 스캔의 상한 도입은 "최근 N개만 고려"라는 의미 변경이라 평가와 함께 결정. | history on/off ablation 데이터(§3) |
| **§18 / §20** | 코드 수정이 아니라 평가 전략(LLM은 목/우회되어 가설 미검증)·로드맵 시퀀싱(토대 선검증 후 확장)에 관한 프로세스 권고. | 별도 평가 트랙·제안 검증 절차 |

---

## 변경 파일 요약

**신규**
- `py/bio_serialize.py`
- `tests/conftest.py`
- `tests/harness_core/test_bio_serialize.py`
- `tests/harness_core/test_node_layer_no_unsafe_pickle.py`
- `tests/harness_core/test_workflow_validator_graph.py`
- `tests/harness_core/test_llm_contracts_multiblock.py`
- `tests/harness_core/test_registry_in_sync.py`
- `tests/harness_core/test_freeform_generation_path.py`

**수정**
- `__init__.py` — `py/`를 sys.path에 추가
- `llm_interface/harness_core/workflow_validator.py` — `_ensure_acyclic`
- `llm_interface/harness_core/llm_contracts.py` — 다중 블록 시 마지막 유효 블록 반환
- `py/*.py` (15개 노드 파일) — pickle→bio_serialize 마이그레이션
