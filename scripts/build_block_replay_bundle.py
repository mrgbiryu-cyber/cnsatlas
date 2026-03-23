#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import textwrap
from pathlib import Path
from typing import Any

from build_visual_first_replay_bundle import (
    build_connector_node,
    build_rectangle_node,
    build_shape_node,
    build_table_node,
    build_text_node,
    build_text_style,
    build_visual_node_from_candidate,
    should_skip_layout_placeholder_text,
)
from detect_visual_blocks import build_blocks_for_page
from ppt_source_extractor import (
    TARGET_SLIDE_HEIGHT,
    TARGET_SLIDE_WIDTH,
    build_page_context,
    identity_affine,
    iter_selected_pages,
    load_intermediate_payload,
    make_bounds,
    scale_point,
    scale_value,
    sort_by_position_key,
)


def build_block_frame(block: dict[str, Any]) -> dict[str, Any]:
    bounds = block["bounds"]
    return {
        "id": block["block_id"],
        "type": "FRAME",
        "name": block["block_type"],
        "absoluteBoundingBox": bounds,
        "relativeTransform": identity_affine(),
        "fills": [],
        "strokes": [],
        "strokeWeight": 0,
        "children": [],
        "debug": {
            "generator": "block-prototype-v1",
            "block_type": block["block_type"],
            "render_mode": block["render_mode"],
            "page_type": block["page_type"],
            "root_candidate_ids": block["root_candidate_ids"],
        },
    }


