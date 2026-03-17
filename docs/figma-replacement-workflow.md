# Figma Replacement Workflow

## 목적

복잡 도형과 화살표를 초기에는 `vector fallback` 후보로 렌더하되,
나중에 Figma 디자인 에셋 또는 컴포넌트로 치환할 수 있도록 한다.

## 현재 반영 상태

`figma-plugin/code.js`는 replacement 후보 객체를 Figma에 렌더할 때
plugin data를 함께 심는다.

저장되는 주요 값:

- `candidate_id`
- `source_path`
- `current_mode`
- `preferred_mode`
- `replacement_candidate`
- `replacement_candidate_type`
- `replacement_strategy`
- `replacement_confidence`

또한 replacement 후보는 이름에 `VF/<candidate_type>/...` prefix를 붙인다.

예:

- `VF/process_flow_connector/...`
- `VF/decision_diamond/...`

## 의도

이렇게 해두면 나중에 Figma 안에서 다음 흐름이 가능하다.

1. replacement 후보만 필터링
2. candidate_type별 에셋/컴포넌트 정의
3. `VF/...` 노드를 검색
4. 해당 노드를 component instance 또는 asset node로 교체

## 권장 치환 순서

1. `process_flow_connector`
2. `decision_diamond`
3. `process_box`
4. `callout_box`
5. `labeled_ui_box`

## 주의

- 화살표 자체는 운영 DB의 핵심 node가 아니라 render object다.
- 따라서 DB에는 의미 관계만 남기고, 시각 치환은 Figma 쪽에서 처리하는 구조가 적합하다.
- 모든 vector fallback을 치환할 필요는 없다.
- 반복성과 재사용 가치가 높은 것부터 치환한다.
