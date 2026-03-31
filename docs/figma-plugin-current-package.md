# Current Figma Plugin Package

현재 패키지는 `raw PPTX`를 Figma 안에서 직접 파싱하지 않습니다.

현재 지원 경로:

1. `PPT intermediate candidates JSON` 생성
2. 필요 시 `resolved IR` 또는 `dense_ui_panel bundle` 생성
3. Figma 플러그인에서 생성된 `JSON bundle`을 업로드

## 포함 파일

- `figma-plugin/manifest.json`
- `figma-plugin/code.js`
- `figma-plugin/ui.html`
- `scripts/build_ppt_replay_bundle.py`
- `scripts/build_resolved_ppt_ir.py`
- `scripts/build_dense_ui_panel_ir_bundle.py`
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
5. 생성된 `figma replay bundle JSON` 또는 `dense_ui_panel bundle JSON` 업로드

## 패키지 생성

```bash
python3 scripts/package_figma_plugin.py
```

출력:

- `dist/cnsatlas-figma-plugin-current.zip`
