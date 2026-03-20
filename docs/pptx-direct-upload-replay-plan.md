# PPTX Direct Upload Replay 계획

## 목적

이 문서는 현재 `PPTX direct upload`가 예전 intermediate 렌더러로 연결되어 있는 문제를 정리하고,
이를 `최종 visual replay 품질` 경로로 붙이기 위한 개발 범위를 고정한다.

현재 목표는 하나다.

> 사용자가 `.pptx`를 직접 올렸을 때도, 3개 샘플에서 최종적으로 맞춘 visual replay 수준으로 Figma에 변환되게 한다.

이 단계에서는 semantic / node 저장은 다루지 않는다.

## 현재 상태

현재 플러그인에는 렌더 경로가 2개 있다.

### 1. 최종 품질 경로

- 입력: `figma-page-*.bundle.json`
- 라우팅:
  - `payload.kind === "figma-replay-bundle"`
  - `renderFigmaReplayBundle()`
- 특징:
  - 뒤집힘 해결
  - vector transform 해결
  - page 3 검은 overlay 해결
  - visual 기준선으로 사용 중

### 2. PPTX direct upload 경로

- 입력: `.pptx`
- 라우팅:
  - `parsePptxArrayBuffer()`
  - `pptx-replay-bundle` 생성
  - `renderPptxReplayBundle()`
- 특징:
  - old intermediate 경로와는 분리됨
  - 하지만 현재는 여전히 candidate 기반 렌더 수준이라 최종 visual 품질에는 못 미침
  - 화살표, 외곽선, clip/mask 품질 보강이 추가로 필요

## 핵심 문제

문제는 단순 버그가 아니라 `잘못된 렌더 경로 연결`에서 시작되었고, 현재는 그 경로 분리를 1차로 완료한 상태다.

기존에는:

- `PPTX -> intermediate payload -> old renderer`

로 연결되어 있었다.

현재는:

- `PPTX -> pptx-replay-bundle -> renderPptxReplayBundle()`

로 분리되었다.

사용자가 원하는 건:

- `PPTX -> replay-grade visual model -> final replay renderer`

이다.

## 최종 판단

### 가능한가

가능하다.

### 그냥 연결만 바꾸면 되는가

아니다.

이유:

- 현재 PPTX parser가 만드는 것은 `intermediate payload`다.
- 최종 품질 경로가 먹는 것은 `figma replay bundle` 수준의 visual model이다.
- 따라서 `PPTX -> intermediate`를 그대로 `renderFigmaReplayBundle()`에 넣는 방식은 성립하지 않는다.

즉 경로 분리만으로는 충분하지 않고, 추가 개발이 필요하다.

## 필요한 개발 범위

개발은 4개 트랙으로 나눈다.

### Track A. Replay-grade Visual Model Builder

목적:
- PPTX parser 결과를 old intermediate payload가 아니라 replay-grade visual model로 변환

현재:
- `parsePptxArrayBuffer()`는 `pages[]`와 candidate 중심 구조를 만든다

필요한 변경:
- 새 단계 추가:
  - `buildReplayVisualModelFromPptx(parsedPptx)`
- 출력 스키마:
  - `kind: "pptx-replay-bundle"`
  - `document`
  - `pages`
  - `assets`
  - `visual_nodes`
  - `page_layout`
  - `debug`

필수 포함 정보:
- page size
- visual block hierarchy
- text style
- shape fill/stroke/opacity
- connector visual fallback 정보
- clip/mask candidate 정보
- image asset reference

핵심 원칙:
- semantic 모델이 아니라 visual 모델 우선
- 보이는 해석성 기준

### Track B. PPTX 전용 Visual Replay Renderer

목적:
- PPTX에서 만든 replay-grade visual model을 최종 품질 렌더러로 태움

현재:
- `renderFigmaReplayBundle()`는 Figma JSON replay bundle 전용
- `renderIntermediatePayload()`는 품질이 부족

필요한 변경:
- `renderPptxReplayBundle()` 추가
- 또는 `renderFigmaReplayBundle()`를 일반화해서
  - `figma-replay-bundle`
  - `pptx-replay-bundle`
  둘 다 처리

권장:
- 전용 경로 추가 후 공통 유틸만 공유

공통 유틸로 빼야 할 것:
- text rendering
- vector rendering
- rectangle/image rendering
- clip/overlay filtering
- page/frame placement

### Track C. Visual Fallback 규칙 정리

목적:
- PPTX 원본에서 exact Figma JSON이 없는 요소를 어떻게 그릴지 고정

핵심 대상:
- 화살표
- diamond
- 복잡한 외곽선
- 표 선/grid
- clip/mask 의심 도형

