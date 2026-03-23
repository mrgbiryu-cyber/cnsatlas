# Block Prototype v1

## 목적

이 문서는 기존 요소 기반 generator와 별도로, **블록을 1차 생성 단위로 삼는 최소 프로토타입**을 정의한다.

이번 단계의 목표는 visual quality를 바로 보장하는 것이 아니라:

- 슬라이드를 의미 있는 시각 블록으로 자를 수 있는지
- 그 블록을 bundle 구조로 올릴 수 있는지
- 이후 block-native / block-vector / block-image 전략을 실을 수 있는지

를 검증하는 것이다.

## 현재 범위

생성 파일:

- `scripts/detect_visual_blocks.py`
- `scripts/build_block_replay_bundle.py`

출력:

- `block-slide-12.bundle.json`
- `block-slide-19.bundle.json`
- `block-slide-29.bundle.json`

## 블록 종류

- `header_block`
- `table_block`
- `flow_block`
- `right_panel_block`
- `content_block`

## 현재 프로토타입의 성격

중요:

- **진짜 block-image fallback은 아직 없다**
- 현재는 `block detector`와 `block bundle path`를 만든 상태다
- `header_block`은 이제 `SVG_BLOCK`으로 렌더된다
- `table_block`도 이제 `SVG_BLOCK`으로 렌더된다
- `flow_block`은 이제 `SVG_BLOCK`으로 렌더된다
- `right_panel_block`도 이제 `SVG_BLOCK`으로 렌더된다
- `ui-mockup`의 `content_block`도 이제 `SVG_BLOCK`으로 렌더된다

즉 이번 버전은:

- 요소 엔진을 완전히 대체한 것이 아니라
- **블록을 page 구조의 1차 단위로 도입하고, 일부 블록은 실제 block renderer를 타기 시작한 상태**

이다.

## 슬라이드별 기대 블록

### Slide 12

- `header_block`
- `flow_block`

### Slide 19

- `header_block`
- `table_block`

### Slide 29

- `header_block`
- `right_panel_block`
- `content_block`

## 다음 단계

다음부터 진짜 block engine이 되려면 아래가 필요하다.

1. block detector refinement
2. block render strategy selector
   - `native`
   - `vector`
   - `image`
3. `table-heavy`의 `content_block` renderer 여부 결정
4. `SVG_BLOCK`와 image fallback의 분기 기준 정리
5. block 이미지 fallback이 실제로 필요한 영역 정의

즉 이번 프로토타입은 **진짜 block engine의 출발점**이지, 완성본이 아니다.
