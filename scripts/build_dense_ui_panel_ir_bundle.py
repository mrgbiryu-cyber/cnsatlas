#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


TARGET_SLIDE_WIDTH = 960.0
TARGET_SLIDE_HEIGHT = 540.0
RIGHT_PANEL_X_CUTOFF = TARGET_SLIDE_WIDTH * 0.58


def make_bounds(x: float, y: float, width: float, height: float) -> dict[str, float]:
    return {
        "x": round(float(x), 2),
        "y": round(float(y), 2),
        "width": round(float(width), 2),
        "height": round(float(height), 2),
    }


def identity_affine() -> list[list[float]]:
    return [[1, 0, 0], [0, 1, 0]]


def union_bounds(bounds_list: list[dict[str, Any]]) -> dict[str, float]:
    if not bounds_list:
        return make_bounds(0.0, 0.0, 1.0, 1.0)
    min_x = min(float(bounds["x"]) for bounds in bounds_list)
    min_y = min(float(bounds["y"]) for bounds in bounds_list)
    max_x = max(float(bounds["x"]) + float(bounds["width"]) for bounds in bounds_list)
    max_y = max(float(bounds["y"]) + float(bounds["height"]) for bounds in bounds_list)
    return make_bounds(min_x, min_y, max_x - min_x, max_y - min_y)


def color_from_style(style_color: dict[str, Any] | None, fallback: dict[str, float]) -> tuple[dict[str, float], float]:
    if not style_color:
        return fallback, 1.0
    resolved_hex = style_color.get("resolved_value") or style_color.get("value")
    alpha = style_color.get("alpha")
    opacity = float(alpha) if isinstance(alpha, (int, float)) else 1.0
    if isinstance(resolved_hex, str) and len(resolved_hex) == 6:
        return {
            "r": int(resolved_hex[0:2], 16) / 255.0,
            "g": int(resolved_hex[2:4], 16) / 255.0,
            "b": int(resolved_hex[4:6], 16) / 255.0,
        }, opacity
    return fallback, opacity


def make_solid_fill(style_color: dict[str, Any] | None, fallback: dict[str, float]) -> dict[str, Any]:
    color, opacity = color_from_style(style_color, fallback)
    return {"type": "SOLID", "color": color, "opacity": opacity}


def make_strokes(shape_style: dict[str, Any] | None) -> tuple[list[dict[str, Any]], float]:
    line = (shape_style or {}).get("line") or {}
    if line.get("kind") == "none":
        return [], 0.0
    color, opacity = color_from_style(line, {"r": 0.78, "g": 0.78, "b": 0.78})
    stroke_weight = float(line.get("width_px") or 1.0)
    return ([{"type": "SOLID", "color": color, "opacity": opacity}], stroke_weight)


def text_style(atom: dict[str, Any], font_size: float | None = None) -> dict[str, Any]:
    source_style = atom.get("text_style") or {}
    size = float(font_size or source_style.get("font_size_max") or source_style.get("font_size_avg") or 8.0)
    return {
        "fontFamily": str(source_style.get("font_family") or "LG스마트체"),
        "fontStyle": "Regular",
        "fontSize": size,
        "textAlignHorizontal": "LEFT",
        "textAlignVertical": "TOP",
        "textAutoResize": "HEIGHT",
        "lineHeightPx": round(size * 1.25, 2),
    }


def build_text_node(atom: dict[str, Any], bounds: dict[str, Any] | None = None, *, suffix: str = "") -> dict[str, Any]:
    node_bounds = dict(bounds or atom.get("visual_bounds_px") or make_bounds(0.0, 0.0, 1.0, 1.0))
    source_style = atom.get("text_style") or {}
    fill_style = source_style.get("fill")
    if not fill_style and (atom.get("cell_style") or {}).get("fill"):
        fill_style = None
    return {
        "id": f"{atom['id']}{suffix}",
        "type": "TEXT",
        "name": atom.get("title") or atom.get("id") or "text",
        "characters": str(atom.get("text") or ""),
        "absoluteBoundingBox": node_bounds,
        "relativeTransform": identity_affine(),
        "fills": [make_solid_fill(fill_style, {"r": 0.1, "g": 0.1, "b": 0.1})],
        "style": text_style(atom),
        "children": [],
        "debug": {
            "generator": "dense-ui-ir-v1",
            "layer_role": atom.get("layer_role"),
            "owner_id": atom.get("owner_id"),
            "source_atom_id": atom.get("id"),
        },
    }


