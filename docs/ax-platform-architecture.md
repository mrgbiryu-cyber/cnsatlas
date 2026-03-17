# AX 전환 프로젝트 아키텍처 초안

## 1. 현재 상태 분석

### 1-1. 왜 단순 변환기가 아닌 운영 플랫폼인가

이 프로젝트의 시작점은 PPT 기획서를 Figma로 옮기는 일이다. 그러나 실제 운영 흐름은 변환에서 끝나지 않는다.

- 기존 기획서는 PPT에 존재한다.
- 초기 이관 후 실제 운영 산출물은 Figma에서 계속 수정된다.
- 기획팀은 별도 내부 포털에서 정책, 설명, 담당자, 승인 상태, 변경 이력, 관련 문서를 함께 관리해야 한다.
- 변경된 Figma 구조를 다시 내부 시스템으로 수집해야 한다.
- 검색과 질의응답은 화면 구조뿐 아니라 정책 문서, 주석, 담당자, 연결 관계까지 함께 다뤄야 한다.

따라서 이 시스템은 "PPT를 Figma로 옮기는 도구"가 아니라 아래를 통합하는 운영 플랫폼이다.

- 초기 산출물 이관
- 산출물 구조 운영
- 정책/설명/담당 지식 연결
- Figma 증분 동기화
- 검색 및 질의응답

### 1-2. 왜 `knowledge_document`와 `ownership`가 필요한가

PPT나 Figma만으로는 운영에 필요한 설명 정보가 충분하지 않다.

- 특정 셀이나 영역의 기획 의도
- 왜 이 정책이 적용되는지
- 누가 담당자인지
- 누가 승인자인지
- 어떤 부서와 연관되는지
- 어떤 검수 기준이 연결되는지

이 정보는 화면 구조와 성격이 다르다. 따라서 화면 구조와 별개로 저장해야 한다.

- 화면 구조: `document`, `page`, `node`, `asset`
- 지식 구조: `knowledge_document`, `annotation`
- 책임 구조: `ownership`

이렇게 분리해야 검색, 권한, 승인, 변경 이력, 추적성이 안정적으로 유지된다.

### 1-3. 왜 Figma incremental pull이 필수인가

초기 변환 이후 운영은 Figma에서 계속된다. 따라서 내부 시스템이 최신 상태를 유지하려면 정기 또는 수동으로 Figma 변경분을 다시 가져와야 한다.

필수 이유는 다음과 같다.

- 화면 구조와 레이아웃은 Figma가 실질 원본이다.
- 내부 포털의 설명, 정책, 담당 정보는 DB가 실질 원본이다.
- 두 시스템이 함께 운영되므로 변경사항을 필드 단위로 병합해야 한다.
- 전체 파일 재빌드만 하면 운영 중 연결된 정책, 담당, 주석, 검색 인덱스가 쉽게 깨진다.

따라서 checkpoint 기반의 증분 pull, page/node 단위 diff, field-level merge가 필요하다.

## 2. 최종 설계 결정

### 2-1. 최상위 구조

시스템은 아래 5계층 도메인으로 설계한다.

1. 산출물 계층
- `document`
- `page`
- `node`
- `asset`

2. 지식 계층
- `knowledge_document`
- `annotation`

3. 책임 계층
- `ownership`

4. 연결 계층
- `relation`
- `source_mapping`

5. 검색/질의 계층
- `search_index`
- `qa_context`(논리 레이어)

### 2-2. 문서 중심 모델

최상위 엔티티는 항상 `document`다. 모든 산출물과 지식은 문서 문맥 안에서 탐색 가능해야 한다.

- 기획서, 정책서, 가이드, Figma 파일, PPT 파일을 모두 문서로 취급
- 화면 단위는 `page`
- 세부 UI/셀/영역/파트는 `node`
- 첨부 리소스는 `asset`

이 구조는 내부 포털에서 "문서 > 페이지 > 영역" 흐름으로 탐색 가능하게 해준다.

### 2-3. 화면 구조와 지식 구조 분리

화면 구조는 Figma/PPT 계층을 반영한다.

