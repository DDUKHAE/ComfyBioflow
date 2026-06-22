# ComfyBIO LLM-기반 Biopython 워크플로우 구축 — 비판적 리뷰

- **문서 성격**: 비판적 코드·연구 리뷰 (논문 리뷰어 + 시니어 엔지니어 관점)
- **작성일**: 2026-06-04
- **대상 시스템**: `ComfyBIO_biopython` — 159개 Biopython 노드 + 템플릿 그라운딩 LLM 엔진(`goal → 템플릿 선택 → 확장 spec 생성 → 검증 → ComfyUI JSON`) + 벤치마크 하니스 + 워크플로우 이력 재사용
- **검토 범위**: `llm_interface/harness_core/*`, `benchmarks/*`, `docs/superpowers/specs/2026-06-04-breeding-multimodal-expansion-design.md`

논문 리뷰어와 시니어 엔지니어 두 관점에서 비판을 정리했다. 공정성을 위해 강점부터 짚는다.

---

## 인정할 만한 설계 (리뷰어가 먼저 칭찬할 부분)

- **템플릿 그라운딩 + 확장 패턴** (`template_selector.py` → `workflow_assembler.py`): LLM을 자유생성이 아니라 "검증된 base에 최소 확장만"으로 제약하는 것은 환각(hallucinated class_type/port)을 줄이는 합리적 설계다.
- **아티팩트 지문화** (`artifact_fingerprints.py`, registry/template sha256 기록): 재현성·provenance를 의식한 흔치 않은 좋은 습관이다.
- **canonical spec ↔ ComfyUI JSON 분리** (`biopython_comfy_adapter.py`): LLM 출력 포맷과 GUI 포맷을 디커플링한 것은 깔끔하다.
- **AST 기반 자동 레지스트리** (`build_registry.py`): 노드 추가 시 엔진 무수정 — 확장성 면에서 영리하다.

---

## A. 논문 리뷰어 관점 (연구 기여·평가의 문제)

**1. 기여(contribution)와 신규성이 불명확하다.**
"ComfyUI + LLM + Biopython"은 *시스템 통합*이지 그 자체로 방법론적 신규성이 아니다. 리뷰어는 즉시 묻는다: GeneGPT, AutoBA, BioMANIA, Galaxy/Nextflow+LLM, 일반적 LLM tool-calling 대비 **무엇이 새로운가?** 기여가 (a) 아키텍처인지 (b) 평가/발견인지 (c) "GUI 노드 그래프로 워크플로우를 생성한다"는 점인지 한 문장으로 정의되어 있지 않다. 이게 없으면 "engineering report"로 분류되어 reject된다.

**2. 평가가 치명적으로 빈약하고 순환적이다 (가장 큰 결격 사유).**
`benchmarks/cases/`에 템플릿 선택 **3건**, 확장 **1건**, 실행 **1건**이 전부다. 이건 평가가 아니라 smoke test다. 게다가:
- 벤치마크 쿼리("load a Newick phylogenetic tree")가 템플릿 keywords(`newick`, `tree`)와 **어휘를 공유** → 같은 저자가 만든 정답으로 자기 시스템을 평가하는 **순환 평가/과적합**.
- 통계적 검정력 없음, held-out 셋 없음, 실제 생물학자 phrasing 없음, 모호/다단계 쿼리 없음.

리뷰어는 "최소 수십~수백 개의 독립 구축된 테스트셋, 패러프레이즈/모호성 포함"을 요구할 것이다.

**3. 베이스라인·ablation이 전무하다.**
"템플릿 그라운딩이 도움이 된다"고 주장하려면 **자유생성 경로**(`get_biopython_workflow_prompt`)와 비교해야 하는데, 그 경로는 코드에 존재만 하고 벤치마크에 없다. history 재사용 on/off, 모델별 비교도 없다. 즉 핵심 설계 선택을 뒷받침하는 증거가 0이다.

**4. "정확성"의 정의가 잘못 잡혀 있다.**
`execution_success`는 노드를 직접 호출해 출력 문자열(`count=2`, `seq1 len=8`)을 매칭한다. 이는 "실행되어 예상 문자열을 냈는가"이지 **"워크플로우가 생물학적으로 옳은가 / 사용자 의도를 달성했는가"가 아니다.** schema-valid ≠ semantically correct. 검증을 다 통과하면서도 생물학적으로 무의미한 워크플로우가 가능하다. 의미적/과업적 정확성을 측정하는 지표가 없다.