def build_rect_node(atom: dict[str, Any], bounds: dict[str, Any] | None = None, *, suffix: str = "") -> dict[str, Any]:
    node_bounds = dict(bounds or atom.get("visual_bounds_px") or make_bounds(0.0, 0.0, 1.0, 1.0))
    shape_style = atom.get("shape_style") or {}
    fill_style = shape_style.get("fill")
    fills = [make_solid_fill(fill_style, {"r": 1.0, "g": 1.0, "b": 1.0})]
    strokes, stroke_weight = make_strokes(shape_style)
    return {
        "id": f"{atom['id']}{suffix}",
        "type": "RECTANGLE",
        "name": atom.get("title") or atom.get("id") or "rect",
        "absoluteBoundingBox": node_bounds,
        "relativeTransform": identity_affine(),
        "fills": fills,
        "strokes": strokes,
        "strokeWeight": stroke_weight,
        "children": [],
        "debug": {
            "generator": "dense-ui-ir-v1",
            "layer_role": atom.get("layer_role"),
            "owner_id": atom.get("owner_id"),
            "source_atom_id": atom.get("id"),
        },
    }


def build_image_node(atom: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any] | None:
    image_base64 = atom.get("image_base64")
    if not image_base64:
        return None
    image_ref = f"asset:{atom['id']}"
    assets[image_ref] = {
        "base64": image_base64,
        "mime_type": atom.get("mime_type") or "image/png",
    }
    return {
        "id": atom["id"],
        "type": "RECTANGLE",
        "name": atom.get("title") or atom.get("id") or "image",
        "absoluteBoundingBox": atom.get("visual_bounds_px") or make_bounds(0.0, 0.0, 1.0, 1.0),
        "relativeTransform": identity_affine(),
        "fills": [{"type": "IMAGE", "imageRef": image_ref, "scaleMode": "FIT"}],
        "strokes": [],
        "strokeWeight": 0,
        "children": [],
        "debug": {
            "generator": "dense-ui-ir-v1",
            "layer_role": atom.get("layer_role"),
            "owner_id": atom.get("owner_id"),
            "source_atom_id": atom.get("id"),
        },
    }


def build_owner_group(owner_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    bounds = union_bounds(
        [
            child.get("absoluteBoundingBox") or make_bounds(0.0, 0.0, 1.0, 1.0)
            for child in children
        ]
    )
    return {
        "id": owner_id,
        "type": "GROUP",
        "name": owner_id.split(":")[-1],
        "absoluteBoundingBox": bounds,
        "relativeTransform": identity_affine(),
        "children": children,
        "debug": {
            "generator": "dense-ui-ir-v1",
            "owner_id": owner_id,
        },
    }


def dense_panel_bounds(page: dict[str, Any]) -> dict[str, float]:
    relevant = []
    for atom in page.get("atoms") or []:
        role = str(atom.get("layer_role") or "")
        if role in {
            "top_meta_cell",
            "version_stack",
            "issue_card",
            "description_card",
            "description_text_lane",
            "description_footer",
            "description_marker",
        }:
            bounds = atom.get("visual_bounds_px")
            if bounds and float(bounds["x"]) + float(bounds["width"]) >= RIGHT_PANEL_X_CUTOFF:
                relevant.append(bounds)
    if not relevant:
        return make_bounds(TARGET_SLIDE_WIDTH * 0.6, 0.0, TARGET_SLIDE_WIDTH * 0.4, TARGET_SLIDE_HEIGHT)
    return union_bounds(relevant)


def is_right_panel_atom(atom: dict[str, Any]) -> bool:
    bounds = atom.get("visual_bounds_px") or {}
    x = float(bounds.get("x") or 0.0)
    width = float(bounds.get("width") or 0.0)
    role = str(atom.get("layer_role") or "")
    if role in {"description_card", "description_text_lane", "description_footer", "description_marker", "issue_card", "version_stack"}:
        return True
    return x + width >= RIGHT_PANEL_X_CUTOFF


def owner_priority(owner_id: str) -> int:
    order = {
        "dense_ui_panel:top_meta_rows": 10,
        "dense_ui_panel:top_meta_cells": 12,
        "dense_ui_panel:version_stack": 14,
        "dense_ui_panel:issue_card": 16,
        "dense_ui_panel:description_cards": 18,
        "dense_ui_panel:description_markers": 20,
        "dense_ui_panel:description_lanes": 22,
        "dense_ui_panel:description_footer": 24,
        "dense_ui_panel:small_assets": 30,
    }
    return order.get(owner_id, 50)


def atom_priority(atom: dict[str, Any]) -> tuple[int, float, float]:
    return (
        int(atom.get("z_index") or 0),
        float((atom.get("visual_bounds_px") or {}).get("y") or 0.0),
        float((atom.get("visual_bounds_px") or {}).get("x") or 0.0),
    )


def build_dense_ui_panel_nodes(page: dict[str, Any], assets: dict[str, Any]) -> list[dict[str, Any]]:
    panel_bounds = dense_panel_bounds(page)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for atom in page.get("atoms") or []:
        owner_id = str(atom.get("owner_id") or "")
        if not owner_id.startswith("dense_ui_panel:"):
            continue
        if not is_right_panel_atom(atom):
            continue
        grouped[owner_id].append(atom)

    children: list[dict[str, Any]] = []
    for owner_id in sorted(grouped.keys(), key=owner_priority):
        atoms = sorted(grouped[owner_id], key=atom_priority)
        owner_children: list[dict[str, Any]] = []
        for atom in atoms:
            role = str(atom.get("layer_role") or "")
            subtype = str(atom.get("subtype") or "")
            if role in {"top_meta_cell", "description_card", "issue_card", "version_stack"}:
                owner_children.append(build_rect_node(atom, suffix=":bg"))
                if atom.get("text"):
                    owner_children.append(build_text_node(atom, suffix=":label"))
                continue
            if role in {"description_text_lane", "description_footer", "description_marker"}:
                owner_children.append(build_text_node(atom))
                continue
            if role == "small_asset":
                if subtype == "image":
                    image_node = build_image_node(atom, assets)
                    if image_node:
                        owner_children.append(image_node)
                    continue
                if atom.get("text"):
                    owner_children.append(build_text_node(atom))
                else:
                    owner_children.append(build_rect_node(atom))
                continue
        if owner_children:
            children.append(build_owner_group(owner_id, owner_children))

    panel_frame = {
        "id": f"{page['page_id']}:dense_ui_panel",
        "type": "FRAME",
        "name": "dense_ui_panel",
        "absoluteBoundingBox": panel_bounds,
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}, "opacity": 1.0}],
        "strokes": [{"type": "SOLID", "color": {"r": 0.9, "g": 0.9, "b": 0.9}, "opacity": 1.0}],
        "strokeWeight": 1,
        "children": children,
        "debug": {
            "generator": "dense-ui-ir-v1",
            "page_id": page["page_id"],
            "page_type": page["page_type"],
        },
    }
    return [panel_frame]


