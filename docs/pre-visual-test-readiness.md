# Pre-Visual Test Readiness

대상:

- PPT slide `12`
- PPT slide `19`
- PPT slide `29`

목적:

- 1차 비주얼 테스트 전에
- 현재 구조 추출과 intermediate model 개선 상태를 정리하고
- 비주얼 테스트에서 무엇을 확인해야 하는지 고정한다.

## 현재 완료 상태

완료된 것:

- `12`, `19`, `29`의 PPT 상세 추출
- text / shape / connector / group / image / table 추출
- `19`의 table -> row -> cell 구조화
- `29`의 image 후보 및 table 구조 추출
- intermediate node candidate 생성
- 기존 Figma JSON과 구조 비교 리포트 생성

아직 하지 않은 것:

- 새 converter의 실제 Figma-like 출력 생성
- 새 converter 결과의 시각 비교
- 사람검수 `usable` 판정

즉 현재 단계는 비주얼 테스트 직전의 구조 준비 단계다.

## 슬라이드별 준비 상태

### Slide 12

현재 구조 요약:

- candidate count: `115`
- 핵심 subtype:
  - `text_block: 1`
  - `labeled_shape: 61`
  - `connector: 24`
  - `group: 13`
  - `section_block: 3`

의미:

- flow / process diagram 성격이 강하다.
- text, labeled node, connector 흐름이 핵심이다.

비주얼 테스트에서 볼 것:

- process 흐름이 화면상 이해 가능한가
- connector와 labeled shape 관계가 무너지지 않았는가
- group/section 단위가 납작해지지 않았는가

### Slide 19

현재 구조 요약:

- candidate count: `299`
- 핵심 subtype:
  - `table: 3`
  - `table_row: 55`
  - `table_cell: 232`

의미:

- table 중심 슬라이드다.
- intermediate model에서는 semantic table 구조를 확보했다.
- 반면 기존 고급 플러그인 결과는 vector grid + text 중심이다.

비주얼 테스트에서 볼 것:

- table가 단순 선과 글자 덩어리로 flatten되지 않는가
- row/cell 구조를 유지한 채 Figma에서 읽히는가
- 셀 텍스트 정렬과 표 경계가 안정적인가

### Slide 29

현재 구조 요약:

- candidate count: `184`
- 핵심 subtype:
  - `labeled_shape: 87`
  - `group: 17`
  - `image: 11`
  - `table: 1`
  - `table_row: 6`
  - `table_cell: 12`
  - `section_block: 2`

의미:

- 복합 UI 성격이 가장 강하다.
- text, image, group, table가 함께 섞인 종합 난이도 슬라이드다.

비주얼 테스트에서 볼 것:

- 가격/옵션 정보가 읽기 쉬운가
- image가 asset처럼 유지되는가
- section/group 단위가 실무적으로 이해 가능한가
- 복합 구조에서 과도한 vector flatten이 없는가

## 현재 판단

구조 개선 관점에서 보면:

- `12`: flow 구조를 intermediate model로 설명 가능
- `19`: semantic table 구조를 intermediate model로 복원 가능
- `29`: 복합 UI를 intermediate model로 분해 가능

즉 비주얼 테스트 전 단계에서 필요한 구조 준비는 완료된 상태로 본다.

## 비주얼 테스트 직전 확인 항목

1. slide `12`
- connector + labeled shape + section 흐름 확인

2. slide `19`
- table -> row -> cell 구조 유지 여부 확인

3. slide `29`
- image + text + group + table 복합 구조 유지 여부 확인

## 비주얼 테스트 목표

이번 1차 비주얼 테스트의 목표는 완성품 평가가 아니다.

목표는 아래 두 가지다.

1. 현재 intermediate model이 실제 변환 규칙으로 이어질 수 있는지 확인
2. 기존 고급 플러그인 결과와 비교해 우리가 개선해야 할 포인트를 조기 확정
