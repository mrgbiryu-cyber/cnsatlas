# CNS Atlas AX 전환 프로젝트 보고서

## 1. 프로젝트 개요

이 프로젝트의 목적은 기존 PPT 기반 기획 산출물을 Figma로 고품질 전환하고, 전환된 결과를 구조화된 데이터로 적재해 정책 탐색과 질의응답까지 가능한 운영 기반을 만드는 것입니다.

즉, 단순 변환 도구를 만드는 것이 아니라 다음 흐름을 시스템화하는 것이 핵심입니다.

- PPT 기획서의 Figma 전환
- Figma 기반 기획 운영
- 전환 결과의 node 구조화
- 정책 찾기, 검색, 질의응답 연결

## 2. 왜 필요한가

현재 기획 업무는 산출물이 여러 도구에 분산되어 있어 운영 효율이 낮습니다.

- 기획 원본은 PPT에 남아 있음
- 실제 수정은 Figma에서 이어짐
- 정책, 설명, 담당 정보는 별도 문서에 흩어져 있음
- 특정 화면이나 영역의 의도와 담당자를 찾는 데 시간이 많이 듦

이 구조에서는 문서가 많아질수록 아래 문제가 커집니다.

- 최신본 혼선
- 정책 누락
- 담당자 확인 지연
- 검수 및 인수인계 비용 증가

## 3. 해결하려는 문제

이 프로젝트는 아래 두 문제를 함께 해결하려고 합니다.

### 3-1. 산출물 전환 문제

기존 PPT 기획서를 Figma로 옮겼을 때, 단순히 “비슷하게 보이는 화면”이 아니라 실제로 이어서 작업 가능한 수준으로 전환해야 합니다.

핵심 기준:

- 텍스트가 읽히고 수정 가능할 것
- 표, 박스, 흐름 구조가 무너지지 않을 것
- PPT 사용자가 Figma에서 바로 이해할 수 있을 것

### 3-2. 운영 데이터화 문제

전환 결과는 단순 디자인 산출물로 끝나면 안 됩니다. 이후 정책 찾기, 담당자 연결, 검색, 질의응답이 가능하도록 `page / node / cell` 단위로 구조화되어야 합니다.

## 4. 목표 상태

최종적으로는 아래와 같은 운영 상태를 목표로 합니다.

- PPT를 Figma로 고품질 전환
- 전환 결과를 node 단위로 구조화
- 문서, 페이지, 영역 기준 정책 연결
- 담당자 및 설명 정보 연결
- 검색과 질의응답으로 관련 근거 탐색 가능

즉, 기획 산출물을 “파일”이 아니라 “운영 가능한 자산”으로 바꾸는 것이 목표입니다.

## 5. 현재 추진 방향

현재 단계의 최우선 목표는 `PPT -> Figma 고품질 전환`입니다.

이 단계의 품질 기준은 `edit-first`가 아니라 `read-first`입니다.

즉, 우선순위는 다음과 같습니다.

1. 보이는 결과가 원본과 유사하게 해석되는가
2. 텍스트, 표, 박스, 화살표 관계가 명확하게 읽히는가
3. 최소한의 수정은 가능한가

현재는 에셋화나 컴포넌트 치환보다, PPT 사용자가 Figma 결과를 보고 바로 이해할 수 있는 수준까지 품질을 올리는 것이 우선입니다.

## 6. 현재 진행 현황

현재까지 아래 작업을 진행했습니다.

- benchmark PPT 샘플 선정
- 핵심 슬라이드 구조 분석
- PPT 요소를 text / group / table / cell / image / connector 단위로 분해
- Figma 비주얼 테스트용 플러그인 제작
- 실제 Figma 전환 결과를 보며 반복 검증 진행

현재 판단은 다음과 같습니다.

- 1page, 2page는 화살표와 일부 정합성만 보완되면 실사용 근처까지 접근
- 3page는 별도 품질 개선이 필요한 상태

## 7. 다음 단계

다음 단계는 아래 순서로 진행하는 것이 맞습니다.

### 7-1. Figma 변환 품질 마무리

우선 1page, 2page를 기준으로 아래를 안정화합니다.

- 화살표 방향, 연결, 위치
- 텍스트 줄바꿈
- 표 가독성
- 박스와 그룹 배치

### 7-2. 3page 품질 개선

복합 UI 구조가 섞인 페이지를 별도 트랙으로 개선합니다.

### 7-3. node 구조 DB 적재

