# Replay Generator QA Gate

## 목적

이 문서는 `PPT -> replay-grade JSON generator`의 품질을 사람 눈으로만 판단하지 않고,
시스템이 먼저 `합격 / 불합격`을 판정하기 위한 자동 검증 기준을 고정한다.

핵심 원칙은 아래다.

1. 먼저 `PPT를 파싱했을 때 replay-grade JSON이 잘 생성되는지` 본다.
2. 그 다음 `그 JSON이 완료 renderer에서 고급 플러그인 수준에 가까운지` 본다.
3. 이 두 기준을 시스템이 먼저 점수화하고, 마지막에만 사람이 시각 검수한다.

즉 순서는 아래다.

1. `PPT -> generated replay bundle`
2. `generated replay bundle -> renderer`
3. `reference Figma JSON` 대비 자동 비교
4. `PASS / FAIL / HOLD`
5. 마지막 visual review

---

## 입력

자동 판정은 아래 3개 입력을 사용한다.

### 1. Reference

고급 플러그인 결과 Figma JSON

- `scripts/figma-page-1.json`
- `scripts/figma-page-2.json`
- `scripts/figma-page-3.json`

### 2. Generated

우리 generator가 만든 replay bundle을 renderer로 렌더한 뒤,
같은 방식으로 다시 받은 Figma JSON

- `scripts/generated-page-1.json`
- `scripts/generated-page-2.json`
- `scripts/generated-page-3.json`

### 3. Intermediate diagnostics

generator가 만든 bundle 자체

- `docs/generated-replay-bundles/ppt-slide-12.bundle.json`
- `docs/generated-replay-bundles/ppt-slide-19.bundle.json`
- `docs/generated-replay-bundles/ppt-slide-29.bundle.json`

즉 자동 판정은 아래 두 레이어를 같이 본다.

- `generator output quality`
- `rendered result similarity`

---

## 검증 레이어

자동 판정은 3개 레이어로 나눈다.

### Layer A. Generator completeness

질문:

> replay bundle이 renderer가 기대하는 구조를 빠짐없이 만들었는가?

주요 항목:

- `kind == figma-replay-bundle`
- `document` 존재
- `assets` 구조 정상
- page root `FRAME` 존재
- `TEXT / VECTOR / FRAME / RECTANGLE` 최소 타입이 존재
- overlay metadata / debug metadata 누락 여부

이 레이어가 실패하면 바로 `FAIL`이다.

### Layer B. Structural similarity

질문:

> reference와 비교했을 때 구조가 충분히 비슷한가?

주요 항목:

- canvas size
- node type distribution
- vector presence
- table tree structure
- text node presence
- missing / extra node ratio

이 레이어는 사람이 보기 전에 먼저 걸러내는 용도다.

### Layer C. Visual approximation

질문:

> 구조가 비슷한 수준을 넘어, 보이는 결과가 reference에 가까운가?

주요 항목:

- arrow direction proxy
- text size delta
- diamond / key shape position delta
- table cell bbox delta
- background fill match
- overlay absence

이 레이어까지 통과한 뒤에만 사람이 최종 검수한다.

---

## 매핑 기준

자동 판정은 먼저 `reference node`와 `generated node`를 매칭해야 한다.

기본 원칙:

1. `semantic key`
2. `content key`
3. `type + bbox proximity`
4. `structure context`

### semantic key

생성 규칙 예시:

- `TEXT:제품선택`
- `TEXT:케어십`
- `VECTOR:Google Shape;469;p15`
- `FRAME:cell 1-1`
- `GROUP:Group`

### content key

텍스트:

- normalized characters
- line break signature

벡터:

- type
- name
- bbox bucket

표:

- row index
- cell index
- text content

화살표:

- connector title/name
- start/end proximity
- bbox bucket

주의:

- 현재 단계에서는 `node id exact match`를 쓰지 않는다.
- reference / generated는 서로 다른 Figma node id를 가진다.

---

## 페이지별 핵심 비교 대상

### Page 1

중요도 순서:

1. 화살표
2. diamond / decision shape
3. 우하단 그룹
4. 텍스트 크기
5. 불필요한 외곽선

### Page 2

중요도 순서:

1. 표 구조
2. 표 상단 박스 배경
3. 표 하위 열 존재 여부
4. 텍스트 크기
5. 화살표

### Page 3

중요도 순서:

1. overlay 없음
2. 표/설명 영역
3. 이미지/박스 배치
4. 텍스트 크기/줄바꿈
5. 상단 구조

---

## 타입별 점수 항목

각 페이지는 아래 타입별 점수를 가진다.

### 1. Canvas score

비교:

- root width / height
- root fill 존재
- background color match

