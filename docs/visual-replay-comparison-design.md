# Visual Replay Comparison Design

## 목적

이 문서는 `고급 플러그인 결과`와 `우리 visual replay 결과`를 사람 눈으로 수기 비교하지 않고,
시스템이 구조적으로 비교할 수 있도록 만드는 내부 진단 모듈 설계 초안이다.

핵심 목적은 아래와 같다.

1. 어떤 객체가 틀렸는지 값을 기준으로 찾는다.
2. `1page / 2page / 3page`에 매몰된 하드코딩을 피한다.
3. 좌표/회전/뒤집힘 문제를 원론적으로 수정할 수 있게 한다.
4. 비교 결과가 바로 `replay core` 수정 포인트로 이어지게 한다.

이 설계의 핵심 원칙은 단순하다.

> 단순 좌표 비교가 아니라 `추출 -> source metadata 보존 -> 매칭 -> 정규화 -> diff -> 패턴 리포트` 순서로 간다.

---

## 현재 코드 기준 문제 정의

현재 direct replay가 흔들리는 이유는 개별 도형 문제가 아니라 replay core의 기준 좌표계가 섞여 있기 때문이다.

현재 코드 기준 사실:

- 위치는 주로 `absoluteBoundingBox`를 사용한다.
- `relativeTransform`는 일부만 반영한다.
- `TEXT`, `VECTOR`, `GROUP`, `FRAME`가 같은 transform 파이프라인을 쓰지 않는다.
- `clip path`는 삭제하거나 skip하는 방식이 섞여 있다.

그래서 현재 비교 모듈은 아래 문제를 잡아야 한다.

1. `bbox`는 비슷하지만 `flip/rotation`이 다른 경우
2. 부모 그룹이 틀려서 subtree 전체가 밀린 경우
3. clip/mask 처리가 잘못되어 일부 노드가 통째로 빠진 경우
4. 화살표처럼 semantic connector가 아니라 vector로 렌더된 노드가 뒤집히는 경우

즉, 이 비교 모듈은 “어디가 틀렸는지”만 찾는 도구가 아니라, `transform core`가 어디서 잘못되었는지 찾는 도구여야 한다.

---

## 전체 구조

비교 모듈은 5단계로 구성한다.

1. `reference manifest generator`
2. `replay metadata injector`
3. `actual manifest generator`
4. `mapping layer`
5. `diff engine`

즉, 먼저 reference를 뽑고, replay가 만든 노드에 source metadata를 심고, actual을 다시 뽑은 뒤 비교한다.

---

## 1. Reference Manifest

고급 플러그인 Figma JSON에서 추출한 기준 데이터다.

입력:
- `figma-page-1.json`
- `figma-page-2.json`
- `figma-page-3.json`

출력:
- `reference_manifest.json`

각 레코드는 아래 필드를 가진다.

### 공통 필드
- `page_id`
- `reference_node_id`
- `reference_parent_id`
- `node_type`
- `node_name`
- `depth`
- `child_count`

### 위치/변환 필드
- `bbox_absolute`
- `bbox_parent_relative`
- `relative_transform`
- `composed_transform`
- `transform_signature`
- `flip_x`
- `flip_y`
- `rotation_hint`

### 시각 필드
- `has_fill`
- `has_stroke`
- `has_image_fill`
- `has_vector_geometry`
- `text_characters`
- `text_line_break_signature`
- `font_family`
- `font_style`
- `font_size`

### 분류 필드
- `is_mask_like`
- `is_clip_like`
- `is_fullpage_overlay_candidate`
- `comparison_level`

### 비교 보조 필드
- `semantic_key`
- `content_key`
- `structure_key`

중요:
- `absoluteBoundingBox`만 저장하면 안 된다.
- 반드시 `relative_transform`와 `composed_transform`를 같이 저장해야 한다.

---

## 2. Replay Metadata Injector

이 계층은 reference와 actual을 연결하기 위한 핵심 계층이다.

역할:
- replay가 Figma에 노드를 만들 때, reference 쪽 메타데이터를 plugin data로 심는다.

모든 replay 노드에 최소한 아래를 심는다.

- `reference_node_id`
- `reference_parent_id`
- `reference_type`
- `replay_page_id`
- `replay_role`

권장 저장 위치:
- `pluginData`

