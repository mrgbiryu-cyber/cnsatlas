# Figma Visual Replay Input Audit

## 목적

현재 단계의 목적은 `node 저장`이 아니라, 고급 플러그인 결과를 기준으로 `visual replay` 모듈을 만드는 것이다.

이 문서는 현재 저장소에 들어온 Figma 산출물이 비주얼 리플레이 구현에 충분한지, 무엇을 바로 쓸 수 있는지, 무엇이 아직 부족한지 정리한다.

## 현재 확보된 입력

### 전체 파일
- `figma-full-file.json`

### 페이지별 JSON
- `figma-page-1.json`
- `figma-page-2.json`
- `figma-page-3.json`

### 페이지별 기준 이미지
- `figma-page-1.png`
- `figma-page-2.png`
- `figma-page-3.png`

### 이미지 자산
- `assets/*.png` 총 10개

### 묶음 파일
- `figma-export.zip`

## 바로 구현에 쓸 수 있는 것

### 1. Frame / Group / 위치 구조
페이지별 JSON에는 `FRAME`, `GROUP`, `VECTOR`, `TEXT`, `RECTANGLE` 구조가 들어 있다.

활용 가능:
- 페이지 구조 재생
- 그룹 계층 유지
- `absoluteBoundingBox`, `relativeTransform` 기반 위치 재현

### 2. Vector 재생 정보
`VECTOR` 노드에는 `fillGeometry`, `strokeGeometry`, `relativeTransform`가 들어 있다.

활용 가능:
- 화살표
- 복잡 도형
- 외곽선
- 장식 요소

즉, 현재부터는 `PPT를 다시 해석해서 그리기`보다, `Figma vector geometry를 직접 재생`하는 방향이 가능하다.

### 3. Text 재생 정보
`TEXT` 노드에는 아래 정보가 들어 있다.

- `characters`
- `absoluteBoundingBox`
- `relativeTransform`
- `style.fontFamily`
- `style.fontPostScriptName`
- `style.fontSize`
- `style.textAlignHorizontal`
- `style.textAlignVertical`
- `style.letterSpacing`
- `style.lineHeightPx`
- fill/stroke color

활용 가능:
- 텍스트 내용
- 폰트 크기
- 정렬
- 줄 간격
- 위치 재현

### 4. Image 재생 정보
이미지형 노드는 `IMAGE` fill을 가지고 있고, 실제 asset png도 저장소에 들어 있다.

활용 가능:
- 이미지 fill 재생
- 기준 이미지와 직접 비교

### 5. 비교 기준선
페이지별 PNG가 있으므로 사람 눈 기준으로 비교 가능하다.

활용 가능:
- `visual replay` 결과와 고급 플러그인 결과 비교
- 페이지별 품질 점검

## 확인된 구조 특징

### Page 1
- `VECTOR 233`
- `TEXT 101`
- `GROUP 47`
- `FRAME 3`

### Page 2
- `TEXT 257`
- `VECTOR 114`
- `GROUP 25`
- `FRAME 2`

### Page 3
- `TEXT 222`
- `VECTOR 183`
- `GROUP 86`
- `FRAME 12`
- `RECTANGLE 11`
- `IMAGE fill 11`

해석:
- 고급 플러그인은 `텍스트는 native`, `시각 shell은 vector-heavy` 전략을 쓴 것으로 보인다.
- 특히 화살표와 복잡 도형을 굳이 다시 계산하려 하지 말고, 우선 vector 재생 기준으로 보는 것이 맞다.

## 아직 없는 것

### 1. `figma-used-fonts.json`
파일명 기준으로는 들어오지 않았다.

다만 현재 JSON만으로도 실제 사용 폰트는 상당 부분 추출 가능하다.

현재 확인된 폰트:
- `Inter`
- `Malgun Gothic`
- `Malgun Gothic Bold`
- `Arial Narrow`

즉, `used-fonts` 파일이 없어도 1차 재생 구현은 가능하다.

### 2. Components / Styles
`figma-full-file.json` 기준:
- `components = 0`
- `componentSets = 0`
- `styles = 0`

해석:
- 공통 컴포넌트/스타일 재생은 지금 단계 핵심이 아니다.
- 오히려 개별 node replay에 집중하면 된다.

### 3. Effects
현재 페이지 JSON 기준으로 `effects`는 거의 없다.

해석:
- 그림자/블러 같은 효과 재현은 우선순위가 낮다.

## 객관적 판단

현재 확보된 입력은 `visual replay` 모듈을 시작하기에 충분하다.

특히 중요한 점:
- vector path가 있다
- text style이 있다
- image asset이 있다
- page png 기준선이 있다

즉, 더 이상 `입력이 부족해서 못 한다` 단계는 아니다.

현재 남은 문제는 입력 부족이 아니라, 어떤 방식으로 replay 엔진을 짤지의 문제다.

## 다음 구현 방향

### 우선순위 1
`PPT -> Figma 재해석`이 아니라 `Figma JSON -> Figma direct replay` 기준으로 실험한다.

### 우선순위 2
재생 기준은 아래 순서로 둔다.
- `FRAME / GROUP`
- `VECTOR`
- `TEXT`
- `IMAGE fill`

### 우선순위 3
페이지별 비교는 다음 순서로 한다.
- `Page 1`
- `Page 2`
- `Page 3`

## 결론

현재 확보된 Figma 자료는 `visual replay` 모듈 구현에 충분하다.

가장 중요한 결론은 아래와 같다.

> 다음 단계는 PPT 기반 렌더 품질 보정이 아니라, 고급 플러그인 Figma JSON을 직접 재생하는 `visual replay` 엔진으로 전환하는 것이다.
