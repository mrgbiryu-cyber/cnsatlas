#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from ppt_source_extractor import (
    TARGET_SLIDE_HEIGHT,
    TARGET_SLIDE_WIDTH,
    build_page_context,
    build_source_debug,
    identity_affine,
    iter_selected_pages,
    load_intermediate_payload,
    make_bounds,
    normalize_degrees,
    placeholder_key,
    relative_transform_from_bounds,
    scale_bounds,
    scale_point,
    scale_value,
    sort_by_position_key,
)


def solid_paint(style_color: dict[str, Any] | None, fallback: dict[str, float], default_opacity: float = 1.0) -> dict[str, Any]:
    style_color = style_color or {}
    resolved_hex = style_color.get("resolved_value") or style_color.get("value")
    color = fallback
    if isinstance(resolved_hex, str) and len(resolved_hex) == 6:
        color = {
            "r": round(int(resolved_hex[0:2], 16) / 255, 4),
            "g": round(int(resolved_hex[2:4], 16) / 255, 4),
            "b": round(int(resolved_hex[4:6], 16) / 255, 4),
        }
    opacity = style_color.get("alpha", default_opacity)
    return {
        "type": "SOLID",
        "color": color,
        "opacity": opacity,
    }


def has_renderable_fill(shape_style: dict[str, Any] | None) -> bool:
    if not shape_style:
        return False
    fill = shape_style.get("fill") or {}
    if not fill or fill.get("kind") == "none":
        return False
    alpha = fill.get("alpha")
    return alpha is None or alpha > 0


def has_renderable_line(shape_style: dict[str, Any] | None) -> bool:
    if not shape_style:
        return False
    line = shape_style.get("line") or {}
    if not line or line.get("kind") in {"none", "default"}:
        return False
    alpha = line.get("alpha")
    width_px = line.get("width_px")
    if alpha is not None and alpha <= 0:
        return False
    if width_px is not None and width_px <= 0:
        return False
    return True


def build_fill_array(shape_style: dict[str, Any] | None, fallback: dict[str, float]) -> list[dict[str, Any]]:
    if not has_renderable_fill(shape_style):
        return []
    return [solid_paint((shape_style or {}).get("fill"), fallback, 1.0)]


def build_stroke_array(shape_style: dict[str, Any] | None, fallback: dict[str, float]) -> list[dict[str, Any]]:
    if not has_renderable_line(shape_style):
        return []
    return [solid_paint((shape_style or {}).get("line"), fallback, 1.0)]


def map_horizontal_align(value: str | None, fallback: str = "l") -> str:
    raw = (value or fallback or "l").lower()
    if raw in {"ctr", "center", "middle"}:
        return "CENTER"
    if raw in {"r", "right"}:
        return "RIGHT"
    if raw in {"just", "justify", "justified"}:
        return "JUSTIFIED"
    return "LEFT"


def map_vertical_align(value: str | None, fallback: str = "t") -> str:
    raw = (value or fallback or "t").lower()
    if raw in {"ctr", "center", "middle"}:
        return "CENTER"
    if raw in {"b", "bottom"}:
        return "BOTTOM"
    return "TOP"


def clamp_font_size(value: float) -> int:
    return max(8, min(int(round(value)), 72))


def estimate_text_font_size(text_value: str, text_style: dict[str, Any], bounds: dict[str, Any], *, table_cell: bool = False, scale: float = 1.0) -> int:
    explicit = text_style.get("font_size_max") or text_style.get("font_size_avg") or 0
    if explicit:
        return clamp_font_size(float(explicit) * scale)
    width = max(float(bounds.get("width", 120)), 1.0)
    height = max(float(bounds.get("height", 24)), 1.0)
    single_line = "\n" not in (text_value or "")
    short_text = len((text_value or "").strip()) <= 18
    base_by_height = height * (0.56 if single_line and short_text else 0.42)
    rough_capacity = max(int((width - 12) / max(base_by_height * 0.55, 4)), 4)
    multiline_penalty = 0.82 if len(text_value or "") > rough_capacity else 1.0
    width_penalty = 0.86 if width < 120 else 0.94 if width < 220 else 1.0
    local_scale = 0.9 if table_cell else 1.0
    return clamp_font_size(base_by_height * multiline_penalty * width_penalty * local_scale * scale)


