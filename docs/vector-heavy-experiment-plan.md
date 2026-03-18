# Vector-Heavy 비교 실험 계획

## 1. 실험 목적

현재 `read-first` 방식은 구조 유지에는 강하지만, Figma에서 보이는 결과가 기대보다 빠르게 좋아지지 않고 있다.

따라서 현재 방식을 기준점으로 고정한 뒤, 별도의 비교 실험 트랙으로 아래 가설을 검증한다.

> 핵심 노드는 유지하되, 나머지 시각 요소를 적극적으로 vector fallback 처리하면 PPT 사용자가 Figma에서 더 쉽게 읽고 이해할 수 있는가?

이 실험의 목적은 구조 완성도가 아니라 `보이는 해석성` 개선 여부를 확인하는 것이다.

## 2. 기준점

현재 롤백 기준점:

- git tag: `checkpoint/read-first-v1`
- branch: `experiment/vector-heavy-read-first`

의미:

- 현재 `read-first` 렌더러 상태를 언제든 복구 가능한 기준점으로 둔다.
- 이후 실험은 이 기준점과 비교한다.

## 3. 비교할 두 방식

### A. 현재 방식

특징:

- text / table / group / connector를 비교적 구조적으로 렌더
- editable 가능성을 일부 유지
- node 구조와 시각 표현이 비교적 가까움

장점:

- 이후 DB 적재와 node 연결에 유리
- semantic 구조 보존이 강함

단점:

- 화살표, 복잡 도형, 일부 그룹 표현이 시각적으로 불안정
- PPT 사용자가 보기엔 오히려 해석이 어려운 경우가 생김

### B. Vector-Heavy 방식

특징:

- 핵심 노드만 native로 유지
- 나머지 시각 요소는 vector fallback 중심으로 렌더
- 시각 fidelity와 해석성을 우선

장점:

- 복잡한 도형/화살표를 더 안정적으로 보이게 할 가능성
- PPT 사용자가 익숙한 화면 인지에 유리할 가능성

단점:

- editable 범위가 줄어들 수 있음
- node 구조와 시각 표현이 분리될 수 있음

## 4. 실험 원칙

### 4-1. 핵심 노드는 반드시 유지

아래는 native 유지 대상이다.

- text_block
- table
- table_row
- table_cell
- image asset
- DB와 연결해야 하는 핵심 labeled node

즉, 나중에 정책 찾기 / 질의응답으로 이어질 데이터 구조는 사라지면 안 된다.

### 4-2. 나머지는 적극적으로 시각 레이어로 처리 가능

아래는 vector fallback 후보로 본다.

- connector
- complex shape
- diamond
- decoration shape
- 일부 group container
- 가독성을 위해 native일 필요가 없는 박스/라인

### 4-3. 판단 기준은 editable보다 read-first

질문:

- PPT 사용자가 Figma 결과를 봤을 때 더 쉽게 이해되는가?

즉,

- 수정하기 약간 불편해도 괜찮다
- 대신 화면 해석이 쉬워져야 한다

## 5. 핵심 노드 정의

이번 실험에서 핵심 노드는 다음처럼 본다.

### 필수 native

- 제목
- 본문 설명 텍스트
- 표 셀 텍스트
- 가격 / 옵션 / 설명 등 핵심 정보 텍스트
- 향후 node DB로 연결해야 하는 의미 노드

### 조건부 native

- labeled shape
  - 내부 텍스트가 중요한 경우 native
  - 단순 장식 박스는 vector 가능

### vector fallback 우선

- 화살표
- diamond
- callout
- 특수 도형
- 장식성 박스
- 복잡한 흐름선

## 6. 구현 방식

### Step 1. 렌더 레이어 분리

논리:

- semantic layer는 그대로 유지
- visual layer만 vector-heavy로 바꾼다

즉 DB용 node 구조는 유지하고,
Figma에 보이는 표현만 다르게 실험한다.

### Step 2. 타입별 렌더 모드 재분류

예시:

- `connector` -> `vector_fallback`
- `decision_diamond` -> `vector_fallback`
- `decorative_shape` -> `vector_fallback`
- `table_cell` -> `native`
- `text_block` -> `native`

### Step 3. 비교 기준 고정

비교 기준:

- 1page
- 2page
- 3page

질문:

- 현재 방식보다 화면이 더 읽히는가?
- 고급 플러그인 느낌에 더 가까워지는가?
- 핵심 정보는 여전히 수정 가능하고 추적 가능한가?

## 7. 테스트 기준

### 1page / 2page

우선 확인:

- 화살표가 더 읽히는가
- 흐름 해석이 쉬워지는가
- 박스/텍스트 관계가 더 자연스러운가

### 3page

우선 확인:

- 복합 UI가 더 안정적으로 보이는가
- 상단 영역, 표, 텍스트, 그룹이 더 읽히는가

## 8. 성공 조건

실험 성공은 아래 조건을 만족해야 한다.

1. 현재 방식보다 `시각 해석성`이 좋아진다
2. 고급 플러그인 결과와의 체감 격차가 줄어든다
3. 필수 node 구조는 유지된다

## 9. 실패 조건

아래 중 하나면 실패로 본다.

1. 화면은 좋아 보이지만 핵심 노드가 사라진다
2. 텍스트/표 같은 필수 수정 대상까지 vector화된다
3. 현재 방식보다도 더 읽기 어려워진다

## 10. 결론

이번 실험은 현재 방식을 버리는 것이 아니라,
`현재 방식`과 `vector-heavy 방식`을 비교해 더 나은 방향을 찾기 위한 것이다.

즉, 목표는 다음과 같다.

> 핵심 노드는 유지하고, 나머지 시각 요소는 과감히 vector fallback 처리했을 때, PPT 사용자가 Figma 결과를 더 쉽게 읽고 이해하는지 비교 검증한다.