def build_bundle(page: dict[str, Any], source_file: str) -> dict[str, Any]:
    assets: dict[str, Any] = {}
    page_children = build_dense_ui_panel_nodes(page, assets)
    root_bounds = make_bounds(0.0, 0.0, TARGET_SLIDE_WIDTH, TARGET_SLIDE_HEIGHT)
    inner_frame = {
        "id": f"{page['page_id']}:frame",
        "type": "FRAME",
        "name": "Frame",
        "absoluteBoundingBox": root_bounds,
        "relativeTransform": identity_affine(),
        "fills": [],
        "strokes": [],
        "strokeWeight": 0,
        "children": page_children,
        "debug": {
            "generator": "dense-ui-ir-v1",
            "page_id": page["page_id"],
            "page_type": page["page_type"],
        },
    }
    root = {
        "id": page["page_id"],
        "type": "FRAME",
        "name": f"Slide {page['slide_no']} - Dense UI Panel",
        "absoluteBoundingBox": root_bounds,
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}, "opacity": 1.0}],
        "strokes": [],
        "strokeWeight": 0,
        "children": [inner_frame],
        "debug": {
            "generator": "dense-ui-ir-v1",
            "page_id": page["page_id"],
            "page_type": page["page_type"],
        },
    }
    return {
        "kind": "figma-replay-bundle",
        "source_kind": "resolved-ppt-ir",
        "visual_model_version": "dense-ui-ir-v1",
        "source_file": source_file,
        "file_name": Path(source_file).name,
        "page_name": root["name"],
        "node_id": root["id"],
        "document": root,
        "assets": assets,
        "missing_assets": [],
        "debug": {
            "status": "dense_ui_ir_bundle",
            "page_type": page["page_type"],
            "owner_count": len(page.get("owner_buckets") or []),
            "atom_count": len(page.get("atoms") or []),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a dense-ui-panel replay bundle from resolved PPT IR.")
    parser.add_argument("--input", required=True, help="Resolved IR JSON path")
    parser.add_argument("--output", required=True, help="Output bundle path")
    parser.add_argument("--slide", type=int, default=29, help="Slide number to render")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    data = json.loads(input_path.read_text(encoding="utf-8"))
    pages = data.get("pages") or []
    page = next((page for page in pages if int(page.get("slide_no") or 0) == args.slide), None)
    if not page:
        raise SystemExit(f"slide {args.slide} not found in {input_path}")
    if str(page.get("page_type") or "") != "dense_ui_panel":
        raise SystemExit(f"slide {args.slide} is not dense_ui_panel (got {page.get('page_type')})")

    bundle = build_bundle(page, str(input_path))
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {output_path}")


if __name__ == "__main__":
    main()