def infer_placeholder_font_size(candidate: dict[str, Any], bounds: dict[str, Any], scale: float = 1.0) -> int | None:
    placeholder = ((candidate.get("extra") or {}).get("placeholder") or {})
    ph_type = str(placeholder.get("type") or "").lower()
    if not ph_type:
        return None
    height = max(float(bounds.get("height", 0)), 1.0)
    text_value = str(candidate.get("text") or candidate.get("title") or "")
    if ph_type == "title":
        if len(text_value) <= 24:
            return clamp_font_size(max(height * 0.78, 18) * scale)
        return clamp_font_size(max(height * 0.72, 16) * scale)
    if ph_type == "body":
        if "\n" in text_value:
            return clamp_font_size(max(height * 0.82, 10) * scale)
        return clamp_font_size(max(height * 0.7, 10) * scale)
    return None


def derive_wrap_mode(text_value: str, text_style: dict[str, Any], bounds: dict[str, Any], *, force_wrap: bool = False) -> str:
    if force_wrap or "\n" in (text_value or ""):
        return "wrap"
    raw_wrap = str((text_style or {}).get("wrap") or "").lower()
    if raw_wrap in {"square", "tight", "through"}:
        return "wrap"
    width = float(bounds.get("width", 120))
    if width < 180 and len(text_value or "") > 12:
        return "wrap"
    return "none"


def build_text_style(candidate: dict[str, Any], bounds: dict[str, Any], *, force_wrap: bool = False, table_cell: bool = False, horizontal_fallback: str = "l", vertical_fallback: str = "t", scale: float = 1.0) -> dict[str, Any]:
    text_style = (candidate.get("extra") or {}).get("text_style") or {}
    text_value = candidate.get("text") or candidate.get("title") or ""
    wrap_mode = derive_wrap_mode(text_value, text_style, bounds, force_wrap=force_wrap)
    inferred_placeholder_size = None if table_cell else infer_placeholder_font_size(candidate, bounds, scale)
    font_size = inferred_placeholder_size or estimate_text_font_size(text_value, text_style, bounds, table_cell=table_cell, scale=scale)
    placeholder = ((candidate.get("extra") or {}).get("placeholder") or {})
    text_auto_resize = "HEIGHT" if wrap_mode != "none" or placeholder else "WIDTH_AND_HEIGHT"
    return {
        "fontSize": font_size,
        "fontFamily": text_style.get("font_family") or "Inter",
        "textAlignHorizontal": map_horizontal_align(text_style.get("horizontal_align"), horizontal_fallback),
        "textAlignVertical": map_vertical_align(text_style.get("vertical_align"), vertical_fallback),
        "textAutoResize": text_auto_resize,
        "lineHeightPx": None,
    }


def inset_text_bounds(candidate: dict[str, Any], abs_bounds: dict[str, Any]) -> dict[str, Any]:
    text_style = (candidate.get("extra") or {}).get("text_style") or {}
    left = float(text_style.get("lIns") or 0)
    right = float(text_style.get("rIns") or 0)
    top = float(text_style.get("tIns") or 0)
    bottom = float(text_style.get("bIns") or 0)
    width = max(float(abs_bounds.get("width", 0)) - left - right, 1.0)
    height = max(float(abs_bounds.get("height", 0)) - top - bottom, 1.0)
    return {
        "x": round(float(abs_bounds.get("x", 0)) + left, 2),
        "y": round(float(abs_bounds.get("y", 0)) + top, 2),
        "width": round(width, 2),
        "height": round(height, 2),
    }


def inset_table_text_bounds(candidate: dict[str, Any], abs_bounds: dict[str, Any]) -> dict[str, Any]:
    cell_style = (candidate.get("extra") or {}).get("cell_style") or {}
    left = float(cell_style.get("marL") or 0)
    right = float(cell_style.get("marR") or 0)
    top = float(cell_style.get("marT") or 0)
    bottom = float(cell_style.get("marB") or 0)
    width = max(float(abs_bounds.get("width", 0)) - left - right, 1.0)
    height = max(float(abs_bounds.get("height", 0)) - top - bottom, 1.0)
    return {
        "x": round(float(abs_bounds.get("x", 0)) + left, 2),
        "y": round(float(abs_bounds.get("y", 0)) + top, 2),
        "width": round(width, 2),
        "height": round(height, 2),
    }