**5. Edge P/R/F1이 "정답 워크플로우 유일" 가정에 기반한다.**
`metrics.py`의 exact-match edge 채점은 동일 목표를 달성하는 **여러 유효한 워크플로우**를 오답 처리한다 → 성능을 과소평가하고, 동시에 "한 가지 정답"이라는 비현실적 전제를 깐다. 기능적 등가성 평가나 전문가 레이팅이 필요하다.

**6. 도메인 전문가/사용자 평가 부재.**
생물정보 도구인데 생물학자가 유용성·정확성을 판정한 user study가 없다.

**7. 재현성 위협.**
엔진이 claude/codex/gemini **CLI 래퍼**(`llm_adapters/`)라 비결정적이고 모델 버전이 드리프트한다. temperature/seed/모델 스냅샷 고정이 없다. registry는 sha256으로 고정했지만 *정작 변동의 주범인 LLM*은 고정 안 됨 → 논문 결과를 6개월 후 재현 불가.

**8. 일반화 주장이 아티팩트로 뒷받침되지 않는다 (결정적).**
`workflow_templates.json`의 5개 템플릿이 **전부 단일 노드, edges 빈 배열**("read/parse")이다. 시스템이 진짜 다단계 파이프라인(parse→align→build tree→render, 분기, 파라미터 와이어링)을 생성한 증거가 없다. 정작 어려운 문제(다중 노드 오케스트레이션)가 미시연인데 "워크플로우 구축"을 주장하면 리뷰어가 정면으로 반박한다.

---

## B. 엔지니어 관점 (코드·아키텍처)

**9. 보안: 와이어로 흐르는 pickle = RCE.**
설계 문서 §1.2가 객체를 "STRING(base64+pickle)"으로 직렬화한다고 명시한다. 공유된 워크플로우를 로드하면 `pickle.loads`가 **임의 코드 실행** 벡터가 된다. 도구를 배포·공유할 거라면 심각한 결함이다. 안전 직렬화(JSON 스키마, 또는 타입드 소켓)로 교체해야 한다.

**10. 타입 시스템이 사실상 무의미하다.**
`workflow_validator.py`는 `src.type == tgt.type`를 검사하지만 SeqRecord·Alignment·BLAST result·Tree가 **전부 "STRING"**이다. 즉 phylo tree 출력을 sequence 입력에 그대로 연결해도 검증을 통과한다. 자랑하는 "타입 안전 검증"이 도메인 객체에는 거의 안전을 제공하지 않는다. `SEQRECORD`/`ALIGNMENT`/`TREE` 같은 **의미적 서브타입을 별도 ComfyUI 소켓 타입**으로 만들어야 진짜 검증이 된다.

**11. 템플릿 선택이 순진한 bag-of-words.**
`select_template`은 토큰 교집합 Jaccard + path-hint 0.2 보너스다. 패러프레이즈("build an evolutionary tree from sequences")에 newick/tree 토큰이 없으면 실패한다. 5개 템플릿이라 지금은 trivial하게 맞지만, 노드/템플릿이 늘면(문서가 159→200+ 예고) 깨진다. 임베딩 기반 검색으로 가야 한다.

**12. 자유생성 경로가 죽은 코드.**
`get_biopython_workflow_prompt`, `validate_biopython_workflow_spec_schema`는 존재하지만 `llm_runner`는 확장 경로만 쓴다. 미사용·미테스트 병렬 경로 → 유지보수 위험 + "실제 시스템이 무엇인가" 혼선.

