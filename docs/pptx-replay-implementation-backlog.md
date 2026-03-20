# PPTX Replay 구현 Backlog

## 목적

이 문서는 `PPTX direct upload`를 최종 visual replay 품질 경로로 연결하기 위한 실제 코딩 계획이다.

최종 목표:

> `.pptx`를 직접 업로드했을 때, 기존 완료 버전(`figma replay bundle -> renderReplayNode`)과 같은 렌더 엔진을 타게 만든다.

원칙:

- old candidate renderer를 계속 보정하는 방식으로 가지 않는다
- `PPTX -> replay-grade node tree -> renderReplayNode()` 구조로 간다
- semantic / node 저장은 현재 범위에서 제외한다

## 현재 구조 요약

### 완료 버전 경로

- 입력: `figma-replay-bundle`
- 렌더: `renderFigmaReplayBundle() -> renderReplayNode()`
- 장점:
  - 뒤집힘 해결
  - vector transform 해결
  - clip/mask/overlay 해결

### PPTX direct 경로

- 입력: `pptx-replay-bundle`
- 실제 내용: `pages + candidates`
- 렌더: `renderPptxReplayBundle() -> renderCandidateTree()`
- 문제:
  - 렌더 엔진이 다름
  - 화살표/텍스트/표 품질이 계속 따로 흔들림

## 구현 목표

PPTX direct 경로를 아래로 바꾼다.

- `parsePptxArrayBuffer()`
- `buildReplayTreeFromPptxBundle()`
- `renderReplayBundleDocument()`
- `renderReplayNode()`

즉:
- 입력 모델 통일
- 렌더 엔진 통일

## Phase 1. 입력 모델 정규화

### 1-1. replay tree builder 추가

목표:
- `pages + candidates`를 직접 그리지 않고 replay-grade tree로 변환

추가할 함수:
- `buildReplayTreeFromPptxBundle(bundle)`
- `buildReplayPageNode(page)`
- `buildReplayNodesFromCandidates(page)`

수정 파일:
- `figma-plugin/code.js`

산출 구조:
- `document`
- `children`
- `type`
- `name`
- `absoluteBoundingBox`
- `relativeTransform`
- `fills`
- `strokes`
- `style`
- `children`

완료 기준:
- PPTX bundle을 `document` 루트 tree로 만들 수 있음

### 1-3. replay node 최소 스키마 고정

목표:
- adapter가 어떤 필드를 반드시 만들어야 하는지 확정

필수 공통 필드:
- `id`
- `type`
- `name`
- `children`
- `absoluteBoundingBox`
- `relativeTransform`

타입별 필수 필드:

#### TEXT
- `characters`
- `style.fontSize`
- `style.fontFamily`
- `style.textAlignHorizontal`
- `style.textAlignVertical`
- `style.textAutoResize`
- `fills`

#### RECTANGLE
- `fills`
- `strokes`
- `strokeWeight`
- `cornerRadius`(필요 시)

#### FRAME
- `fills`
- `strokes`
- `strokeWeight`
- `children`

#### VECTOR
- `fillGeometry`
- `strokeGeometry`
- `fills`
- `strokes`
- `strokeWeight`

#### IMAGE RECTANGLE
- `fills: [{ type: "IMAGE", imageRef, scaleMode }]`

debug / metadata 필드:
- `debug.source_path`
- `debug.source_node_id`
- `debug.source_subtype`
- `debug.full_page_overlay_candidate`

완료 기준:
- 각 adapter가 어떤 출력을 만들어야 하는지 구현 전에 모호함이 없음

### 1-2. node type 매핑표 고정

목표:
- candidate subtype을 replay node type으로 고정

매핑:
- `text_block` -> `TEXT`
- `labeled_shape` -> `FRAME + RECTANGLE + TEXT` 또는 `RECTANGLE + TEXT`
- `shape` -> `RECTANGLE` 또는 `VECTOR fallback`
- `connector` -> `VECTOR fallback`
- `group/section_block` -> `GROUP` 또는 `FRAME`
- `table` -> `FRAME`
- `table_row` -> `FRAME`
- `table_cell` -> `FRAME + TEXT`
- `image` -> `RECTANGLE(image fill)`

완료 기준:
- subtype별 target replay node가 고정됨

## Phase 2. 텍스트/도형/이미지 우선 이관

### 2-1. text adapter

목표:
- 텍스트를 replay renderer에서 그대로 처리 가능한 `TEXT` node로 변환

필수 필드:
- `characters`
- `style.fontSize`
- `style.fontFamily`
- `style.textAlignHorizontal`
- `style.textAlignVertical`
- `style.textAutoResize`
- `fills`
- `absoluteBoundingBox`

수정 파일:
- `figma-plugin/code.js`

검증:
- page 1, 3 제목/긴 문장 줄바꿈

### 2-2. shape adapter

목표:
- box/ellipse/diamond를 replay renderer 기준 shape로 변환

필수 필드:
- `type`
- `fills`
- `strokes`
- `strokeWeight`
- `cornerRadius`
- `absoluteBoundingBox`

주의:
- diamond는 초기엔 `VECTOR fallback` 허용
- noFill/noLine은 실제로 반영

검증:
- 외곽선 과다 문제 감소
- diamond 영역이 old renderer보다 안정적

### 2-3. image adapter

목표:
- image candidate를 replay rectangle image fill로 변환

필수 필드:
- `fills: [{ type: "IMAGE", imageRef }]`
- `absoluteBoundingBox`
- `assets`

검증:
- page 3 이미지 영역 재현

## Phase 3. 화살표/표 이관

### 3-1. connector adapter

목표:
- old `createConnector()` 의존을 줄이고 replay node로 변환