def estimate_wrapped_height(text_value: str, candidate: dict[str, Any], width: float, min_height: float, scale: float = 1.0) -> float:
    text_style = (candidate.get("extra") or {}).get("text_style") or {}
    font_size = estimate_text_font_size(text_value, text_style, {"width": width, "height": min_height}, table_cell=True, scale=scale)
    average_char_width = max(font_size * 0.55, 4)
    chars_per_line = max(int((width - 10) / average_char_width), 1)
    explicit_lines = str(text_value or "").split("\n")
    rendered_lines = 0
    for line in explicit_lines:
        length = max(len(line), 1)
        rendered_lines += max(math.ceil(length / chars_per_line), 1)
    line_height = font_size * 1.35
    return max(math.ceil(rendered_lines * line_height + 8), int(min_height))


def resolve_text_bounds(candidate: dict[str, Any], abs_bounds: dict[str, Any], context: dict[str, Any] | None, table_cell: bool) -> dict[str, Any]:
    if table_cell:
        return inset_table_text_bounds(candidate, abs_bounds)
    bounds = candidate.get("bounds_px")
    placeholder = ((candidate.get("extra") or {}).get("placeholder") or {})
    source_scope = str(((candidate.get("extra") or {}).get("source_scope") or "slide")).lower()
    if context and source_scope == "slide" and not bounds and placeholder:
        anchor = context.get("placeholder_anchor_map", {}).get(placeholder_key(placeholder))
        if anchor and anchor.get("bounds_px"):
            return scale_bounds(anchor["bounds_px"], context["scale_x"], context["scale_y"])
    return inset_text_bounds(candidate, abs_bounds)


def should_skip_layout_placeholder_text(candidate: dict[str, Any]) -> bool:
    extra = candidate.get("extra") or {}
    placeholder = extra.get("placeholder") or {}
    source_scope = str(extra.get("source_scope") or "slide").lower()
    if source_scope not in {"layout", "master"} or candidate.get("subtype") != "text_block":
        return False
    text_value = str(candidate.get("text") or candidate.get("title") or "").strip()
    placeholder_type = str(placeholder.get("type") or "").lower()
    if text_value in {"‹#›", "<#>", "Click to edit Master title style"}:
        return True
    if placeholder_type in {"title", "sldnum", "dt", "hdr", "ftr", "body"}:
        return True
    return False


def build_text_node(candidate: dict[str, Any], abs_bounds: dict[str, Any], *, context: dict[str, Any] | None = None, force_wrap: bool = False, table_cell: bool = False, horizontal_fallback: str = "l", vertical_fallback: str = "t", scale: float = 1.0) -> dict[str, Any]:
    text_bounds = resolve_text_bounds(candidate, abs_bounds, context, table_cell)
    return {
        "id": f"{candidate['candidate_id']}:text",
        "type": "TEXT",
        "name": candidate.get("title") or candidate.get("subtype") or "text",
        "characters": candidate.get("text") or candidate.get("title") or "",
        "absoluteBoundingBox": text_bounds,
        "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
        "fills": [solid_paint(((candidate.get("extra") or {}).get("text_style") or {}).get("fill"), {"r": 0.12, "g": 0.12, "b": 0.12}, 1.0)],
        "style": build_text_style(candidate, text_bounds, force_wrap=force_wrap, table_cell=table_cell, horizontal_fallback=horizontal_fallback, vertical_fallback=vertical_fallback, scale=scale),
        "children": [],
        "debug": dict(build_source_debug(candidate), rotation_degrees=normalize_degrees((candidate.get("bounds_px") or {}).get("rotation", 0))),
    }


def build_vector_node(node_id: str, name: str, abs_bounds: dict[str, Any], *, fill_geometry: list[dict[str, Any]] | None = None, stroke_geometry: list[dict[str, Any]] | None = None, fills: list[dict[str, Any]] | None = None, strokes: list[dict[str, Any]] | None = None, stroke_weight: float = 1.0, debug: dict[str, Any] | None = None, relative_transform: list[list[float]] | None = None) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "VECTOR",
        "name": name,
        "absoluteBoundingBox": abs_bounds,
        "relativeTransform": relative_transform or identity_affine(),
        "fillGeometry": fill_geometry or [],
        "strokeGeometry": stroke_geometry or [],
        "fills": fills or [],
        "strokes": strokes or [],
        "strokeWeight": stroke_weight,
        "children": [],
        "debug": debug or {},
    }


def rect_path(width: float, height: float) -> str:
    return f"M 0 0 H {width} V {height} H 0 Z"