- `document`
- `page`
- `node`
- `asset`

운영 지식은 별도 계층으로 둔다.

- `knowledge_document`: 정책, 가이드, 용어집, 검수 기준 등 독립 문서
- `annotation`: 문서/페이지/노드에 부착되는 설명, 메모, 검수 의견

중요한 원칙은 정책 문서를 주석으로 축소하지 않는 것이다. 정책 문서는 검색과 연결의 중심이 되는 독립 객체여야 한다.

### 2-4. 책임 정보 분리

담당자 정보는 메모가 아니라 정규 모델로 저장한다.

- `ownership_type`: owner, planner, approver, reviewer, related_team, dev_owner, ops_owner
- `actor_type`: user, team, org_unit, external_partner

이 구조가 있어야 "이 영역은 누가 담당인가" 같은 질문에 안정적으로 응답할 수 있다.

### 2-5. 필드별 authoritative source

엔티티 전체를 한 시스템의 원본으로 두지 않는다. 필드별 원본 정책을 적용한다.

허용 source:

- `ppt`
- `figma`
- `db`
- `manual`
- `system_generated`

필드 그룹별 원칙:

- Figma authoritative
  - geometry
  - z-order
  - hierarchy
  - frame/group/component structure
  - style binding
  - page ordering
  - node visibility
  - layout structure

- PPT authoritative
  - 최초 업로드 원본 파일
  - import trace
  - 원본 슬라이드 번호
  - 원본 해시
  - 초기 이관 lineage

- DB authoritative
  - 정책 설명
  - 페이지 목적
  - 노드 설명
  - 운영 메모
  - 승인 상태
  - 태그
  - 담당자 정보
  - 관련 조직 정보
  - 연결 문서 설명
  - 검색용 정규화 텍스트

- manual authoritative
  - 수동 교정 텍스트
  - 확정 문구
  - 검수 결과
  - override 값

- system_generated authoritative
  - AI 요약
  - 자동 태깅
  - OCR 보정
  - 추천 연결
  - merge suggestion

`system_generated`는 승인 전까지 최종 진실값으로 채택하지 않는다.

### 2-6. 핵심 엔티티 정의

#### `document`

의미:

- 기획서
- 정책서
- 가이드 문서
- Figma 파일 논리 문서
- PPT 원본 문서
- 포털 문서

주요 subtype:

- `planning_doc`
- `policy_doc`
- `guide_doc`
- `figma_file`
- `ppt_file`
- `portal_doc`

#### `page`

의미:

- PPT 슬라이드
- Figma page
- 내부 문서 페이지
- 논리 섹션

주요 subtype:

- `ppt_slide`
- `figma_page`
- `web_page`
- `logical_section`

#### `node`

의미:

- 텍스트 블록
- 표
- 셀
- 프레임
- 그룹
- 컴포넌트
- 섹션 영역
- 특정 UI block

주요 subtype:

- `text`
- `shape`
- `frame`
- `group`
- `component`
- `instance`
- `table`
- `row`
- `cell`
- `chart`
- `connector`
- `image_placeholder`
- `section_block`

이 모델은 "어느 셀", "어느 파트", "어느 영역" 수준까지 표현 가능해야 한다.

#### `asset`

의미:

- 이미지
- 아이콘
- 원본 파일
- export 결과물
- 썸네일
- 첨부파일

주요 subtype:

- `image`
- `svg`
- `ppt_file`
- `pdf_export`
- `thumbnail`
- `attachment`

#### `knowledge_document`

의미:

- 정책 문서
- 업무 기준서
- 서비스 설명서
- 운영 정책
- 용어집
- 업무 가이드
- 검수 기준

주요 subtype:

- `policy`
- `guideline`
- `terminology`
- `process_doc`
- `review_guide`
- `qa_reference`

#### `annotation`

의미:

- 특정 문서/페이지/노드에 부착되는 설명
- 검수 의견
- 경고
- 운영 메모

주요 subtype:

- `description`
- `policy_note`
- `review_comment`
- `sync_warning`
- `ai_generated_note`
- `operator_note`

#### `ownership`

