# PPTX -> Figma Technical Research Notes

이 문서는 PPTX를 Figma로 고해상도로 변환하기 위해 필요한 조사 내용을 구현 관점으로 정리한 저장용 노트다.

목적:
- 이후 구현 시 반복 조사 방지
- OOXML/DrawingML 구조를 `IR -> pattern renderer` 설계로 연결
- 슬라이드별 땜질이 아니라 공통 규칙으로 환원할 수 있는 근거 축적

이 문서는 런타임 스펙 문서가 아니라, 구현 의사결정용 참고 문서다.

## 1. 핵심 전제

- PPTX는 OOXML 기반의 압축 XML 아카이브다.
- Figma는 실시간 scene graph 기반의 노드 트리다.
- 따라서 `PPTX -> 직접 Figma 노드 생성`보다 `PPTX -> IR -> pattern renderer -> Figma`가 맞다.
- 고급 플러그인이 존재하고 더 좋은 결과를 낸다는 것은, 문제는 "불가능"이 아니라 "구현 전략"의 문제라는 뜻이다.

## 2. 좌표계와 단위 변환

### 2.1 EMU -> px

PPTX는 EMU(English Metric Unit)를 사용한다.

- `1 inch = 914,400 EMU`
- 일반적인 Windows 기준:
  - `1 px = 9,525 EMU`

실무적으로는 다음 상수가 기준이다.

- Windows 96 DPI: `9525`
- Mac / point 기반 72 DPI: `12700`

구현 메모:
- IR에는 가능하면 `float px`로 저장
- 원본 EMU도 debug/reference용으로 남겨두면 좋다
- group transform 전/후 좌표를 모두 확인할 수 있게 `source_bounds_emu`, `source_bounds_px`, `visual_bounds_px`를 분리하는 것이 좋다

## 3. 슬라이드 마스터 / 레이아웃 / 플레이스홀더 상속

PPTX의 상속 계층:

1. `slide master`
2. `slide layout`
3. `slide`

속성 해석 원칙:
- slide에 명시된 값이 없으면 layout
- layout에도 없으면 master
- 하위 계층의 구체값이 상위 계층 값을 override

플레이스홀더 핵심 속성:
- `type`
- `idx`
- `orient`
- `sz`

매핑 규칙 메모:
- layout -> master는 주로 `type` 기준
- slide -> layout은 주로 `idx` 기준

특수 플레이스홀더:
- `dt`
- `ftr`
- `sldNum`

구현 메모:
- extractor에서 반드시 `source_scope`를 유지해야 한다
  - `master`
  - `layout`
  - `slide`
- placeholder text는 일반 text와 같은 방식으로 그리지 말고, 상속 해제 후 실제 visible row/box 기준으로 배치해야 한다

## 4. DrawingML Transform

### 4.1 기본 요소

`a:xfrm`에서 확인할 것:
- `off.x`
- `off.y`
- `ext.cx`
- `ext.cy`
- `rot`
- `flipH`
- `flipV`

### 4.2 그룹 변환

group은 내부 좌표계를 가진다.

핵심 필드:
- `chOffX`
- `chOffY`
- `chExtCx`
- `chExtCy`

스케일링 비율:

`ScaleX = ext.cx / chExt.cx`

`ScaleY = ext.cy / chExt.cy`

기본 좌표 변환:

`x_p = off.x + (x_c - chOff.x) * ScaleX`

`y_p = off.y + (y_c - chOff.y) * ScaleY`

### 4.3 아핀 변환 합성

권장 방식:
- 개별 속성으로 중간중간 풀기보다 최종적으로 2x3 또는 3x3 아핀 행렬로 보존

권장 합성 순서:

`M = T(off) * R(theta) * F(flip) * S(scale) * T(-chOff)`

구현 메모:
- PPTX의 회전/반전은 중심점 기준이라는 점을 놓치지 말 것
- nested group에서는 부모 transform을 루트에서 leaf까지 누적해서 절대 좌표를 얻어야 한다
- IR에는 가능하면 `relative_matrix`, `absolute_matrix` 둘 다 남기는 것이 좋다

