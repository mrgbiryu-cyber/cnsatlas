# Benchmark Slide Metadata Template

대상 파일:

- `sampling/pptsample.pptx`

운영 규칙:

- 전체 39슬라이드를 benchmark set v1로 관리한다.
- 마지막 `39`번은 “감사합니다” 슬라이드로 구분한다.
- 현재 PPT -> Figma 비교 실험 우선 대상은 `12`, `19`, `29`다.
- 자동검증과 사람검수는 최소한 위 3개 슬라이드에 대해 별도 결과를 남긴다.

## 기록 컬럼 정의

- `slide_no`
- `title_or_label`
- `difficulty`
- `structure_tags`
- `risk_notes`
- `must_pass`
- `human_review_required`
- `auto_result`
- `human_result`
- `notes`

### 값 가이드

- `difficulty`: `low`, `medium`, `high`
- `structure_tags`: 예) `table`, `cell`, `group`, `section`, `mixed_text`, `image`, `repeat_ui`, `complex_layout`
- `must_pass`: `yes`, `no`
- `human_review_required`: `yes`, `no`
- `auto_result`: `pass`, `warn`, `fail`
- `human_result`: `usable`, `usable_with_fix`, `not_usable`

## 초안 표

| slide_no | title_or_label | difficulty | structure_tags | risk_notes | must_pass | human_review_required | auto_result | human_result | notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 |  |  |  |  | no | no |  |  |  |
| 2 |  |  |  |  | no | no |  |  |  |
| 3 |  |  |  |  | no | no |  |  |  |
| 4 |  |  |  |  | no | no |  |  |  |
| 5 |  |  |  |  | no | no |  |  |  |
| 6 |  |  |  |  | no | no |  |  |  |
| 7 |  |  |  |  | no | no |  |  |  |
| 8 |  |  |  |  | no | no |  |  |  |
| 9 |  |  |  |  | no | no |  |  |  |
| 10 |  |  |  |  | no | no |  |  |  |
| 11 |  |  |  |  | no | no |  |  |  |
| 12 |  |  |  |  | yes | yes |  |  | core benchmark slide |
| 13 |  |  |  |  | no | no |  |  |  |
| 14 |  |  |  |  | no | no |  |  |  |
| 15 |  |  |  |  | no | no |  |  |  |
| 16 |  |  |  |  | no | no |  |  |  |
| 17 |  |  |  |  | no | no |  |  |  |
| 18 |  |  |  |  | no | no |  |  |  |
| 19 |  |  |  |  | yes | yes |  |  | current figma json mapping |
| 20 |  |  |  |  | no | no |  |  |  |
| 21 |  |  |  |  | no | no |  |  |  |
| 22 |  |  |  |  | no | no |  |  |  |
| 23 |  |  |  |  | no | no |  |  |  |
| 24 |  |  |  |  | no | no |  |  |  |
| 25 |  |  |  |  | no | no |  |  |  |
| 26 |  |  |  |  | no | no |  |  |  |
| 27 |  |  |  |  | no | no |  |  |  |
| 28 |  |  |  |  | no | no |  |  |  |
| 29 |  |  |  |  | yes | yes |  |  | core benchmark slide |
| 30 |  |  |  |  | no | no |  |  |  |
| 31 |  |  |  |  | no | no |  |  |  |
| 32 |  |  |  |  | no | no |  |  |  |
| 33 |  |  |  |  | no | no |  |  |  |
| 34 |  |  |  |  | no | no |  |  |  |
| 35 |  |  |  |  | no | no |  |  |  |
| 36 |  |  |  |  | no | no |  |  |  |
| 37 |  |  |  |  | no | no |  |  |  |
| 38 |  |  |  |  | no | no |  |  |  |
| 39 |  |  |  |  | no | no |  |  | thank-you slide |

## 우선 작성 순서

1. 슬라이드 `12`, `19`, `29`부터 메타태깅
2. 각 슬라이드의 `structure_tags`와 `risk_notes`를 먼저 채움
3. 이후 나머지 36슬라이드를 같은 형식으로 확장

## 초기 검토 질문

- 이 슬라이드는 표/셀 구조 보존이 핵심인가
- 이 슬라이드는 그룹/섹션 계층 보존이 핵심인가
- 이 슬라이드는 mixed text나 font 처리가 핵심인가
- 이 슬라이드는 반복 UI나 component 후보 식별이 핵심인가
- 이 슬라이드는 운영 연결 관점에서 node 단위를 어디까지 살려야 하는가
