# Slide 29 Static Compare Report

기준 파일:
- Reference: `sampling/test8/static.json`
- PPT IR: `docs/resolved-ppt-ir-12-19-29.json`
- Bundle: `docs/block-bundles/ir-dense-ui-panel-29-left-product-price-only.bundle.json`

## 핵심 결론

`static.json`은 우리가 화면에서 보고 있던 하단 가격영역 전체가 아니다.

reference `static.json`의 실제 범위는:
- `구매하기` 블록 1개
- 내부 자식 순서: `VECTOR x4 -> TEXT x1`

즉 reference 기준으로는 현재 우리 bundle의 `page_left_cluster:22:subgroup:01`에 더 가깝고,
`page_left_cluster:22:subgroup:02`의 가격 요약 블록은 이 reference 범위에 포함되지 않는다.

## 1. Reference 구조

`sampling/test8/static.json`

- root: `GROUP`
- children:
  1. `VECTOR`
  2. `VECTOR`
  3. `VECTOR`
  4. `VECTOR`
  5. `TEXT("구매하기")`

관찰:
- 명시적 `z-index` 필드는 없음
- `children` 순서가 사실상 paint order 역할을 함
- 이 그룹은 단일 `purchase block`이다

## 2. PPT Source 대응

같은 영역에 해당하는 PPT source는 다음이 가장 직접적이다.

- `s29:slide_29/element_99/child_3`
  - `background_card`
  - `z_index=10`
  - `source_order_path=[99,3]`
  - 텍스트: `구매하기`
- `s29:slide_29/element_99/child_4`
  - `group`
  - `z_index=20`
  - `source_order_path=[99,4]`
- `s29:slide_29/element_99/child_4/child_1`
  - `text`
  - `회원할인가`
- `s29:slide_29/element_99/child_4/child_2`
  - `text`
  - `9,900,000원`
- `s29:slide_29/element_99/child_2`
  - `small_asset`
  - `Like`
- `s29:slide_29/element_99/child_4/child_3`
  - `small_asset`
  - `?`

관찰:
- PPT source는 reference보다 더 많은 자식을 가진다
- 즉 reference `static.json`이 선택한 범위와 PPT 원문 범위가 완전히 같지 않다
- 현재 범위만 보면 `구매하기 배경 + 하트 + 라벨`이 핵심이고,
  `회원할인가/9,900,000원/?`는 reference 선택 범위 밖일 가능성이 높다

## 3. Current Bundle 구조

현재 bundle에서 대응 그룹:

- `page_left_cluster:22`
  - `subgroup:01`
    - `element_99/child_1` `SVG_BLOCK`
    - `element_99/child_3` `SVG_BLOCK`
    - `element_99/child_3:label` `TEXT("구매하기")`
    - `element_99/child_4/child_1` `TEXT("회원할인가")`
    - `element_99/child_4/child_2` `TEXT("9,900,000원")`
  - `subgroup:02`
    - `element_11` `SVG_BLOCK`
    - `element_5` `TEXT("9,400,000원")`
    - `element_6/child_1` `TEXT("최대할인가")`
    - `element_7` `TEXT("9,900,000원")`
    - `element_8` `TEXT("10,969,600원")`
    - `element_9/child_1` `TEXT("회원할인가")`
    - `element_6/child_2` `SVG_BLOCK(Info)`
    - `element_9/child_2` `SVG_BLOCK(Info)`
    - `element_10` `TEXT("10%")`

관찰:
- 우리 bundle은 `purchase block`과 `price summary block`을 둘 다 같은 큰 클러스터 아래에 유지한다
- 하지만 reference `static.json`은 `purchase block`만 잡고 있다

## 4. 실제 차이

reference와의 직접 차이는 다음이다.

1. Reference는 단일 그룹이다
- `VECTOR x4 + TEXT("구매하기")`

2. 우리 bundle은 범위가 더 넓다
- `회원할인가`
- `9,900,000원`
- `?`
가 같은 하위 그룹 안에 포함된다

3. 즉 현재의 핵심 문제는 단순 `z-order`만이 아니다
- reference 선택 범위와
- 우리 bundle의 그룹 범위 자체가 다르다

## 5. 다음 판단 기준

이 보고서 기준으로 다음 질문은 둘 중 하나다.

1. `static`은 reference 기준으로 `purchase block only`로 잘라야 하는가
2. 아니면 `purchase block`과 `price summary block`을 각각 별도 reference 그룹으로 다시 받아야 하는가

현재 증거상 더 타당한 해석:
- `static.json`은 `purchase block only`
- 하단 가격 요약은 다른 reference 그룹으로 따로 봐야 한다
