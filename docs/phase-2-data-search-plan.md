# 2차 개발 계획: 데이터 적재 및 검색 검증

## 1. 1차 판정

- 판정: 조건부 통과
- 통과 범위:
  - PPT `12/19/29` 구조 추출 가능
  - intermediate candidate 생성 가능
  - Figma 비교 기준 확보
  - 비주얼 테스트 플러그인 동작 경로 확보
- 보류 범위:
  - 색상 / 알파
  - 도형 fidelity
  - connector 정확도
  - typography / 정확한 좌표
  - 실제 slide canvas 크기 반영

2차는 위 보류 항목을 1차 보완 backlog로 분리한 채 진행한다.

## 2. 2차 목표

현재 intermediate candidate를 canonical 데이터 모델로 적재하고,
정책/담당/설명 연결과 검색 검증이 가능한 최소 구조를 만든다.

핵심 질문:

1. 현재 추출 결과가 `document/page/node/asset/source_mapping` 구조로 안정적으로 내려가는가
2. `12/19/29` 기준으로 page/node 단위 검색이 가능한가
3. 이후 `knowledge_document`, `annotation`, `ownership`를 연결할 수 있는가

## 3. 범위

### 포함

- canonical entity 매핑
- 로컬 저장용 DB 스키마 초안
- intermediate -> canonical 변환 스크립트
- search projection 초안
- 검색 검증 시나리오

### 제외

- 시각 fidelity 개선
- full sync / conflict / approval 구현
- 포털 UI

## 4. 현재 intermediate -> canonical 매핑

### document

- source: PPT 파일
- 예시 subtype: `planning_doc`
- 주요 필드:
  - `id`
  - `title`
  - `source_type = ppt`
  - `source_ref = sampling/pptsample.pptx`

### page

- source: slide 12 / 19 / 29
- subtype: `ppt_slide`
- 주요 필드:
  - `id`
  - `document_id`
  - `order_index`
  - `title`
  - `source_path`

### node

- source: intermediate candidates
- 현재 우선 subtype:
  - `text_block`
  - `labeled_shape`
  - `shape`
  - `connector`
  - `group`
  - `section_block`
  - `table`
  - `table_row`
  - `table_cell`

### asset

- source: `image`
- 주요 필드:
  - `id`
  - `document_id`
  - `page_id`
  - `node_id(optional)`
  - `asset_type = image`
  - `source_ref`

### source_mapping

- PPT 기준:
  - `internal_entity_type`
  - `internal_entity_id`
  - `source_type = ppt`
  - `external_ref_id = source_node_id`
  - `source_path`

## 5. 2차 작업 순서

### Step 1. canonical 변환 규칙 확정

- slide -> page 매핑
- candidate -> node/asset 매핑
- parent_candidate_id -> parent_node_id 매핑
- source_path / source_node_id -> source_mapping 저장 규칙 확정

산출물:

- canonical mapping spec v1

### Step 2. 로컬 DB 스키마 초안

우선 테이블:

- `atlas_documents`
- `atlas_pages`
- `atlas_nodes`
- `atlas_assets`
- `atlas_source_mappings`

보조 테이블:

- `atlas_knowledge_documents`
- `atlas_annotations`
- `atlas_ownerships`
- `atlas_relations`
- `atlas_search_index`

산출물:

- schema draft v1

### Step 3. intermediate -> canonical 변환 스크립트

입력:

- `docs/ppt-intermediate-candidates-12-19-29.json`

출력:

- canonical JSON
- DB insert seed JSON 또는 SQL

산출물:

- canonical export 파일

### Step 4. search projection 생성

우선 projection 대상:

- page title
- node text
- labeled shape text
- table cell text
- image placeholder label
- source refs

검색 결과는 최소한 아래 문맥을 가져야 한다.

- `document_id`
- `page_id`
- `node_id`
- `entity_type`
- `title`
- `searchable_text`
- `source_path`

### Step 5. 검색 검증

1차 검증 질의:

- `케어십`
- `리뷰`
- `제품 카테고리별 평가 항목`
- `최대할인가`
- `옵션 선택`

검증 포인트:

- 올바른 slide/page로 연결되는가
- node 수준 결과가 나오는가
- table cell text가 검색되는가
- source_path 추적이 가능한가

## 6. 2차 종료 조건

아래를 만족하면 2차 1차본 통과로 본다.

1. `12/19/29`가 canonical `document/page/node/asset/source_mapping` 구조로 적재된다
2. page/node 단위 검색 결과가 나온다
3. 검색 결과에서 어느 slide/page/node인지 추적 가능하다
4. 이후 `knowledge_document`, `annotation`, `ownership`를 붙일 수 있는 위치가 명확하다

## 7. 기획자 검토 포인트

2차에서 기획자가 볼 것은 시각이 아니라 데이터 운영성이다.

- 검색 결과가 기획 문맥으로 읽히는가
- table cell 단위가 실제로 유의미한가
- page/node 단위로 정책/담당 연결이 가능해 보이는가
- 어느 수준까지 node를 유지해야 하는지 판단 가능한가