**13. JSON 추출이 깨지기 쉽다.**
`extract_json_blocks`의 수제 brace matcher, `parse_and_validate_llm_output`의 "마지막 문자가 `}])."`가 아니고 brace 불균형이면 truncated" 휴리스틱, 복수 유효 블록 시 `ambiguous` 에러 — 모두 LLM이 *bare JSON*을 준다는 가정에 의존한다. 모델의 자연 출력과 싸우는 구조다. 가능한 provider에서는 **structured output / JSON mode / tool-calling**으로 바꾸는 게 정석이다. 또 끝부분 `validate_*_schema(candidates[0])` 호출들은 반환값을 버리고 첫 후보 에러만 re-raise하는 혼란스러운 흐름이다.

**14. ComfyUI JSON이 실제 서버에서 로드·실행되는지 end-to-end 검증이 없다.**
`benchmarks/README.md`가 "서버 없이 노드를 직접 호출"한다고 명시한다. `canonical_to_comfy_json`의 `widgets_values`(연결 입력 스킵, 스키마 순서), `slot_index`, `last_link_id = len(links)`는 ComfyUI의 악명 높은 위젯/링크 순서 민감성에 노출된다. "ComfyUI-loadable 워크플로우를 생성한다"는 주장이 **실 서버 라운드트립으로 입증되지 않았다.**

**15. 검증이 구조 검사에 그친다.**
`validate_workflow_spec`은 DAG 비순환성, 필수 입력 충족(default 없는 `source`가 미연결인 경우), output 노드 도달성을 검사하지 않는다. 즉 "validated" 워크플로우가 실행 불가일 수 있다.

**16. 이력 재사용이 품질을 떨어뜨릴 수 있고 O(N)이다.**
`find_similar`의 min_score 0.42 Jaccard는 약한 문턱이라 LLM을 틀린 prior에 앵커링할 수 있는데, 재사용이 도움/해악인지 평가가 없다. 또 매 요청마다 JSONL 전체를 선형 스캔한다.

**17. 동시성/상태가 단일 사용자 가정.**
`exec_log`는 프로세스 전역 + `exec_log.clear()`, `active_jobs` 전역 dict → 동시 생성 시 로그가 섞인다.

**18. 테스트가 가설이 아니라 배관을 검증한다.**
테스트는 schema/assembler/selector 같은 결정적 플러밍을 잘 덮지만 **정작 연구 대상인 LLM은 우회/목**된다 → 통과가 "하니스가 동작한다"는 의미일 뿐 "LLM이 올바른 워크플로우를 만든다"의 근거가 못 되어 false confidence를 준다.

**19. AST 추출의 silent drift.**
`build_registry.py`가 `io.Schema` 패턴을 정확히 안 따르는 노드를 조용히 누락하거나 COMBO 옵션/타입을 오추론하면 카탈로그와 실제가 어긋나는데, 이를 감지하는 일관성 테스트가 없다.

**20. 육종/멀티모달 제안의 시퀀싱 리스크.**
설계 문서가 "gemini CLI는 @경로 이미지 지원, claude CLI도 *알려진 바로는* 가능"이라는 **미검증** 전제 위에 GWAS/GS/GEBV/QTL 로드맵을 얹는다. 정작 코어 엔진이 3-노드 파이프라인도 미시연인데 스코프를 먼저 확장하는 것은 위험하다. 게다가 pickle-as-STRING 직렬화는 이미지 텐서를 의미 있게 운반하지 못한다. (문서가 리스크를 표로 인지한 점은 좋으나, Phase 1 "첫 작업으로 실측"이라는 완화책은 *제안 승인 전에* 해소되어야 할 핵심 불확실성이다.)

---

## 만약 Reviewer 2라면: "이게 안 고쳐지면 reject"

1. **기여 한 문장 정의** + 관련연구 대비 위치 설정.
2. **독립 구축된 평가셋**(수십~수백, 패러프레이즈/모호/다단계 포함)으로 순환성 제거.
3. **베이스라인**(자유생성 vs 템플릿그라운딩, history on/off, 모델별)과 ablation.
4. **다단계 워크플로우**(≥3 노드, 비자명 edge)를 실제로 생성·실행하는 증거.
5. **의미적 정확성 지표** + 도메인 전문가 평가.
6. **실 ComfyUI 서버 end-to-end 실행 성공률**.
7. 모델 버전/temperature **고정**하고 다회 실행 분산 보고.

---

## 엔지니어로서 "지금 당장" 권하는 것

- 도메인 객체에 **의미적 소켓 타입** 도입 (10·14번을 동시 해결).
- pickle 직렬화 **보안 검토/교체** (9번).
- 죽은 자유생성 경로 **제거 또는 벤치마크 편입** (12번).
- 검증기에 **비순환·필수입력·도달성** 추가 (15번).
- benchmark를 **실 ComfyUI 서버 라운드트립**으로 승격 (14번).
