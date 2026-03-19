# Visual Replay 테스트 상태

## 목적

이 문서는 `PPT -> Figma` visual replay 모듈의 현재 테스트 결과를 고정하는 상태 문서다.

기준:

- visual 기준은 `read-first`
- semantic / DB 적재는 후속 단계
- 현재 문서는 `고급 플러그인 결과 대비 visual replay 품질`만 다룬다

## 현재 기준 버전

- visual replay core:
  - `5e4a1f1` `Improve replay transform handling for v4`
- clip overlay 처리:
  - `0e1a2e2` `Skip full-page clip overlay vectors in replay`
  - `5c35215` `Add clip overlay debug logging`
  - `a3a03db` `Propagate clip-like state through replay tree`
  - `09ed066` `Use page bounds for clip overlay detection`

최종 확인 입력:

- `docs/figma-page-1.bundle.json`
- `docs/figma-page-2.bundle.json`
- `docs/figma-page-3.bundle.json`

최종 확인 산출물:

- `sampling/test7/actual-manifest-1_1440.json`
- `docs/page-3.test7.diff.v2.json`

## 테스트 결론

현재 visual replay 모듈은 `1차 visual 검증 완료` 상태로 본다.

핵심 판단:

1. `Page 1`, `Page 2`는 visual 관점에서 큰 병목이던 뒤집힘/화살표 축이 정리되었다.
2. `Page 3`의 검은 full-page overlay 문제는 해결되었다.
3. 비교 모듈 기준으로도 `flip mismatch`가 제거되어, 현재 남는 수치는 주로 flatten 구조 차이에 가깝다.

즉, 현재 상태는

- visual replay 모듈: 계속 진행 가능한 상태
- semantic / node 모듈: 다음 단계로 이어갈 수 있는 상태

로 기록한다.

## 페이지별 상태

### Page 1

상태:

- `PASS`

정리된 항목:

- 뒤집힘 해소
- 화살표/벡터 방향 축 정리
- comparison 기준 `flip_mismatch = 0`

비고:

- 구조 비교상 `GROUP/FRAME flatten` 차이는 남아 있을 수 있으나, visual 병목으로는 보지 않는다.

### Page 2

상태:

- `PASS`

정리된 항목:

- 뒤집힘 해소
- 화살표/벡터 방향 축 정리
- comparison 기준 `flip_mismatch = 0`

비고:

- 구조 비교상 flatten 차이는 후속 semantic 단계에서 본다.

### Page 3

상태:

- `PASS`

정리된 항목:

- 뒤집힘 해소
- 검은 full-page overlay 제거
- comparison 기준 `flip_mismatch = 0`

확정된 overlay 제거 대상:

- `reference_node_id: 1:1948`
- `reference_parent_id: 1:1949`
- reason: `skip_full_page_clip_overlay_vector`

확인 로그:

- `sampling/test7/actual-manifest-1_1440.json`
- `summary.skipped_node_count = 1`
- `debug.skipped_nodes[0].reference_node_id = 1:1948`

## 현재 comparison 결과 해석

`docs/page-3.test7.diff.v2.json` 기준:

- `matched_nodes: 415`
- `missing_nodes: 98`
- `extra_nodes: 0`
- `flip_mismatches: 0`
- `rotation_mismatches: 0`
- `bbox_critical_mismatches: 2`
- `parent_mismatches: 0`

해석:

- `flip_mismatches = 0`은 visual replay의 핵심 병목이 해소되었음을 의미한다.
- 남아 있는 `missing_nodes`는 현재 direct replay가 `GROUP/FRAME`을 flatten해서 렌더하는 구조 차이의 영향이 크다.
- 즉 현재 단계에서 `missing_nodes`를 visual 실패로 해석하지 않는다.

## 현재 확정된 원칙

1. visual replay의 핵심 판정은 `visual readability`와 `transform correctness`로 본다.
2. `GROUP/FRAME flatten` 때문에 생기는 구조 diff는 현재 단계의 실패 기준으로 쓰지 않는다.
3. `clip/mask`는 전역 skip이 아니라, 문제 패턴을 좁혀서 제거한다.
4. visual 모듈이 기준을 넘은 뒤 semantic / node 저장 단계로 넘어간다.

## 다음 단계

### 1. visual 모듈

- 현재 버전을 visual 기준선으로 유지
- 추가 visual 이슈가 새로 발견되면 `comparison + debug log`로 원인을 먼저 특정

### 2. semantic / node 모듈

- visual 기준 통과를 전제로 node/DB 단계 재개
- `document/page/node/asset/source_mapping` 적재 흐름으로 연결

### 3. comparison 모듈

- visual replay 회귀 테스트용으로 유지
- 이후 새 페이지/새 PPT가 들어오면 동일 기준으로 재사용

## 현재 상태 한 줄 요약

`Visual replay 모듈은 Page 1 / 2 / 3 기준으로 1차 visual 검증을 통과했고, clip overlay 문제까지 해결된 상태다. 이제 이 기준선을 바탕으로 semantic / node 단계로 넘어갈 수 있다.`