의미:

- 담당자
- 담당 조직
- 승인자
- 관련 부서
- 개발 담당
- 운영 담당

주요 subtype:

- `owner`
- `planner`
- `approver`
- `reviewer`
- `related_team`
- `dev_owner`
- `ops_owner`

#### `relation`

의미:

- 엔티티 간 논리 관계

주요 subtype:

- `parent_child`
- `figma_mapping`
- `ppt_mapping`
- `references`
- `derived_from`
- `linked_policy`
- `linked_owner_scope`
- `similar_to`
- `synced_to`

#### `source_mapping`

의미:

- 내부 엔티티와 외부 원본 간 연결

핵심 필드 예:

- `figma_file_key`
- `figma_node_id`
- `ppt_object_path`
- `original_slide_no`
- `source_hash`
- `source_version`

### 2-7. 선택적 동기화 정책

완전 양방향 sync는 허용하지 않는다. selective sync + approval 기반으로 설계한다.

지원 `sync_mode`:

- `import_only`
- `figma_to_db`
- `db_to_figma`
- `selective_bidirectional`
- `manual_approval_required`
- `frozen`

운영 원칙:

- geometry, hierarchy, style ref, component binding, page order, asset link는 자동 반영 가능
- 정책 문구, 설명 텍스트, 담당자 정보, 승인 상태, 운영 메모, 수동 교정 텍스트는 승인 또는 수동 처리
- 충돌은 `field_name` 단위로 저장하고 approval queue로 보낸다

## 3. DB 모델 초안

### 3-1. 핵심 테이블

#### `atlas_documents`

역할:

- 모든 문서의 최상위 메타 저장

주요 컬럼:

- `id`
- `workspace_id`
- `project_id`
- `document_type`
- `subtype`
- `title`
- `description`
- `status`
- `primary_source_type`
- `created_at`
- `updated_at`
- `deleted_at`

권장 인덱스:

- `(workspace_id, project_id, document_type)`
- `(primary_source_type, status)`
- full-text or trigram on `title`

#### `atlas_pages`

역할:

- 문서 내부 페이지, 슬라이드, 논리 섹션 저장

주요 컬럼:

- `id`
- `document_id`
- `page_type`
- `subtype`
- `title`
- `order_index`
- `source_ref_id`
- `status`
- `created_at`
- `updated_at`

권장 인덱스:

- `(document_id, order_index)`
- `(document_id, subtype)`

#### `atlas_nodes`

역할:

- 화면 구조의 핵심 엔티티

주요 컬럼:

- `id`
- `document_id`
- `page_id`
- `parent_node_id`
- `node_type`
- `subtype`
- `title`
- `raw_text`
- `normalized_text`
- `semantic_summary`
- `geometry_json`
- `style_json`
- `status`
- `authoritative_source`
- `created_at`
- `updated_at`

권장 인덱스:

- `(page_id, parent_node_id)`
- `(document_id, page_id, subtype)`
- GIN on `geometry_json` if JSONB
- full-text on `raw_text`, `normalized_text`, `semantic_summary`

#### `atlas_assets`

역할:

- 화면/문서에 연결된 리소스 저장

주요 컬럼:

- `id`
- `document_id`
- `page_id`
- `node_id`
- `asset_type`
- `storage_url`
- `mime_type`
- `width`
- `height`
- `checksum`
- `created_at`
- `updated_at`

권장 인덱스:

- `(document_id, page_id)`
- `(node_id)`
- `(checksum)`

#### `atlas_knowledge_documents`

역할:

- 정책, 가이드, 운영 지식의 독립 문서 저장

주요 컬럼:

- `id`
- `workspace_id`
- `knowledge_type`
- `subtype`
- `title`
- `body`
- `normalized_text`
- `status`
- `source_type`
- `created_at`
- `updated_at`

권장 인덱스:

- `(workspace_id, knowledge_type, subtype)`
- full-text on `title`, `body`, `normalized_text`

#### `atlas_annotations`

역할:

- 문서/페이지/노드 대상 주석 저장

주요 컬럼:

