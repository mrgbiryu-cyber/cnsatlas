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


def build_hybrid_frame(
    baseline_bundle: dict,
    ir_bundle: dict,
    *,
    include_top_meta: bool = True,
    include_top_meta_band: bool = True,
    include_top_meta_info: bool = True,
    include_top_rows: bool = True,
    include_description_header: bool = True,
    include_version_stack: bool = True,
    include_issue: bool = True,
    include_small_assets: bool = True,
) -> dict:
    baseline_frame = copy.deepcopy(find_full_frame(baseline_bundle))
    ir_logical = find_ir_logical_panel(ir_bundle)
    children_by_id = {child.get("id"): copy.deepcopy(child) for child in ir_logical.get("children") or []}
    top_meta_group = children_by_id.get("dense_ui_panel:top_meta_group")
    top_meta_info_group = children_by_id.get("dense_ui_panel:top_meta_info_group")
    top_rows_group = children_by_id.get("dense_ui_panel:top_rows_group")
    description_header_group = children_by_id.get("dense_ui_panel:description_header_group")
    version_stack_group = children_by_id.get("dense_ui_panel:version_stack_group")
    issue_group = children_by_id.get("dense_ui_panel:issue_group")
    small_asset_group = children_by_id.get("dense_ui_panel:small_asset_group")

    name_parts = ["hybrid_full"]
    if include_top_meta:
        name_parts.append("meta")
        if include_top_meta_band and not include_top_meta_info:
            name_parts.append("band")
        if include_top_meta_info and not include_top_meta_band:
            name_parts.append("info")
    if include_top_rows:
        name_parts.append("rows")
    if include_description_header:
        name_parts.append("desc_header")
    if include_version_stack:
        name_parts.append("version")
    if include_issue:
        name_parts.append("issue")
    if include_small_assets:
        name_parts.append("assets")
    baseline_frame["name"] = "_".join(name_parts)
    rebuilt_children = []
    for child in baseline_frame.get("children") or []:
        child_name = child.get("name")
        if child_name == "top_meta_block":
            if include_top_meta and include_top_meta_band and top_meta_group is not None:
                rebuilt_children.append(top_meta_group)
            if include_top_meta and include_top_meta_info and top_meta_info_group is not None:
                rebuilt_children.append(top_meta_info_group)
            if include_top_rows and top_rows_group is not None:
                rebuilt_children.append(top_rows_group)
            if include_version_stack and version_stack_group is not None:
                rebuilt_children.append(version_stack_group)
            continue
        if child_name != "right_panel_block":
            rebuilt_children.append(child)
            continue
        right_panel = copy.deepcopy(child)
        right_panel_children = []
        for panel_child in right_panel.get("children") or []:
            panel_name = str(panel_child.get("name") or "")
            # Replacement hybrid:
            # - keep dense baseline background/description style layers
            # - drop semantic table text group that overlaps everything
            if panel_name == "표 48":
                continue
            right_panel_children.append(panel_child)
        if include_description_header and description_header_group is not None:
            right_panel_children.append(description_header_group)
        if include_issue and issue_group is not None:
            right_panel_children.append(issue_group)
        if include_small_assets and small_asset_group is not None:
            right_panel_children.append(small_asset_group)
        right_panel["children"] = right_panel_children
        rebuilt_children.append(right_panel)
    baseline_frame["children"] = rebuilt_children
    return baseline_frame


def build_hybrid_bundle(baseline_bundle: dict, ir_bundle: dict, out_path: Path) -> None:
    hybrid_bundle = copy.deepcopy(baseline_bundle)
    hybrid_bundle["page_name"] = "Slide 29 - Full Style Hybrid"
    hybrid_bundle["node_id"] = "page:29:full-style-hybrid"
    hybrid_bundle["visual_model_version"] = "dense-ui-style-hybrid-v1"
    hybrid_bundle["source_kind"] = "ppt-full-style-hybrid"
    hybrid_bundle["file_name"] = out_path.name
    hybrid_bundle["document"]["id"] = "page:29:full-style-hybrid"
    hybrid_bundle["document"]["name"] = "Slide 29 - Full Style Hybrid"
    hybrid_bundle["document"]["children"][0] = build_hybrid_frame(baseline_bundle, ir_bundle)
    hybrid_bundle["assets"] = bundle_assets(baseline_bundle, ir_bundle)
    hybrid_bundle["debug"] = {"status": "page29_full_style_hybrid"}
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(hybrid_bundle, handle, ensure_ascii=False, indent=2)


