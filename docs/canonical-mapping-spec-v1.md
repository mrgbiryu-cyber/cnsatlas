# Canonical Mapping Spec v1

## 목적

`docs/ppt-intermediate-candidates-12-19-29.json`를
2차 검증용 canonical 데이터 구조로 내리는 규칙을 고정한다.

## 범위

- 입력: intermediate candidates
- 출력:
  - `atlas_documents`
  - `atlas_pages`
  - `atlas_nodes`
  - `atlas_assets`
  - `atlas_source_mappings`
  - `atlas_relations`

## 매핑 원칙

### document

- 현재 benchmark PPT 전체를 하나의 `document`로 적재
- `document_type = planning_doc`
- `subtype = ppt_file`

### page

- slide 1개 = page 1개
- `page_type = ppt_slide`
- `subtype = ppt_slide`
- `source_ref_id = slide:{slide_no}`

### node

- intermediate candidate 중 `node_type = node`는 모두 `atlas_nodes`로 적재
- `parent_candidate_id`가 다른 candidate를 가리키면 `parent_node_id`로 변환
- `page:{slide_no}`를 가리키는 경우는 page 루트로 간주하고 `parent_node_id = null`

### asset

- intermediate candidate 중 `node_type = asset`는 `atlas_assets`로 적재
- 현재는 `image`만 해당

### source_mapping

- document / page / node / asset 모두 source mapping 생성
- `source_type = ppt`
- `external_container_id = original pptx path`
- `external_ref_id = source_node_id 또는 slide_no`
- `source_path = intermediate source_path`

## subtype -> node_type

| subtype | node_type |
|---|---|
| text_block | text |
| labeled_shape | shape |
| shape | shape |
| connector | connector |
| group | group |
| section_block | frame |
| table | table |
| table_row | row |
| table_cell | cell |

## geometry / style

- `bounds_px` -> `geometry_json`
- `extra` -> `style_json`

현재 `style_json`은 제한적이다.
실제 색상, alpha, typography, connector geometry는 1차 보완 backlog로 분리한다.

## 검색 projection 규칙

### document

- title
- description
- subtype

### page

- page title
- subtype
- source ref

### node

- title
- raw_text
- normalized_text
- subtype
- page title

### asset

- asset type
- storage_url
- page title

## 한계

- visual fidelity 정보는 아직 충분히 없음
- cell별 실제 width/height 반영 안 됨
- connector의 실제 경로 정보 없음
- knowledge / annotation / ownership는 아직 seed에 포함 안 됨

## 2차 검증에 필요한 최소 보장

1. 검색 가능한 text가 page/node/cell 단위로 보존된다
2. source_path로 원본 slide 내부 위치를 역추적할 수 있다
3. 이후 knowledge/ownership를 page/node 단위로 연결할 수 있다
