# Figma Plugin Usage

플러그인 위치:

- `figma-plugin/manifest.json`

플러그인 목적:

- `figma replay bundle JSON`
- `dense_ui_panel bundle JSON`
- `slide review manifest JSON`
- 로컬 helper server를 통한 `PPTX 직접 업로드`

를 Figma canvas에 렌더하는 비주얼 테스트용 플러그인

## 사용 순서

1. Figma Desktop App 실행
2. 새 Design file 열기
3. `Plugins > Development > Import plugin from manifest...`
4. `figma-plugin/manifest.json` 선택
5. 플러그인 실행
6. 생성된 `JSON bundle` 파일 업로드 또는 `PPTX 직접 업로드`
7. `Render In Figma` 클릭

## PPTX 직접 업로드

1. 터미널에서 아래 실행

```bash
python3 scripts/figma_plugin_local_server.py
```

2. Figma 플러그인 실행
3. `PPTX 직접 업로드` 영역에서 `.pptx` 선택
4. 슬라이드 번호 입력
슬라이드 번호를 비우면 전체 슬라이드를 처리합니다.
5. `PPTX 변환 후 렌더` 클릭

## 기대 결과

- 현재 페이지에 `CNS Atlas Replay` 프레임 생성
- 입력한 bundle 기준으로 page preview가 렌더됨
- table / group / text / image placeholder 구조를 눈으로 확인 가능

## 현재 제한

- `PPTX 직접 업로드`는 로컬 helper server가 켜져 있어야 동작함
- 실제 PPT 이미지 바이너리를 가져오지 않으므로 image는 placeholder로 렌더함
- shape style은 단순화되어 있음
- text style은 기본 폰트로 단순화되어 있음
- 목적은 완성형 변환이 아니라 1차 비주얼 테스트임