방식:
- 1차는 `VECTOR fallback`
- parser가 가진
  - `start_point_px`
  - `end_point_px`
  - `shape_kind`
  - `connector_adjusts`
를 이용해 geometry 생성

VECTOR fallback 최소 규칙:
- `fillGeometry`는 비워도 됨
- `strokeGeometry`는 최소 1개 이상 path 생성
- `strokes`에는 line color 반영
- `strokeWeight` 반영
- arrow head가 있으면 마지막 segment 기준 geometry 추가

초기 범위:
- `straightConnector1`
- `bentConnector2`
- `bentConnector4`

후순위:
- 그 외 connector geometry 정교화

수정 파일:
- `figma-plugin/code.js`
- 필요 시 `figma-plugin/pptx-parser.js`

검증:
- page 1/2 화살표 방향/위치가 old renderer보다 개선

### 3-2. table adapter

목표:
- table을 replay tree로 전환

구조:
- table frame
- row frame
- cell frame
- text child

필수 반영:
- column width
- row height
- merged cell skip/placeholder
- cell fill/stroke

추가 정책:
- 셀 텍스트 줄바꿈으로 text height가 커지면
  - cell height 확장
  - row frame height 확장
  - 필요 시 table frame height 확장
- merged cell은 초기엔 placeholder 유지
- visual 우선이므로 border/stroke 정합성 먼저 확보

검증:
- page 2 표
- page 3 표

## Phase 4. clip / overlay 규칙 이관

### 4-1. overlay metadata 정리

목표:
- parser가 찾은 full-page overlay 후보를 replay node metadata에 유지

필드:
- `debug.full_page_overlay_candidate`
- `debug.source_path`
- `debug.shape_kind`
- `debug.source_bounds`
- `debug.source_fill`

### 4-2. replay renderer 공통 규칙 적용

목표:
- figma replay bundle과 PPTX replay bundle 모두 같은 overlay 규칙 사용

작업:
- 현재 `isFullPageBlackOverlayVector()` 계열 규칙을 공통 renderer 기준으로 정리

검증:
- page 3 검은 overlay 재발 금지

## Phase 5. renderer 통합

### 5-1. 공통 render 진입점 정리

목표:
- `renderPptxReplayBundle()`를 실제 tree 변환 + 공통 renderer 호출만 하게 축소

변경 목표:
- `renderPptxReplayBundle()` 내부에서 `renderCandidateTree()` 제거
- 대신:
  - `const documentNode = buildReplayTreeFromPptxBundle(payload)`
  - `renderReplayNode(documentNode, ...)`

### 5-2. old renderer 역할 축소

목표:
- `renderIntermediatePayload()`는 preview/debug 전용으로만 유지

원칙:
- direct upload는 기본적으로 타지 않음

## Phase 6. 검증 루프

### 6-0. 중간 산출물 검증

목표:
- 렌더 전에 replay tree가 제대로 생성됐는지 확인

추가할 것:
- `PPTX -> replay tree` JSON dump 경로

검증 포인트:
- page/frame 구조가 맞는가
- text node 수가 터무니없이 줄지 않았는가
- overlay candidate가 metadata로 남는가
- connector/table/image가 기대 타입으로 변환됐는가

원칙:
- visual 렌더 전 replay tree를 먼저 본다

### 6-1. visual 검증

대상:
- page 1
- page 2
- page 3

체크:
- 화살표
- 텍스트 크기/줄바꿈
- 표 가독성
- overlay

### 6-2. manifest 검증

대상:
- actual manifest export
- diff 비교

체크:
- flip mismatch
- overlay skip correctness
- missing node trend

원칙:
- visual 우선
- diff는 보조 기준

## 파일별 작업 목록

### `figma-plugin/code.js`

해야 할 것:
- `buildReplayTreeFromPptxBundle()` 추가
- candidate -> replay node adapter 추가
- `renderPptxReplayBundle()`를 공통 renderer 경로로 변경
- text/shape/image/connector/table adapter 연결
- replay tree JSON dump helper 추가

### `figma-plugin/pptx-parser.js`

해야 할 것:
- 현재 candidate 정보 유지
- replay adapter에 필요한 metadata 보강
- overlay candidate, connector metadata, table layout metadata 유지

### `figma-plugin/ui.html`

해야 할 것:
- `.pptx` 업로드 후 payload summary를 replay 기준으로 표시
- parser inlined code 동기화

### `docs/pptx-direct-upload-replay-plan.md`

해야 할 것:
- 구조 설계 문서 유지

### `docs/visual-replay-test-status.md`

해야 할 것:
- direct upload가 최종본 기준선에 근접했을 때 상태 업데이트

## 구현 순서

1. `buildReplayTreeFromPptxBundle()` 골격 추가
2. replay node 최소 스키마 구현
3. page/frame + text + shape + image 먼저 replay node로 전환
4. replay tree JSON dump로 중간 검증
5. `renderPptxReplayBundle()`에서 공통 renderer 사용
6. connector adapter 추가
7. table adapter 추가
8. overlay 규칙 공통화
9. visual 검증

## 완료 조건

아래를 만족하면 direct upload 1차 완료로 본다.

1. `.pptx` direct upload가 더 이상 old candidate renderer에 의존하지 않는다
2. page 1/2/3에서 기존 완료 버전과 같은 renderer를 사용한다
3. overlay 문제가 재발하지 않는다
4. 화살표/텍스트/표 품질이 old renderer 대비 명확히 개선된다

## 한 줄 요약

다음 코딩은 `PPTX를 더 잘 그리는 것`이 아니라, `PPTX를 완료 버전 renderer가 먹는 replay-grade node tree로 바꾸는 것`에 집중한다.
