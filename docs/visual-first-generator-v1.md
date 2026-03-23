# Visual-First Generator v1

## 목적

이 문서는 `PPT -> replay-grade Figma JSON` 생성기의 새 기준을 고정한다.

기존 `candidate -> renderer 보정` 방식은 중단선으로 본다.
새 목표는 아래다.

- `PPT/PPTX`
- `-> source extractor`
- `-> visual-first generator`
- `-> figma-replay-bundle`
- `-> renderFigmaReplayBundle()`

## 왜 새로 가는가

현재 generator는 semantic/candidate 재구성에 가깝다.

- connector를 추정해서 만든다
- text 크기를 추정한다
- table을 semantic frame tree로 만든다
- shape를 rectangle/frame 위주로 만든다

반면 고급 플러그인 결과는 visual-first, vector-heavy다.

즉 새 엔진은 `candidate를 예쁘게 그리는 것`이 아니라
`고급 플러그인 JSON과 동등한 시각 결과용 node tree`를 만드는 것이 목적이다.

## 엔진 경계

### 1. Source Extractor

역할:
- PPT에서 사실만 읽기

포함:
- slide size
- bounds / rotation / flip
- connector start/end points
- text run / paragraph
- table grid / merge
- group hierarchy
- image asset reference

출력:
- `source page context`
- `source candidate`

### 2. Visual-First Generator

역할:
- extractor 결과를 replay-grade visual node tree로 변환

출력:
- `figma-replay-bundle`

### 3. Replay Renderer

역할:
- bundle을 Figma node로 렌더

현재 완료 renderer 재사용:
- `renderFigmaReplayBundle()`
- `renderReplayNode()`

## 빌더 구성

### Page Builder
- page root frame
- canvas bounds
- background fill

### Text Builder
- text runs / paragraphs
- explicit font size 우선
- wrap / align / inset

### Shape Builder
- simple boxes
- labeled shapes
- diamond / ellipse

### Vector Builder
- connector
- line
- visual fallback shape

### Table Builder
- row / cell visual tree
- merge / span
- border / fill / text

### Image Builder
- image fill / asset ref

### Overlay / Clip Builder
- full-page blocking overlay 제거
- clip-like metadata 유지

## 우선 구현 순서

1. page + background
2. connector / vector
3. text sizing / wrap
4. table layout
5. shape / diamond
6. image
7. overlay / clip refinement

## 성공 기준

1. 생성 bundle이 현재 replay renderer에서 정상 렌더된다
2. reference JSON 대비 QA gate 점수가 오른다
3. page 12 / 19 / 29 visual이 고급 플러그인에 수렴한다

## 하지 않을 것

- candidate renderer 보정 반복
- semantic/DB 구조를 visual engine에 재사용
- 페이지별 하드코딩