def rounded_rect_path(width: float, height: float, radius: float) -> str:
    r = max(0.0, min(radius, width / 2, height / 2))
    if r <= 0:
        return rect_path(width, height)
    return (
        f"M {r} 0 H {width - r} "
        f"Q {width} 0 {width} {r} "
        f"V {height - r} "
        f"Q {width} {height} {width - r} {height} "
        f"H {r} "
        f"Q 0 {height} 0 {height - r} "
        f"V {r} "
        f"Q 0 0 {r} 0 Z"
    )


def diamond_path(width: float, height: float) -> str:
    mid_x = width / 2
    mid_y = height / 2
    return f"M {mid_x} 0 L {width} {mid_y} L {mid_x} {height} L 0 {mid_y} Z"


def ellipse_path(width: float, height: float) -> str:
    rx = width / 2
    ry = height / 2
    return f"M {rx} 0 A {rx} {ry} 0 1 1 {rx} {height} A {rx} {ry} 0 1 1 {rx} 0 Z"


def build_shape_node(candidate: dict[str, Any], abs_bounds: dict[str, Any], scale: float = 1.0) -> dict[str, Any]:
    extra = candidate.get("extra") or {}
    shape_style = extra.get("shape_style") or {}
    shape_kind = extra.get("shape_kind") or ""
    relative_transform = relative_transform_from_bounds(candidate.get("bounds_px"))
    debug = dict(build_source_debug(candidate), full_page_overlay_candidate=bool(extra.get("full_page_overlay_candidate")))
    path = rect_path(abs_bounds["width"], abs_bounds["height"])
    if shape_kind == "flowChartDecision":
        path = diamond_path(abs_bounds["width"], abs_bounds["height"])
    elif shape_kind == "ellipse":
        path = ellipse_path(abs_bounds["width"], abs_bounds["height"])
    elif shape_kind == "rightBracket":
        w = abs_bounds["width"]
        h = abs_bounds["height"]
        path = f"M {w * 0.2} 0 L {w} 0 L {w} {h} L {w * 0.2} {h}"
    elif shape_kind == "roundRect":
        path = rounded_rect_path(abs_bounds["width"], abs_bounds["height"], min(abs_bounds["height"] * 0.18, 12 * scale))
    fills = [] if shape_kind == "rightBracket" else build_fill_array(shape_style, {"r": 1, "g": 1, "b": 1})
    strokes = build_stroke_array(shape_style, {"r": 0.28, "g": 0.28, "b": 0.28})
    return build_vector_node(
        candidate["candidate_id"],
        candidate.get("title") or candidate.get("subtype") or "shape",
        abs_bounds,
        fill_geometry=[{"path": path, "windingRule": "NONZERO"}] if fills else [],
        stroke_geometry=[{"path": path}] if strokes else [],
        fills=fills,
        strokes=strokes,
        stroke_weight=max(float(((shape_style.get("line") or {}).get("width_px") or 1)) * scale, 1.0),
        debug=debug,
        relative_transform=relative_transform,
    )