def collect_block_candidates(block: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {candidate["candidate_id"]: candidate for candidate in context["candidates"]}
    children_map = context["children_map"]
    queue = list(block["root_candidate_ids"])
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    while queue:
        candidate_id = queue.pop(0)
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        candidate = by_id.get(candidate_id)
        if not candidate:
            continue
        ordered.append(candidate)
        for child in sorted(children_map.get(candidate_id, []), key=sort_by_position_key):
            queue.append(child["candidate_id"])
    return ordered


def build_block_group_node(block: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "id": block["block_id"],
        "type": "GROUP",
        "name": block["block_type"],
        "absoluteBoundingBox": block["bounds"],
        "relativeTransform": identity_affine(),
        "children": [],
        "debug": {
            "generator": "block-prototype-v1",
            "block_type": block["block_type"],
            "render_mode": block["render_mode"],
            "page_type": block["page_type"],
            "role": role,
            "root_candidate_ids": block["root_candidate_ids"],
        },
    }


def style_color_to_svg(style_color: dict[str, Any] | None, fallback: str) -> tuple[str, float]:
    style_color = style_color or {}
    resolved_hex = style_color.get("resolved_value") or style_color.get("value")
    if isinstance(resolved_hex, str) and len(resolved_hex) == 6:
        return f"#{resolved_hex}", float(style_color.get("alpha") if style_color.get("alpha") is not None else 1.0)
    return fallback, float(style_color.get("alpha") if style_color.get("alpha") is not None else 1.0)


def local_bounds(bounds: dict[str, Any], origin: dict[str, Any]) -> dict[str, float]:
    return {
        "x": round(float(bounds["x"]) - float(origin["x"]), 2),
        "y": round(float(bounds["y"]) - float(origin["y"]), 2),
        "width": round(float(bounds["width"]), 2),
        "height": round(float(bounds["height"]), 2),
    }


def svg_escape(text: str) -> str:
    return html.escape(str(text or ""), quote=False)


def wrap_text_lines(text: str, max_chars: int) -> list[str]:
    raw_lines = str(text or "").splitlines() or [str(text or "")]
    output: list[str] = []
    for line in raw_lines:
        if len(line) <= max_chars:
            output.append(line)
            continue
        output.extend(textwrap.wrap(line, width=max_chars, break_long_words=False, break_on_hyphens=False) or [line])
    return output


def text_svg_markup(
    text_value: str,
    bounds: dict[str, float],
    *,
    font_size: float,
    fill_hex: str,
    fill_opacity: float,
    font_family: str,
    horizontal_align: str = "LEFT",
    vertical_align: str = "TOP",
    l_ins: float = 2.0,
    r_ins: float = 2.0,
    t_ins: float = 2.0,
    b_ins: float = 2.0,
) -> str:
    lines = wrap_text_lines(text_value, max(1, int(max((bounds["width"] - l_ins - r_ins) / max(font_size * 0.62, 4), 1))))
    line_height = font_size * 1.25
    content_height = len(lines) * line_height
    x = bounds["x"] + l_ins
    anchor = "start"
    if horizontal_align == "CENTER":
        x = bounds["x"] + bounds["width"] / 2
        anchor = "middle"
    elif horizontal_align == "RIGHT":
        x = bounds["x"] + bounds["width"] - r_ins
        anchor = "end"
    y = bounds["y"] + t_ins + font_size
    if vertical_align == "CENTER":
        y = bounds["y"] + (bounds["height"] - content_height) / 2 + font_size
    elif vertical_align == "BOTTOM":
        y = bounds["y"] + bounds["height"] - b_ins - content_height + font_size
    parts = [
        f'<text x="{round(x,2)}" y="{round(y,2)}" font-size="{font_size}" fill="{fill_hex}" fill-opacity="{fill_opacity}" text-anchor="{anchor}" font-family="{svg_escape(font_family)}">'
    ]
    for idx, line in enumerate(lines):
        dy = 0 if idx == 0 else line_height
        parts.append(f'<tspan x="{round(x,2)}" dy="{round(dy,2)}">{svg_escape(line)}</tspan>')
    parts.append("</text>")
    return "".join(parts)


def render_candidate_svg(candidate: dict[str, Any], abs_bounds: dict[str, Any], block_bounds: dict[str, Any], context: dict[str, Any]) -> str:
    subtype = candidate.get("subtype")
    extra = candidate.get("extra") or {}
    local = local_bounds(abs_bounds, block_bounds)
    if subtype == "text_block":
        if should_skip_layout_placeholder_text(candidate):
            return ""
        text_value = str(candidate.get("text") or candidate.get("title") or "").strip()
        if not text_value:
            return ""
        style = build_text_style(candidate, abs_bounds, scale=min(context["scale_x"], context["scale_y"]))
        fill_hex, fill_opacity = style_color_to_svg((extra.get("text_style") or {}).get("fill"), "#111111")
        text_style = extra.get("text_style") or {}
        return text_svg_markup(
            text_value,
            local,
            font_size=style.get("fontSize") or 12,
            fill_hex=fill_hex,
            fill_opacity=fill_opacity,
            font_family=style.get("fontFamily") or "Arial",
            horizontal_align=style.get("textAlignHorizontal") or "LEFT",
            vertical_align=style.get("textAlignVertical") or "TOP",
            l_ins=float(text_style.get("lIns") or 2),
            r_ins=float(text_style.get("rIns") or 2),
            t_ins=float(text_style.get("tIns") or 2),
            b_ins=float(text_style.get("bIns") or 2),
        )
    if subtype == "connector":
        raw = candidate.get("bounds_px") or {}
        stroke_hex, stroke_opacity = style_color_to_svg(((extra.get("shape_style") or {}).get("line") or {}), "#777777")
        scale_x = context["scale_x"]
        scale_y = context["scale_y"]
        start_px = scale_point(extra.get("start_point_px"), scale_x, scale_y)
        end_px = scale_point(extra.get("end_point_px"), scale_x, scale_y)
        kind = str(extra.get("shape_kind") or "straightConnector1")
        if start_px and end_px:
            start = {"x": round(start_px["x"] - block_bounds["x"], 2), "y": round(start_px["y"] - block_bounds["y"], 2)}
            end = {"x": round(end_px["x"] - block_bounds["x"], 2), "y": round(end_px["y"] - block_bounds["y"], 2)}
            points = [start]
            start_conn = extra.get("start_connection") or {}
            end_conn = extra.get("end_connection") or {}

            def dir_from_idx(value: Any) -> str:
                mapping = {0: "up", 1: "right", 2: "down", 3: "left", 4: "up", 5: "right", 6: "down", 7: "left"}
                try:
                    return mapping.get(int(value), "")
                except Exception:
                    return ""

            def offset_point(point: dict[str, float], direction: str, amount: float) -> dict[str, float]:
                if direction == "up":
                    return {"x": point["x"], "y": point["y"] - amount}
                if direction == "down":
                    return {"x": point["x"], "y": point["y"] + amount}
                if direction == "left":
                    return {"x": point["x"] - amount, "y": point["y"]}
                if direction == "right":
                    return {"x": point["x"] + amount, "y": point["y"]}
                return {"x": point["x"], "y": point["y"]}

            start_dir = dir_from_idx(start_conn.get("idx"))
            end_dir = dir_from_idx(end_conn.get("idx"))
            lead = 10.0
            if start_dir or end_dir:
                start_exit = offset_point(start, start_dir, lead)
                end_entry = offset_point(end, end_dir, -lead)
                points = [start, start_exit]
                if abs(end_entry["x"] - start_exit["x"]) >= abs(end_entry["y"] - start_exit["y"]):
                    points.extend([{"x": end_entry["x"], "y": start_exit["y"]}, end_entry])
                else:
                    points.extend([{"x": start_exit["x"], "y": end_entry["y"]}, end_entry])
            if kind == "bentConnector2":
                points.append({"x": start["x"], "y": end["y"]})
            elif kind in {"bentConnector3", "bentConnector4"}:
                if abs(end["x"] - start["x"]) >= abs(end["y"] - start["y"]):
                    mid_x = round((start["x"] + end["x"]) / 2, 2)
                    points.extend([{"x": mid_x, "y": start["y"]}, {"x": mid_x, "y": end["y"]}])
                else:
                    mid_y = round((start["y"] + end["y"]) / 2, 2)
                    points.extend([{"x": start["x"], "y": mid_y}, {"x": end["x"], "y": mid_y}])
            points.append(end)
            path = "M " + " L ".join(f"{p['x']} {p['y']}" for p in points)
            arrow_svg = ""
            if len(points) >= 2:
                p1 = points[-2]
                p2 = points[-1]
                dx = p2["x"] - p1["x"]
                dy = p2["y"] - p1["y"]
                size = 6
                if end_dir == "left":
                    dx, dy = -1, 0
                elif end_dir == "right":
                    dx, dy = 1, 0
                elif end_dir == "up":
                    dx, dy = 0, -1
                elif end_dir == "down":
                    dx, dy = 0, 1
                if abs(dx) >= abs(dy):
                    if dx >= 0:
                        arrow = [(p2["x"], p2["y"]), (p2["x"] - size, p2["y"] - size / 2), (p2["x"] - size, p2["y"] + size / 2)]
                    else:
                        arrow = [(p2["x"], p2["y"]), (p2["x"] + size, p2["y"] - size / 2), (p2["x"] + size, p2["y"] + size / 2)]
                else:
                    if dy >= 0:
                        arrow = [(p2["x"], p2["y"]), (p2["x"] - size / 2, p2["y"] - size), (p2["x"] + size / 2, p2["y"] - size)]
                    else:
                        arrow = [(p2["x"], p2["y"]), (p2["x"] - size / 2, p2["y"] + size), (p2["x"] + size / 2, p2["y"] + size)]
                arrow_points = " ".join(f"{round(x,2)},{round(y,2)}" for x, y in arrow)
                arrow_svg = f'<polygon points="{arrow_points}" fill="{stroke_hex}" fill-opacity="{stroke_opacity}" />'
            return f'<path d="{path}" fill="none" stroke="{stroke_hex}" stroke-opacity="{stroke_opacity}" stroke-width="1.5" />{arrow_svg}'
        width = max(local["width"], 1.0)
        height = max(local["height"], 1.0)
        x0 = local["x"]
        y0 = local["y"]
        x1 = local["x"] + width
        y1 = local["y"] + height
        if width >= height:
            return f'<line x1="{round(x0,2)}" y1="{round(y0 + height/2,2)}" x2="{round(x1,2)}" y2="{round(y0 + height/2,2)}" stroke="{stroke_hex}" stroke-opacity="{stroke_opacity}" stroke-width="1.5" />'
        return f'<line x1="{round(x0 + width/2,2)}" y1="{round(y0,2)}" x2="{round(x0 + width/2,2)}" y2="{round(y1,2)}" stroke="{stroke_hex}" stroke-opacity="{stroke_opacity}" stroke-width="1.5" />'
    if subtype == "image":
        image_base64 = extra.get("image_base64")
        mime_type = extra.get("mime_type") or "image/png"
        if image_base64:
            return (
                f'<image x="{round(local["x"],2)}" y="{round(local["y"],2)}" '
                f'width="{round(local["width"],2)}" height="{round(local["height"],2)}" '
                f'href="data:{mime_type};base64,{image_base64}" preserveAspectRatio="xMidYMid meet" />'
            )
        return ""
    if subtype in {"shape", "labeled_shape"}:
        shape_kind = str(extra.get("shape_kind") or "").lower()
        fill_hex, fill_opacity = style_color_to_svg(((extra.get("shape_style") or {}).get("fill") or {}), "#ffffff")
        line_hex, line_opacity = style_color_to_svg(((extra.get("shape_style") or {}).get("line") or {}), "#444444")
        has_fill = ((extra.get("shape_style") or {}).get("fill") or {}).get("kind") != "none"
        has_stroke = ((extra.get("shape_style") or {}).get("line") or {}).get("kind") not in {"none", "default"}
        fill_attr = f'fill="{fill_hex}" fill-opacity="{fill_opacity}"' if has_fill else 'fill="none"'
        stroke_attr = f'stroke="{line_hex}" stroke-opacity="{line_opacity}" stroke-width="1"' if has_stroke else 'stroke="none"'
        if shape_kind == "flowchartdecision":
            cx = local["x"] + local["width"] / 2
            cy = local["y"] + local["height"] / 2
            points = [
                f"{round(cx,2)},{round(local['y'],2)}",
                f"{round(local['x'] + local['width'],2)},{round(cy,2)}",
                f"{round(cx,2)},{round(local['y'] + local['height'],2)}",
                f"{round(local['x'],2)},{round(cy,2)}",
            ]
            shape_svg = f'<polygon points="{" ".join(points)}" {fill_attr} {stroke_attr} />'
        elif shape_kind == "ellipse":
            shape_svg = f'<ellipse cx="{round(local["x"] + local["width"]/2,2)}" cy="{round(local["y"] + local["height"]/2,2)}" rx="{round(local["width"]/2,2)}" ry="{round(local["height"]/2,2)}" {fill_attr} {stroke_attr} />'
        else:
            rx = 8 if shape_kind == "roundrect" else 0
            shape_svg = f'<rect x="{round(local["x"],2)}" y="{round(local["y"],2)}" width="{round(local["width"],2)}" height="{round(local["height"],2)}" rx="{rx}" ry="{rx}" {fill_attr} {stroke_attr} />'
        if subtype == "labeled_shape":
            text_svg = render_candidate_svg(
                {
                    "subtype": "text_block",
                    "text": candidate.get("text") or candidate.get("title") or "",
                    "title": candidate.get("title"),
                    "extra": {
                        "text_style": (extra.get("text_style") or {}),
                        "source_scope": extra.get("source_scope"),
                        "placeholder": extra.get("placeholder"),
                    },
                },
                abs_bounds,
                block_bounds,
                context,
            )
            return shape_svg + text_svg
        return shape_svg
    return ""


def render_generated_node_svg(node: dict[str, Any], block_bounds: dict[str, Any]) -> str:
    node_type = node.get("type")
    bounds = node.get("absoluteBoundingBox") or block_bounds
    local = local_bounds(bounds, block_bounds)
    if node_type in {"GROUP", "FRAME"}:
        return "".join(render_generated_node_svg(child, block_bounds) for child in node.get("children", []))
    if node_type == "RECTANGLE":
        fills = node.get("fills") or []
        strokes = node.get("strokes") or []
        fill_hex, fill_opacity = style_color_to_svg(fills[0] if fills else None, "#ffffff")
        stroke_hex, stroke_opacity = style_color_to_svg(strokes[0] if strokes else None, "#c7c7c7")
        fill_attr = f'fill="{fill_hex}" fill-opacity="{fill_opacity}"' if fills else 'fill="none"'
        stroke_attr = f'stroke="{stroke_hex}" stroke-opacity="{stroke_opacity}" stroke-width="{node.get("strokeWeight") or 1}"' if strokes else 'stroke="none"'
        radius = float(node.get("cornerRadius") or 0)
        return (
            f'<rect x="{round(local["x"],2)}" y="{round(local["y"],2)}" width="{round(local["width"],2)}" '
            f'height="{round(local["height"],2)}" rx="{round(radius,2)}" ry="{round(radius,2)}" {fill_attr} {stroke_attr} />'
        )
    if node_type == "TEXT":
        text_value = str(node.get("characters") or node.get("name") or "")
        style = node.get("style") or {}
        fills = node.get("fills") or []
        fill_hex, fill_opacity = style_color_to_svg(fills[0] if fills else None, "#111111")
        return text_svg_markup(
            text_value,
            local,
            font_size=style.get("fontSize") or 12,
            fill_hex=fill_hex,
            fill_opacity=fill_opacity,
            font_family=style.get("fontFamily") or "Arial",
            horizontal_align=style.get("textAlignHorizontal") or "LEFT",
            vertical_align=style.get("textAlignVertical") or "TOP",
        )
    return ""


def build_svg_block_node(block: dict[str, Any], markup: str, role: str) -> dict[str, Any]:
    width = round(block["bounds"]["width"], 2)
    height = round(block["bounds"]["height"], 2)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">{markup}</svg>'
    )
    return {
        "id": block["block_id"],
        "type": "SVG_BLOCK",
        "name": block["block_type"],
        "absoluteBoundingBox": block["bounds"],
        "relativeTransform": identity_affine(),
        "svgMarkup": svg,
        "children": [],
        "debug": {
            "generator": "block-prototype-v1",
            "block_type": block["block_type"],
            "render_mode": block["render_mode"],
            "page_type": block["page_type"],
            "role": role,
            "root_candidate_ids": block["root_candidate_ids"],
        },
    }


