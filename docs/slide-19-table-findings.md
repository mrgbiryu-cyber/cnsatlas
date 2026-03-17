# Slide 19 Table Findings

대상:

- PPT slide `19`
- Figma page `Page 2`

## 결론

현재 고급 변환 플러그인 결과에서 slide `19`의 표는 semantic table 구조로 유지되지 않았다.

실제 Figma 결과는 아래 형태에 가깝다.

- vector line grid
- text labels
- 일부 group wrapping

즉, 표 자체가 `table -> row -> cell` 구조로 남은 것이 아니라,
시각적으로는 표처럼 보이지만 내부적으로는 `vector + text` 조합으로 재구성된 상태다.

## PPT 원본 구조 요약

- text element: `6`
- table element: `3`
- group element: `0`
- image element: `0`

핵심 의미:

- 원본은 table 중심 슬라이드다.
- table 보존 품질을 판단하기에 적합하다.

## Figma 결과 구조 요약

- text node: `257`
- vector node: `114`
- group node: `25`
- frame node: `2`

핵심 의미:

- 텍스트는 많이 살아남았다.
- 하지만 표 grid는 대부분 vector line으로 표현되었다.
- semantic table 모델은 직접 드러나지 않는다.

## 관찰 포인트

1. 컬럼/행 경계가 vector로 표현된다.
2. 셀 값은 TEXT로 분리되어 있다.
3. 일부 하위 블록은 GROUP으로 묶여 있다.
4. table 자체의 의미 구조는 Figma node 타입으로 보존되지 않는다.

## 프로젝트 관점의 해석

현재 변환 결과는 아래에는 강하다.

- 시각적 유사성
- 텍스트 세분화
- 표 내용을 읽는 용도

현재 변환 결과는 아래에는 약하다.

- cell 단위 source mapping
- row/cell 단위 annotation target
- table diff
- 운영용 semantic table model

## 개발 시사점

새 converter는 slide `19` 유형에서 아래를 목표로 해야 한다.

1. table를 row/cell 구조로 먼저 intermediate model에 저장
2. Figma 변환 시에도 가능하면 cell 단위 frame/text 구조로 유지
3. 최소한 table boundary와 cell boundary를 semantic metadata로 잃지 않게 설계
4. 이후 source_mapping에서 table / row / cell identity를 별도로 유지

## 우선 개선 포인트

- table extraction 강화
- row/cell identity 부여
- figma output에서 vector flatten 최소화
- table형 node에 대한 metadata 유지
