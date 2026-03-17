# 실행 Backlog 초안

## 원칙

프로젝트는 아래 3개의 검증 마감을 기준으로 진행한다.

1. 1차 마감: PPT -> Figma 변환 품질 검증
2. 2차 마감: DB/데이터 변환 및 검색 검증
3. 3차 마감: 웹 UI 초기 테스트

각 마감 전에는 개발 산출물과 기획자 검증 항목이 모두 준비되어야 한다.

## 1차 마감 Backlog

목표:

- 39슬라이드 benchmark 세트로 PPT -> Figma 변환 품질을 검증 가능하게 만든다.

### A. 입력 기준 고정

- benchmark PPT 파일 경로 확정
- 공식 benchmark 파일: `sampling/pptsample.pptx`
- 39슬라이드 목록 확정
- 슬라이드별 식별자 부여
- 슬라이드별 난이도 태깅
- 슬라이드별 핵심 구조 태깅
- 필수 통과 슬라이드 선정
- 경고 허용 슬라이드 선정
- 현재 대응 확인 완료 슬라이드 고정: `12`, `19`, `29`

현재 결정:

- `sampling/pptsample.pptx`를 benchmark set v1로 사용한다.
- 전체 39슬라이드를 검증 대상으로 사용한다.
- 마지막 `39`번은 “감사합니다” 슬라이드다.
- 현재 Figma JSON 대응 확인이 된 슬라이드는 `12`, `19`, `29`다.
- 1차 실행은 우선 `12`, `19`, `29`의 PPT -> Figma 변환 비교 실험부터 진행한다.

기획자 개입:

- 필수 통과 슬라이드 승인
- 난이도/대표성 확인

### B. 변환 엔진 조사 및 설계

- `pptx-to-design` 심층 분석
- text 처리 구조 정리
- table/cell 처리 구조 정리
- group/frame 처리 구조 정리
- chart/image 처리 수준 정리
- 재사용/폐기/보완안 확정

기획자 개입:

- 변환 품질 우선순위 승인

### B-1. 현재 Figma JSON 대응표 확정

- `sampling/figma-current-page.json` 구조 확인
- Figma `Page 1`, `Page 2`, `Page 3`와 PPT 슬라이드 대응 확정
- 현재 대응 슬라이드 `12`, `19`, `29`를 비교 실험 기준으로 사용

기획자 개입:

- 대응 관계 승인

### C. PPT parser 초안

- PPTX unzip/read flow 설계
- presentation/rels/theme/slide 파싱
- slide element 추출
- text / shape / image / table / group 분류
- parser output schema 정의
- source path 수집

우선 범위:

- 전체 문서용 범용 parser가 아니라
- 슬라이드 `12`, `19`, `29`를 먼저 처리하는 상세 추출기부터 구현

### C-1. 구조 확인용 중간 비주얼 테스트

- slide `12`, `19`, `29`의 상세 추출 결과 미리보기
- text/group/table/image 분해 상태 확인
- 과소/과다 분해 이슈 기록

기획자 개입:

- node 단위가 기획 운영에 맞는지 1차 확인

### D. canonical intermediate model v1

- `document/page/node/asset/source_mapping` 정의
- node subtype v1 정의
- section/group/frame/table/row/cell 표현 규칙 정의
- stable identity 초안 정의

기획자 개입:

- node 운영 단위 승인

### E. Figma node generation v1

- frame-first 정책 정리
- group 예외 사용 규칙 정리
- text node 생성 규칙 정리
- table/cell 생성 규칙 정리
- asset 생성 규칙 정리
- page/frame naming 규칙 정리

기획자 개입:

- Figma 결과물 사용성 기준 승인

### E-1. PPT -> Figma 비교 실험

- 슬라이드 `12`, `19`, `29`를 새 parser/converter로 변환
- 기존 `sampling/figma-current-page.json`과 비교
- text / table / group / image / hierarchy 기준으로 동일/향상/열화 판정

산출물:

- 비교 실험 리포트
- 재사용/보완/폐기 포인트

### E-2. 1차 변환 결과 비주얼 테스트

- 새 변환 결과와 기존 Figma JSON 시각 비교
- text readability 확인
- table flatten 여부 확인
- group/frame 납작화 여부 확인
- image 배치 확인

기획자 개입:

- 초기 변환 방향이 맞는지 1차 판정

### F. 자동검증 v1

- page 매칭률 계산
- editable text 비율 계산
- table/cell 보존 여부 판정
- hierarchy 보존 여부 판정
- source_mapping 생성률 계산
- auto pass / warn / fail 초안

기획자 개입:

- 자동검증 합격선 승인

### G. 사람검수 v1

- 검수 질문 3~5개 확정
- `usable / usable_with_fix / not_usable` 확정
- 검수 기록 포맷 확정