이 계층이 필요한 이유:
- 현재 replay 결과의 Figma node id는 reference node id와 같지 않다.
- 따라서 `node_id exact match`는 성립하지 않는다.
- 먼저 source metadata를 심어야 reference와 actual을 안정적으로 연결할 수 있다.

---

## 3. Actual Manifest

우리 replay 결과에서 추출한 실제 결과 데이터다.

입력:
- plugin이 Figma에 생성한 결과물

출력:
- `actual_manifest.json`

필드 스키마는 `reference_manifest`와 동일하게 맞춘다.

추가 필드:
- `actual_node_id`
- `actual_parent_id`

중요:
- `actual manifest generator`는 plugin 내부 export로 먼저 구현하는 것이 좋다.
- Figma REST API 재조회는 후순위다.

즉 실제 구현 순서는:
1. replay 결과 생성
2. plugin 내부에서 현재 replay subtree를 읽음
3. 같은 스키마로 `actual_manifest` export

이 계층이 없으면 비교 설계는 실제 코드로 이어질 수 없다.

---

## 4. 비교 전에 필요한 정규화

단순히 `bbox`만 비교하면 안 된다.

### 4-1. 좌표계 정규화

비교용 좌표는 아래 2종류를 분리한다.

- `absolute space`
- `parent-relative space`

이유:
- 어떤 문제는 전체 위치 오차이고
- 어떤 문제는 부모 그룹 안에서의 상대 위치 오차다.

### 4-2. transform 정규화

`relativeTransform`는 바로 비교하지 않고 아래 값으로 요약한다.

- `scale_x_sign`
- `scale_y_sign`
- `translate_x`
- `translate_y`
- `rotation_bucket`

이유:
- 지금 핵심 문제는 수치 미세오차가 아니라
- `뒤집힘 / 회전 / 좌표계 불일치`다.

### 4-3. 이름/텍스트 정규화

텍스트 비교는 아래 기준으로 정규화한다.

- trim
- 연속 공백 제거
- 줄바꿈 signature 분리
- 한글/영문 혼합 그대로 유지

### 4-4. clip/mask 정규화

이 비교에서는 `clip path`를 바로 삭제하지 않는다.

별도 클래스로 분류:
- `is_clip_like`
- `is_mask_like`
- `is_fullpage_overlay_candidate`

이유:
- 일반 노드와 섞어 비교하면 noise가 커진다.
- 반대로 skip해버리면 실제 누락 원인을 놓친다.

---

## 5. Mapping Layer 설계

좌표 비교 전에 `같은 객체`를 찾아야 한다.

이 계층이 없으면 비교 결과가 쓸모 없어진다.

### 매칭 우선순위

1. `reference_node_id` from plugin data
2. `semantic_key`
3. `content_key + parent candidate`
4. `type + bbox proximity`

중요:
- 현재 설계에서는 `node_id exact match`를 쓰지 않는다.
- 그 대신 replay가 심은 `reference_node_id`를 1순위로 사용한다.

### semantic_key 생성 기준

예시:
- `TEXT:홈`
- `TEXT:제품선택`
- `GROUP:비회원주문`
- `VECTOR:path_cluster`

### content_key 생성 기준

텍스트:
- `text characters`

벡터:
- `geometry_count + bbox bucket + parent context`

그룹:
- `child text signature`

### structure_key 생성 기준

- `parent semantic key`
- `depth`
- `sibling order bucket`

### 매칭 실패 fallback

같은 객체를 찾지 못했을 때는 아래 중 하나로 분기한다.

- `missing_in_actual`
- `extra_in_actual`
- `near_match_candidate`

즉, 무조건 missing으로 떨어뜨리지 않고 근접 후보를 둘 수 있어야 한다.

---

## 6. 비교 단위 규칙

모든 노드를 같은 방식으로 비교하면 안 된다.

### Level 1: major block

대상:
- `FRAME`
- `GROUP`
- 큰 `RECTANGLE`
- 큰 섹션 블록

비교 목적:
- 전체 구조가 어디서 어긋나는지 파악

### Level 2: key visual node

대상:
- `TEXT`
- `VECTOR`
- `RECTANGLE(image)`
- 핵심 정보 박스

비교 목적:
- 뒤집힘/회전/텍스트 방향 문제 파악

### Level 3: fine leaf

대상:
- 작은 장식 벡터
- separator line
- 미세 장식 도형

