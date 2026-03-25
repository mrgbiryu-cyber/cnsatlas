#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ppt_source_extractor import (
    build_page_context,
    iter_selected_pages,
    load_intermediate_payload,
    make_bounds,
    scale_bounds,
    scale_point,
)


def union_bounds(bounds_list: list[dict[str, float]]) -> dict[str, float]:
    if not bounds_list:
        return make_bounds(0.0, 0.0, 1.0, 1.0)
    min_x = min(float(bounds["x"]) for bounds in bounds_list)
    min_y = min(float(bounds["y"]) for bounds in bounds_list)
    max_x = max(float(bounds["x"]) + float(bounds["width"]) for bounds in bounds_list)
    max_y = max(float(bounds["y"]) + float(bounds["height"]) for bounds in bounds_list)
    return make_bounds(min_x, min_y, max_x - min_x, max_y - min_y)


def atom_type(candidate: dict[str, Any]) -> str:
    subtype = str(candidate.get("subtype") or "")
    if subtype == "text_block":
        return "text_row"
    if subtype == "table":
        return "semantic_table"
    if subtype == "table_cell":
        return "table_cell"
    if subtype == "connector":
        return "connector"
    if subtype == "image":
        return "image_asset"
    if subtype in {"shape", "labeled_shape"}:
        return "background_card"
    if subtype in {"group", "section_block"}:
        return "container"
    return subtype or "unknown"


def render_mode(candidate: dict[str, Any], page_type: str) -> str:
    subtype = str(candidate.get("subtype") or "")
    if subtype == "text_block":
        return "native_text"
    if subtype == "connector":
        return "vector"
    if subtype == "image":
        return "image_asset"
    if subtype == "table":
        if page_type in {"table-heavy", "dense_ui_panel"}:
            return "semantic_table"
        return "svg_block"
    if subtype == "table_cell":
        return "lane_text" if page_type == "dense_ui_panel" else "semantic_cell"
    if subtype in {"shape", "labeled_shape"}:
        return "native_shape"
    return "native_shape"


def layer_role(candidate: dict[str, Any], page_type: str) -> str:
    subtype = str(candidate.get("subtype") or "")
    text_value = str(candidate.get("text") or "").strip()
    bounds = candidate.get("bounds_px") or {}
    width = float(bounds.get("width") or 0)
    height = float(bounds.get("height") or 0)
    x = float(bounds.get("x") or 0)
    y = float(bounds.get("y") or 0)

    if page_type == "dense_ui_panel":
        if subtype == "table":
            return "description_table"
        if subtype in {"image"} or (width <= 40 and height <= 40):
            return "small_asset"
        if subtype == "connector":
            return "overlay_mark"
        if subtype == "labeled_shape" and text_value.startswith("ISSUE"):
            return "issue_card"
        if subtype == "labeled_shape" and (text_value.startswith("V ") or text_value.startswith("V.")):
            if width < 220 and y < 220:
                return "version_stack"
            if width >= 230 and x >= 680:
                return "description_card"
        if subtype == "text_block":
            if x >= 650 and y < 260:
                return "top_text_row"
            if x >= 650:
                return "description_text_lane"
        if subtype in {"shape", "labeled_shape"} and width >= 120 and height >= 20:
            return "background_card"

    if page_type == "table-heavy":
        if subtype == "table":
            return "table_root"
        if subtype == "table_cell":
            return "table_cell"
        if subtype == "text_block":
            return "table_text" if x > 200 else "section_label"
        if subtype == "connector":
            return "overlay_mark"

    if page_type == "flow-process":
        if subtype == "connector":
            return "connector"
        if subtype == "text_block":
            return "flow_label"
        if subtype in {"shape", "labeled_shape"}:
            return "flow_shape"

    if subtype == "text_block":
        return "text"
    if subtype == "connector":
        return "connector"
    if subtype == "image":
        return "image"
    return subtype or "unknown"


def z_index(layer_role_value: str) -> int:
    order = {
        "background_card": 10,
        "description_card": 12,
        "version_stack": 14,
        "issue_card": 16,
        "top_text_row": 20,
        "description_text_lane": 22,
        "table_root": 24,
        "table_cell": 26,
        "table_text": 28,
        "small_asset": 30,
        "overlay_mark": 32,
        "connector": 34,
        "flow_shape": 12,
        "flow_label": 18,
        "text": 20,
        "image": 24,
        "unknown": 20,
    }
    return order.get(layer_role_value, 20)


def clip_scope(candidate: dict[str, Any], page_type: str) -> str:
    subtype = str(candidate.get("subtype") or "")
    if page_type == "dense_ui_panel" and subtype in {"table", "table_cell", "text_block", "shape", "labeled_shape", "image"}:
        return "dense_ui_panel"
    return "page"