- `id`
- `target_entity_type`
- `target_entity_id`
- `annotation_type`
- `subtype`
- `body`
- `author_type`
- `author_id`
- `status`
- `created_at`
- `updated_at`

권장 인덱스:

- `(target_entity_type, target_entity_id)`
- `(annotation_type, status)`

#### `atlas_ownerships`

역할:

- 담당자, 조직, 승인 구조 저장

주요 컬럼:

- `id`
- `target_entity_type`
- `target_entity_id`
- `ownership_type`
- `actor_type`
- `actor_id`
- `team_id`
- `metadata_json`
- `starts_at`
- `ends_at`
- `created_at`
- `updated_at`

권장 인덱스:

- `(target_entity_type, target_entity_id, ownership_type)`
- `(actor_id, ownership_type)`
- `(team_id, ownership_type)`

#### `atlas_relations`

역할:

- 엔티티 간 연결 저장

주요 컬럼:

- `id`
- `from_entity_type`
- `from_entity_id`
- `to_entity_type`
- `to_entity_id`
- `relation_type`
- `subtype`
- `metadata_json`
- `created_at`
- `updated_at`

권장 인덱스:

- `(from_entity_type, from_entity_id, relation_type)`
- `(to_entity_type, to_entity_id, relation_type)`

#### `atlas_source_mappings`

역할:

- 내부 엔티티와 외부 원본의 연결 저장

주요 컬럼:

- `id`
- `internal_entity_type`
- `internal_entity_id`
- `source_type`
- `external_container_id`
- `external_ref_id`
- `source_path`
- `source_hash`
- `source_version`
- `is_primary`
- `raw_payload_json`
- `fetched_at`
- `created_at`
- `updated_at`

권장 인덱스:

- `(internal_entity_type, internal_entity_id, source_type)`
- `(source_type, external_container_id, external_ref_id)`
- `(source_hash)`

#### `atlas_entity_fields`

역할:

- 필드별 authoritative source와 sync 추적

주요 컬럼:

- `id`
- `entity_type`
- `entity_id`
- `field_name`
- `field_value_json`
- `authoritative_source`
- `last_synced_from`
- `last_synced_at`
- `conflict_flag`
- `created_at`
- `updated_at`

권장 인덱스:

- `(entity_type, entity_id, field_name)` unique
- `(authoritative_source, conflict_flag)`

이 테이블은 필드별 충돌 관리와 selective sync의 핵심이다.

#### `atlas_sync_jobs`

역할:

- import, pull, push, reindex, remap 등 sync 작업 추적

주요 컬럼:

- `id`
- `job_type`
- `scope_type`
- `scope_entity_id`
- `source_type`
- `target_type`
- `sync_mode`
- `status`
- `summary_json`
- `started_at`
- `finished_at`
- `created_at`

권장 인덱스:

- `(job_type, status, created_at)`
- `(scope_type, scope_entity_id)`

#### `atlas_sync_conflicts`

역할:

- 필드 단위 충돌 내역 저장

주요 컬럼:

- `id`
- `entity_type`
- `entity_id`
- `field_name`
- `source_a`
- `source_b`
- `source_a_value_json`
- `source_b_value_json`
- `source_a_updated_at`
- `source_b_updated_at`
- `source_a_actor`
- `source_b_actor`
- `merge_suggestion_json`
- `resolution_status`
- `resolved_by`
- `resolved_at`
- `created_at`

권장 인덱스:

- `(entity_type, entity_id, field_name, resolution_status)`
- `(resolution_status, created_at)`

#### `atlas_figma_connections`

역할:

- 연결된 Figma 파일 및 상태 저장

주요 컬럼:

- `id`
- `workspace_id`
- `project_id`
- `figma_team_id`
- `figma_file_key`
- `figma_file_name`
- `status`
- `last_synced_at`
- `last_seen_modified_at`
- `last_seen_version`
- `created_at`
- `updated_at`

권장 인덱스:

- `(workspace_id, project_id)`
- `(figma_file_key)` unique
- `(status, last_seen_modified_at)`

#### `atlas_sync_checkpoints`

역할:

