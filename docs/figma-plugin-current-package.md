# Current Figma Plugin Package

현재 패키지는 두 경로를 지원합니다.

1. JSON bundle 직접 업로드
2. 로컬 helper server를 통한 PPTX 직접 업로드

현재 지원 경로:

1. `PPT intermediate candidates JSON` 생성
2. 필요 시 `resolved IR` 또는 `dense_ui_panel bundle` 생성
3. Figma 플러그인에서 생성된 `JSON bundle`을 업로드

또는

1. 로컬 helper server 실행
2. Figma 플러그인에서 `PPTX` 직접 업로드
3. helper server가 intermediate JSON으로 변환
4. 플러그인이 바로 렌더

## 포함 파일

- `figma-plugin/manifest.json`
- `figma-plugin/code.js`
- `figma-plugin/ui.html`
- `scripts/build_ppt_replay_bundle.py`
- `scripts/build_resolved_ppt_ir.py`
- `scripts/build_dense_ui_panel_ir_bundle.py`
- `scripts/figma_plugin_local_server.py`
- `docs/block-bundles/ir-dense-ui-panel-29.bundle.json`
- `docs/block-bundles/ir-dense-ui-panel-29-left-product-price-only.bundle.json`

## 기본 사용 흐름

일반 PPT intermediate candidates JSON에서 replay bundle 생성:

```bash
python3 scripts/build_ppt_replay_bundle.py \
  --input docs/ppt-intermediate-candidates-12-19-29.json \
  --output-dir docs/generated-replay-bundles
```

Slide 29 dense UI panel full bundle 생성:

```bash
python3 scripts/build_resolved_ppt_ir.py \
  --input docs/ppt-intermediate-candidates-12-19-29.json \
  --output docs/resolved-ppt-ir-12-19-29.json \
  --slides 29

python3 scripts/build_dense_ui_panel_ir_bundle.py \
  --input docs/resolved-ppt-ir-12-19-29.json \
  --slide 29 \
  --export-mode full \
  --output docs/block-bundles/ir-dense-ui-panel-29.bundle.json
```

## Figma 플러그인 실행

1. Figma Desktop App 실행
2. `Plugins > Development > Import plugin from manifest...`
3. `figma-plugin/manifest.json` 선택
4. 플러그인 실행
5. `JSON bundle` 업로드 또는 `PPTX 직접 업로드` 사용

## PPTX 직접 업로드

먼저 로컬 helper server 실행:

```bash
python3 scripts/figma_plugin_local_server.py
```

그 다음 플러그인에서:

1. `PPTX 직접 업로드` 영역에서 `.pptx` 선택
2. 슬라이드 번호 입력
슬라이드 번호를 비우면 전체 슬라이드를 처리합니다.
3. `PPTX 변환 후 렌더` 클릭

## 패키지 생성

```bash
python3 scripts/package_figma_plugin.py
```

출력:

- `dist/cnsatlas-figma-plugin-current.zip`
