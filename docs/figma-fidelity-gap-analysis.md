# 고품질 변환기 대비 Figma Fidelity Gap 분석

## 1. 목적

현재 구현은 `운영 구조 추출 + 구조 확인용 렌더러`에 가깝다.
반면 benchmark로 삼고 있는 고품질 변환기는 `시각 fidelity + editable 구조`에 더 가깝다.

이 문서는 현재 구현이 고품질 변환기보다 떨어지는 이유를

- parser
- intermediate model
- renderer

관점으로 나누고, 이후 보강 우선순위를 정리한다.

## 2. 현재 상태 요약

### 현재 구현이 강한 부분

- text / group / table / cell / image를 semantic 단위로 분해 가능
- `document/page/node/asset/source_mapping`으로 확장 가능한 구조 확보
- slide `12/19/29` 기준 intermediate candidate 생성 가능
- Figma 플러그인으로 시각 확인 가능

### 현재 구현이 약한 부분

- 실제 시각 재현 정확도 부족
- typography 반영 부족
- shape style / alpha / theme 반영 부족
- connector / arrow geometry 부족
- table real layout 부족
- image actual rendering 부족

## 3. gap의 본질

현재 구현은 다음 질문에는 강하다.

- 어떤 element가 있는가
- table/cell이 존재하는가
- group/section이 있는가
- 이후 운영 대상으로 삼을 node가 무엇인가

하지만 아래 질문에는 약하다.

- 원래 몇 px 크기로 보여야 하는가
- 어떤 폰트/크기/정렬인가
- fill/stroke/alpha가 무엇인가
- connector arrow가 어디를 향하는가
- table cell 폭/높이가 실제로 얼마인가
- image가 실제로 어떤 방식으로 보이는가

즉 semantic fidelity는 어느 정도 확보했지만 visual fidelity가 약하다.

## 4. parser 부족 항목

### P1. slide canvas size

현황:

- 현재 slide size는 추출 시작
- renderer 반영 시작

부족:

- page bounds 계산과 원본 slide padding 관계 정리 필요

영향:

- 캔버스 크기 불일치

### P2. text typography

현황:

- run level font size 일부 추출
- bold / italic 일부 추출
- text fill 일부 추출

부족:

- font family
- font weight/style 정확도
- line spacing
- paragraph spacing
- text box inset / internal padding
- vertical text alignment
- wrap rules

영향:

- 텍스트 크기 / 위치 / 줄바꿈 불일치

### P3. fill / stroke / alpha

현황:

- solid fill / line color 일부 추출
- alpha 일부 추출 시작

부족:

- theme color 해석
- gradient fill
- transparency 상세
- dash / compound line

영향:

- 색감 부족
- 알파값 부정확
- 도형이 단조로워 보임

### P4. shape geometry

현황:

- `rect`, `roundRect`, `ellipse`, `connector` 정도만 구분

부족:

- freeform / chevron / callout / custom geometry
- rotation / flip
- corner 처리

영향:

- 도형 구분이 약함

### P5. connector / arrow path

현황:

- connector를 bounding box 기반 line으로 처리

부족:

- 실제 start/end point
- elbow / bend path
- arrowhead direction
- connector style

영향:

- 화살표 방향과 위치 불일치

### P6. table actual layout

현황:

- semantic `table -> row -> cell` 보존 가능

부족:

- 실제 column width
- 실제 row height 전부
- merge layout 반영
- cell fill / border style

영향:

- 표는 semantic하게 맞아도 비주얼은 다름

### P7. image rendering

현황:

- image target 추적 가능

부족:

- actual binary import
- crop / fit / clip
- transparency

영향:

- 현재는 placeholder 수준

## 5. intermediate model 부족 항목

### M1. visual render layer 부재

현재 intermediate는 semantic layer 중심이다.

- `text_block`
- `table_cell`
- `group`
- `section_block`

하지만 visual layer로 필요한 정보가 부족하다.

- actual style
- actual render geometry
- actual text layout info
- z-order

### M2. semantic과 visual 분리 부족

지금은 candidate 하나에 semantic과 visual이 섞여 있다.

향후에는 다음이 필요하다.

- semantic payload
- render payload

예:

- semantic: `table_cell`
- render: 실제 셀 크기, border, fill, text inset

## 6. renderer 부족 항목

### R1. 기본 shape 렌더링만 있음

- rectangle / ellipse / line 중심
- 고급 도형 재현 부족

### R2. text placement 추정값 사용

- bounds 기반 추정 font size
- 정렬 일부만 반영
- text box internal layout 미반영

### R3. table layout 균등 분할

- row/cell semantic은 좋지만 visual layout는 원본과 다름

### R4. image placeholder 처리

- 실제 이미지 표시가 아니라 placeholder

### R5. connector 단순화

- bounding box line 수준
- 실제 arrow direction/shape 미반영

## 7. 우선 보강 순위

### Priority 1

- slide canvas size
- text typography
- fill / stroke / alpha

이 세 가지가 개선되면 체감 품질이 가장 크게 올라간다.

직결 이슈:

- 색감
- 텍스트 크기
- 텍스트 위치
- 캔버스 크기

### Priority 2

- shape geometry
- table actual layout

직결 이슈:

- 도형 구분
- 표 비주얼 정합성

### Priority 3

- connector / arrow path
- image actual rendering

직결 이슈:

- 화살표 정확도
- 이미지 fidelity

## 8. 다음 구현 backlog

### Backlog A. Typography fidelity

- font family 추출
- font size 정확도 강화
- paragraph align 강화
- text inset / wrap 규칙 반영
- Figma text placement 로직 개선

### Backlog B. Shape fidelity

- fill/stroke/theme color 보강
- alpha / opacity 보강
- roundRect / ellipse / line / connector 보강
- rotation / flip 추출 가능성 확인

### Backlog C. Table fidelity

- row height / column width 추출
- merged cell layout 반영
- border style 반영
- cell text align 반영

### Backlog D. Connector fidelity

- start/end point 추출
- arrow head mapping
- bend path 표현 가능성 확인

### Backlog E. Image fidelity

- image binary read
- Figma image fill 적용
- crop/fit 정책 정의

## 9. 실무 판단

현재 구현은 버릴 상태는 아니다.

왜냐하면:

- semantic 구조는 이미 강하다
- 운영 플랫폼으로 가는 기반은 확보했다

다만 고품질 변환기 수준으로 가려면,
현재 파이프라인 위에 `visual fidelity layer`를 추가해야 한다.

즉 방향은 틀린 것이 아니라, 아직 반쪽이다.

## 10. 결론

고품질 변환기보다 떨어지는 이유는

1. parser가 원본 시각 정보를 충분히 추출하지 못하고
2. intermediate model이 semantic 중심이며
3. renderer가 placeholder 수준이기 때문이다

따라서 앞으로의 핵심은 다음 한 줄로 정리된다.

> 현재 semantic pipeline 위에 visual fidelity 전용 parser 필드와 renderer 로직을 추가해, 운영 가능성과 시각 품질을 동시에 만족시키는 방향으로 확장한다.