- 증분 수집 기준점 저장

주요 컬럼:

- `id`
- `checkpoint_scope`
- `checkpoint_key`
- `source_type`
- `last_successful_sync_at`
- `last_seen_remote_modified_at`
- `cursor_or_version`
- `metadata_json`
- `created_at`
- `updated_at`

권장 인덱스:

- `(checkpoint_scope, checkpoint_key, source_type)` unique

#### `atlas_migration_jobs`

역할:

- 초기 이관과 운영 중 재수집 작업 저장

주요 컬럼:

- `id`
- `source_type`
- `source_ref`
- `parser_version`
- `run_version`
- `result_json`
- `status`
- `started_at`
- `finished_at`
- `created_at`

권장 인덱스:

- `(source_type, status, created_at)`

#### `atlas_search_index`

역할:

- 검색용 projection 저장

주요 컬럼:

- `entity_type`
- `entity_id`
- `document_id`
- `page_id`
- `searchable_text`
- `metadata_json`
- `embedding_vector`
- `updated_at`

권장 인덱스:

- `(entity_type, entity_id)` unique
- `(document_id, page_id)`
- full-text on `searchable_text`
- vector index on `embedding_vector`

### 3-2. 관계 원칙

반드시 별도 모델로 분리할 관계:

- `document -> page`
- `page -> node`
- `node -> child node`
- `node -> asset`
- `document/page/node -> annotation`
- `document/page/node -> ownership`
- `document/page/node -> knowledge_document`
- `document/page/node <-> Figma source mapping`
- `document/page/node <-> PPT source mapping`
- `old entity -> new entity (derived_from)`

중요한 점은 다음 네 가지를 절대 하나의 의미로 뭉개지 않는 것이다.

- 계층 구조
- 외부 원본 매핑
- 정책 연결
- 담당 연결

## 4. Sync 정책

### 4-1. 초기 import flow

1. PPT 업로드
2. `atlas_migration_jobs` 생성
3. PPT 파싱 후 `document/page/node/asset` 임시 구조 생성
4. `atlas_source_mappings`에 원본 PPT lineage 저장
5. Figma 생성 또는 기존 Figma 연결
6. 생성된 Figma file/page/node와 내부 엔티티 매핑 저장
7. 기본 `sync_mode`를 `manual_approval_required`로 부여
8. 초기 search index 생성

### 4-2. `figma_to_db` flow

1. `atlas_figma_connections`와 `atlas_sync_checkpoints` 조회
2. 마지막 checkpoint 이후 변경된 파일 탐색
3. 변경 파일 상세 조회
4. page/node 구조 파싱
5. `atlas_source_mappings`로 기존 엔티티와 매칭
6. diff 생성
7. 필드 단위 merge 수행
8. geometry/layout/hierarchy/style는 자동 반영
9. 정책/설명/담당/승인 상태 충돌은 `atlas_sync_conflicts`에 저장
10. 반영 후 `atlas_search_index` 재색인
11. checkpoint 갱신

### 4-3. `db_to_figma` 허용 범위

허용 범위:

- 승인된 label 또는 display text 중 Figma 반영 대상 필드
- asset link
- 일부 component binding metadata

비허용 또는 승인 필요:

- 정책 문구
- 운영 메모
- 담당자 정보
- 승인 상태
- AI 추천 결과

### 4-4. conflict/approval flow

1. 동일 필드에 서로 다른 값이 감지되면 충돌 생성
2. `atlas_sync_conflicts`에 source/value/time/actor 저장
3. `merge_suggestion_json` 생성 가능
4. 승인 큐에 노출
5. 운영자 승인 후 `atlas_entity_fields`와 본 엔티티 갱신
6. 필요한 경우 Figma 또는 DB 쪽으로 후속 반영

### 4-5. checkpoint 전략

checkpoint는 최소 3수준을 지원한다.

- workspace/project 수준
- figma connection 수준
- file 수준

저장 항목:

- `checkpoint_scope`
- `checkpoint_key`
- `last_successful_sync_at`
- `last_seen_remote_modified_at`
- `cursor_or_version`
- `updated_at`