def build_header_block_node(block: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    candidates = collect_block_candidates(block, context)
    parts: list[str] = []
    parts.append(
        f'<rect x="0" y="0" width="{round(block["bounds"]["width"],2)}" height="{round(min(block["bounds"]["height"], 42),2)}" fill="white" fill-opacity="0" />'
    )
    for candidate in candidates:
        subtype = candidate.get("subtype")
        if subtype in {"group", "section_block", "table_row", "table_cell"}:
            continue
        abs_bounds = make_bounds(
            scale_value((candidate.get("bounds_px") or {}).get("x", 0), context["scale_x"]),
            scale_value((candidate.get("bounds_px") or {}).get("y", 0), context["scale_y"]),
            scale_value((candidate.get("bounds_px") or {}).get("width", 0), context["scale_x"]),
            scale_value((candidate.get("bounds_px") or {}).get("height", 0), context["scale_y"]),
        )
        svg = render_candidate_svg(candidate, abs_bounds, block["bounds"], context)
        if not svg:
            continue
        parts.append(svg)
    return build_svg_block_node(block, "".join(parts), "header_block_svg")


def build_table_visual_group(table_candidate: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    scale_x = context["scale_x"]
    scale_y = context["scale_y"]
    bounds = table_candidate.get("bounds_px") or {"x": 0, "y": 0, "width": 120, "height": 40}
    abs_bounds = make_bounds(
        scale_value(bounds["x"], scale_x),
        scale_value(bounds["y"], scale_y),
        scale_value(bounds["width"], scale_x),
        scale_value(bounds["height"], scale_y),
    )
    table_group = {
        "id": table_candidate["candidate_id"],
        "type": "GROUP",
        "name": table_candidate.get("title") or "table_block_table",
        "absoluteBoundingBox": abs_bounds,
        "relativeTransform": identity_affine(),
        "children": [],
        "debug": {
            "generator": "block-prototype-v1",
            "role": "table_visual_group",
            "source_candidate_id": table_candidate["candidate_id"],
        },
    }

    children_map = context["children_map"]
    rows = sorted(
        [child for child in children_map.get(table_candidate["candidate_id"], []) if child.get("subtype") == "table_row"],
        key=sort_by_position_key,
    )
    grid_columns = (table_candidate.get("extra") or {}).get("grid_columns") or []
    if grid_columns:
        column_widths = [scale_value(column.get("width_px") or 0, scale_x) for column in grid_columns]
    else:
        max_cols = max(
            (len([child for child in children_map.get(row["candidate_id"], []) if child.get("subtype") == "table_cell"]) for row in rows),
            default=1,
        )
        column_widths = [abs_bounds["width"] / max(max_cols, 1)] * max_cols
    column_x = [abs_bounds["x"]]
    for width in column_widths:
        column_x.append(column_x[-1] + width)

    row_heights: list[float] = []
    for row in rows:
        base_height = scale_value(((row.get("extra") or {}).get("row_height_px") or 28), scale_y)
        row_heights.append(max(base_height, 18.0))
    row_y = [abs_bounds["y"]]
    for height in row_heights:
        row_y.append(row_y[-1] + height)

    line_color = {"r": 0.78, "g": 0.78, "b": 0.78}
    header_fill = {"r": 0.92, "g": 0.92, "b": 0.92}
    for row_index, row in enumerate(rows):
        row_cells = [child for child in children_map.get(row["candidate_id"], []) if child.get("subtype") == "table_cell"]
        for cell in row_cells:
            cell_extra = cell.get("extra") or {}
            if cell_extra.get("h_merge") or cell_extra.get("v_merge"):
                continue
            start_column_index = max(int(cell_extra.get("start_column_index") or 1), 1)
            col_span = max(int(cell_extra.get("col_span") or 1), 1)
            row_span = max(int(cell_extra.get("row_span") or 1), 1)
            left = column_x[start_column_index - 1]
            right_index = min(start_column_index - 1 + col_span, len(column_x) - 1)
            right = column_x[right_index]
            top = row_y[row_index]
            bottom_index = min(row_index + row_span, len(row_y) - 1)
            bottom = row_y[bottom_index]
            cell_bounds = make_bounds(left, top, max(right - left, 1.0), max(bottom - top, 1.0))

            cell_style = cell_extra.get("cell_style") or {}
            rect_candidate = dict(cell)
            rect_candidate["extra"] = dict(cell.get("extra") or {})
            rect_candidate["extra"]["shape_style"] = {
                "fill": cell_style.get("fill"),
                "line": {"type": "srgb", "value": "C7C7C7", "alpha": 1.0, "width_px": 1},
            }
            rect_candidate["extra"]["shape_kind"] = "rect"
            rect = build_rectangle_node(rect_candidate, cell_bounds, min(scale_x, scale_y))
            if not cell_style.get("fill"):
                rect["fills"] = []
            rect["strokes"] = [{"type": "SOLID", "color": line_color, "opacity": 1.0}]
            rect["strokeWeight"] = 1
            if row_index == 0 and not rect["fills"]:
                rect["fills"] = [{"type": "SOLID", "color": header_fill, "opacity": 1.0}]
            rect["name"] = f"cell {row_index + 1}-{start_column_index}"
            rect["debug"] = dict(rect.get("debug") or {}, role="table_cell_rect")
            table_group["children"].append(rect)

            if cell.get("text"):
                text_node = build_text_node(
                    cell,
                    cell_bounds,
                    context=context,
                    force_wrap=True,
                    table_cell=True,
                    horizontal_fallback="ctr" if row_index == 0 else "l",
                    vertical_fallback=(cell_style.get("anchor") or ("ctr" if row_index == 0 else "t")),
                    scale=min(scale_x, scale_y),
                )
                table_group["children"].append(text_node)

    return table_group


def build_table_block_node(block: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    root_candidates = {candidate["candidate_id"]: candidate for candidate in context["roots"]}
    table_roots = [root_candidates[candidate_id] for candidate_id in block["root_candidate_ids"] if candidate_id in root_candidates]
    parts: list[str] = []
    for candidate in table_roots:
        if candidate.get("subtype") == "table":
            table_group = build_table_visual_group(candidate, context, assets)
            for child in table_group["children"]:
                bounds = child.get("absoluteBoundingBox") or table_group["absoluteBoundingBox"]
                if child.get("type") == "TEXT":
                    text_value = child.get("characters") or child.get("name") or ""
                    style = child.get("style") or {}
                    local = local_bounds(bounds, block["bounds"])
                    fill = (child.get("fills") or [{}])[0]
                    fill_hex, fill_opacity = style_color_to_svg(fill, "#111111")
                    parts.append(
                        text_svg_markup(
                            text_value,
                            local,
                            font_size=style.get("fontSize") or 12,
                            fill_hex=fill_hex,
                            fill_opacity=fill_opacity,
                            font_family=style.get("fontFamily") or "Arial",
                            horizontal_align=style.get("textAlignHorizontal") or "LEFT",
                            vertical_align=style.get("textAlignVertical") or "TOP",
                            l_ins=4,
                            r_ins=4,
                            t_ins=2,
                            b_ins=2,
                        )
                    )
                elif child.get("type") == "RECTANGLE":
                    local = local_bounds(bounds, block["bounds"])
                    fills = child.get("fills") or []
                    strokes = child.get("strokes") or []
                    fill_hex, fill_opacity = style_color_to_svg(fills[0] if fills else None, "#ffffff")
                    stroke_hex, stroke_opacity = style_color_to_svg(strokes[0] if strokes else None, "#c7c7c7")
                    fill_attr = f'fill="{fill_hex}" fill-opacity="{fill_opacity}"' if fills else 'fill="none"'
                    stroke_attr = f'stroke="{stroke_hex}" stroke-opacity="{stroke_opacity}" stroke-width="1"' if strokes else 'stroke="none"'
                    parts.append(
                        f'<rect x="{round(local["x"],2)}" y="{round(local["y"],2)}" width="{round(local["width"],2)}" height="{round(local["height"],2)}" {fill_attr} {stroke_attr} />'
                    )
        else:
            child = build_visual_node_from_candidate(candidate, context, assets)
            if child:
                bounds = child.get("absoluteBoundingBox") or block["bounds"]
                if child.get("type") == "TEXT":
                    local = local_bounds(bounds, block["bounds"])
                    style = child.get("style") or {}
                    fill = (child.get("fills") or [{}])[0]
                    fill_hex, fill_opacity = style_color_to_svg(fill, "#111111")
                    parts.append(
                        text_svg_markup(
                            child.get("characters") or child.get("name") or "",
                            local,
                            font_size=style.get("fontSize") or 12,
                            fill_hex=fill_hex,
                            fill_opacity=fill_opacity,
                            font_family=style.get("fontFamily") or "Arial",
                            horizontal_align=style.get("textAlignHorizontal") or "LEFT",
                            vertical_align=style.get("textAlignVertical") or "TOP",
                            l_ins=4,
                            r_ins=4,
                            t_ins=2,
                            b_ins=2,
                        )
                    )
    return build_svg_block_node(block, "".join(parts), "table_block_svg")


def build_flow_block_node(block: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    candidates = collect_block_candidates(block, context)
    layers: list[tuple[int, float, float, str]] = []
    for candidate in candidates:
        subtype = candidate.get("subtype")
        if subtype in {"group", "section_block", "table_row", "table_cell"}:
            continue
        abs_bounds = make_bounds(
            scale_value((candidate.get("bounds_px") or {}).get("x", 0), context["scale_x"]),
            scale_value((candidate.get("bounds_px") or {}).get("y", 0), context["scale_y"]),
            scale_value((candidate.get("bounds_px") or {}).get("width", 0), context["scale_x"]),
            scale_value((candidate.get("bounds_px") or {}).get("height", 0), context["scale_y"]),
        )
        svg = render_candidate_svg(candidate, abs_bounds, block["bounds"], context)
        if not svg:
            continue
        role = 1
        if subtype == "shape":
            role = 0
        elif subtype == "connector":
            role = 2
        elif subtype == "text_block":
            role = 3
        layers.append((role, abs_bounds["y"], abs_bounds["x"], svg))
    markup = "".join(svg for _, _, _, svg in sorted(layers, key=lambda row: (row[0], row[1], row[2])))
    return build_svg_block_node(block, markup, "flow_block_svg")


def build_right_panel_block_node(block: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    candidates = collect_block_candidates(block, context)
    seen_tables: set[str] = set()
    layers: list[tuple[int, float, float, str]] = []
    for candidate in candidates:
        subtype = candidate.get("subtype")
        if subtype in {"group", "section_block", "table_row", "table_cell"}:
            continue
        if subtype == "table":
            if candidate["candidate_id"] in seen_tables:
                continue
            seen_tables.add(candidate["candidate_id"])
            table_group = build_table_visual_group(candidate, context, assets)
            table_svg = render_generated_node_svg(table_group, block["bounds"])
            bounds = table_group["absoluteBoundingBox"]
            layers.append((1, bounds["y"], bounds["x"], table_svg))
            continue
        abs_bounds = make_bounds(
            scale_value((candidate.get("bounds_px") or {}).get("x", 0), context["scale_x"]),
            scale_value((candidate.get("bounds_px") or {}).get("y", 0), context["scale_y"]),
            scale_value((candidate.get("bounds_px") or {}).get("width", 0), context["scale_x"]),
            scale_value((candidate.get("bounds_px") or {}).get("height", 0), context["scale_y"]),
        )
        svg = render_candidate_svg(candidate, abs_bounds, block["bounds"], context)
        if not svg:
            continue
        role = 2 if subtype == "text_block" else 1
        if subtype == "shape":
            role = 0
        layers.append((role, abs_bounds["y"], abs_bounds["x"], svg))
    markup = "".join(svg for _, _, _, svg in sorted(layers, key=lambda row: (row[0], row[1], row[2])))
    return build_svg_block_node(block, markup, "right_panel_block_svg")


def build_generic_block_node(block: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    frame = build_block_frame(block)
    roots_by_id = {candidate["candidate_id"]: candidate for candidate in context["roots"]}
    for candidate_id in block["root_candidate_ids"]:
        candidate = roots_by_id.get(candidate_id)
        if not candidate:
            continue
        child = build_visual_node_from_candidate(candidate, context, assets)
        if child:
            frame["children"].append(child)
    return frame


def build_content_svg_block_node(block: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    candidates = collect_block_candidates(block, context)
    layers: list[tuple[int, float, float, str]] = []
    for candidate in candidates:
        subtype = candidate.get("subtype")
        if subtype in {"group", "section_block", "table_row", "table_cell"}:
            continue
        abs_bounds = make_bounds(
            scale_value((candidate.get("bounds_px") or {}).get("x", 0), context["scale_x"]),
            scale_value((candidate.get("bounds_px") or {}).get("y", 0), context["scale_y"]),
            scale_value((candidate.get("bounds_px") or {}).get("width", 0), context["scale_x"]),
            scale_value((candidate.get("bounds_px") or {}).get("height", 0), context["scale_y"]),
        )
        svg = render_candidate_svg(candidate, abs_bounds, block["bounds"], context)
        if not svg:
            continue
        role = 1
        if subtype == "shape":
            role = 0
        elif subtype == "connector":
            role = 2
        elif subtype == "text_block":
            role = 3
        layers.append((role, abs_bounds["y"], abs_bounds["x"], svg))
    markup = "".join(svg for _, _, _, svg in sorted(layers, key=lambda row: (row[0], row[1], row[2])))
    return build_svg_block_node(block, markup, "content_block_svg")


def build_block_node(block: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    if block["block_type"] == "header_block":
        return build_header_block_node(block, context, assets)
    if block["block_type"] == "table_block":
        return build_table_block_node(block, context, assets)
    if block["block_type"] == "flow_block":
        return build_flow_block_node(block, context, assets)
    if block["block_type"] == "right_panel_block":
        return build_right_panel_block_node(block, context, assets)
    if block["block_type"] == "content_block" and block["page_type"] == "ui-mockup":
        return build_content_svg_block_node(block, context, assets)
    return build_generic_block_node(block, context, assets)


def build_page_root(context: dict[str, Any], block_frames: list[dict[str, Any]]) -> dict[str, Any]:
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
        "children": block_frames,
        "debug": {
            "generator": "block-prototype-v1",
            "source_slide_no": context["slide_no"],
            "source_title": context["title"],
            "visual_strategy": (context.get("visual_strategy") or {}).get("page_type"),
            "strategy_signals": (context.get("visual_strategy") or {}).get("signals"),
        },
    }
    return {
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
            "generator": "block-prototype-v1",
            "source_slide_no": context["slide_no"],
            "source_title": context["title"],
            "visual_strategy": (context.get("visual_strategy") or {}).get("page_type"),
            "strategy_signals": (context.get("visual_strategy") or {}).get("signals"),
        },
    }


def build_bundle_from_page(page: dict[str, Any], source_file: str) -> dict[str, Any]:
    context = build_page_context(page)
    detection = build_blocks_for_page(page)
    assets: dict[str, Any] = {}
    block_frames = []
    for block in detection["blocks"]:
        block_frames.append(build_block_node(block, context, assets))

    root = build_page_root(context, block_frames)
    return {
        "kind": "figma-replay-bundle",
        "source_kind": "ppt-block-prototype",
        "visual_model_version": "block-v1",
        "source_file": source_file,
        "file_name": Path(source_file).name,
        "page_name": root["name"],
        "node_id": root["id"],
        "document": root,
        "assets": assets,
        "missing_assets": [],
        "debug": {
            "status": "block_prototype_generator",
            "candidate_count": len(context["candidates"]),
            "root_candidate_count": len(context["roots"]),
            "visual_strategy": context["visual_strategy"],
            "blocks": detection["blocks"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build block-first replay bundle prototype from PPT intermediate JSON.")
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
        output_path = output_dir / f"block-slide-{page['slide_no']}.bundle.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(bundle, handle, ensure_ascii=False, indent=2)
        print(f"saved {output_path}")


if __name__ == "__main__":
    main()