def build_connector_node(candidate: dict[str, Any], abs_bounds: dict[str, Any], scale_x: float, scale_y: float) -> dict[str, Any]:
    extra = candidate.get("extra") or {}
    shape_style = extra.get("shape_style") or {}
    kind = extra.get("shape_kind") or "connector"
    stroke_weight = max(float(((shape_style.get("line") or {}).get("width_px") or 1.5)) * min(scale_x, scale_y), 1.0)
    local_width = max(abs_bounds["width"], 6)
    local_height = max(abs_bounds["height"], 6)
    relative_transform = identity_affine()

    def readable_elbow(start: dict[str, float], end: dict[str, float], kind_name: str, adjusts: dict[str, Any]) -> list[dict[str, float]]:
        lead_margin = 16
        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]
        if abs(dx) <= 4 or abs(dy) <= 4:
            return [start, end]
        horizontal = abs(dx) >= abs(dy)
        if kind_name == "straightConnector1":
            if horizontal:
                return [start, {"x": end["x"], "y": start["y"]}, end]
            return [start, {"x": start["x"], "y": end["y"]}, end]
        if kind_name == "bentConnector2":
            if horizontal:
                return [start, {"x": end["x"], "y": start["y"]}, end]
            return [start, {"x": start["x"], "y": end["y"]}, end]
        if kind_name == "bentConnector3":
            adj1 = adjusts.get("adj1", 50000) / 100000
            if horizontal:
                mid_x = start["x"] + (end["x"] - start["x"]) * adj1
                return [start, {"x": mid_x, "y": start["y"]}, {"x": mid_x, "y": end["y"]}, end]
            mid_y = start["y"] + (end["y"] - start["y"]) * adj1
            return [start, {"x": start["x"], "y": mid_y}, {"x": end["x"], "y": mid_y}, end]
        if kind_name == "bentConnector4":
            adj1 = adjusts.get("adj1", 50000) / 100000
            if horizontal:
                mid_x = start["x"] + (end["x"] - start["x"]) * adj1
                return [start, {"x": mid_x, "y": start["y"]}, {"x": mid_x, "y": end["y"]}, end]
            mid_y = start["y"] + (end["y"] - start["y"]) * adj1
            return [start, {"x": start["x"], "y": mid_y}, {"x": end["x"], "y": mid_y}, end]
        if horizontal:
            route_y = start["y"] + (lead_margin if dy >= 0 else -lead_margin)
            return [start, {"x": start["x"], "y": route_y}, {"x": end["x"], "y": route_y}, end]
        route_x = start["x"] + (lead_margin if dx >= 0 else -lead_margin)
        return [start, {"x": route_x, "y": start["y"]}, {"x": route_x, "y": end["y"]}, end]

    start_px = scale_point(extra.get("start_point_px"), scale_x, scale_y)
    end_px = scale_point(extra.get("end_point_px"), scale_x, scale_y)
    adjusts = extra.get("connector_adjusts") or {}
    if start_px and end_px:
        points = readable_elbow(start_px, end_px, kind, adjusts)
    elif kind == "straightConnector1":
        points = [
            {"x": abs_bounds["x"], "y": abs_bounds["y"] + local_height / 2},
            {"x": abs_bounds["x"] + local_width, "y": abs_bounds["y"] + local_height / 2},
        ]
    else:
        points = [
            {"x": abs_bounds["x"], "y": abs_bounds["y"]},
            {"x": abs_bounds["x"], "y": abs_bounds["y"] + local_height * 0.5},
            {"x": abs_bounds["x"] + local_width, "y": abs_bounds["y"] + local_height * 0.5},
            {"x": abs_bounds["x"] + local_width, "y": abs_bounds["y"] + local_height},
        ]

    min_x = min(point["x"] for point in points)
    min_y = min(point["y"] for point in points)
    max_x = max(point["x"] for point in points)
    max_y = max(point["y"] for point in points)
    arrow_margin = max(stroke_weight * 6, 8)
    absolute_bounds = make_bounds(
        min_x - arrow_margin / 2,
        min_y - arrow_margin / 2,
        (max_x - min_x) + arrow_margin,
        (max_y - min_y) + arrow_margin,
    )
    localized_points = [
        {"x": round(point["x"] - absolute_bounds["x"], 2), "y": round(point["y"] - absolute_bounds["y"], 2)}
        for point in points
    ]

    stroke_path = " ".join(("M" if i == 0 else "L") + f" {round(p['x'],2)} {round(p['y'],2)}" for i, p in enumerate(localized_points))
    arrow_paths: list[str] = []
    tail_end = (shape_style.get("line") or {}).get("tail_end") or {}
    head_end = (shape_style.get("line") or {}).get("head_end") or {}

    def append_arrow(points_for_head: list[dict[str, float]], point_index: int, prev_index: int) -> None:
        tip = points_for_head[point_index]
        prev = points_for_head[prev_index]
        dx = tip["x"] - prev["x"]
        dy = tip["y"] - prev["y"]
        angle = math.atan2(dy, dx)
        size = max(8 * min(scale_x, scale_y), 6)
        back_x = tip["x"] - math.cos(angle) * size
        back_y = tip["y"] - math.sin(angle) * size
        left_x = back_x + math.cos(angle + math.pi / 2) * size * 0.45
        left_y = back_y + math.sin(angle + math.pi / 2) * size * 0.45
        right_x = back_x + math.cos(angle - math.pi / 2) * size * 0.45
        right_y = back_y + math.sin(angle - math.pi / 2) * size * 0.45
        arrow_paths.append(
            f"M {round(tip['x'],2)} {round(tip['y'],2)} L {round(left_x,2)} {round(left_y,2)} L {round(right_x,2)} {round(right_y,2)} Z"
        )

    # PPT connector arrow metadata tends to indicate the visible head at the
    # line end even when tail_end is set. Prefer visual fidelity here.
    if head_end.get("type") == "triangle" and len(localized_points) >= 2:
        append_arrow(localized_points, 0, 1)
    if tail_end.get("type") == "triangle" and len(localized_points) >= 2:
        append_arrow(localized_points, len(localized_points) - 1, len(localized_points) - 2)

    line_color = solid_paint((shape_style.get("line") or {}), {"r": 0, "g": 0, "b": 0}, 1.0)
    connector_name = candidate.get("title") or candidate.get("subtype") or "connector"
    line_node = build_vector_node(
        f"{candidate['candidate_id']}:line",
        f"{connector_name}:line",
        absolute_bounds,
        stroke_geometry=[{"path": stroke_path}],
        fills=[],
        strokes=[line_color],
        stroke_weight=stroke_weight,
        debug=build_source_debug(candidate),
        relative_transform=relative_transform,
    )
    if not arrow_paths:
        return line_node
    children = [line_node]
    for index, path in enumerate(arrow_paths, start=1):
        children.append(
            build_vector_node(
                f"{candidate['candidate_id']}:arrow_{index}",
                f"{connector_name}:arrow_{index}",
                absolute_bounds,
                fill_geometry=[{"path": path, "windingRule": "NONZERO"}],
                stroke_geometry=[],
                fills=[line_color],
                strokes=[],
                stroke_weight=stroke_weight,
                debug=build_source_debug(candidate),
                relative_transform=relative_transform,
            )
        )
    return {
        "id": candidate["candidate_id"],
        "type": "GROUP",
        "name": connector_name,
        "absoluteBoundingBox": absolute_bounds,
        "relativeTransform": relative_transform,
        "children": children,
        "debug": build_source_debug(candidate),
    }