비교 목적:
- 마지막 cosmetic 조정

원칙:
- 1차 진단은 `Level 1 + Level 2`
- `Level 3`는 후순위

이 규칙이 없으면 Page 3 같은 복잡한 화면에서 diff 결과가 폭발한다.

---

## 7. Diff 규칙

### 7-1. Bounding box diff

필드:
- `dx`
- `dy`
- `dw`
- `dh`

판정:
- `ok`
- `warn`
- `critical`

### 7-2. Transform diff

필드:
- `flip_x_mismatch`
- `flip_y_mismatch`
- `rotation_mismatch`
- `transform_signature_mismatch`

판정:
- 뒤집힘 불일치: `critical`
- 회전 차이: tolerance 기반 `warn/critical`

### 7-3. Parent structure diff

필드:
- `parent_mismatch`
- `depth_mismatch`

이건 좌표보다 먼저 봐야 한다.

이유:
- 부모가 틀리면 좌표는 연쇄적으로 다 틀어진다.

### 7-4. Missing node diff

필드:
- `missing_in_actual`
- `extra_in_actual`
- `near_match_candidate`

이 규칙은 특히 `3page` 누락 문제를 잡는 데 중요하다.

### 7-5. Text diff

필드:
- `characters_mismatch`
- `line_break_signature_mismatch`
- `font_size_delta`
- `text_direction_mismatch`

### 7-6. Vector diff

현재 화살표 다수는 semantic connector가 아니라 vector 결과다.

따라서 1차 diff에서는 화살표를 별도 route로 보지 않고 우선 vector로 본다.

필드:
- `vector_bbox_mismatch`
- `vector_flip_mismatch`
- `vector_rotation_mismatch`
- `vector_parent_mismatch`

### 7-7. Connector route diff

이건 후순위다.

조건:
- direct replay가 transform-aware 해진 뒤
- semantic connector가 따로 확보되었을 때만 적용

즉 현재 단계에서는 설계만 두고 구현은 미룬다.

필드 예시:
- `direction_signature`
- `start_anchor_bucket`
- `end_anchor_bucket`
- `route_signature`

---

## 8. 실제 리포트 형식

출력은 사람이 바로 고칠 수 있는 형태여야 한다.

### 페이지 요약
- `matched nodes`
- `missing nodes`
- `flip mismatches`
- `rotation mismatches`
- `bbox critical mismatches`
- `parent mismatches`

### 패턴 요약
- `47 nodes have flip_y mismatch`
- `12 vectors share the same vertical offset cluster`
- `3 text nodes are mapped to wrong parent group`
- `2 clip-like nodes are missing in actual`

### 수정 우선순위
- `transform core issue`
- `parent mapping issue`
- `clip/mask handling issue`
- `text wrap issue`
- `leaf-only cosmetic issue`

---

## 9. 현재 설계의 빈 부분

아직 비어 있는 부분도 있다.

### 9-1. actual manifest 추출기

현재 plugin이 만든 결과를 다시 JSON/manifest로 뽑는 수단이 아직 없다.

필요:
- plugin 내부 export

이건 구현 착수 전에 반드시 닫아야 한다.

확정안:
- `plugin 내부 export`로 간다.
- 이유:
  - Figma REST API 재조회보다 빠르다.
  - replay 직후 동일 파일 안에서 바로 추출 가능하다.
  - local plugin data를 그대로 읽을 수 있다.

실행 방식:
1. replay 완료
2. root replay frame 선택 또는 내부적으로 root reference id 추적
3. 해당 subtree를 순회
4. `actual_manifest.json` 생성
5. UI에서 다운로드

출력 형식:
- `kind: actual-manifest`
- `page_id`
- `generated_at`
- `root_actual_node_id`
- `nodes: []`

### 9-2. replay metadata injector

replay가 만드는 노드에 `reference_node_id`를 심는 로직이 아직 없다.

이게 없으면 mapping layer가 약해진다.

확정안:
- `pluginData`를 기준으로 고정한다.
- 이름 suffix나 node name 인코딩은 쓰지 않는다.

저장 키 초안:
- `reference_node_id`
- `reference_parent_id`
- `reference_type`
- `reference_name`
- `replay_page_id`
- `replay_role`
- `comparison_level`