def owner_key(candidate: dict[str, Any], page_type: str) -> str:
    subtype = str(candidate.get("subtype") or "")
    candidate_id = str(candidate.get("candidate_id") or "")
    parent_id = str(candidate.get("parent_candidate_id") or "")
    role = layer_role(candidate, page_type)

    if page_type == "dense_ui_panel":
        if role == "top_text_row":
            return "dense_ui_panel:top_rows"
        if role == "version_stack":
            return "dense_ui_panel:version_stack"
        if role == "issue_card":
            return "dense_ui_panel:issue_card"
        if role == "description_card":
            return "dense_ui_panel:description_cards"
        if role == "description_text_lane":
            return "dense_ui_panel:description_lanes"
        if role == "small_asset":
            return "dense_ui_panel:small_assets"
        if role == "description_table":
            return "dense_ui_panel:description_table"

    if subtype == "table_cell" and parent_id:
        return f"owner:{parent_id}"
    if parent_id:
        return f"owner:{parent_id}"
    return f"owner:{candidate_id}"


def build_atom(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    page_type = context["visual_strategy"]["page_type"]
    scaled = scale_bounds(candidate.get("bounds_px"), context["scale_x"], context["scale_y"])
    start_point = scale_point(((candidate.get("extra") or {}).get("start_point_px")), context["scale_x"], context["scale_y"])
    end_point = scale_point(((candidate.get("extra") or {}).get("end_point_px")), context["scale_x"], context["scale_y"])
    extra = candidate.get("extra") or {}
    return {
        "id": str(candidate.get("candidate_id") or ""),
        "parent_id": str(candidate.get("parent_candidate_id") or ""),
        "source_scope": str(extra.get("source_scope") or "slide"),
        "source_node_id": str(candidate.get("source_node_id") or ""),
        "atom_type": atom_type(candidate),
        "subtype": str(candidate.get("subtype") or ""),
        "pattern_type": page_type,
        "owner_id": owner_key(candidate, page_type),
        "layer_role": layer_role(candidate, page_type),
        "z_index": z_index(layer_role(candidate, page_type)),
        "clip_scope": clip_scope(candidate, page_type),
        "render_mode": render_mode(candidate, page_type),
        "text": str(candidate.get("text") or ""),
        "title": str(candidate.get("title") or ""),
        "source_bounds_px": candidate.get("bounds_px"),
        "visual_bounds_px": scaled,
        "start_point_px": start_point,
        "end_point_px": end_point,
        "shape_kind": str(extra.get("shape_kind") or ""),
        "placeholder": extra.get("placeholder"),
        "connector_adjusts": (extra.get("connector_adjusts") or []),
        "grid_columns": (extra.get("grid_columns") or []),
        "text_style": (extra.get("text_style") or {}),
        "cell_style": (extra.get("cell_style") or {}),
        "debug_tags": {
            "page_type": page_type,
            "source_path": candidate.get("source_path"),
        },
    }


def build_owner_bucket(owner_id: str, atoms: list[dict[str, Any]]) -> dict[str, Any]:
    bounds = union_bounds([atom["visual_bounds_px"] for atom in atoms if atom.get("visual_bounds_px")])
    roles = sorted({str(atom.get("layer_role") or "") for atom in atoms})
    render_modes = sorted({str(atom.get("render_mode") or "") for atom in atoms})
    return {
        "owner_id": owner_id,
        "pattern_type": atoms[0]["pattern_type"] if atoms else "generic",
        "layer_roles": roles,
        "render_modes": render_modes,
        "visual_bounds_px": bounds,
        "atom_ids": [atom["id"] for atom in atoms],
        "atom_count": len(atoms),
    }


def build_page_ir(page: dict[str, Any]) -> dict[str, Any]:
    context = build_page_context(page)
    atoms = [build_atom(candidate, context) for candidate in context["candidates"]]
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for atom in atoms:
        buckets[atom["owner_id"]].append(atom)
    owner_buckets = [build_owner_bucket(owner_id, grouped) for owner_id, grouped in sorted(buckets.items())]
    return {
        "page_id": context["page_id"],
        "slide_no": context["slide_no"],
        "title": context["title"],
        "page_type": context["visual_strategy"]["page_type"],
        "slide_bounds_px": make_bounds(0.0, 0.0, context["width"], context["height"]),
        "signals": context["visual_strategy"]["signals"],
        "atoms": atoms,
        "owner_buckets": owner_buckets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build resolved PPT IR from current intermediate payload.")
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "ppt-intermediate-candidates-12-19-29.json"),
        help="Intermediate candidates JSON path",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "resolved-ppt-ir-12-19-29.json"),
        help="Output JSON path",
    )
    parser.add_argument("--slides", default="12,19,29", help="Comma-separated slide numbers")
    args = parser.parse_args()

    slide_numbers = {int(token.strip()) for token in args.slides.split(",") if token.strip()}
    payload = load_intermediate_payload(args.input)
    pages = list(iter_selected_pages(payload, slide_numbers))
    result = {
        "ir_version": "resolved-ppt-ir-v1",
        "source_kind": "ppt-intermediate",
        "source_file": str(Path(args.input).resolve()),
        "pages": [build_page_ir(page) for page in pages],
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(f"saved {output_path}")
    for page in result["pages"]:
        print(
            f"slide {page['slide_no']}: page_type={page['page_type']} atoms={len(page['atoms'])} owners={len(page['owner_buckets'])}"
        )


if __name__ == "__main__":
    main()