기획자 개입:

- 사람검수 기준 승인

### H. 1차 마감 검증

- 39슬라이드 benchmark 기준 유지
- 1차 우선 실행은 슬라이드 `12`, `19`, `29` 대상으로 진행
- 자동검증 리포트 생성
- Figma 결과 샘플 준비
- 사람검수 수행
- 실패 패턴 정리
- Gate 1 직전 통합 비주얼 테스트 수행

기획자 개입:

- Gate 1 승인

## 2차 마감 Backlog

목표:

- 변환 결과를 DB와 canonical model에 저장하고, 정책/담당/설명 연결 및 검색 검증을 가능하게 만든다.

### A. canonical model v2 확정

- `document/page/node/asset` 확정
- `knowledge_document` 정의
- `annotation` 정의
- `ownership` 정의
- `relation` 정의
- `source_mapping` 정의

기획자 개입:

- 운영 단위와 연결 단위 승인

### B. DB 스키마 v1

- 핵심 테이블 정의
- 관계 정의
- 인덱스 초안 정의
- source lineage 저장 구조 정의
- field-level authoritative source 저장 구조 정의

### C. 데이터 적재 파이프라인

- parser output -> canonical transform
- canonical -> DB persistence
- source_mapping persistence
- migration job 기록

### D. 지식/책임 연결

- 정책 문서 입력 구조
- annotation 입력 구조
- ownership 입력 구조
- document/page/node 대상 연결 규칙

기획자 개입:

- 정책/담당 연결 최소 단위 승인

### E. 검색 인덱스 v1

- searchable projection 정의
- document/page/node 인덱싱
- knowledge_document 인덱싱
- annotation 인덱싱
- ownership projection 인덱싱

### F. 검색 테스트 시나리오

- “이 영역은 누가 담당인가?”
- “이 셀의 기획 의도는 어디에 적혀 있나?”
- “이 화면과 연결된 정책 문서는 무엇인가?”
- “이 Figma 파트의 원본 PPT는 어디인가?”

기획자 개입:

- 실제 업무 질문 세트 승인

### G. 2차 마감 검증

- DB 적재 확인
- source mapping 추적 확인
- 검색 시나리오 실행
- 결과 문맥 표시 확인
- 검색 리포트 정리

기획자 개입:

- Gate 2 승인

## 3차 마감 Backlog

목표:

- 내부 포털 형태로 문서 탐색, 정책 확인, 담당 확인, 이력 확인이 가능한 최소 운영 UI를 만든다.

### A. 포털 정보 구조

- 메뉴 구조 확정
- 문서 목록 정보 구조 확정
- 문서 상세 정보 구조 확정
- 페이지/노드 상세 정보 구조 확정
- 정책/담당/이력/sync 정보 배치 확정

기획자 개입:

- 메뉴 구조 승인

### B. read model v1

- 문서 목록 read model
- 문서 상세 read model
- 페이지 상세 read model
- 노드 상세 read model
- 검색 결과 read model

### C. UI 구현 v1

- 문서 목록 화면
- 문서 상세 화면
- 페이지 상세 화면
- 노드/영역 상세 화면
- 정책 연결 보기
- 담당자 보기
- 검색 화면
- 기본 sync 상태 보기

### D. 초기 사용성 테스트

- 문서 탐색 시나리오
- 특정 페이지 접근 시나리오
- 특정 노드 정책 확인 시나리오
- 담당자 탐색 시나리오
- 검색 시나리오

기획자 개입:

- 실제 사용 흐름 검토

### E. 3차 마감 검증

- 내부 포털 사용성 점검
- 정보 누락 여부 점검
- 탐색 흐름 점검
- 개선 요구사항 정리

기획자 개입:

- Gate 3 승인

## 즉시 시작 작업

실행 시작 순서:

1. `sampling/figma-current-page.json`와 PPT `12`, `19`, `29` 대응표 확정
2. 슬라이드 `12`, `19`, `29` 상세 추출기 구현
3. `pptx-to-design` 심층 분석
4. Figma text/node 제약 정리
5. PPT -> Figma 비교 실험 수행
6. canonical intermediate model v1 초안

## 실행 전 마지막 확인

아래 5개만 확정되면 바로 개발 착수 가능하다.

- benchmark 38슬라이드가 공식 품질 기준 세트인지
- 필수 통과 슬라이드가 무엇인지
- node를 어디까지 운영 단위로 볼지
- 사람검수 기준을 `usable / usable_with_fix / not_usable`로 고정할지
- 1차 마감을 변환 품질 검증으로 확정할지

현재 확정된 항목:

- benchmark 세트: `sampling/pptsample.pptx`
- 총 슬라이드 수: `39`
- 현재 비교 실험 대상 슬라이드: `12`, `19`, `29`