원칙:
- 실제 렌더 노드마다 심는다.
- wrapper 전용 노드에는 `replay_role=wrapper`를 둔다.
- 실제 비교 대상이 아닌 노드는 `comparison_level=ignore`를 둘 수 있다.

### 9-3. tolerance 값

`dx/dy/dw/dh` 허용치를 아직 고정하지 않았다.

이건 실제 1/2/3페이지로 한 번 돌려보고 정해야 한다.

초기 확정안:

#### Level 1: major block
- `dx/dy <= 8px`: `ok`
- `9px ~ 24px`: `warn`
- `25px 이상`: `critical`
- `dw/dh <= 8px`: `ok`
- `9px ~ 20px`: `warn`
- `21px 이상`: `critical`

#### Level 2: key visual node
- `dx/dy <= 4px`: `ok`
- `5px ~ 12px`: `warn`
- `13px 이상`: `critical`
- `dw/dh <= 4px`: `ok`
- `5px ~ 10px`: `warn`
- `11px 이상`: `critical`

#### Level 3: fine leaf
- 1차 구현에서는 tolerance 계산 대상에서 제외
- cluster 통계용으로만 사용

절대 규칙:
- `flip mismatch`: 무조건 `critical`
- `parent mismatch`: 무조건 `critical`
- `rotation mismatch`: `15도 이상 critical`, `5도~14도 warn`

### 9-4. vector cluster 기준

vector leaf를 어디까지 묶을지 아직 고정하지 않았다.

권장 초안:
- `same parent`
- `close bbox`
- `same transform signature`

확정안:
아래 5개를 모두 만족하면 같은 cluster 후보로 본다.

1. `same replay_page_id`
2. `same reference_parent_id` 또는 `same actual_parent_id`
3. `same transform_signature`
4. `bbox 중심점 거리 <= 24px`
5. `geometry_count bucket` 동일

cluster 목적:
- leaf vector를 하나하나 보지 않고,
- `같이 뒤집히는 묶음`, `같이 밀리는 묶음`을 찾는다.

cluster 출력 예시:
- `cluster_id`
- `member_count`
- `avg_dx`
- `avg_dy`
- `flip_y_ratio`
- `rotation_bucket`

### 9-5. connector route signature

현재 단계에서 바로 구현하면 과하다.

우선순위:
1. vector mismatch
2. transform mismatch
3. route signature

확정안:
- Phase 1에서는 화살표를 `vector mismatch`로만 본다.
- Phase 2에서만 `route signature`를 도입한다.

Phase 2 진입 조건:
- direct replay가 transform-aware가 되어서
- 동일 화살표가 더 이상 random flip/rotation을 일으키지 않을 때

Phase 2 route signature 초안:
- `straight-horizontal`
- `straight-vertical`
- `elbow-h-first`
- `elbow-v-first`
- `multi-bend`

### 9-6. clip/mask 판정 기준

이름 기반 skip은 금지한다.

필요:
- 실제 fill/stroke/size 기준 분류
- fullpage overlay 여부 별도 판정

초기 확정안:

`is_fullpage_overlay_candidate = true` 조건:
- page bbox 대비 width/height가 90% 이상
- fill이 거의 단색 검정 또는 단색 어두운색
- child가 없거나 의미 없는 leaf
- name이 `clip path` 또는 `mask` 계열이거나, fill/stroke만 존재

`is_clip_like = true` 조건:
- child가 있고
- 자기 자신보다 child bbox가 작으며
- name/path 패턴상 clipping shell 가능성이 높음

처리 원칙:
- 1차 diff에서 일반 missing node로 섞지 않는다.
- 별도 `clip/mask report`로 분리한다.

---

## 10. 구현 전 체크리스트

코딩 들어가기 전 아래 항목이 모두 `yes`여야 한다.

### A. 입력/출력
- `reference manifest` 스키마가 고정되었는가
- `actual manifest` 스키마가 reference와 동일한가
- plugin 내부에서 actual export 경로가 정의되었는가

### B. replay metadata
- 모든 replay 노드에 `reference_node_id`를 심기로 확정했는가
- metadata 저장 위치를 `pluginData`로 고정했는가

### C. 비교 단위
- 1차 diff를 `Level 1 + Level 2`로 제한했는가
- `Level 3`는 후순위로 두었는가

