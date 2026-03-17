# 2차 진행 상태: 데이터 적재 및 검색 검증

## 현재 생성된 산출물

- canonical 매핑 규칙:
  - `docs/canonical-mapping-spec-v1.md`
- canonical seed:
  - `docs/canonical-seed-12-19-29.json`
- search projection:
  - `docs/phase2-search-index-12-19-29.json`
- SQLite demo DB:
  - `docs/phase2-demo.sqlite`
- 검색 검증 결과:
  - `docs/phase2-search-checks.json`
- 로컬 DB 스키마:
  - `sql/atlas_phase2_schema.sql`

## 현재 적재 결과

- documents: 1
- pages: 3
- nodes: 587
- assets: 11
- source mappings: 602
- relations: 392
- search rows: 602

## 현재 검색 검증 결과

### `케어십`

- slide 12의 제목/라벨 노드 중심으로 검색됨
- flow/step 노드까지 추적 가능

### `리뷰`

- slide 19의 제목과 table cell이 검색됨
- table cell 단위 검색이 가능한 상태
- 일부 slide 29 cell도 문구 포함 시 검색됨

### `제품 카테고리별 평가 항목`

- slide 19 page + 관련 node 검색 가능

### `최대할인가`

- slide 29의 특정 labeled shape 1건으로 정확히 검색됨

### `옵션 선택`

- slide 29의 page + 핵심 라벨 노드 검색 가능

## 현재 판단

2차 기준으로 아래는 확인되었다.

1. intermediate candidate를 canonical `document/page/node/asset/source_mapping` 구조로 적재 가능
2. page/node/cell 단위 검색 가능
3. source_path를 통해 원본 slide 내부 위치 역추적 가능
4. 이후 `knowledge_document`, `annotation`, `ownership`를 page/node 단위로 붙일 수 있는 구조 확보

## 현재 한계

- relevance ranking은 아직 단순 substring 기반
- `리뷰`처럼 범용 키워드는 일부 다른 slide cell도 같이 검색될 수 있음
- knowledge / ownership / annotation 실제 데이터는 아직 적재 안 됨
- 검색 결과 집계 UI는 아직 없음

## 다음 단계

### 우선순위 1

- `knowledge_document`
- `annotation`
- `ownership`

를 최소 샘플 데이터로 붙여서 검색 결과가 운영 문맥까지 확장되는지 검증

### 우선순위 2

- 검색 결과 집계 포맷 정의
- 문서 / 페이지 / 노드 / 정책 / 담당자 문맥 노출 방식 정리

### 우선순위 3

- 포털 read model 설계
- 웹 UI 초기 테스트로 연결