권장 운영:

- 배치 실행은 connection 수준 checkpoint 사용
- 문제 파일 재처리는 file 수준 checkpoint 사용
- 대규모 재스캔은 workspace/project 수준 checkpoint 사용

## 5. Search 구조

### 5-1. 검색 대상

- `document`
- `page`
- `node`
- `knowledge_document`
- `annotation`
- `ownership`
- 일부 `relation` projection

### 5-2. 인덱싱 단위

작은 단위로 인덱싱하고, 큰 문맥으로 응답한다.

인덱싱 단위:

- 문서 단위
- 페이지 단위
- 노드/영역/셀 단위
- 정책 문서 단위
- 주석 단위
- 담당 정보 단위

### 5-3. 검색 필드

- `entity_id`
- `entity_type`
- `subtype`
- `title`
- `raw_text`
- `normalized_text`
- `semantic_summary`
- `tags`
- `document_id`
- `page_id`
- `parent_node_id`
- `ownership_refs`
- `policy_refs`
- `source_refs`
- `authoritative_source`
- `sync_status`
- `updated_at`

### 5-4. 질의 유형

반드시 가능한 질의 예:

- 이 영역은 누가 담당인가?
- 이 셀의 기획 의도는 어디에 적혀 있나?
- 이 화면과 연결된 정책 문서는 무엇인가?
- 이 Figma 파트의 원본 PPT는 어디인가?
- 이 기능과 관련된 설명 문서는 무엇인가?
- 특정 정책이 적용된 화면을 모두 찾아라
- 특정 담당자가 맡은 파트들을 보여줘
- 관련 경로와 근거 문서를 함께 보여줘

### 5-5. 결과 집계 방식

검색 hit는 세부 단위에서 찾고, 응답은 문맥 단위로 재조합한다.

응답에 항상 포함할 정보:

- 문서명
- 페이지명
- 노드 경로
- 관련 정책 문서
- 관련 담당자
- 연결된 원본 정보
- 최근 변경 시각
- sync 상태

`qa_context`는 물리 테이블이 아니라 응답 조합 레이어로 두는 것이 적절하다. 즉 검색 결과와 relation graph를 조합해 질의응답용 문맥을 생성한다.

## 6. Migration 구조

### 6-1. 초기 대량 이관

대상:

- PPT/PPTX
- 기존 Figma 파일
- 정책 문서
- 엑셀 메타데이터
- 기존 DB 데이터

목표:

- canonical graph 생성
- source lineage 저장
- Figma mapping 생성
- 초기 search index 생성

처리 흐름:

1. source inventory 수집
2. parser 실행
3. 문서/페이지/노드/asset 생성
4. knowledge_document/annotation/ownership 매핑
5. source_mapping 생성
6. relation 생성
7. search index 생성

### 6-2. 운영 중 증분 반입

대상:

- 신규 PPT 업로드
- 신규 Figma 연결
- Figma 변경분 재수집
- 특정 문서 재동기화
- 특정 페이지 재가져오기
- 특정 node remap

### 6-3. migration job 필드

필수 관리 항목:

- `migration_job_id`
- `source_type`
- `source_ref`
- `source_hash`
- `parser_version`
- `run_version`
- `started_at`
- `finished_at`
- `status`
- `imported_count`
- `updated_count`
- `skipped_count`
- `conflict_count`
- `failed_count`
- `error_summary`

### 6-4. identity 유지 전략

재수집과 재변환 시에도 가능한 한 기존 `entity_id`를 유지해야 한다.

매칭 키 후보:

- `figma_file_key`
- `figma_node_id`
- `ppt_object_path`
- `source_path`
- `page_order`
- `hierarchy_key`
- `stable semantic fingerprint`

완전히 구조가 바뀐 경우:

- 신규 entity 생성 허용
- `derived_from` relation 생성
- 과거 source mapping 유지
- 검색 인덱스와 정책 연결 재검증

### 6-5. re-import / re-map / re-index 전략

- `re-import`: 원본을 다시 읽어 canonical graph 재생성
- `re-map`: 기존 source mapping을 재평가해 identity 재연결
- `re-index`: 변경된 entity와 관련 relation만 부분 재색인