### D. transform / mask
- 비교 기준이 `bbox only`가 아니라 `composed_transform`까지 포함하는가
- clip/mask를 skip이 아니라 별도 클래스 처리하는가

### E. diff 우선순위
- 1차 diff는 `parent / flip / rotation / bbox`인가
- 화살표는 1차에 `vector mismatch`로만 보는가

이 중 하나라도 `no`면 구현 착수 전 설계를 다시 닫아야 한다.

### F. 실제 구현 형식
- actual export는 plugin UI에서 파일 다운로드 가능한가
- replay가 심은 pluginData를 actual extractor가 읽을 수 있는가
- diff 결과가 page별 JSON으로 출력되는가

이 항목도 모두 `yes`여야 한다.

---

## 11. 구현 순서

1. `reference manifest generator`
2. `replay metadata injector`
3. `actual manifest generator`
4. `mapping layer v1`
5. `parent/flip/rotation/bbox diff`
6. `vector mismatch cluster report`
7. `clip/mask report`
8. `connector route diff`는 후순위

---

## 12. 현재 확정된 구현 경계

이 설계 기준으로 당장 구현하지 않을 것은 아래와 같다.

- PNG baseline 비교
- 사람 눈 수기 diff
- node name 기반 매칭
- 화살표 개별 하드코딩
- clip path 이름만 보고 skip

반대로 반드시 구현해야 하는 것은 아래다.

- reference manifest
- replay pluginData 주입
- actual manifest export
- mapping layer
- bbox/flip/rotation/parent diff
- vector cluster report

---

## 13. 현재 남아 있는 마지막 점검 포인트

이 문서 기준으로 마지막으로 닫아야 했던 질문 3개를 아래처럼 확정한다.

### 13-1. comparison_level 결정 주체

확정안:
- `reference extractor`가 1차 자동 판정한다.
- replay 단계에서는 이 값을 그대로 복사만 한다.

이유:
- 비교 단위는 reference 기준으로 고정되어야 한다.
- replay 결과가 흔들린다고 level 분류까지 바뀌면 diff 기준이 흔들린다.

판정 원칙:
- `FRAME/GROUP/큰 RECTANGLE`: `L1`
- `TEXT/VECTOR/IMAGE RECTANGLE/핵심 박스`: `L2`
- 작은 장식 vector / separator: `L3`

### 13-2. vector cluster 키

확정안:
- `geometry_count bucket`만으로는 부족하다.
- 아래 4개를 함께 쓴다.

cluster key:
- `parent signature`
- `transform_signature`
- `geometry_count bucket`
- `bbox aspect ratio bucket`

보조 키:
- `has_fill`
- `has_stroke`

이유:
- geometry 개수만 같아도 전혀 다른 vector가 섞일 수 있다.
- 특히 화살표와 diamond 외곽선이 같은 cluster로 뭉치면 리포트 품질이 떨어진다.

### 13-3. text_line_break_signature 정의

확정안:
- 단순 줄 수만 보지 않는다.
- 아래 3개를 조합한다.

구성:
- `explicit_newline_count`
- `rendered_line_count`
- `width_bucket`

예시:
- `NL0-L2-WM`
- `NL1-L3-WL`

이유:
- 같은 텍스트라도 폭이 다르면 줄 수가 달라진다.
- 반대로 강제 줄바꿈이 있는 텍스트는 줄 수만 보면 안 된다.

---

## 14. 최종 설계 판단

현재 문서 기준으로 비교 모듈 설계는 구현 착수 가능한 수준까지 닫혔다고 본다.

남아 있는 것은 설계 공백이 아니라 구현 선택이다.

즉 다음 단계는:
- reference extractor 구현
- replay pluginData 주입
- actual extractor 구현
- diff v1 구현

으로 넘어가면 된다.

---

## 15. 구현 명세 보강

구현 착수 전 마지막으로 아래 4개를 명세 수준으로 고정한다.

### 15-1. composed_transform 계산 규칙

정의:
- `composed_transform(node) = composed_transform(parent) * relative_transform(node)`

표현 형식:
- 2x3 affine matrix
- `[[a, c, e], [b, d, f]]`

기준 규칙:
1. root page/document의 기준 transform은 identity
2. 자식은 항상 부모 composed transform에 자기 relative transform을 곱한다
3. `absoluteBoundingBox`는 검산용/비교용 참고값으로만 사용한다
4. `flip_x`, `flip_y`, `rotation_hint`는 composed transform에서 유도한다