def build_image_node(candidate: dict[str, Any], abs_bounds: dict[str, Any], assets: dict[str, Any], scale: float = 1.0) -> dict[str, Any]:
    extra = candidate.get("extra") or {}
    image_ref = extra.get("image_ref") or candidate.get("source_node_id") or candidate.get("candidate_id")
    mime_type = extra.get("mime_type") or "image/png"
    base64_value = extra.get("image_base64")
    if image_ref and base64_value:
        assets[image_ref] = {
            "filename": extra.get("filename") or f"{image_ref}.png",
            "mime_type": mime_type,
            "base64": base64_value,
        }
    return {
        "id": candidate["candidate_id"],
        "type": "RECTANGLE",
        "name": candidate.get("title") or "image",
        "absoluteBoundingBox": abs_bounds,
        "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
        "fills": [{
            "type": "IMAGE",
            "imageRef": image_ref,
            "scaleMode": "FILL",
        }] if image_ref else [],
        "strokes": [],
        "strokeWeight": 0,
        "children": [],
        "debug": build_source_debug(candidate),
    }


def build_table_node(candidate: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    scale_x = context["scale_x"]
    scale_y = context["scale_y"]
    page_offset_x = 0.0
    page_offset_y = 0.0
    children_map = context["children_map"]
    bounds = candidate.get("bounds_px") or {"x": 0, "y": 0, "width": 120, "height": 40}
    abs_bounds = make_bounds(page_offset_x + scale_value(bounds["x"], scale_x), page_offset_y + scale_value(bounds["y"], scale_y), scale_value(bounds["width"], scale_x), scale_value(bounds["height"], scale_y))
    extra = candidate.get("extra") or {}
    shape_style = extra.get("shape_style") or {}
    table_node = {
        "id": candidate["candidate_id"],
        "type": "GROUP",
        "name": candidate.get("title") or "table",
        "absoluteBoundingBox": abs_bounds,
        "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
        "children": [],
        "debug": build_source_debug(candidate),
    }
    rows = sorted([child for child in children_map.get(candidate["candidate_id"], []) if child.get("subtype") == "table_row"], key=sort_by_position_key)
    grid_columns = extra.get("grid_columns") or []
    row_cursor_y = abs_bounds["y"]
    scaled_row_heights: dict[str, float] = {}
    for row_candidate in rows:
        scaled_row_heights[row_candidate["candidate_id"]] = max(scale_value((row_candidate.get("extra") or {}).get("row_height_px") or 28, scale_y), 21.0)

    for row_candidate in rows:
        cell_candidates = [child for child in children_map.get(row_candidate["candidate_id"], []) if child.get("subtype") == "table_cell"]
        row_height = scaled_row_heights[row_candidate["candidate_id"]]
        for cell_candidate in cell_candidates:
            cell_extra = cell_candidate.get("extra") or {}
            if cell_extra.get("h_merge") or cell_extra.get("v_merge"):
                continue
            cell_width = scale_value(cell_extra.get("width_px") or (abs_bounds["width"] / max(len(cell_candidates), 1)), scale_x if cell_extra.get("width_px") else 1.0)
            row_height = max(row_height, estimate_wrapped_height(cell_candidate.get("text") or cell_candidate.get("title") or "", cell_candidate, cell_width, row_height, min(scale_x, scale_y)))
        row_abs_bounds = make_bounds(abs_bounds["x"], row_cursor_y, abs_bounds["width"], row_height)
        for cell_candidate in cell_candidates:
            cell_extra = cell_candidate.get("extra") or {}
            if cell_extra.get("h_merge") or cell_extra.get("v_merge"):
                continue
            start_column_index = int(cell_extra.get("start_column_index") or 1)
            cell_width = scale_value(cell_extra.get("width_px") or (row_abs_bounds["width"] / max(len(cell_candidates), 1)), scale_x if cell_extra.get("width_px") else 1.0)
            if grid_columns:
                cell_x = sum(scale_value(column.get("width_px") or 0, scale_x) for column in grid_columns if int(column.get("column_index") or 0) < start_column_index)
            else:
                rendered_cells = [child for child in table_node["children"] if str(child.get("id", "")).startswith(f"{row_candidate['candidate_id']}:cell")]
                cell_x = sum(float(child["absoluteBoundingBox"]["width"]) for child in rendered_cells)
            row_span = int(cell_extra.get("row_span") or 1)
            spanned_height = row_height
            if row_span > 1:
                current_index = rows.index(row_candidate)
                spanned_height = sum(scaled_row_heights[rows[i]["candidate_id"]] for i in range(current_index, min(current_index + row_span, len(rows))))
            cell_abs_bounds = make_bounds(row_abs_bounds["x"] + cell_x, row_abs_bounds["y"], cell_width, spanned_height)
            cell_style = cell_extra.get("cell_style") or {}
            fills = [solid_paint(cell_style.get("fill"), {"r": 1, "g": 1, "b": 1}, 1.0)] if cell_style.get("fill") else [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}}]
            cell_path = rect_path(cell_abs_bounds["width"], cell_abs_bounds["height"])
            cell_node = build_vector_node(
                f"{cell_candidate['candidate_id']}:cell",
                cell_candidate.get("title") or f"cell {start_column_index}",
                cell_abs_bounds,
                fill_geometry=[{"path": cell_path, "windingRule": "NONZERO"}] if fills else [],
                stroke_geometry=[{"path": cell_path}],
                fills=fills,
                strokes=[{"type": "SOLID", "color": {"r": 0.75, "g": 0.75, "b": 0.75}}],
                stroke_weight=max(min(scale_x, scale_y), 1),
                debug=build_source_debug(cell_candidate),
                relative_transform=relative_transform_from_bounds(cell_candidate.get("bounds_px")),
            )
            table_node["children"].append(cell_node)
            if cell_candidate.get("text"):
                cell_text = str(cell_candidate.get("text") or "")
                is_header_cell = bool(cell_style.get("fill"))
                horizontal_fallback = "ctr" if is_header_cell or (len(cell_text) <= 18 and "\n" not in cell_text) else "l"
                table_node["children"].append(
                    build_text_node(
                        cell_candidate,
                        cell_abs_bounds,
                        context=context,
                        force_wrap=True,
                        table_cell=True,
                        horizontal_fallback=horizontal_fallback,
                        vertical_fallback=(cell_style.get("anchor") or "ctr"),
                        scale=min(scale_x, scale_y),
                    )
                )
        row_cursor_y += row_height
    return table_node


