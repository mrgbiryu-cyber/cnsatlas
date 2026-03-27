# Dense UI Panel Design V1

이 문서는 `dense_ui_panel` 패턴을 구현하기 전에, 현재까지의 실패/성공 신호와 reference JSON을 기준으로
공통 설계 항목을 먼저 고정하기 위한 문서다.

목표:
- slide 29 전용 튜닝을 멈춘다
- `resolved atoms -> visual chunks -> chunk-specific renderer -> frame composition` 순서를 고정한다
- 구현 전에 `chunk classification`, `render strategy`, `text composition`을 먼저 결정한다

## 1. 현재까지의 핵심 판단

### 1.1 유지할 것

- `master -> layout -> slide` 상속 해제
- `grpSp / xfrm`의 절대좌표 복원
- `semantic table != visual render`
- `Frame-first + clipsContent`
- `chunk-first`
- dense body 안의 텍스트는 `leaf-heavy`

### 1.2 버릴 것

- slide 29 전용 숫자 보정
- `owner/group`을 그대로 렌더 단위로 쓰는 방식
- `description_body`를 giant text group 하나로 만드는 방식
- baseline 위에 임의로 additive/replacement hybrid를 반복하는 방식
- panel-only 미세 조정 결과를 최종 품질로 착각하는 방식

### 1.3 reference JSON이 보여준 것

- 우측 패널 전체가 큰 그룹 하나로 닫혀 있지 않다
- `Frame` 아래에 `TEXT` leaf가 많이 직접 깔린다
- 필요한 곳만 `Group + Vector`가 쓰인다
- 즉 정답 방향은:
  - `chunk-first`
  - `chunk 내부는 leaf-text-heavy`
  - `Frame-first composition`

## 2. Chunk Classification Features

`dense_ui_panel` 분류는 이름 기반이 아니라 입력 피처 기반이어야 한다.

### 2.1 공통 입력 피처

- `x/y/w/h`
- `absolute_matrix`
- `parent_id`
- `owner_id`
- `atom_type`
- `layer_role`
- `text_char_count`
- `shape_fill_count`
- `stroke_count`
- `has_table_backing`
- `shared_transform_ancestry`
- `local_density`
- `is_narrow_panel_region`
- `repeated_colored_band_pattern`

### 2.2 visual chunk 분류 후보

- `header_band`
  - 상단 가로 밴드
  - 너비가 크고 높이가 낮다
  - 텍스트 수가 적고 선/사각형 비율이 높다

- `meta_grid`
  - 표처럼 보이는 정보 셀 블록
  - cell 분할이 있고 행/열 경계가 명확하다

- `stacked_badges`
  - 세로로 반복되는 색 카드/배지
  - 좁은 폭, 반복 fill, 일정 간격

- `body_text_region`
  - 본문 설명 덩어리
  - text density가 가장 높다
  - semantic source는 table일 수 있지만 visual은 카드+텍스트 lane이다

- `issue_card`
  - 짧은 강조 카드
  - 배경색 강함, 텍스트 수 적음

- `panel_local_assets`
  - 우측 패널 내부 아이콘/표식/작은 배지
  - panel bounds 안에 머문다

- `global_ui_assets`
  - 슬라이드 전역의 작은 UI 자산
  - 우측 패널 소속이 아니다

## 3. Chunk-specific Render Strategy

모든 chunk를 같은 방식으로 렌더하면 안 된다.

| chunk | 권장 전략 | 이유 |
|---|---|---|
| `header_band` | `frame + text leaf + line/rect native` | 구조가 단순하고 편집성이 중요 |
| `meta_grid` | `frame/grid + text leaf` | 표 구조를 유지하되 giant SVG는 피함 |
| `stacked_badges` | `group/vector-heavy + text leaf` | 배경 도형 반복성이 강함 |
| `issue_card` | `frame/vector background + text leaf` | 강조 카드라 색/알파 보존 중요 |
| `body_text_region` | `chunk container + leaf text composition` | giant text group 금지 |
| `panel_local_assets` | `atom absolute placement` | 위치 정합성이 중요 |
| `global_ui_assets` | 패널 renderer에서 제외 | 패널 local composition과 섞이면 깨짐 |