대량 재처리 시 전체 리빌드보다 문서/페이지 범위 부분 처리 우선 전략이 필요하다.

## 7. 구현 우선순위

### Phase 1

범위:

- `document/page/node/asset` 기본 모델
- `source_mapping`
- PPT import
- Figma 생성 매핑

선행조건:

- canonical subtype 목록
- PPT parser 출력 규격
- Figma 생성 대상 범위

리스크:

- PPT 구조 해석 품질
- node granularity 과소/과대 설계

### Phase 2

범위:

- `knowledge_document`
- `annotation`
- `ownership`
- 정책 연결
- 담당 연결
- 내부 포털 read model

선행조건:

- 정책 문서 원천 정리
- 담당 정보 체계 정리

리스크:

- 지식 문서 품질 편차
- ownership 기준 모호성

### Phase 3

범위:

- field-level authoritative source
- `sync_job`
- `conflict`
- approval 구조
- selective sync 적용

선행조건:

- 필드 분류표
- 승인 프로세스 정의

리스크:

- 필드별 원본 규칙 누락
- 충돌량 급증

### Phase 4

범위:

- Figma incremental pull sync
- checkpoint 기반 증분 수집
- diff merge
- remap
- reindex

선행조건:

- Figma connection 관리
- source mapping 안정화
- diff 정책 정의

리스크:

- Figma node identity 불안정
- rename/move/regroup 판단 오류

### Phase 5

범위:

- 검색 인덱스
- 문서/페이지/노드/정책/담당 검색
- 질의응답 context assembly

선행조건:

- searchable projection 정의
- 메타데이터 필드 확정

리스크:

- 검색 정확도 편차
- context assembly 비용 증가

### Phase 6

범위:

- 운영 UI
- 승인 큐
- 변경 이력
- 감사 로그
- sync 모니터링

선행조건:

- read model 정리
- 운영 시나리오 확정

리스크:

- UI 복잡도 상승
- 승인 처리 병목

## 8. 리스크와 대응책

### 8-1. Figma node identity 불안정

위험:

- rename, regroup, detach, component 교체 시 동일성 판단이 깨질 수 있다.

대응:

- `figma_node_id` 단독 의존 금지
- `hierarchy_key`, `page_order`, `semantic fingerprint` 조합 사용
- identity 실패 시 `derived_from` relation으로 이력 유지

### 8-2. PPT 파싱 품질 문제

위험:

- 표, 셀, 그룹, 텍스트 박스 구조가 일관되게 추출되지 않을 수 있다.

대응:

- parser output과 canonical mapping 분리
- low-confidence 파싱 결과는 review queue 적재
- 원본 path와 preview를 함께 저장해 수동 교정 가능하게 설계

### 8-3. source conflict 증가

위험:

- Figma와 DB가 동시에 운영되면 충돌이 빠르게 늘어난다.

대응:

- 자동 반영 대상 필드 최소화
- 나머지는 approval queue로 전송
- `atlas_entity_fields`로 필드 단위 원본 추적

### 8-4. 검색 인덱스 부정확성

위험:

- 노드, 정책, 주석, ownership이 분리되어 있어 검색 결과가 단절될 수 있다.

대응:

- 작은 단위 인덱싱 + 큰 단위 집계 전략 적용
- relation 기반 context assembly 제공
- 재색인을 sync/migration 후 후속 작업으로 강제

### 8-5. 운영자 승인 부담

위험:

- 충돌과 승인 항목이 많아지면 운영 피로도가 커진다.

대응:

- 필드 우선순위별 자동 처리 정책 도입
- 충돌 요약과 merge suggestion 제공
- 문서/페이지/담당자 단위 큐 필터 제공

### 8-6. 모델 과설계 위험

위험:

- 초기에 모든 subtype를 세밀하게 확정하면 구현 속도가 느려질 수 있다.

대응:

- 1차는 공통 필드 + subtype 확장 구조로 구현
- 세부 subtype는 운영 데이터 축적 후 보강