def build_visual_node_from_candidate(candidate: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any] | None:
    scale_x = context["scale_x"]
    scale_y = context["scale_y"]
    bounds = candidate.get("bounds_px") or {"x": 0, "y": 0, "width": 120, "height": 24}
    abs_bounds = make_bounds(scale_value(bounds["x"], scale_x), scale_value(bounds["y"], scale_y), scale_value(bounds["width"], scale_x), scale_value(bounds["height"], scale_y))
    subtype = candidate.get("subtype")
    node_type = candidate.get("node_type")
    children_map = context["children_map"]

    if node_type == "asset" and subtype == "image":
        return build_image_node(candidate, abs_bounds, assets, min(scale_x, scale_y))
    if subtype == "text_block":
        if should_skip_layout_placeholder_text(candidate):
            return None
        return build_text_node(candidate, abs_bounds, context=context, scale=min(scale_x, scale_y))
    if subtype == "connector":
        return build_connector_node(candidate, abs_bounds, scale_x, scale_y)
    if subtype == "table":
        return build_table_node(candidate, context, assets)
    if subtype in {"table_row", "table_cell"}:
        return None
    if subtype in {"group", "section_block"}:
        node = {
            "id": candidate["candidate_id"],
            "type": "GROUP",
            "name": candidate.get("title") or subtype or "group",
            "absoluteBoundingBox": abs_bounds,
            "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
            "children": [],
            "debug": build_source_debug(candidate),
        }
        for child in sorted(children_map.get(candidate["candidate_id"], []), key=sort_by_position_key):
            child_node = build_visual_node_from_candidate(child, context, assets)
            if child_node:
                node["children"].append(child_node)
        return node
    if subtype == "labeled_shape":
        child_text = build_text_node(candidate, abs_bounds, context=context, horizontal_fallback="ctr", vertical_fallback="ctr", scale=min(scale_x, scale_y))
        return {
            "id": candidate["candidate_id"],
            "type": "GROUP",
            "name": candidate.get("title") or subtype or "labeled_shape",
            "absoluteBoundingBox": abs_bounds,
            "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
            "children": [build_shape_node(candidate, abs_bounds, min(scale_x, scale_y)), child_text],
            "debug": build_source_debug(candidate),
        }
    if subtype == "shape":
        return build_shape_node(candidate, abs_bounds, min(scale_x, scale_y))
    return None


