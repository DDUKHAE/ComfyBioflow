# Workflow Selection Rubric

## Purpose

생물학적 질문을 분석 workflow와 도구군으로 연결하는 탐색 rubric이다. 특정 도구의 최신 버전을 고정하는 문서가 아니라, 어떤 정보를 확인해야 선택할 수 있는지를 정의한다.

## Routing dimensions

1. **Question type**: 기술통계, 그룹 비교, 예측, 인과, 시간 변화, 분류, 군집화, pathway, 구조·기능
2. **Evidence type**: raw data, count matrix, reference genome, GTF/GFF, phenotype table, literature, public database
3. **Analysis unit**: read, cell, sample, gene, transcript, protein, variant, pathway
4. **Data constraints**: 표본 수, replicate, batch, time point, read layout, missingness, annotation 품질
5. **Delivery**: 비교표, workflow graph, 도구 shortlist, 검증 계획, 문헌 기반 추천

## Candidate comparison matrix

| 질문/조건 | 먼저 비교할 도구군 | 선택을 바꾸는 정보 |
|---|---|---|
| reference 기반 gene-level 발현 비교 | alignment/count, transcript quantification | splice QC 필요 여부, annotation 품질, 저장공간 |
| transcript 또는 isoform 질문 | transcript-aware quantification, isoform usage | read length, transcript annotation, unique junction support |
| reference 또는 annotation 부족 | annotation retrieval, homolog mapping, assembly | strain/line 일치성, novel feature 필요 여부 |
| time-course | factorial model, interaction, trajectory | time point 수, replicate, missing cell, 선형성 가정 |
| batch 또는 confounder 존재 | covariate model, stratified analysis | design matrix 식별 가능성, 변수 간 완전 중복 |
| pathway 또는 gene-set 질문 | ranked enrichment, over-representation, network | gene ID mapping, background set, 사전 정의 여부 |
| single-cell 또는 cell-type 질문 | cell-level QC, clustering, pseudobulk, cell-type model | cell 수, biological replicate, tissue composition |

## Decision labels

- **확정 가능한 경로**: 필요한 입력과 핵심 근거가 확인됨
- **조건부 추천**: 한두 개의 미정 정보가 선택을 바꿈
- **탐색적 대안**: 질문에는 관련되지만 validation 또는 annotation 근거가 부족함
- **현재 판단 불가**: 후보를 비교할 핵심 정보가 없음

## Exploration output

각 후보는 다음 순서로 설명한다.

```text
생물학적 질문
→ 필요한 증거와 분석 단위
→ 후보 workflow
→ 후보 도구군
→ 출처 확인 항목
→ 장점·한계·실패 조건
→ 추천 상태와 다음 확인 정보
```