Figma 품질이 기준에 도달하면, 전환 결과를 node 구조로 DB에 적재합니다.

### 7-4. 정책 탐색 / 질의응답 연결

적재된 데이터를 바탕으로 정책 찾기, 검색, 질의응답 기능으로 확장합니다.

## 8. 기대 효과

이 프로젝트가 완료되면 기대할 수 있는 효과는 아래와 같습니다.

- PPT 기반 산출물의 Figma 전환 효율 확보
- 기획 산출물의 재사용성 향상
- 정책 및 담당 정보 탐색 시간 단축
- 문서 기반 업무를 구조화된 운영 자산으로 전환
- 향후 검색 및 질의응답 기반 운영 가능

## 9. 이미지 후보

아래 이미지는 노션 보고서에 같이 넣으면 이해도가 올라갑니다.

### 이미지 후보 A. 현재 문제 상황

의미:

- PPT, Figma, 정책 문서, 메신저, 엑셀 등이 흩어져 있는 현재 상태

추천 용도:

- “왜 이 프로젝트가 필요한가” 섹션

형태:

- 분산된 문서와 도구를 보여주는 개념 이미지

### 이미지 후보 B. PPT -> Figma 전환 예시

의미:

- 원본 PPT와 전환된 Figma를 나란히 보여주는 비교 이미지

추천 용도:

- “해결하려는 문제” 또는 “현재 추진 방향” 섹션

형태:

- 실제 캡처 우선
- 가능하면 같은 화면의 Before / After

### 이미지 후보 C. 구조화 개념도

의미:

- 화면이 document / page / node / cell 단위로 분해되는 모습

추천 용도:

- “운영 데이터화 문제” 또는 “목표 상태” 섹션

형태:

- 간단한 다이어그램
- 화면 -> 노드 -> DB 흐름

### 이미지 후보 D. 미래 운영 포털 이미지

의미:

- 하나의 포털 안에서 문서, 정책, 담당자, 검색, 질의응답이 연결되는 미래 상태

추천 용도:

- “목표 상태” 섹션

형태:

- AI 생성 이미지 또는 UI 목업

### 이미지 후보 E. 기대 효과 / KPI 이미지

의미:

- 탐색 시간 단축, 재사용률 향상, 운영 효율 증가를 시각적으로 보여주는 이미지

추천 용도:

- “기대 효과” 섹션

형태:

- 카드형 KPI 이미지
- 간단한 인포그래픽

## 10. AI 이미지 생성 프롬프트 예시

실제 캡처가 없는 섹션에는 아래와 같은 프롬프트를 활용할 수 있습니다.

### 프롬프트 A. 현재 문제 상황

```text
A clean enterprise illustration showing fragmented planning workflow, PowerPoint files, Figma screens, policy documents, spreadsheets, chat messages, and version confusion across teams, modern corporate style, white background, blue and gray accents, executive presentation quality
```

### 프롬프트 B. 미래 운영 포털

```text
A modern enterprise planning operations portal showing document tree, Figma preview, linked policy documents, ownership panel, search results, and Q&A assistant in one dashboard, realistic SaaS interface, clean white background, blue and teal accents
```

### 프롬프트 C. 구조화 개념도

```text
A system diagram showing a planning screen decomposed into document, page, node, table, row, and cell structure flowing into a database and search system, clean architecture visualization, executive-friendly style
```

### 프롬프트 D. 기대 효과

```text
A premium business infographic showing planning productivity improvement, faster document search, connected knowledge, lower review time, and reusable planning assets, clean corporate style, white background, blue accent
```

## 11. 보고용 핵심 문장

### 프로젝트 정의

본 프로젝트는 기존 PPT 기반 기획 산출물을 Figma 중심 운영 체계로 전환하고, 전환 결과를 구조화된 데이터로 적재해 정책 탐색과 질의응답까지 가능한 기획 운영 기반을 만드는 것을 목표로 합니다.

### 현재 단계

현재는 PPT -> Figma 고품질 전환 품질을 우선 검증하고 있으며, 기존 PPT 사용자가 Figma 결과를 보고 바로 이해하고 작업할 수 있는 수준까지 품질을 끌어올리는 단계입니다.

### 기대 효과

이 프로젝트를 통해 기획 산출물은 단순 문서가 아니라 정책, 담당, 설명, 검색이 연결된 운영 자산으로 전환되며, 문서 탐색 시간과 운영 비용을 줄일 수 있습니다.
