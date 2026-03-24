#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from build_block_replay_bundle import build_bundle_from_page
from ppt_source_extractor import TARGET_SLIDE_HEIGHT, TARGET_SLIDE_WIDTH, identity_affine, iter_selected_pages, load_intermediate_payload


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
        "absoluteBoundingBox": {"x": x, "y": y, "width": 180.0, "height": 18.0},
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


def build_compare_bundle(slide_no: int, bundles: list[tuple[str, dict]], source_file: str) -> dict:
    gap = 40.0
    top_pad = 28.0
    total_width = len(bundles) * TARGET_SLIDE_WIDTH + (len(bundles) - 1) * gap
    total_height = TARGET_SLIDE_HEIGHT + top_pad
    compare_children: list[dict] = []
    merged_assets: dict = {}

    for index, (label, bundle) in enumerate(bundles):
        dx = index * (TARGET_SLIDE_WIDTH + gap)
        dy = top_pad
        inner = bundle["document"]["children"][0]
        shifted = shift_node(inner, f"compare:{label}", dx, dy)
        shifted["name"] = label
        compare_children.append(make_label_node(f"compare:{label}:label", label, dx + 8.0, 6.0))
        compare_children.append(shifted)
        merged_assets.update(bundle.get("assets") or {})

    inner_frame = {
        "id": f"page:{slide_no}:compare:frame",
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
        "id": f"page:{slide_no}:compare",
        "type": "FRAME",
        "name": f"Slide {slide_no} Compare",
        "absoluteBoundingBox": {"x": 0.0, "y": 0.0, "width": total_width, "height": total_height},
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": {"r": 1.0, "g": 1.0, "b": 1.0}, "opacity": 1.0}],
        "strokes": [],
        "strokeWeight": 0,
        "children": [inner_frame],
        "debug": {"generator": "page29-variant-compare"},
    }
    return {
        "kind": "figma-replay-bundle",
        "source_kind": "ppt-block-prototype-compare",
        "visual_model_version": "block-v1-compare",
        "source_file": source_file,
        "file_name": Path(source_file).name,
        "page_name": root["name"],
        "node_id": root["id"],
        "document": root,
        "assets": merged_assets,
        "missing_assets": [],
        "debug": {"status": "page29_compare_bundle", "variants": [label for label, _ in bundles]},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build page 29 comparison variants for block replay bundle.")
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "ppt-intermediate-candidates-12-19-29.json"),
        help="Intermediate candidates JSON path",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "block-bundles"),
        help="Output directory",
    )
    parser.add_argument("--slide", type=int, default=29, help="Slide number to export variants for")
    args = parser.parse_args()

    payload = load_intermediate_payload(args.input)
    selected = list(iter_selected_pages(payload, {args.slide}))
    if not selected:
        raise SystemExit(f"slide {args.slide} not found in {args.input}")
    page = selected[0]

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("29-1", "v1"),
        ("29-2", "v2"),
        ("29-3", "v3"),
    ]
    source_file = str(Path(args.input).resolve())
    built_variants: list[tuple[str, dict]] = []
    for label, variant in variants:
        bundle = build_bundle_from_page(page, source_file, variant)
        output_path = output_dir / f"block-slide-{args.slide}-{label.split('-')[-1]}.bundle.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(bundle, handle, ensure_ascii=False, indent=2)
        print(f"saved {output_path}")
        built_variants.append((label, bundle))

    compare_bundle = build_compare_bundle(args.slide, built_variants, source_file)
    compare_output_path = output_dir / f"block-slide-{args.slide}-compare.bundle.json"
    with compare_output_path.open("w", encoding="utf-8") as handle:
        json.dump(compare_bundle, handle, ensure_ascii=False, indent=2)
    print(f"saved {compare_output_path}")


if __name__ == "__main__":
    main()