### 3.1 body_text_region 세부 원칙

- giant `description_text_group` 금지
- `paragraph` 또는 `line` 단위 `TEXT` leaf 사용
- 배경 카드는 chunk 배경으로 두되 텍스트는 별도 leaf로 둔다
- semantic table cell은 source truth로만 쓰고 render는 `lane/background/text`로 분리한다

### 3.2 stacked_badges 세부 원칙

- 카드 배경은 `Vector/Rectangle` 중심
- 텍스트는 가능한 `TEXT` leaf
- 카드 자체를 지나치게 atomize하지 않는다

## 4. Text Composition Granularity

텍스트는 일괄 규칙이 아니라 영역별 단위를 다르게 써야 한다.

### 4.1 기본 규칙

- 일반 박스 텍스트: `single TextNode`
- dense panel 본문: `paragraph/line leaf`
- run 스타일 차이가 중요한 텍스트: `paragraph -> run`

### 4.2 dense panel 권장 단위

- `header_band`: line 또는 single text
- `meta_grid`: cell text leaf
- `body_text_region`: paragraph/line leaf
- `stacked_badges`: badge label line

### 4.3 금지 규칙

- dense panel 전체 본문을 giant `TextNode 1개`로 넣기
- giant `SVG text block`으로 넣기
- semantic row 높이를 그대로 visual line 높이로 사용하기

## 5. Composition Policy

`Replacement / Overlay / Preserve / Fallback`는 chunk 단위로 판단한다.

### 5.1 preserve

- reference/baseline이 이미 시각적으로 가장 강한 dense style layer를 가지고 있을 때
- 예: 복잡한 배경 벡터/장식이 한 번에 안정적으로 보이는 경우

### 5.2 overlay

- 배경은 유지하되 editable text 또는 작은 자산만 보강할 때
- text search/editability가 중요할 때

### 5.3 replacement

- chunk 전체가 native 구조로 충분히 재현 가능할 때
- giant dense style layer를 오히려 제거해야 할 때

### 5.4 fallback

- SmartArt, chart, video, 복잡한 dense decoration 등
- native/overlay로 갈수록 fidelity가 급격히 무너질 때

## 6. Style Source Priority

스타일은 아래 우선순위로 최종값을 정한다.

1. source shape style
2. source table/cell style
3. slide-level resolved style
4. layout/master resolved style
5. fallback default

주의:
- `cell_style fill fallback`만으로 회색 기본 박스가 남지 않게 해야 한다
- dense panel에서는 fill/alpha가 실제 시각 chunk 존재감을 크게 좌우한다

## 7. Asset Scope Rule

`small_assets`는 반드시 둘로 나눈다.

- `panel_local_assets`
  - 패널 bounds 내부
  - panel composition의 일부

- `global_ui_assets`
  - 슬라이드 전역 UI
  - 패널 renderer 밖에서 처리

## 8. Evaluation Checklist

구현 전에/후에 항상 확인할 것:

- `chunk`가 실제 visual unit처럼 보이는가
- `body_text_region`이 giant group이 아닌가
- `global_ui_assets`가 panel에 섞이지 않았는가
- `style_source`가 회색 fallback으로 무너지지 않았는가
- `replacement/overlay/preserve/fallback` 판단이 chunk 단위로 일관적인가
- `Frame + clipsContent + native Text` 원칙을 어기지 않았는가

## 9. 다음 구현 순서

1. `visual chunk classifier v1`
2. `chunk -> render strategy matrix` 코드화
3. `body_text_region` 전용 renderer
4. `stacked_badges` 전용 renderer
5. full-slide 기준 비교

이 문서는 구현 전에 먼저 업데이트하고, slide 29는 검증 샘플로만 사용한다.