def build_page_root(context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    root_bounds = {
        "x": 0.0,
        "y": 0.0,
        "width": TARGET_SLIDE_WIDTH,
        "height": TARGET_SLIDE_HEIGHT,
    }
    page_name = f"Slide {context['slide_no']} - {context['title']}"
    inner_frame = {
        "id": f"{context['page_id']}:frame",
        "type": "FRAME",
        "name": "Frame",
        "absoluteBoundingBox": root_bounds,
        "relativeTransform": identity_affine(),
        "fills": [],
        "strokes": [],
        "strokeWeight": 0,
        "children": [],
        "debug": {
            "generator": "visual-first-v1",
            "source_slide_no": context["slide_no"],
            "source_title": context["title"],
        },
    }
    root = {
        "id": context["page_id"],
        "type": "FRAME",
        "name": page_name,
        "absoluteBoundingBox": root_bounds,
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}}],
        "strokes": [],
        "strokeWeight": 0,
        "children": [inner_frame],
        "debug": {
            "generator": "visual-first-v1",
            "source_slide_no": context["slide_no"],
            "source_title": context["title"],
        },
    }
    for candidate in context["roots"]:
        child = build_visual_node_from_candidate(candidate, context, assets)
        if child:
            inner_frame["children"].append(child)
    return root


def build_bundle_from_page(page: dict[str, Any], source_file: str) -> dict[str, Any]:
    context = build_page_context(page)
    assets: dict[str, Any] = {}
    root = build_page_root(context, assets)
    return {
        "kind": "figma-replay-bundle",
        "source_kind": "ppt-visual-first",
        "visual_model_version": "v1",
        "source_file": source_file,
        "file_name": Path(source_file).name,
        "page_name": root["name"],
        "node_id": root["id"],
        "document": root,
        "assets": assets,
        "missing_assets": [],
        "debug": {
            "status": "visual_first_generator",
            "candidate_count": len(context["candidates"]),
            "root_candidate_count": len(context["roots"]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build visual-first replay bundle from PPT intermediate JSON.")
    parser.add_argument("--input", required=True, help="Intermediate candidates JSON path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--slides", nargs="*", type=int, help="Optional slide numbers")
    args = parser.parse_args()

    payload = load_intermediate_payload(args.input)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = iter_selected_pages(payload, set(args.slides) if args.slides else None)
    for page in selected:
        bundle = build_bundle_from_page(page, str(Path(args.input).resolve()))
        output_path = output_dir / f"visual-slide-{page['slide_no']}.bundle.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(bundle, handle, ensure_ascii=False, indent=2)
        print(f"saved {output_path}")


if __name__ == "__main__":
    main()