파생 필드:
- `flip_x = sign(a) < 0`
- `flip_y = sign(d) < 0`
- `rotation_hint = atan2(b, a)` 기반 degree bucket
- `transform_signature = sign(a), sign(d), rotation_bucket`

주의:
- node 타입별 별도 계산을 두지 않는다
- `TEXT`, `VECTOR`, `GROUP`, `FRAME`, `RECTANGLE` 모두 같은 transform 파이프라인을 사용한다

### 15-2. pluginData namespace 규칙

namespace:
- `cnsatlas.replay`

저장 키:
- `cnsatlas.replay.reference_node_id`
- `cnsatlas.replay.reference_parent_id`
- `cnsatlas.replay.reference_type`
- `cnsatlas.replay.reference_name`
- `cnsatlas.replay.replay_page_id`
- `cnsatlas.replay.replay_role`
- `cnsatlas.replay.comparison_level`

원칙:
1. replay가 생성하는 실제 비교 대상 노드에는 모두 기록한다
2. wrapper나 shell은 `replay_role=wrapper`로 분리한다
3. 실제 비교 제외 노드는 `comparison_level=ignore`를 둘 수 있다
4. node name은 비교 키로 쓰지 않는다

### 15-3. actual exporter의 subtree 선택 기준

기준:
- export 대상 root는 `CNS Atlas Replay (...)` frame 1개다

선택 우선순위:
1. 현재 selection 안의 `CNS Atlas Replay (...)` frame
2. selection이 없으면 current page에서 가장 최근 생성된 `CNS Atlas Replay (...)` frame
3. 그 안의 descendants 중 `cnsatlas.replay.reference_node_id`가 있는 노드만 actual manifest 대상

이유:
- wrapper/shell/frame까지 전부 비교 대상에 넣으면 noise가 증가한다
- 실제 replay 결과만 추려야 mapping이 안정적이다

actual exporter 출력 필수 필드:
- `actual_node_id`
- `actual_parent_id`
- pluginData의 모든 `reference_*`
- `bbox_absolute`
- `bbox_parent_relative`
- `relative_transform`
- `composed_transform`
- `flip_x`
- `flip_y`
- `rotation_hint`

### 15-4. comparison_level 자동 분류 threshold

입력 기준:
- node type
- bbox size
- child count
- text/image/vector 여부

초기 규칙:

#### L1
- `FRAME`, `GROUP`
- 또는 `RECTANGLE` 중
  - page 대비 width 20% 이상 또는
  - page 대비 height 12% 이상
- 또는 child count 3 이상인 큰 시각 블록

#### L2
- 모든 `TEXT`
- 모든 `VECTOR`
- `RECTANGLE(image)`
- 핵심 정보 박스
- L1에 해당하지 않는 주요 box/shape

#### L3
- width < 24px and height < 24px 인 장식성 leaf
- separator line
- 반복 장식 vector

보정 규칙:
- `is_fullpage_overlay_candidate`는 comparison_level과 별도로 분류
- `is_clip_like`, `is_mask_like`는 level과 독립적으로 표시

---

## 16. 구현 착수 최종 조건

이 문서 기준으로 구현 착수 가능 조건은 아래와 같다.

1. `composed_transform` 규칙이 고정되었는가
2. `pluginData namespace`가 고정되었는가
3. `actual exporter subtree 기준`이 고정되었는가
4. `comparison_level threshold`가 고정되었는가

현재 판단:
- 위 4개 모두 `yes`

따라서 다음 단계는 설계 보완이 아니라 구현으로 전환한다.

---

## 결론

이 비교 모듈은 단순 좌표 비교 도구가 아니다.

정의:
- `visual replay`의 구조적 오차를 원론적으로 찾기 위한 내부 진단 모듈

핵심 원칙은 아래와 같다.

> 사람이 화면을 보고 찾는 대신, 시스템이 reference와 actual의 구조/좌표/변환 차이를 manifest 수준에서 비교해 원인 패턴을 찾아야 한다.

그리고 실제 구현 기준으로 가장 중요한 전제는 이것이다.

> 비교를 하기 전에, replay가 만든 결과에 source metadata를 심고 actual manifest를 다시 뽑을 수 있어야 한다.
