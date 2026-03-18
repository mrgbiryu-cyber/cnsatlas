# Dual Model Architecture

## 1. 목적

현재 프로젝트는 하나의 모델로 아래 두 목표를 동시에 만족시키기 어렵다.

- Figma에서 원본 PPT처럼 잘 읽히는 시각 품질
- DB 적재, 정책 탐색, 질의응답에 필요한 구조화된 node 저장

따라서 모델을 두 개로 분리한다.

- `Visual Model`
- `Semantic Node Model`

그리고 두 모델을 연결하는 `Mapping Layer`를 둔다.

이 구조의 목적은 다음과 같다.

1. 시각 품질은 고급 변환기 수준으로 최대한 맞춘다.
2. 의미 구조는 별도 node 모델로 안정적으로 저장한다.
3. 나중에 필요한 부분만 selective replacement 할 수 있게 한다.

## 2. 전체 구조

### 2-1. Visual Model

역할:

- Figma에서 보이는 결과를 만드는 모델
- 사용자가 PPT와 유사하게 읽고 이해할 수 있는 결과를 우선

특징:

- text는 editable 유지 가능
- 화살표, 복잡 도형, 표 선, 장식 요소는 vector-heavy 허용
- 목적은 `read-first visual fidelity`

### 2-2. Semantic Node Model

역할:

- DB 적재용 구조
- 정책 탐색, 검색, 질의응답, source mapping, lineage 관리

특징:

- `document`
- `page`
- `node`
- `asset`
- `relation`
- `table / row / cell`

목적은 `운영 가능한 구조화 데이터`

### 2-3. Mapping Layer

역할:

- Visual Model과 Semantic Node Model의 대응 관계를 연결

이 레이어가 없으면:

- 화면은 잘 보여도 DB와 연결되지 않고
- DB는 잘 쌓여도 Figma 결과와 매칭되지 않는다

## 3. 왜 이 구조가 필요한가

하나의 모델로 두 목표를 모두 해결하려고 하면 충돌이 생긴다.

예:

- 화살표는 시각적으로는 vector가 유리
- 하지만 DB node로는 의미 관계만 필요

또는:

- 표는 시각적으로 선과 배경이 중요
- DB에서는 cell 의미 구조가 중요

즉, 시각 모델과 저장 모델을 분리해야 한다.

## 4. Visual Model 설계 원칙

### 4-1. 기준

Visual Model의 기준은 `edit-first`가 아니라 `read-first`다.

질문:

- PPT 사용자가 Figma 결과를 보고 바로 이해할 수 있는가

### 4-2. native 유지 대상

- 본문 텍스트
- 제목
- 표 셀 텍스트
- 가격/옵션/설명 등 핵심 정보 텍스트
- 향후 DB node와 직접 연결할 핵심 labeled object

### 4-3. vector-heavy 허용 대상

- connector
- diamond
- 특수 도형
- 표 선 / grid
- 장식 박스
- 복잡한 그룹 외곽

### 4-4. 성공 기준

- 사용자가 화면을 오해하지 않고 읽을 수 있을 것
- 흐름, 단계, 묶음, 표 의미가 보일 것

## 5. Semantic Node Model 설계 원칙

### 5-1. 기준

Semantic Model의 기준은 `운영 데이터로 쓸 수 있는가`다.

질문:

- 이 구조를 DB에 넣어서 정책 찾기와 질의응답에 활용할 수 있는가

### 5-2. 저장 대상

- `document`
- `page`
- `node`
- `asset`
- `relation`
- `table`
- `table_row`
- `table_cell`

### 5-3. relation 중심 저장

화살표 자체는 핵심 node가 아니라 relation으로 보는 것이 맞다.

예:

- `from_node_id`
- `to_node_id`
- `relation_type = flow_transition`

즉, DB에는 화살표 모양을 저장하지 않고 의미 관계를 저장한다.

### 5-4. 성공 기준

- node 단위 검색 가능
- page / node / cell 기준 정책 연결 가능
- source lineage 유지 가능
- 질의응답 컨텍스트 구성 가능

## 6. Mapping Layer 설계 원칙

### 6-1. 목적

Visual Model과 Semantic Model이 같은 객체를 가리키는지 추적하는 레이어다.

### 6-2. 필요한 키

- `document_id`
- `page_id`
- `source_path`
- `source_node_id`
- `figma_node_id`
- `bbox`
- `semantic_fingerprint`

