#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

from ppt_source_extractor import TARGET_SLIDE_HEIGHT, TARGET_SLIDE_WIDTH, identity_affine


def shift_node(node: dict, prefix: str, dx: float, dy: float) -> dict:
    cloned = copy.deepcopy(node)
    cloned["id"] = f"{prefix}:{cloned['id']}"
    bounds = cloned.get("absoluteBoundingBox")
    if bounds:
        cloned["absoluteBoundingBox"] = {
            "x": round(float(bounds["x"]) + dx, 2),
            "y": round(float(bounds["y"]) + dy, 2),
            "width": float(bounds["width"]),
            "height": float(bounds["height"]),
        }
    children = cloned.get("children") or []
    if children:
        cloned["children"] = [shift_node(child, prefix, dx, dy) for child in children]
    return cloned


def make_label_node(node_id: str, label: str, x: float, y: float) -> dict:
    return {
        "id": node_id,
        "type": "TEXT",
        "name": label,
        "characters": label,
        "absoluteBoundingBox": {"x": x, "y": y, "width": 260.0, "height": 18.0},
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": {"r": 0.12, "g": 0.12, "b": 0.12}, "opacity": 1.0}],
        "style": {
            "fontSize": 14,
            "fontFamily": "Inter",
            "textAlignHorizontal": "LEFT",
            "textAlignVertical": "TOP",
            "textAutoResize": "HEIGHT",
            "lineHeightPx": None,
        },
        "children": [],
        "debug": {"role": "compare_label"},
    }


def load_bundle(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def bundle_assets(*bundles: dict) -> dict:
    merged: dict = {}
    for bundle in bundles:
        merged.update(bundle.get("assets") or {})
    return merged


def find_full_frame(bundle: dict) -> dict:
    return bundle["document"]["children"][0]


def find_ir_logical_panel(bundle: dict) -> dict:
    return bundle["document"]["children"][0]["children"][0]["children"][0]


def build_hybrid_frame(baseline_bundle: dict, ir_bundle: dict) -> dict:
    baseline_frame = copy.deepcopy(find_full_frame(baseline_bundle))
    ir_logical = find_ir_logical_panel(ir_bundle)
    selected_ids = {
        "dense_ui_panel:version_stack",
        "dense_ui_panel:issue_card",
        "dense_ui_panel:small_assets",
    }
    selected_groups = [
        copy.deepcopy(child)
        for child in ir_logical.get("children") or []
        if child.get("id") in selected_ids
    ]

    baseline_frame["name"] = "hybrid_full_baseline_plus_ir_layers"
    baseline_frame["children"] = list(baseline_frame.get("children") or []) + selected_groups
    return baseline_frame


def build_compare_bundle(baseline_bundle: dict, hybrid_bundle: dict, out_path: Path) -> None:
    gap = 40.0
    top_pad = 28.0
    total_width = TARGET_SLIDE_WIDTH * 2 + gap
    total_height = TARGET_SLIDE_HEIGHT + top_pad
    compare_children = [
        make_label_node("compare:baseline:label", "baseline_full", 8.0, 6.0),
        shift_node(find_full_frame(baseline_bundle), "compare:baseline", 0.0, top_pad),
        make_label_node("compare:hybrid:label", "hybrid_full_baseline_plus_ir_layers", TARGET_SLIDE_WIDTH + gap + 8.0, 6.0),
        shift_node(find_full_frame(hybrid_bundle), "compare:hybrid", TARGET_SLIDE_WIDTH + gap, top_pad),
    ]

    inner_frame = {
        "id": "page:29:full-style-hybrid-compare:frame",
        "type": "FRAME",
        "name": "Frame",
        "absoluteBoundingBox": {"x": 0.0, "y": 0.0, "width": total_width, "height": total_height},
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": {"r": 1.0, "g": 1.0, "b": 1.0}, "opacity": 1.0}],
        "strokes": [],
        "strokeWeight": 0,
        "children": compare_children,
    }
    root = {
        "id": "page:29:full-style-hybrid-compare",
        "type": "FRAME",
        "name": "Slide 29 Full Style Hybrid Compare",
        "absoluteBoundingBox": {"x": 0.0, "y": 0.0, "width": total_width, "height": total_height},
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": {"r": 1.0, "g": 1.0, "b": 1.0}, "opacity": 1.0}],
        "strokes": [],
        "strokeWeight": 0,
        "children": [inner_frame],
        "debug": {"generator": "page29-full-style-hybrid-compare"},
    }
    hybrid_assets = bundle_assets(baseline_bundle, hybrid_bundle)
    compare_bundle = {
        "kind": "figma-replay-bundle",
        "source_kind": "ppt-full-style-hybrid-compare",
        "visual_model_version": "dense-ui-style-hybrid-compare-v1",
        "source_file": str(out_path),
        "file_name": out_path.name,
        "page_name": root["name"],
        "node_id": root["id"],
        "document": root,
        "assets": hybrid_assets,
        "missing_assets": [],
        "debug": {"status": "page29_full_style_hybrid_compare"},
    }
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(compare_bundle, handle, ensure_ascii=False, indent=2)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    baseline_path = repo_root / "docs" / "block-bundles" / "block-slide-29.bundle.json"
    ir_path = repo_root / "docs" / "block-bundles" / "ir-dense-ui-panel-29.bundle.json"
    out_path = repo_root / "docs" / "block-bundles" / "block-slide-29-full-style-hybrid-compare.bundle.json"

    baseline_bundle = load_bundle(baseline_path)
    ir_bundle = load_bundle(ir_path)
    hybrid_bundle = copy.deepcopy(baseline_bundle)
    hybrid_bundle["document"]["children"][0] = build_hybrid_frame(baseline_bundle, ir_bundle)
    build_compare_bundle(baseline_bundle, hybrid_bundle, out_path)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