원칙:
- text는 native 우선
- 표 셀 텍스트는 native 우선
- 화살표/복잡 도형/외곽은 visual fallback 허용
- 의미를 해치지 않으면 vector-like shell 사용 가능

필수 규칙:
- connector fallback signature
- diamond visual signature
- full-page overlay 판정 규칙
- box outline thickness 규칙

### Track D. 회귀 검증 체계 연결

목적:
- direct upload 품질이 최종본과 얼마나 가까운지 자동으로 확인

현재 있는 것:
- reference manifest
- actual manifest export
- diff v2

필요한 연결:
- `pptx direct upload` 결과도 동일하게 actual manifest export
- page 1 / 2 / 3 기준 regression loop 유지

핵심 지표:
- visual review
- flip mismatch
- overlay skip correctness
- missing node trend

## 구현 순서

### Phase 1. 경로 분리

목표:
- direct upload가 old renderer로 타는 문제 제거

작업:
1. `parsePptxArrayBuffer()` 결과를 intermediate와 replay 후보로 분리
2. UI에서 `.pptx` 업로드 시 `pptx-replay-bundle` 생성 경로 추가
3. old renderer는 fallback / preview 용으로만 남김

완료 기준:
- `.pptx` 업로드가 더 이상 기본적으로 `renderIntermediatePayload()`를 타지 않음

### Phase 2. Visual Model 생성

목표:
- PPTX에서 replay-grade visual model 생성

작업:
1. page size / layout 메타 고정
2. text visual node 생성
3. box/shape visual node 생성
4. image asset reference 생성
5. connector fallback node 생성
6. clip/mask candidate metadata 생성

완료 기준:
- page 1 / 2 / 3를 replay-grade input으로 만들 수 있음

### Phase 3. Renderer 연결

목표:
- visual model을 최종 품질 렌더러로 연결

작업:
1. `renderPptxReplayBundle()` 추가
2. common render utilities 분리
3. overlay/clip 규칙 연결
4. row layout / chapter layout 유지

완료 기준:
- `.pptx` direct upload 결과가 기존 최종 visual replay에 근접

### Phase 4. Regression

목표:
- 개선이 실제로 맞는지 검증

작업:
1. page 1 / 2 / 3 실제 렌더
2. actual manifest export
3. diff 실행
4. visual review
5. regression 기록

완료 기준:
- direct upload 결과가 기존 old renderer보다 명확히 개선

## 하지 않을 것

현재 단계에서 아래는 하지 않는다.

- `.ppt` 직접 파싱
- semantic / node 저장 연결
- DB 적재
- component / asset replacement
- visual을 위해 exporter 결과를 조작하는 방식

## 사용자 경험 원칙

PPTX direct upload는 최종적으로 아래를 만족해야 한다.

1. 사용자는 `.pptx`만 올리면 된다
2. 오래된 PPTX 내부 참조 깨짐은 가능한 범위에서 자동 복구한다
3. 결과는 old preview 수준이 아니라 최종 visual replay 수준에 가깝게 보인다
4. 지원하지 않는 `.ppt`는 명확히 안내한다

## 구현 리스크

### 1. exact Figma JSON 수준을 그대로 만들 수 없는 구간

대상:
- connector
- clip/mask
- 복잡 도형

대응:
- visual fallback 규칙으로 보완

### 2. parser와 renderer가 다시 강하게 결합될 위험

대응:
- parser -> visual model -> renderer 3단 분리 유지

### 3. intermediate 경로와 replay 경로가 다시 섞일 위험

대응:
- payload kind를 명확히 분리
  - `intermediate-preview`
  - `pptx-replay-bundle`
  - `figma-replay-bundle`

## 개발 산출물

필수 산출물:

1. `pptx -> replay-grade visual model` builder
2. `pptx-replay-bundle` schema
3. `renderPptxReplayBundle()` 또는 공통 replay renderer
4. regression comparison 연결
5. page 1 / 2 / 3 검증 기록

## 완료 판정

이 작업이 완료되었다고 보려면 아래를 만족해야 한다.

1. `.pptx` direct upload 결과가 기존 old intermediate renderer와 다르게 최종 visual replay 품질에 근접한다
2. page 1 / 2 / 3에서 기존 최종본 대비 주요 문제(뒤집힘, overlay, 심한 화살표 오해)가 재발하지 않는다
3. regression loop로 확인 가능하다

## 한 줄 요약

`PPTX direct upload`를 진짜 최종본으로 만들려면, 현재 old intermediate renderer 연결을 버리고 `PPTX -> replay-grade visual model -> final replay renderer` 경로를 새로 만들어야 한다.