## 5. DrawingML Table

### 5.1 논리적 그리드

`a:tblGrid / a:gridCol`가 논리적 열 구조를 정의한다.

핵심:
- 모든 수직 경계를 연장해 만든 최소 단위 열이 논리적 열
- 각 열은 `w`로 너비를 갖는다

### 5.2 병합 셀

핵심 속성:
- `gridSpan`
- `rowSpan`
- `hMerge`
- `vMerge`

중요한 구현 포인트:
- semantic table 구조와 visual render를 분리해야 한다
- `gridSpan/rowSpan`은 source semantic 정보로 유지
- 하지만 render는 `table backed lane`, `card background`, `text rows`로 가는 편이 더 나을 수 있다

### 5.3 텍스트 바디

`a:txBody / a:bodyPr`

핵심 속성:
- `lIns`
- `rIns`
- `tIns`
- `bIns`
- `anchor`
- `wrap`

기본 inset 값:
- 좌/상/우 `91,440 EMU`
- 하 `45,720 EMU`

구현 메모:
- 좁은 패널에서 텍스트가 흔들리는 이유는 cell geometry와 visual lane geometry가 다르기 때문인 경우가 많다
- `semantic table cell`과 `visual lane`을 분리해서 생각해야 한다

## 6. Connector / Bent Connector

PPTX는 bend 좌표를 그대로 저장하지 않을 수 있다.

주로 쓰는 요소:
- `p:cxnSp`
- `stCxn`
- `endCxn`
- `prstGeom`
- `avLst`
- `gd`

실무적으로 확인할 것:
- `shape_kind` (`bentConnector2/3/4`)
- `start_connection.idx`
- `end_connection.idx`
- `adjust values`

구현 메모:
- 직접 bend 좌표를 읽기보다
- `shape_kind + connection idx + adjust`로 bend를 복원하는 쪽이 맞다
- connector는 pattern renderer에서 별도 archetype으로 다루는 것이 좋다

## 7. Image / BlipFill

핵심 요소:
- `a:blipFill`
- `a:srcRect`
- `a:stretch`
- `a:tile`
- `a:alphaModFix`

### 7.1 srcRect crop

`srcRect`는 원본 이미지에서 실제 사용할 영역을 비율로 정의한다.

예시:
- `l="15000"` -> 왼쪽 15%
- `t="10000"` -> 위 10%

유효 이미지 크기:

`W' = W * (1 - (l + r) / 100000)`

`H' = H * (1 - (t + b) / 100000)`

### 7.2 alpha / visual effects

주요 효과:
- `alphaModFix`
- `alphaBiLevel`
- `duotone`
- `lum`
- `clrChange`

구현 메모:
- 작은 자산(아이콘, 하트, placeholder X)은 generic rectangle fallback이 아니라 image/vector atom으로 유지하는 편이 좋다
- dense UI에서는 small asset이 누락되면 비어 보이는 문제가 매우 크다

## 8. Text Model

계층:

1. `txBody`
2. `p` (paragraph)
3. `r` (run)

### 8.1 bodyPr

텍스트 박스 수준 제어:
- inset
- vertical align
- wrap
- autofit

### 8.2 paragraph

`a:pPr`에서 볼 것:
- alignment
- bullets
- `marL`
- `marR`
- `indent`
- `lnSpc`

### 8.3 run

`a:r / a:rPr`

핵심 속성:
- `sz`
- `b`
- `i`
- `u`
- color
- kerning
- language

구현 메모:
- native `TEXT`가 가능한 곳은 SVG text보다 우선
- 이유:
  - 검색 가능
  - 편집 가능
  - z-order/clip 디버깅이 쉬움
- 다만 body text 전체를 giant TextNode 1개로 넣으면 흔들리므로, dense panel에서는 `row-group text renderer`가 필요하다

## 9. Figma Layering / Clipping / Text

권장 노드 조합:
- `FRAME`
- `GROUP`
- `TEXT`
- `RECTANGLE`
- `VECTOR`

주의:
- Figma 일반 design node 기준으로 `TableNode`를 전제하지 않는다

