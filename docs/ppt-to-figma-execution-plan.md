# PPT to Figma 변환 우선 실행계획

## 목표

1차 실행은 `PPT -> Figma 변환` 자체에 집중한다.

즉, 지금 단계에서는 검색, DB, 포털보다 먼저 아래 질문에 답해야 한다.

> 우리가 만드는 parser/converter가 현재 확보된 고급 변환 플러그인 결과와 비교해서 동일하거나 향상될 수 있는가?

## 기준 입력

- PPT benchmark: `sampling/pptsample.pptx`
- 전체 슬라이드 수: `39`
- 현재 비교 실험 대상: `12`, `19`, `29`
- 현재 확보된 Figma JSON: `sampling/figma-current-page.json`

## 현재 대응 관계

- PPT `12` <-> Figma `Page 1`
- PPT `19` <-> Figma `Page 2`
- PPT `29` <-> Figma `Page 3`

이 세 장을 먼저 비교 실험 기준으로 고정한다.

## 실행 순서

### Step 1. 대응 관계 고정

- 위 매핑을 기준안으로 고정
- title, 구조 특성, 주요 텍스트로 재검증

산출물:

- slide-page mapping 표

### Step 2. PPT 상세 추출기 구현

대상:

- `12`
- `19`
- `29`

추출 대상:

- text
- shape
- image
- table
- row
- cell
- group
- hierarchy
- source path

산출물:

- slide별 intermediate JSON

### Step 2.5. 구조 확인용 중간 비주얼 테스트

목적:

- 아직 최종 품질을 보려는 것이 아니라
- intermediate model이 실제 화면 구조를 얼마나 잘 설명하는지 빠르게 확인한다.

테스트 대상:

- `12`
- `19`
- `29`

확인 항목:

- text block 분해가 과도하거나 부족하지 않은가
- group/section 경계가 보이는가
- table/row/cell 후보가 식별되는가
- image/asset 후보가 분리되는가

산출물:

- 구조 확인용 미리보기
- 추출 과소/과다 분해 이슈 목록

의미:

- 이 단계의 비주얼 테스트는 “예쁘게 변환됐는가”가 아니라
- “우리가 잡은 구조 단위가 맞는가”를 보는 테스트다.

### Step 3. Figma JSON 구조 분석

각 Figma 페이지에서 아래를 정량화한다.

- text 수
- vector 수
- group 수
- frame 수
- image 관련 node 수
- table/cell에 해당할 수 있는 구조
- hierarchy depth

산출물:

- Figma 페이지별 구조 요약표

### Step 4. 새 변환 결과와 기존 Figma JSON 비교

비교 항목:

- text 보존
- editable 가능성
- table/cell 보존
- group/frame 구조 보존
- image 처리
- vector flatten 정도
- hierarchy 구조

판정:

- 동일
- 향상
- 열화

산출물:

- 비교 리포트

### Step 4.5. 1차 변환 결과 비주얼 테스트

목적:

- 새 parser/converter의 첫 결과를 사람이 직접 보고
- 기존 고급 플러그인 결과와 체감 차이를 확인한다.

테스트 대상:

- `12`
- `19`
- `29`

확인 항목:

- 텍스트가 읽기와 수정에 무리가 없는가
- table이 semantic structure 없이 flatten되지는 않았는가
- group/frame 구조가 지나치게 납작하지 않은가
- image와 주요 shape가 화면상 크게 무너지지 않았는가

산출물:

- 슬라이드별 시각 비교 메모
- 즉시 수정이 필요한 항목 목록

의미:

- 이 단계의 비주얼 테스트는 “초기 변환 방향이 맞는가”를 빠르게 확인하는 테스트다.

### Step 5. 개선 우선순위 도출

출력 형식:

- 재사용 가능한 로직
- 보완 필요한 로직
- 폐기해야 할 로직

우선순위 예시:

- text
- table/cell
- group/frame
- image
- hierarchy

### Step 5.5. Gate 1 직전 통합 비주얼 테스트

목적:

- 구조, 시각, editability 관점을 합쳐서
- 1차 마감 검토에 올릴 수 있는 수준인지 최종 확인한다.

확인 항목:

- `12`: group/connector 흐름이 실무적으로 이해 가능한가
- `19`: table/row/cell 구조가 운영 가능한 수준으로 남는가
- `29`: 복합 구조에서 text/image/group이 함께 유지되는가

산출물:

- Gate 1 제출용 시각 검토 요약
- usable / usable_with_fix / not_usable 초안

## 기획자 검토 포인트

이 단계에서 기획자는 아래를 본다.

- 이 결과로 Figma에서 바로 작업을 이어갈 수 있는가
- 표/셀/영역 구조가 살아 있는가
- 레이어 구조가 이해 가능한가
- 기존 고급 플러그인 결과보다 나빠진 부분이 무엇인가
- 개선 우선순위를 어디에 둘 것인가

## 비주얼 테스트 운영 원칙

비주얼 테스트는 한 번만 하지 않는다.

### 체크포인트 1

시점:

- 상세 추출 직후

목적:

- 구조 단위 확인

### 체크포인트 2

시점:

- 첫 변환 결과 생성 직후

목적:

- 초기 방향 검증

### 체크포인트 3

시점:

- Gate 1 직전

목적:

- 제출 가능 수준 최종 확인

원칙:

- 체크포인트 1은 구조 확인
- 체크포인트 2는 조기 수정
- 체크포인트 3은 최종 검토

즉, “모든 품질 작업 완료 후 마지막에 비주얼 테스트” 방식으로 가지 않는다.

## 1차 판단 기준

좋은 결과:

- `12`, `19`, `29`에서 현재 Figma JSON 대비 동일 이상 품질
- table/group/text 중 최소 2개 이상이 유지 또는 향상
- vector flatten이 과도하지 않음

나쁜 결과:

- 핵심 구조가 대부분 flatten됨
- text 편집 가능성이 낮음
- table/cell 구조를 전혀 살리지 못함

## 다음 단계 연결

이 비교 실험이 끝나면 그 다음에 아래로 넘어간다.

- canonical intermediate model 고도화
- source_mapping 강화
- node 운영 단위 검토
- 지식 구조화 트랙 착수
