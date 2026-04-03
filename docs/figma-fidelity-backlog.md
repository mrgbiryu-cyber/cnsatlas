# Figma Fidelity Backlog

## 목적

고품질 변환기 대비 부족한 visual fidelity 항목을
실제 개발 순서로 잘라낸다.

## Gate 기준

다음 backlog는 모두 `Figma가 실제 운영 가능한가`를 높이기 위한 작업이다.

즉, DB 적재나 포털 이전에 아래 항목을 우선한다.

## Batch 1. 기본 화면 정합성

목표:

- 화면 크기
- 텍스트 크기
- 기본 색상
- 기본 도형 구분

을 먼저 맞춘다.

### 작업

1. slide canvas size 정확 반영
2. text font size / align / fill 반영
3. shape fill / stroke / alpha 반영
4. ellipse / roundRect / rect 구분 강화
5. intermediate JSON 재생성
6. 2차 비주얼 테스트

### 성공 기준

- 캔버스 크기 체감 오류 감소
- 텍스트 크기 체감 오류 감소
- 주요 색감 복원
- 원형/사각형 구분 가능

## Batch 2. 표 정합성

목표:

table/cell이 semantic뿐 아니라 비주얼도 가까워지게 한다.

### 작업

1. row height 반영 강화
2. column width 추출 추가
3. merged cell 반영
4. cell text alignment 반영
5. cell border style 반영

### 성공 기준

- slide 19 table이 원본 구조와 더 유사하게 보임
- cell 단위 운영 가능성과 시각 정합성이 동시에 개선

## Batch 3. 화살표/선 정합성

목표:

connector와 arrow의 실제 방향과 연결감을 높인다.

### 작업

1. connector start/end metadata 추출
2. arrow head type 반영
3. 직선/세로선/기본 방향 처리 보강
4. bend path 가능성 검토
5. start/end `idx` 기반 side(top/left/bottom/right)로 꺾임점 산정
6. PPTX connector adjust(`adj1/adj2`)를 side 경로에 적용

### 성공 기준

- slide 12 flow line이 현재보다 자연스럽게 보임
- 화살표 방향 오류 감소

## Batch 6. Z-order 계층 안정화

목표:

그룹(부모) 레벨에서 발생하는 상하 역전을 제거한다.

### 작업

1. 노드/그룹/청크 모두 `source_order_path` 보존
2. 형제 정렬은 `source_order_path` 우선, 정적 priority는 tie-breaker로만 사용
3. 부모 그룹이 자식보다 앞서는 역전 케이스 회귀 테스트 추가

### 성공 기준

- Figma에서 클릭 시 상단 객체가 의도한 그룹으로 선택됨
- 상위 그룹 때문에 하위 텍스트/도형이 가려지는 케이스 감소

## Batch 4. 이미지 정합성

목표:

placeholder 대신 실제 이미지가 보이게 한다.

### 작업

1. image binary read
2. Figma image fill 적용
3. crop / fit 전략 정의

### 성공 기준

- slide 29의 이미지 영역이 placeholder가 아니라 실제 이미지로 표시

## Batch 5. 고급 typography

목표:

텍스트 줄바꿈과 배치까지 정교하게 맞춘다.

### 작업

1. font family 추출
2. paragraph spacing
3. line spacing
4. text inset / internal padding
5. wrap 규칙 보정

### 성공 기준

- 텍스트 위치 오차 감소
- 긴 문장 레이아웃 안정화

## 우선순위

1. Batch 1
2. Batch 2
3. Batch 3
4. Batch 4
5. Batch 5

## 추천 운영 방식

- Batch 단위로 구현
- 매 Batch 후 비주얼 테스트
- 당신이 직접 `운영 가능 / 아직 부족` 판단
- 통과할 때까지 다음 단계로 넘기지 않음
