# Figma Plugin Usage

플러그인 위치:

- `figma-plugin/manifest.json`

플러그인 목적:

- `docs/ppt-intermediate-candidates-12-19-29.json`를 업로드해서
- slide `12`, `19`, `29`를 Figma canvas에 렌더하는 비주얼 테스트용 플러그인

## 사용 순서

1. Figma Desktop App 실행
2. 새 Design file 열기
3. `Plugins > Development > Import plugin from manifest...`
4. `figma-plugin/manifest.json` 선택
5. 플러그인 실행
6. `docs/ppt-intermediate-candidates-12-19-29.json` 파일 업로드
7. `Render In Figma` 클릭

## 기대 결과

- 현재 페이지에 `CNS Atlas Visual Test` 프레임 생성
- 그 안에 slide `12`, `19`, `29` preview가 가로로 배치됨
- table / group / text / image placeholder 구조를 눈으로 확인 가능

## 현재 제한

- 실제 PPT 이미지 바이너리를 가져오지 않으므로 image는 placeholder로 렌더함
- shape style은 단순화되어 있음
- text style은 기본 폰트로 단순화되어 있음
- 목적은 완성형 변환이 아니라 1차 비주얼 테스트임