### 6-3. 저장 예시

- `mapping_id`
- `visual_ref_id`
- `semantic_node_id`
- `mapping_type`
- `confidence`

### 6-4. 역할

- selective replacement
- node highlight
- source tracing
- visual-to-data drilldown

## 7. 데이터 흐름

### Step 1. PPT Parse

입력:

- PPTX

출력:

- raw element 구조
- text / group / shape / connector / image / table / cell

### Step 2. Intermediate Layer

입력:

- raw PPT parse 결과

출력:

- 공통 intermediate candidate

역할:

- Visual Model과 Semantic Model의 공통 출발점

### Step 3-A. Visual Model 생성

입력:

- intermediate candidate

출력:

- Figma 렌더용 visual object

특징:

- text native
- complex visual 요소는 vector fallback 허용

### Step 3-B. Semantic Model 생성

입력:

- intermediate candidate

출력:

- document / page / node / asset / relation 구조

특징:

- DB 적재 중심
- 정책 탐색 / QA 중심

### Step 4. Mapping 생성

입력:

- Visual object
- Semantic node

출력:

- visual-semantic mapping table

### Step 5. Figma / DB 운영

Visual Model:

- 사용자가 Figma에서 읽고 작업

Semantic Model:

- DB에서 검색, 정책 연결, 질의응답

Mapping Layer:

- 둘의 연결 유지

## 8. 구현 단계

### Phase 1. Visual First

목표:

- PPT 사용자가 Figma 결과를 보고 바로 이해할 수 있는 수준 도달

해야 할 일:

- 고급 플러그인 수준의 visual fidelity 추적
- text / connector / shape / table 시각 품질 개선
- read-first 기준으로 검수

완료 조건:

- 1page / 2page read-first PASS
- 3page baseline 기준 개선 가능 상태

### Phase 2. Semantic 저장

목표:

- 전환 결과를 node 구조로 별도 저장

해야 할 일:

- canonical node schema 적용
- document / page / node / asset / relation 생성
- source mapping 생성

완료 조건:

- DB 적재 가능
- page / node / cell 검색 가능

### Phase 3. Mapping Layer

목표:

- Figma visual object와 semantic node 연결

해야 할 일:

- mapping key 고정
- 시각 객체와 node 대응 관계 저장
- visual->semantic drilldown 가능하게 준비

완료 조건:

- 특정 Figma 영역에서 DB node 역추적 가능

### Phase 4. Selective Replacement

목표:

- 필요한 객체만 semantic 기반 native object로 부분 교체

대상 예시:

- 핵심 labeled box
- 일부 표 cell
- 강조 텍스트

조건:

- 사용자 가독성을 해치지 않을 것
- DB node와 연결 가치가 있을 것

완료 조건:

- visual fidelity 유지
- semantic 활용성 강화

## 9. 무엇을 바로 하지 않을 것인가

현재는 아래를 바로 하지 않는다.

- 전체 객체의 에셋화
- 전체 객체의 컴포넌트 치환
- 디자인 시스템 전면 연계

이유:

- 현재 단계의 핵심 목표가 아니다
- 복잡도 대비 효과가 불확실하다
- 먼저 `고품질 전환 + node 저장`을 달성해야 한다

## 10. 객관적 판단

이 구조의 장점:

- 시각 품질과 저장 구조의 충돌을 줄일 수 있다
- 고급 플러그인의 vector-heavy 전략을 활용할 수 있다
- 동시에 우리 프로젝트의 node/DB 목적도 유지할 수 있다

이 구조의 리스크:

- 모델이 두 개라서 mapping이 약하면 분리 운영될 수 있다
- visual과 semantic의 불일치가 생길 수 있다

따라서 핵심은:

- Visual Model 품질
- Semantic Model 정확성
- Mapping Layer 안정성

이 세 개를 함께 관리하는 것이다.

## 11. 결론

현재 프로젝트에 가장 현실적인 구조는 다음이다.

1. Figma 화면 품질은 Visual Model로 맞춘다.
2. DB 저장과 정책 탐색은 Semantic Node Model로 처리한다.
3. 두 모델은 Mapping Layer로 연결한다.
4. 이후 필요한 부분만 selective replacement 한다.

즉,

> 먼저 잘 보이게 만들고, 동시에 잘 쌓이게 만들며, 나중에 필요한 부분만 연결해서 대체하는 구조가 현재 프로젝트에 가장 적합하다.