### 9.1 Frame vs Group

`FRAME`
- local coordinate system
- `clipsContent`
- constraints / auto layout 가능

`GROUP`
- 단순 그룹화
- clipping 부재
- 자식 좌표는 절대 좌표처럼 다뤄질 수 있음

### 9.2 Native Text vs SVG text

Native `TEXT`
- 검색 가능
- 편집 가능
- font loading 필요

SVG text
- 검색 안 됨
- 편집 안 됨
- 전체가 path/markup에 갇힘

구현 메모:
- dense UI의 핵심 텍스트는 native 우선
- background cluster, 복잡한 non-text decoration만 SVG fallback 고려

## 10. Intermediate Representation (IR)

권장 IR 핵심 필드:

- `id`
- `atom_type`
- `pattern_type`
- `owner_id`
- `parent_id`
- `layer_role`
- `z_index`
- `clip_scope`
- `source_scope`
- `source_bounds_emu`
- `source_bounds_px`
- `visual_bounds_px`
- `relative_matrix`
- `absolute_matrix`
- `render_mode`
- `text_content`
- `text_runs`
- `fills`
- `strokes`
- `effects`
- `asset_ref`
- `debug_tags`

### 10.1 atom_type 예시

- `text_row`
- `background_card`
- `small_asset`
- `table_cell`
- `connector`
- `meta_table`
- `icon`

### 10.2 render_mode 예시

- `native_text`
- `native_shape`
- `vector`
- `svg_block`
- `image_block`
- `lane_text`

## 11. Pattern Renderer

슬라이드별 수정이 아니라 패턴별 renderer가 필요하다.

현재 유효한 패턴:
- `flow-process`
- `table-heavy`
- `dense_ui_panel`

### 11.1 dense_ui_panel

핵심 특성:
- 좁은 폭
- card + text + icon 혼재
- table-backed description
- z-order 민감

권장 렌더 순서:

1. background / base
2. cards
3. text rows / lanes
4. small assets / icons
5. overlay marks / connectors

중요:
- `semantic table != visual render`
- 예:
  - source는 table
  - render는 `lane background + row text + small assets`

## 12. Reference Data의 역할

reference Figma JSON은 런타임 의존 데이터가 아니다.

역할:
- 교사 데이터
- 규칙 추출
- 회귀 테스트

하지 말아야 할 것:
- 매 슬라이드 생성 때 reference와 직접 비교해서 생성

해야 할 것:
- reference에서 패턴/템플릿/계층 특성을 뽑아
- renderer 규칙으로 흡수

## 13. 구현 원칙

- 슬라이드별 땜질 금지
- 공통 규칙으로 설명 가능한 변화만 유지
- 설명이 안 되는 rare case는 fallback 후보로 분리
- visual fidelity와 editability를 둘 다 보되,
  `dense_ui_panel` 같은 어려운 케이스는 부분 fallback 허용

## 14. 현재 프로젝트에 바로 연결되는 해석

### Slide 29 우측 패널

문제는 단순한 위치가 아니라 다음의 조합이다.

- `table-backed text lane`
- `background card`
- `version stack`
- `small assets`
- `z-order`

즉 해결 전략은:
- `row/group text`
- `card background`
- `small asset`
- `owner/layer`
를 분리하는 것

### Slide 12 / 19

- 12: connector / flow archetype
- 19: table-heavy / merged label / simple connector

이 둘은 거의 닫힌 상태로 보고,
새 아키텍처는 주로 `dense_ui_panel` 일반화에 써야 한다.

## 15. 다음 구현 시 체크리스트

- `master/layout/slide` 상속 해제가 실제로 되었는가
- `xfrm`이 group 포함 absolute matrix로 풀렸는가
- semantic table과 visual lane이 분리되었는가
- top lane text는 native `TEXT`인가
- small asset이 generic box로 죽지 않았는가
- z-order가 pattern renderer 순서를 따르는가
- reference는 규칙 추출/회귀 테스트 용도로만 쓰는가

---

이 문서는 구현 중 계속 업데이트한다.
