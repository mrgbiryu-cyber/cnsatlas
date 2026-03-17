# Vector Fallback / Replacement Strategy

## 목적

복잡한 도형, 화살표, 일부 반복 UI는 초기 변환 시 `visual fidelity`를 우선하기 위해
`vector fallback`을 허용한다. 다만 이 객체들이 무엇이었는지 추적 가능해야 하며,
이후 Figma 디자인 에셋 또는 컴포넌트로 치환 가능한 상태로 남겨야 한다.

## 원칙

1. 모든 객체를 native로 만들려고 하지 않는다.
2. 모든 객체를 vector로 보내지도 않는다.
3. 운영 의미가 큰 객체는 native 우선이다.
4. 시각 fidelity 비용이 큰 객체만 vector fallback 후보로 둔다.
5. vector fallback 객체는 반드시 replacement metadata를 가진다.

## 분류

### Native Required

- text_block
- table
- table_row
- table_cell
- 운영 의미가 큰 labeled_shape

### Vector Allowed

- connector
- complex preset shape
- fidelity 비용이 큰 특수 도형

### Vector + Replacement Candidate

- process_flow_connector
- decision_diamond
- process_box
- callout_box
- repeated labeled_ui_box

## metadata 필드

각 candidate는 `rendering` 필드를 가진다.

- `current_mode`
  - 현재 실제 렌더 방식
- `preferred_mode`
  - 장기적으로 권장되는 렌더 방식
- `replacement_candidate`
  - 치환 후보 여부
- `replacement.candidate_type`
  - 치환 타입
- `replacement.strategy`
  - `vector_then_component_replace`
  - `native_then_component_replace`
  - `native_asset_replace`
- `replacement.confidence`
  - `high | medium | low`
- `replacement.reason`
  - 왜 치환 후보인지 설명

## 구현 흐름

1. PPT 파싱
2. intermediate candidate 생성
3. candidate별 `rendering` metadata 부여
4. 초기 렌더
   - native 또는 vector fallback
5. replacement catalog 생성
6. 디자이너가 candidate_type 기준으로 Figma 에셋/컴포넌트 정의
7. 치환 스크립트로 기존 객체를 component instance로 교체

## DB / 운영 모델 원칙

화살표 자체는 운영 DB의 1급 노드로 두지 않는다.

대신 필요하면 의미 관계만 남긴다.

- `from_node_id`
- `to_node_id`
- `relation_type = flow_transition`

실제 선 모양은 렌더 레이어가 담당한다.

## 우선 적용 대상

1. connector
2. flowChartDecision
3. flowChartProcess
4. 반복 안내 박스
5. 반복 프로세스 박스

## 다음 단계

1. benchmark 슬라이드 기준 replacement catalog 검토
2. candidate_type 체계 확정
3. Figma component naming 규칙 정의
4. component replacement prototype 구현