PASS 기준:

- size exact match
- fill exists
- background mismatch 없음

### 2. Text score

비교:

- text node coverage ratio
- bbox mean delta
- font size mean delta
- line break signature match

권장 기준:

- coverage `>= 0.9`
- mean bbox delta `<= 8px`
- mean font size delta `<= 2px`

### 3. Vector score

비교:

- vector count ratio
- bbox mean delta
- rotation / flip mismatch

권장 기준:

- vector count ratio `>= 0.75`
- flip mismatch ratio `<= 0.1`

### 4. Connector score

비교:

- expected connector count vs generated connector-like vector count
- arrow head direction proxy
- missing connector ratio

권장 기준:

- missing connector ratio `<= 0.2`
- critical first-flow connector missing `== 0`

### 5. Table score

비교:

- row count match
- cell count match
- merged cell preservation
- cell bbox mean delta

권장 기준:

- row match exact
- cell presence ratio `>= 0.9`
- major category row loss `== 0`

### 6. Shape score

비교:

- key shape presence
- diamond bbox delta
- major box fill/stroke match

권장 기준:

- decision shape missing `== 0`
- decision bbox center delta `<= 10px`

### 7. Overlay score

비교:

- full-page black overlay presence
- clip candidate skip correctness

권장 기준:

- blocking overlay count `== 0`

---

## 점수 계산 방식

페이지별 총점은 100점으로 본다.

권장 가중치:

- canvas: 10
- text: 20
- vector: 15
- connector: 20
- table: 20
- shape: 10
- overlay: 5

총점 계산:

- 각 항목 0~100으로 계산
- 가중 평균으로 page score 산출

예시:

- `page_1_score = 76.4`
- `page_2_score = 58.2`
- `page_3_score = 84.7`

---

## PASS / FAIL / HOLD 규칙

### FAIL

아래 중 하나면 즉시 FAIL:

- replay bundle 생성 실패
- root canvas size mismatch
- blocking overlay 존재
- page 핵심 타입 누락
  - page 1 connector missing severe
  - page 2 table major category loss
  - page 3 overlay or major section missing

### HOLD

구조는 통과지만 시각 품질이 기준 미달일 때:

- total score `< 80`
- 또는 connector / table / text 중 1개라도 기준 미달

이 상태는 “추가 개발 필요”로 본다.

### PASS

모든 페이지가 아래를 만족:

- total score `>= 80`
- critical fail 없음
- connector severe issue 없음
- table severe issue 없음
- overlay issue 없음

PASS 후에만 시각 검수로 넘어간다.

---

## 최종 시각 검수 조건

자동 판정이 PASS 또는 PASS 직전일 때만 사람이 본다.

사람이 보는 항목은 제한한다.

- Page 1: 첫 화살표 / diamond / 그룹
- Page 2: 표 헤더 / 하위 열 / 표 배경
- Page 3: overlay / 주요 레이아웃

즉 사람이 모든 노드를 보지 않는다.

시스템이 먼저 걸러낸 후,
마지막으로 주요 UX 항목만 본다.

---

## 산출물

각 루프마다 아래 산출물을 남긴다.

### 1. generator diagnostics

- bundle type counts
- missing assets
- overlay candidate count

### 2. structural diff report

- missing nodes
- extra nodes
- type distribution diff
- text/vector/table/shape diff

### 3. qa gate report

예시:

```json
{
  "page": 1,
  "status": "HOLD",
  "score": 74.3,
  "fail_reasons": [
    "connector_missing_ratio_high",
    "diamond_center_delta_exceeded"
  ],
  "metrics": {
    "canvas_match": true,
    "text_bbox_mean_delta": 9.7,
    "vector_count_ratio": 0.24,
    "connector_missing_ratio": 0.42
  }
}
```

---

## 현재 적용 순서

구현 순서는 아래로 고정한다.

1. replay bundle 생성
2. generator diagnostics 출력
3. rendered Figma JSON 추출
4. reference 대비 diff
5. page score 계산
6. PASS / FAIL / HOLD 판정
7. 마지막 visual review

즉 앞으로는

> “눈으로 보니 조금 나아짐”

이 아니라

> “시스템 점수와 fail reason이 개선됨”

을 먼저 본다.

---

## 한 줄 결론

이 프로젝트의 parser/generator 고급화는 반드시

- `reference JSON 대비 자동 비교`
- `page/type별 score`
- `PASS / FAIL / HOLD`

체계 위에서 진행해야 한다.

그래야 대량 PPT에서도 사람이 처음부터 끝까지 수기 검수하지 않고,
시스템이 먼저 합격 여부를 판단한 뒤 최종 시각 검수로 넘어갈 수 있다.