def build_compare_bundle(baseline_bundle: dict, hybrid_bundle: dict, out_path: Path) -> None:
    gap = 40.0
    top_pad = 28.0
    total_width = TARGET_SLIDE_WIDTH * 2 + gap
    total_height = TARGET_SLIDE_HEIGHT + top_pad
    compare_children = [
        make_label_node("compare:baseline:label", "baseline_full", 8.0, 6.0),
        shift_node(find_full_frame(baseline_bundle), "compare:baseline", 0.0, top_pad),
        make_label_node("compare:hybrid:label", hybrid_bundle["document"]["children"][0]["name"], TARGET_SLIDE_WIDTH + gap + 8.0, 6.0),
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


def build_axis_compare_bundle(baseline_bundle: dict, ir_bundle: dict, out_path: Path) -> None:
    gap = 40.0
    top_pad = 28.0
    variants = [
        ("baseline_full", find_full_frame(baseline_bundle)),
        (
            "ir_top_meta_band_only",
            build_hybrid_frame(
                baseline_bundle,
                ir_bundle,
                include_top_meta=True,
                include_top_meta_band=True,
                include_top_meta_info=False,
                include_top_rows=False,
                include_description_header=False,
                include_version_stack=False,
                include_issue=False,
                include_small_assets=False,
            ),
        ),
        (
            "ir_top_meta_info_only",
            build_hybrid_frame(
                baseline_bundle,
                ir_bundle,
                include_top_meta=True,
                include_top_meta_band=False,
                include_top_meta_info=True,
                include_top_rows=False,
                include_description_header=False,
                include_version_stack=False,
                include_issue=False,
                include_small_assets=False,
            ),
        ),
        (
            "ir_version_only",
            build_hybrid_frame(
                baseline_bundle,
                ir_bundle,
                include_top_meta=False,
                include_top_rows=False,
                include_description_header=False,
                include_version_stack=True,
                include_issue=False,
                include_small_assets=False,
            ),
        ),
        (
            "ir_desc_header_only",
            build_hybrid_frame(
                baseline_bundle,
                ir_bundle,
                include_top_meta=False,
                include_top_rows=False,
                include_description_header=True,
                include_version_stack=False,
                include_issue=False,
                include_small_assets=False,
            ),
        ),
        (
            "ir_issue_only",
            build_hybrid_frame(
                baseline_bundle,
                ir_bundle,
                include_top_meta=False,
                include_top_rows=False,
                include_description_header=False,
                include_version_stack=False,
                include_issue=True,
                include_small_assets=False,
            ),
        ),
        (
            "ir_assets_only",
            build_hybrid_frame(
                baseline_bundle,
                ir_bundle,
                include_top_meta=False,
                include_top_rows=False,
                include_description_header=False,
                include_version_stack=False,
                include_issue=False,
                include_small_assets=True,
            ),
        ),
        (
            "ir_meta_version_issue_assets",
            build_hybrid_frame(
                baseline_bundle,
                ir_bundle,
                include_top_meta=True,
                include_top_rows=True,
                include_description_header=True,
                include_version_stack=True,
                include_issue=True,
                include_small_assets=True,
            ),
        ),
    ]
    total_width = TARGET_SLIDE_WIDTH * len(variants) + gap * (len(variants) - 1)
    total_height = TARGET_SLIDE_HEIGHT + top_pad
    compare_children: list[dict[str, Any]] = []
    for index, (label, frame) in enumerate(variants):
        dx = index * (TARGET_SLIDE_WIDTH + gap)
        compare_children.append(make_label_node(f"compare:axis:{index}:label", label, dx + 8.0, 6.0))
        compare_children.append(shift_node(frame, f"compare:axis:{index}", dx, top_pad))

    inner_frame = {
        "id": "page:29:full-style-axis-compare:frame",
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
        "id": "page:29:full-style-axis-compare",
        "type": "FRAME",
        "name": "Slide 29 Full Style Axis Compare",
        "absoluteBoundingBox": {"x": 0.0, "y": 0.0, "width": total_width, "height": total_height},
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": {"r": 1.0, "g": 1.0, "b": 1.0}, "opacity": 1.0}],
        "strokes": [],
        "strokeWeight": 0,
        "children": [inner_frame],
        "debug": {"generator": "page29-full-style-axis-compare"},
    }
    compare_bundle = {
        "kind": "figma-replay-bundle",
        "source_kind": "ppt-full-style-axis-compare",
        "visual_model_version": "dense-ui-style-axis-compare-v1",
        "source_file": str(out_path),
        "file_name": out_path.name,
        "page_name": root["name"],
        "node_id": root["id"],
        "document": root,
        "assets": bundle_assets(baseline_bundle, ir_bundle),
        "missing_assets": [],
        "debug": {"status": "page29_full_style_axis_compare"},
    }
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(compare_bundle, handle, ensure_ascii=False, indent=2)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    baseline_path = repo_root / "docs" / "block-bundles" / "block-slide-29.bundle.json"
    ir_path = repo_root / "docs" / "block-bundles" / "ir-dense-ui-panel-29.bundle.json"
    out_path = repo_root / "docs" / "block-bundles" / "block-slide-29-full-style-hybrid-compare.bundle.json"
    hybrid_out_path = repo_root / "docs" / "block-bundles" / "block-slide-29-full-style-hybrid.bundle.json"
    axis_compare_out_path = repo_root / "docs" / "block-bundles" / "block-slide-29-full-style-axis-compare.bundle.json"

    baseline_bundle = load_bundle(baseline_path)
    ir_bundle = load_bundle(ir_path)
    hybrid_bundle = copy.deepcopy(baseline_bundle)
    hybrid_bundle["document"]["children"][0] = build_hybrid_frame(baseline_bundle, ir_bundle)
    build_compare_bundle(baseline_bundle, hybrid_bundle, out_path)
    build_hybrid_bundle(baseline_bundle, ir_bundle, hybrid_out_path)
    build_axis_compare_bundle(baseline_bundle, ir_bundle, axis_compare_out_path)
    print(f"saved {out_path}")
    print(f"saved {hybrid_out_path}")
    print(f"saved {axis_compare_out_path}")


if __name__ == "__main__":
    main()
