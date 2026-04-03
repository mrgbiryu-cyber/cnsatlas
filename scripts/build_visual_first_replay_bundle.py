#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import textwrap
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
    if table_cell:
        base_by_height = height * (0.64 if single_line and short_text else 0.5)
    else:
        base_by_height = height * (0.56 if single_line and short_text else 0.42)
    rough_capacity = max(int((width - 12) / max(base_by_height * 0.55, 4)), 4)
    multiline_penalty = 0.82 if len(text_value or "") > rough_capacity else 1.0
    if table_cell:
        width_penalty = 0.92 if width < 120 else 0.97 if width < 220 else 1.0
        local_scale = 1.02
    else:
        width_penalty = 0.86 if width < 120 else 0.94 if width < 220 else 1.0
        local_scale = 1.0
    return clamp_font_size(base_by_height * multiline_penalty * width_penalty * local_scale * scale)


def estimate_text_run_width(text_value: str, font_size: float) -> float:
    total = 0.0
    for char in str(text_value or ""):
        if char == " ":
            total += font_size * 0.34
        elif ord(char) < 128:
            if char.isupper():
                total += font_size * 0.66
            elif char.isdigit():
                total += font_size * 0.58
            else:
                total += font_size * 0.56
        else:
            total += font_size * 0.96
    return total


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
    return "none"


def build_text_style(candidate: dict[str, Any], bounds: dict[str, Any], *, force_wrap: bool = False, table_cell: bool = False, horizontal_fallback: str = "l", vertical_fallback: str = "t", scale: float = 1.0) -> dict[str, Any]:
    extra = candidate.get("extra") or {}
    text_style = dict(extra.get("text_style") or {})
    text_runs = extra.get("text_runs") or []
    run_font_sizes = [
        float(run.get("font_size"))
        for run in text_runs
        if run.get("type") == "text" and run.get("font_size")
    ]
    run_font_family = next(
        (str(run.get("font_family")) for run in text_runs if run.get("type") == "text" and run.get("font_family")),
        None,
    )
    run_fill = next(
        (run.get("fill") for run in text_runs if run.get("type") == "text" and run.get("fill")),
        None,
    )
    if not text_style.get("font_size_max") and run_font_sizes:
        text_style["font_size_max"] = max(run_font_sizes)
    if not text_style.get("font_size_avg") and run_font_sizes:
        text_style["font_size_avg"] = round(sum(run_font_sizes) / len(run_font_sizes), 2)
    if not text_style.get("font_family") and run_font_family:
        text_style["font_family"] = run_font_family
    if not text_style.get("fill") and run_fill:
        text_style["fill"] = run_fill
    text_value = candidate.get("text") or candidate.get("title") or ""
    wrap_mode = derive_wrap_mode(text_value, text_style, bounds, force_wrap=force_wrap)
    inferred_placeholder_size = None if table_cell else infer_placeholder_font_size(candidate, bounds, scale)
    font_size = inferred_placeholder_size or estimate_text_font_size(text_value, text_style, bounds, table_cell=table_cell, scale=scale)
    placeholder = ((candidate.get("extra") or {}).get("placeholder") or {})
    text_auto_resize = "HEIGHT" if wrap_mode != "none" or placeholder else "WIDTH_AND_HEIGHT"
    line_height_ratio = 1.22 if table_cell else 1.2
    return {
        "fontSize": font_size,
        "fontFamily": text_style.get("font_family") or "Inter",
        "textAlignHorizontal": map_horizontal_align(text_style.get("horizontal_align"), horizontal_fallback),
        "textAlignVertical": map_vertical_align(text_style.get("vertical_align"), vertical_fallback),
        "textAutoResize": text_auto_resize,
        "lineHeightPx": round(font_size * line_height_ratio, 2),
    }


def fit_text_bounds_to_content(text_value: str, bounds: dict[str, Any], style: dict[str, Any], *, allow_shrink: bool = True, is_table_cell: bool = False) -> dict[str, Any]:
    if not allow_shrink:
        return bounds
    if "\n" in str(text_value or ""):
        return bounds
    font_size = float(style.get("fontSize") or 12)
    estimated_width = estimate_text_run_width(text_value, font_size)
    if estimated_width <= 0:
        return bounds
    padding = max(font_size * (0.9 if is_table_cell else 1.2), 10.0)
    target_width = min(float(bounds.get("width", 0)), max(estimated_width + padding, 12.0))
    if target_width >= float(bounds.get("width", 0)) - 2:
        return bounds
    align = str(style.get("textAlignHorizontal") or "LEFT").upper()
    x = float(bounds.get("x", 0))
    if align == "CENTER":
        x += (float(bounds.get("width", 0)) - target_width) / 2
    elif align == "RIGHT":
        x += float(bounds.get("width", 0)) - target_width
    return {
        "x": round(x, 2),
        "y": round(float(bounds.get("y", 0)), 2),
        "width": round(target_width, 2),
        "height": round(float(bounds.get("height", 0)), 2),
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
    text_value = candidate.get("text") or candidate.get("title") or ""
    extra = candidate.get("extra") or {}
    text_style = dict(extra.get("text_style") or {})
    text_runs = extra.get("text_runs") or []
    run_fill = next(
        (run.get("fill") for run in text_runs if run.get("type") == "text" and run.get("fill")),
        None,
    )
    if not text_style.get("fill") and run_fill:
        text_style["fill"] = run_fill
    style = build_text_style(candidate, text_bounds, force_wrap=force_wrap, table_cell=table_cell, horizontal_fallback=horizontal_fallback, vertical_fallback=vertical_fallback, scale=scale)
    text_bounds = fit_text_bounds_to_content(
        text_value,
        text_bounds,
        style,
        allow_shrink=False,
        is_table_cell=table_cell,
    )
    fragments, layout_mode = header_text_fragments(text_value, candidate, text_bounds, table_cell=table_cell)
    if len(fragments) <= 1:
        fragments, layout_mode = content_text_fragments(
            text_value,
            candidate,
            text_bounds,
            style,
            context=context,
            table_cell=table_cell,
        )
    if len(fragments) > 1:
        return build_fragment_text_group(
            candidate,
            text_bounds,
            style,
            fragments,
            layout_mode,
            scale=min(scale, 1.0),
        )
    return {
        "id": f"{candidate['candidate_id']}:text",
        "type": "TEXT",
        "name": candidate.get("title") or candidate.get("subtype") or "text",
        "characters": text_value,
        "absoluteBoundingBox": text_bounds,
        "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
        "fills": [solid_paint(text_style.get("fill"), {"r": 0.12, "g": 0.12, "b": 0.12}, 1.0)],
        "style": style,
        "children": [],
        "debug": dict(build_source_debug(candidate), rotation_degrees=normalize_degrees((candidate.get("bounds_px") or {}).get("rotation", 0))),
    }


def header_text_fragments(text_value: str, candidate: dict[str, Any], bounds: dict[str, Any], *, table_cell: bool = False) -> tuple[list[str], str]:
    raw = str(text_value or "").strip()
    if not raw:
        return [raw], "none"
    source_scope = str(((candidate.get("extra") or {}).get("source_scope") or "slide")).lower()
    if source_scope not in {"slide", "layout"}:
        return [raw], "none"
    if float(bounds.get("y", 9999)) > 95:
        return [raw], "none"
    if "\n" in raw:
        parts = [part.strip() for part in raw.splitlines() if part.strip()]
        return (parts, "vertical") if len(parts) > 1 else ([raw], "none")
    if len(raw) > (80 if table_cell else 36):
        return [raw], "none"
    if " + " in raw:
        first, second = raw.split("+", 1)
        return [first.strip(), f"+ {second.strip()}"], "horizontal"
    if raw.endswith(")") and "(" in raw and " " not in raw:
        left, right = raw.split("(", 1)
        left = f"{left.strip()}("
        right = right.strip()
        if left and right:
            return [left, right], "horizontal"
    if raw.endswith(" ID"):
        return [raw.replace(" ", "")], "none"
    if " " in raw and len(raw) <= 20:
        parts = [part.strip() for part in raw.split(" ") if part.strip()]
        if len(parts) > 1:
            return parts, "horizontal"
    return [raw], "none"


def wrap_text_fragments(parts: list[str], max_chars: int) -> list[str]:
    wrapped: list[str] = []
    for part in parts:
        cleaned = " ".join(str(part or "").split()).strip()
        if not cleaned:
            continue
        if len(cleaned) <= max_chars:
            wrapped.append(cleaned)
            continue
        for line in textwrap.wrap(cleaned, width=max_chars, break_long_words=False, break_on_hyphens=False):
            line = line.strip()
            if line:
                wrapped.append(line)
    return wrapped


def cap_fragment_lines(parts: list[str], max_lines: int) -> list[str]:
    if len(parts) <= max_lines:
        return parts
    if max_lines <= 1:
        return [" ".join(parts)]
    head = parts[: max_lines - 1]
    tail = " ".join(parts[max_lines - 1 :]).strip()
    return head + ([tail] if tail else [])


def content_text_fragments(
    text_value: str,
    candidate: dict[str, Any],
    bounds: dict[str, Any],
    style: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    table_cell: bool = False,
) -> tuple[list[str], str]:
    raw = str(text_value or "").strip()
    if not raw:
        return [raw], "none"
    strategy = str(((context or {}).get("visual_strategy") or {}).get("page_type") or "")
    subtype = str(candidate.get("subtype") or "")
    if strategy != "ui-mockup":
        return [raw], "none"
    if subtype not in {"table_cell", "labeled_shape", "text_block"} and not table_cell:
        return [raw], "none"
    if len(raw) < (90 if table_cell else 110):
        return [raw], "none"
    width = float(bounds.get("width", 0))
    height = float(bounds.get("height", 0))
    if width <= 0 or height <= 0:
        return [raw], "none"

    normalized = raw
    markers = [
        "[참고사항",
        "★",
        "•",
        "ㄴ ",
        " 2a)",
        " 2b)",
        " 2c)",
        " 2C)",
        " 2d)",
        " 2e)",
        " 문서명 :",
        " 동영상 :",
        " 이미지 :",
        " 버튼 선택 시",
        " 현재 노출",
        " 이전 / 다음",
        " 노출순서 변경됨 :",
        " 디자인 변경됨 :",
        " 신규 추가됨",
        " [BTOCSITE-",
    ]
    for marker in markers:
        normalized = normalized.replace(marker, "\n" + marker)
    normalized = re.sub(r"\s+(?=\[[^\]]+\])", "\n", normalized)
    normalized = normalized.lstrip("\n")

    pieces = [piece.strip(" -") for piece in normalized.splitlines() if piece.strip(" -")]
    font_size = float(style.get("fontSize") or 12)
    max_chars = max(18, min(44, int((width - 12) / max(font_size * 0.62, 5.5))))
    wrapped = wrap_text_fragments(pieces, max_chars)
    max_lines = max(int(height / max(font_size * 1.45, 10.0)), 2)
    wrapped = cap_fragment_lines(wrapped, max_lines)
    if len(wrapped) <= 1:
        return [raw], "none"
    return wrapped, "vertical"


def build_fragment_text_group(candidate: dict[str, Any], bounds: dict[str, Any], style: dict[str, Any], fragments: list[str], layout_mode: str, *, scale: float = 1.0) -> dict[str, Any]:
    total_width = float(bounds.get("width", 0))
    total_height = float(bounds.get("height", 0))
    origin_x = float(bounds.get("x", 0))
    origin_y = float(bounds.get("y", 0))
    font_size = float(style.get("fontSize") or 12)
    children = []
    if layout_mode == "vertical":
        row_height = total_height / max(len(fragments), 1)
        for index, fragment in enumerate(fragments):
            frag_bounds = {
                "x": round(origin_x, 2),
                "y": round(origin_y + row_height * index, 2),
                "width": round(total_width, 2),
                "height": round(row_height, 2),
            }
            children.append(
                {
                    "id": f"{candidate['candidate_id']}:text:{index + 1}",
                    "type": "TEXT",
                    "name": candidate.get("title") or candidate.get("subtype") or "text",
                    "characters": fragment,
                    "absoluteBoundingBox": frag_bounds,
                    "relativeTransform": identity_affine(),
                    "fills": [solid_paint(((candidate.get("extra") or {}).get("text_style") or {}).get("fill"), {"r": 0.12, "g": 0.12, "b": 0.12}, 1.0)],
                    "style": dict(style),
                    "children": [],
                    "debug": dict(build_source_debug(candidate), role="header_text_fragment"),
                }
            )
    else:
        widths = [max(estimate_text_run_width(fragment, font_size), font_size * 1.6) for fragment in fragments]
        gap = max(font_size * 0.5 * scale, 6.0)
        total_est = sum(widths) + gap * max(len(widths) - 1, 0)
        usable = total_width
        scale_ratio = min(1.0, usable / total_est) if total_est > 0 else 1.0
        cursor_x = origin_x
        for index, (fragment, estimated_width) in enumerate(zip(fragments, widths)):
            frag_width = estimated_width * scale_ratio
            if index == len(fragments) - 1:
                frag_width = max(origin_x + total_width - cursor_x, frag_width)
            frag_bounds = {
                "x": round(cursor_x, 2),
                "y": round(origin_y, 2),
                "width": round(frag_width, 2),
                "height": round(total_height, 2),
            }
            children.append(
                {
                    "id": f"{candidate['candidate_id']}:text:{index + 1}",
                    "type": "TEXT",
                    "name": candidate.get("title") or candidate.get("subtype") or "text",
                    "characters": fragment,
                    "absoluteBoundingBox": frag_bounds,
                    "relativeTransform": identity_affine(),
                    "fills": [solid_paint(((candidate.get("extra") or {}).get("text_style") or {}).get("fill"), {"r": 0.12, "g": 0.12, "b": 0.12}, 1.0)],
                    "style": dict(style),
                    "children": [],
                    "debug": dict(build_source_debug(candidate), role="header_text_fragment"),
                }
            )
            cursor_x += frag_width + gap * scale_ratio
    return {
        "id": f"{candidate['candidate_id']}:text_group",
        "type": "GROUP",
        "name": candidate.get("title") or candidate.get("subtype") or "text_group",
        "absoluteBoundingBox": bounds,
        "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
        "children": children,
        "debug": dict(build_source_debug(candidate), role="header_text_group"),
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


def build_rectangle_node(candidate: dict[str, Any], abs_bounds: dict[str, Any], scale: float = 1.0) -> dict[str, Any]:
    extra = candidate.get("extra") or {}
    shape_style = extra.get("shape_style") or {}
    shape_kind = extra.get("shape_kind") or ""
    corner_radius = 0
    if shape_kind == "roundRect":
        corner_radius = round(min(abs_bounds["height"] * 0.18, 12 * scale), 2)
    return {
        "id": candidate["candidate_id"],
        "type": "RECTANGLE",
        "name": candidate.get("title") or candidate.get("subtype") or "shape",
        "absoluteBoundingBox": abs_bounds,
        "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
        "fills": build_fill_array(shape_style, {"r": 1, "g": 1, "b": 1}),
        "strokes": build_stroke_array(shape_style, {"r": 0.28, "g": 0.28, "b": 0.28}),
        "strokeWeight": max(float((((shape_style.get("line") or {}).get("width_px")) or 1)) * scale, 1.0),
        "cornerRadius": corner_radius,
        "children": [],
        "debug": dict(build_source_debug(candidate), shape_kind=shape_kind),
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


def build_frame_shell_node(candidate: dict[str, Any], abs_bounds: dict[str, Any], scale: float = 1.0) -> dict[str, Any]:
    extra = candidate.get("extra") or {}
    shape_style = extra.get("shape_style") or {}
    return {
        "id": candidate["candidate_id"],
        "type": "FRAME",
        "name": candidate.get("title") or candidate.get("subtype") or "frame",
        "absoluteBoundingBox": abs_bounds,
        "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
        "fills": build_fill_array(shape_style, {"r": 1, "g": 1, "b": 1}),
        "strokes": build_stroke_array(shape_style, {"r": 0.28, "g": 0.28, "b": 0.28}),
        "strokeWeight": max(float((((shape_style.get("line") or {}).get("width_px")) or 1)) * scale, 1.0),
        "children": [],
        "debug": dict(build_source_debug(candidate), frame_shell=True, shape_kind=extra.get("shape_kind")),
    }


def build_connector_node(candidate: dict[str, Any], abs_bounds: dict[str, Any], scale_x: float, scale_y: float, strategy: str = "generic") -> dict[str, Any]:
    extra = candidate.get("extra") or {}
    shape_style = extra.get("shape_style") or {}
    kind = extra.get("shape_kind") or "connector"
    stroke_weight = max(float(((shape_style.get("line") or {}).get("width_px") or 1.5)) * min(scale_x, scale_y), 1.0)
    local_width = max(abs_bounds["width"], 6)
    local_height = max(abs_bounds["height"], 6)
    relative_transform = identity_affine()

    def readable_elbow(start: dict[str, float], end: dict[str, float], kind_name: str, adjusts: dict[str, Any], raw_bounds: dict[str, Any]) -> list[dict[str, float]]:
        lead_margin = 16
        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]
        flip_h = bool(raw_bounds.get("flipH"))
        flip_v = bool(raw_bounds.get("flipV"))
        adj1 = (adjusts.get("adj1", 50000) or 50000) / 100000
        if abs(dx) <= 4 or abs(dy) <= 4:
            return [start, end]
        horizontal = abs(dx) >= abs(dy)
        if strategy == "flow-process":
            if kind_name == "bentConnector2":
                elbow_a = {"x": start["x"], "y": end["y"]}
                elbow_b = {"x": end["x"], "y": start["y"]}
                corner_x = abs_bounds["x"] + (abs_bounds["width"] if flip_h else 0)
                corner_y = abs_bounds["y"] + (abs_bounds["height"] if flip_v else 0)
                score_a = abs(elbow_a["x"] - corner_x) + abs(elbow_a["y"] - corner_y)
                score_b = abs(elbow_b["x"] - corner_x) + abs(elbow_b["y"] - corner_y)
                elbow = elbow_a if score_a <= score_b else elbow_b
                return [start, elbow, end]
            if horizontal:
                mid_x = abs_bounds["x"] + abs_bounds["width"] * ((1 - adj1) if flip_h else adj1)
                return [start, {"x": mid_x, "y": start["y"]}, {"x": mid_x, "y": end["y"]}, end]
            mid_y = abs_bounds["y"] + abs_bounds["height"] * ((1 - adj1) if flip_v else adj1)
            return [start, {"x": start["x"], "y": mid_y}, {"x": end["x"], "y": mid_y}, end]
        if kind_name == "straightConnector1":
            if horizontal:
                return [start, {"x": end["x"], "y": start["y"]}, end]
            return [start, {"x": start["x"], "y": end["y"]}, end]
        if kind_name == "bentConnector2":
            elbow_a = {"x": start["x"], "y": end["y"]}
            elbow_b = {"x": end["x"], "y": start["y"]}
            score_a = abs(elbow_a["x"] - abs_bounds["x"]) + abs(elbow_a["y"] - abs_bounds["y"])
            score_b = abs(elbow_b["x"] - abs_bounds["x"]) + abs(elbow_b["y"] - abs_bounds["y"])
            return [start, elbow_a if score_a <= score_b else elbow_b, end]
        if kind_name == "bentConnector3":
            if horizontal:
                mid_x = abs_bounds["x"] + abs_bounds["width"] * ((1 - adj1) if flip_h else adj1)
                return [start, {"x": mid_x, "y": start["y"]}, {"x": mid_x, "y": end["y"]}, end]
            mid_y = abs_bounds["y"] + abs_bounds["height"] * ((1 - adj1) if flip_v else adj1)
            return [start, {"x": start["x"], "y": mid_y}, {"x": end["x"], "y": mid_y}, end]
        if kind_name == "bentConnector4":
            if horizontal:
                mid_x = abs_bounds["x"] + abs_bounds["width"] * ((1 - adj1) if flip_h else adj1)
                return [start, {"x": mid_x, "y": start["y"]}, {"x": mid_x, "y": end["y"]}, end]
            mid_y = abs_bounds["y"] + abs_bounds["height"] * ((1 - adj1) if flip_v else adj1)
            return [start, {"x": start["x"], "y": mid_y}, {"x": end["x"], "y": mid_y}, end]
        if horizontal:
            route_y = start["y"] + (lead_margin if dy >= 0 else -lead_margin)
            return [start, {"x": start["x"], "y": route_y}, {"x": end["x"], "y": route_y}, end]
        route_x = start["x"] + (lead_margin if dx >= 0 else -lead_margin)
        return [start, {"x": route_x, "y": start["y"]}, {"x": route_x, "y": end["y"]}, end]

    start_px = scale_point(extra.get("start_point_px"), scale_x, scale_y)
    end_px = scale_point(extra.get("end_point_px"), scale_x, scale_y)
    inferred_endpoint = bool(extra.get("inferred_start_point") or extra.get("inferred_end_point"))
    adjusts = extra.get("connector_adjusts") or {}
    bounds = candidate.get("bounds_px") or {}
    raw_width = float(bounds.get("width") or 0)
    raw_height = float(bounds.get("height") or 0)
    flip_h = bool(bounds.get("flipH"))
    flip_v = bool(bounds.get("flipV"))

    def bounds_connector_points(kind_name: str) -> list[dict[str, float]]:
        x0 = abs_bounds["x"]
        y0 = abs_bounds["y"]
        x1 = abs_bounds["x"] + abs_bounds["width"]
        y1 = abs_bounds["y"] + abs_bounds["height"]
        mx = abs_bounds["x"] + abs_bounds["width"] / 2
        my = abs_bounds["y"] + abs_bounds["height"] / 2
        adj1 = (adjusts.get("adj1", 50000) or 50000) / 100000
        if kind_name == "straightConnector1":
            if abs_bounds["width"] >= abs_bounds["height"]:
                start = {"x": x1 if flip_h else x0, "y": my}
                end = {"x": x0 if flip_h else x1, "y": my}
            else:
                start = {"x": mx, "y": y1 if flip_v else y0}
                end = {"x": mx, "y": y0 if flip_v else y1}
            return [start, end]
        if kind_name == "bentConnector2":
            start = {"x": x1 if flip_h else x0, "y": y1 if flip_v else y0}
            end = {"x": x0 if flip_h else x1, "y": y0 if flip_v else y1}
            elbow = {"x": start["x"], "y": end["y"]}
            return [start, elbow, end]
        if abs_bounds["width"] >= abs_bounds["height"]:
            start = {"x": x1 if flip_h else x0, "y": y1 if flip_v else y0}
            end = {"x": x0 if flip_h else x1, "y": y0 if flip_v else y1}
            mid_x = x0 + abs_bounds["width"] * ((1 - adj1) if flip_h else adj1)
            return [start, {"x": mid_x, "y": start["y"]}, {"x": mid_x, "y": end["y"]}, end]
        start = {"x": x1 if flip_h else x0, "y": y1 if flip_v else y0}
        end = {"x": x0 if flip_h else x1, "y": y0 if flip_v else y1}
        mid_y = y0 + abs_bounds["height"] * ((1 - adj1) if flip_v else adj1)
        return [start, {"x": start["x"], "y": mid_y}, {"x": end["x"], "y": mid_y}, end]

    is_wide_straight = kind == "straightConnector1" and raw_width >= max(raw_height * 8, 100)
    is_tall_straight = kind == "straightConnector1" and raw_height >= max(raw_width * 8, 100)
    if is_wide_straight:
        points = [
            {"x": abs_bounds["x"], "y": abs_bounds["y"] + (abs_bounds["height"] / 2)},
            {"x": abs_bounds["x"] + abs_bounds["width"], "y": abs_bounds["y"] + (abs_bounds["height"] / 2)},
        ]
    elif is_tall_straight:
        points = [
            {"x": abs_bounds["x"] + (abs_bounds["width"] / 2), "y": abs_bounds["y"]},
            {"x": abs_bounds["x"] + (abs_bounds["width"] / 2), "y": abs_bounds["y"] + abs_bounds["height"]},
        ]
    elif strategy == "flow-process" and start_px and end_px:
        # Flow/process connectors are sensitive to routing heuristics.
        # If endpoint facts are inferred (not explicit in source), keep a direct path.
        if inferred_endpoint:
            points = [start_px, end_px]
        else:
            points = readable_elbow(start_px, end_px, kind, adjusts, bounds)
    elif strategy == "flow-process":
        points = bounds_connector_points(kind)
    elif start_px and end_px:
        points = readable_elbow(start_px, end_px, kind, adjusts, bounds)
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

    if head_end.get("type") == "triangle" and len(localized_points) >= 2:
        append_arrow(localized_points, 0, 1)
    if tail_end.get("type") == "triangle" and len(localized_points) >= 2:
        append_arrow(localized_points, len(localized_points) - 1, len(localized_points) - 2)

    line_color = solid_paint((shape_style.get("line") or {}), {"r": 0, "g": 0, "b": 0}, 1.0)
    connector_name = candidate.get("title") or candidate.get("subtype") or "connector"
    debug_payload = dict(build_source_debug(candidate), visual_strategy=strategy, route_kind=kind)

    if strategy == "flow-process" and len(localized_points) >= 2:
        children = []
        for index in range(len(localized_points) - 1):
            start = localized_points[index]
            end = localized_points[index + 1]
            seg_min_x = min(start["x"], end["x"])
            seg_min_y = min(start["y"], end["y"])
            seg_max_x = max(start["x"], end["x"])
            seg_max_y = max(start["y"], end["y"])
            seg_bounds = make_bounds(
                absolute_bounds["x"] + seg_min_x - stroke_weight / 2,
                absolute_bounds["y"] + seg_min_y - stroke_weight / 2,
                max(seg_max_x - seg_min_x, 1) + stroke_weight,
                max(seg_max_y - seg_min_y, 1) + stroke_weight,
            )
            local_start = {"x": round(start["x"] - seg_min_x + stroke_weight / 2, 2), "y": round(start["y"] - seg_min_y + stroke_weight / 2, 2)}
            local_end = {"x": round(end["x"] - seg_min_x + stroke_weight / 2, 2), "y": round(end["y"] - seg_min_y + stroke_weight / 2, 2)}
            children.append(
                build_vector_node(
                    f"{candidate['candidate_id']}:segment_{index + 1}",
                    f"{connector_name}:segment_{index + 1}",
                    seg_bounds,
                    stroke_geometry=[{"path": f"M {local_start['x']} {local_start['y']} L {local_end['x']} {local_end['y']}"}],
                    fills=[],
                    strokes=[line_color],
                    stroke_weight=stroke_weight,
                    debug=dict(debug_payload, role="connector_segment"),
                    relative_transform=identity_affine(),
                )
            )
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
                    debug=dict(debug_payload, role="connector_arrow"),
                    relative_transform=identity_affine(),
                )
            )
        return {
            "id": candidate["candidate_id"],
            "type": "GROUP",
            "name": connector_name,
            "absoluteBoundingBox": absolute_bounds,
            "relativeTransform": relative_transform,
            "children": children,
            "debug": dict(debug_payload, role="connector_group"),
        }

    line_node = build_vector_node(
        f"{candidate['candidate_id']}:line",
        f"{connector_name}:line",
        absolute_bounds,
        stroke_geometry=[{"path": stroke_path}],
        fills=[],
        strokes=[line_color],
        stroke_weight=stroke_weight,
        debug=dict(debug_payload, role="connector_line"),
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
                debug=dict(debug_payload, role="connector_arrow"),
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
        "debug": dict(debug_payload, role="connector_group"),
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
    strategy = (context.get("visual_strategy") or {}).get("page_type") or "generic"
    table_node = {
        "id": candidate["candidate_id"],
        "type": "GROUP",
        "name": candidate.get("title") or "table",
        "absoluteBoundingBox": abs_bounds,
        "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
        "children": [],
        "debug": dict(build_source_debug(candidate), visual_strategy=strategy),
    }
    rows = sorted([child for child in children_map.get(candidate["candidate_id"], []) if child.get("subtype") == "table_row"], key=sort_by_position_key)
    grid_columns = extra.get("grid_columns") or []
    row_cursor_y = abs_bounds["y"]
    scaled_row_heights: dict[str, float] = {}
    for row_candidate in rows:
        scaled_row_heights[row_candidate["candidate_id"]] = max(scale_value((row_candidate.get("extra") or {}).get("row_height_px") or 28, scale_y), 21.0)
    if grid_columns:
        column_widths = [scale_value(column.get("width_px") or 0, scale_x) for column in grid_columns]
    else:
        max_cols = max((len([child for child in children_map.get(row["candidate_id"], []) if child.get("subtype") == "table_cell"]) for row in rows), default=1)
        column_widths = [abs_bounds["width"] / max(max_cols, 1)] * max_cols
    column_x_positions = [abs_bounds["x"]]
    for width in column_widths:
        column_x_positions.append(column_x_positions[-1] + width)

    effective_row_heights: dict[str, float] = {}
    for row_candidate in rows:
        cell_candidates = [child for child in children_map.get(row_candidate["candidate_id"], []) if child.get("subtype") == "table_cell"]
        row_height = scaled_row_heights[row_candidate["candidate_id"]]
        for cell_candidate in cell_candidates:
            cell_extra = cell_candidate.get("extra") or {}
            if cell_extra.get("h_merge") or cell_extra.get("v_merge"):
                continue
            cell_width = scale_value(cell_extra.get("width_px") or (abs_bounds["width"] / max(len(cell_candidates), 1)), scale_x if cell_extra.get("width_px") else 1.0)
            estimated_height = estimate_wrapped_height(cell_candidate.get("text") or cell_candidate.get("title") or "", cell_candidate, cell_width, row_height, min(scale_x, scale_y))
            if strategy == "table-heavy":
                estimated_height = min(estimated_height, row_height * 1.25)
            row_height = max(row_height, estimated_height)
        effective_row_heights[row_candidate["candidate_id"]] = row_height

    if strategy == "table-heavy":
        total_height = sum(effective_row_heights.values())
        available_height = float(abs_bounds["height"])
        if total_height > available_height and total_height > 0:
            shrink = available_height / total_height
            min_row_height = 16.0
            adjusted: dict[str, float] = {}
            for row_candidate in rows:
                adjusted[row_candidate["candidate_id"]] = max(min_row_height, effective_row_heights[row_candidate["candidate_id"]] * shrink)
            adjusted_total = sum(adjusted.values())
            if adjusted_total > available_height and adjusted_total > 0:
                shrink2 = available_height / adjusted_total
                for row_candidate in rows:
                    adjusted[row_candidate["candidate_id"]] = max(12.0, adjusted[row_candidate["candidate_id"]] * shrink2)
            effective_row_heights = adjusted

    row_y_positions = [abs_bounds["y"]]
    for row_candidate in rows:
        row_y_positions.append(row_y_positions[-1] + effective_row_heights[row_candidate["candidate_id"]])

    for row_index, row_candidate in enumerate(rows, start=1):
        cell_candidates = [child for child in children_map.get(row_candidate["candidate_id"], []) if child.get("subtype") == "table_cell"]
        row_height = effective_row_heights[row_candidate["candidate_id"]]
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
                spanned_height = sum(effective_row_heights[rows[i]["candidate_id"]] for i in range(current_index, min(current_index + row_span, len(rows))))
            cell_abs_bounds = make_bounds(row_abs_bounds["x"] + cell_x, row_abs_bounds["y"], cell_width, spanned_height)
            cell_style = cell_extra.get("cell_style") or {}
            cell_name = f"cell {row_index}-{start_column_index}"
            if strategy in {"table-heavy", "ui-mockup"}:
                if strategy == "table-heavy":
                    frame_fill = (
                        [solid_paint(cell_style.get("fill"), {"r": 0.8471, "g": 0.8471, "b": 0.8471}, 1.0)]
                        if cell_style.get("fill")
                        else [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}, "opacity": 1.0}]
                    )
                    frame_strokes = [{"type": "SOLID", "color": {"r": 0.78, "g": 0.78, "b": 0.78}, "opacity": 1.0}]
                    # Table-heavy pages are frequently over-drawn when each cell keeps a thick border.
                    # Use a slightly lighter default while keeping common table contrast stable.
                    frame_stroke_weight = 0.8
                else:
                    frame_fill = [solid_paint(cell_style.get("fill"), {"r": 1, "g": 1, "b": 1}, 1.0)] if cell_style.get("fill") else []
                    frame_strokes = [{"type": "SOLID", "color": {"r": 0.82, "g": 0.82, "b": 0.82}, "opacity": 1.0}]
                    frame_stroke_weight = 1
                cell_frame = {
                    "id": f"{cell_candidate['candidate_id']}:frame",
                    "type": "FRAME",
                    "name": cell_name,
                    "absoluteBoundingBox": cell_abs_bounds,
                    "relativeTransform": relative_transform_from_bounds(cell_candidate.get("bounds_px")),
                    "fills": frame_fill,
                    "strokes": frame_strokes,
                    "strokeWeight": frame_stroke_weight,
                    "children": [],
                    "debug": dict(build_source_debug(cell_candidate), visual_strategy=strategy, role="table_cell"),
                }
            elif cell_style.get("fill"):
                cell_path = rect_path(cell_abs_bounds["width"], cell_abs_bounds["height"])
                table_node["children"].append(
                    build_vector_node(
                        f"{cell_candidate['candidate_id']}:fill",
                        cell_name,
                        cell_abs_bounds,
                        fill_geometry=[{"path": cell_path, "windingRule": "NONZERO"}],
                        stroke_geometry=[],
                        fills=[solid_paint(cell_style.get("fill"), {"r": 1, "g": 1, "b": 1}, 1.0)],
                        strokes=[],
                        stroke_weight=0,
                        debug=dict(build_source_debug(cell_candidate), visual_strategy=strategy, role="table_cell_fill"),
                        relative_transform=relative_transform_from_bounds(cell_candidate.get("bounds_px")),
                    )
                )
            if cell_candidate.get("text"):
                cell_text = str(cell_candidate.get("text") or "")
                is_header_cell = bool(cell_style.get("fill"))
                if is_header_cell:
                    horizontal_fallback = "ctr"
                elif strategy == "table-heavy":
                    if start_column_index == 1:
                        horizontal_fallback = "ctr"
                    elif len(cell_text) <= 14 and "|" not in cell_text and "/" not in cell_text:
                        horizontal_fallback = "ctr"
                    else:
                        horizontal_fallback = "l"
                else:
                    horizontal_fallback = "ctr" if len(cell_text) <= 18 and "\n" not in cell_text else "l"
                text_node = build_text_node(
                    cell_candidate,
                    cell_abs_bounds,
                    context=context,
                    force_wrap=True,
                    table_cell=True,
                    horizontal_fallback=horizontal_fallback,
                    vertical_fallback=(cell_style.get("anchor") or ("ctr" if strategy == "table-heavy" else "t")),
                    scale=min(scale_x, scale_y),
                )
                if strategy in {"table-heavy", "ui-mockup"}:
                    cell_frame["children"].append(text_node)
                else:
                    table_node["children"].append(text_node)
            if strategy in {"table-heavy", "ui-mockup"}:
                table_node["children"].append(cell_frame)
        row_cursor_y += row_height

    if strategy in {"table-heavy", "ui-mockup"}:
        return table_node

    grid_stroke = [{"type": "SOLID", "color": {"r": 0.75, "g": 0.75, "b": 0.75}}]
    line_weight = max(min(scale_x, scale_y), 1)
    for idx, y in enumerate(row_y_positions):
        local_y = round(y - abs_bounds["y"], 2)
        path = f"M 0 {local_y} L {round(abs_bounds['width'], 2)} {local_y}"
        table_node["children"].append(
            build_vector_node(
                f"{candidate['candidate_id']}:hline:{idx}",
                f"table:hline:{idx}",
                abs_bounds,
                stroke_geometry=[{"path": path}],
                fills=[],
                strokes=grid_stroke,
                stroke_weight=line_weight,
                debug=dict(build_source_debug(candidate), visual_strategy=strategy, role="table_grid"),
                relative_transform=identity_affine(),
            )
        )
    for idx, x in enumerate(column_x_positions):
        local_x = round(x - abs_bounds["x"], 2)
        path = f"M {local_x} 0 L {local_x} {round(abs_bounds['height'], 2)}"
        table_node["children"].append(
            build_vector_node(
                f"{candidate['candidate_id']}:vline:{idx}",
                f"table:vline:{idx}",
                abs_bounds,
                stroke_geometry=[{"path": path}],
                fills=[],
                strokes=grid_stroke,
                stroke_weight=line_weight,
                debug=dict(build_source_debug(candidate), visual_strategy=strategy, role="table_grid"),
                relative_transform=identity_affine(),
            )
        )
    return table_node


def build_visual_node_from_candidate(candidate: dict[str, Any], context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any] | None:
    scale_x = context["scale_x"]
    scale_y = context["scale_y"]
    bounds = candidate.get("bounds_px") or {"x": 0, "y": 0, "width": 120, "height": 24}
    abs_bounds = make_bounds(scale_value(bounds["x"], scale_x), scale_value(bounds["y"], scale_y), scale_value(bounds["width"], scale_x), scale_value(bounds["height"], scale_y))
    subtype = candidate.get("subtype")
    node_type = candidate.get("node_type")
    children_map = context["children_map"]
    strategy = (context.get("visual_strategy") or {}).get("page_type") or "generic"

    if node_type == "asset" and subtype == "image":
        return build_image_node(candidate, abs_bounds, assets, min(scale_x, scale_y))
    if subtype == "text_block":
        if should_skip_layout_placeholder_text(candidate):
            return None
        return build_text_node(candidate, abs_bounds, context=context, scale=min(scale_x, scale_y))
    if subtype == "connector":
        return build_connector_node(candidate, abs_bounds, scale_x, scale_y, strategy)
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
        if strategy == "ui-mockup":
            frame = build_frame_shell_node(candidate, abs_bounds, min(scale_x, scale_y))
            frame["children"].append(child_text)
            frame["debug"] = dict(frame.get("debug") or {}, visual_strategy=strategy, role="labeled_shape_frame")
            return frame
        return {
            "id": candidate["candidate_id"],
            "type": "GROUP",
            "name": candidate.get("title") or subtype or "labeled_shape",
            "absoluteBoundingBox": abs_bounds,
            "relativeTransform": relative_transform_from_bounds(candidate.get("bounds_px")),
            "children": [build_shape_node(candidate, abs_bounds, min(scale_x, scale_y)), child_text],
            "debug": dict(build_source_debug(candidate), visual_strategy=strategy, role="labeled_shape_group"),
        }
    if subtype == "shape":
        shape_kind = ((candidate.get("extra") or {}).get("shape_kind") or "").lower()
        if strategy == "ui-mockup" and shape_kind in {"rect", "roundrect"}:
            rect = build_rectangle_node(candidate, abs_bounds, min(scale_x, scale_y))
            rect["debug"] = dict(rect.get("debug") or {}, visual_strategy=strategy, role="ui_rect")
            return rect
        node = build_shape_node(candidate, abs_bounds, min(scale_x, scale_y))
        node["debug"] = dict(node.get("debug") or {}, visual_strategy=strategy, role="shape_vector")
        return node
    return None


def build_page_root(context: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
    root_bounds = {
        "x": 0.0,
        "y": 0.0,
        "width": float(context.get("width") or TARGET_SLIDE_WIDTH),
        "height": float(context.get("height") or TARGET_SLIDE_HEIGHT),
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
            "visual_strategy": (context.get("visual_strategy") or {}).get("page_type"),
            "strategy_signals": (context.get("visual_strategy") or {}).get("signals"),
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
            "visual_strategy": (context.get("visual_strategy") or {}).get("page_type"),
            "strategy_signals": (context.get("visual_strategy") or {}).get("signals"),
        },
    }
    for candidate in context["roots"]:
        child = build_visual_node_from_candidate(candidate, context, assets)
        if child:
            inner_frame["children"].append(child)
    return root


def build_bundle_from_page(page: dict[str, Any], source_file: str, *, preserve_native_size: bool = False) -> dict[str, Any]:
    context = build_page_context(page, preserve_native_size=preserve_native_size)
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
            "visual_strategy": context["visual_strategy"],
            "preserve_native_size": bool(context.get("preserve_native_size")),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build visual-first replay bundle from PPT intermediate JSON.")
    parser.add_argument("--input", required=True, help="Intermediate candidates JSON path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--slides", nargs="*", type=int, help="Optional slide numbers")
    parser.add_argument(
        "--preserve-native-size",
        action="store_true",
        help="Keep source slide dimensions instead of normalizing to 960x540.",
    )
    args = parser.parse_args()

    payload = load_intermediate_payload(args.input)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = iter_selected_pages(payload, set(args.slides) if args.slides else None)
    for page in selected:
        bundle = build_bundle_from_page(
            page,
            str(Path(args.input).resolve()),
            preserve_native_size=args.preserve_native_size,
        )
        output_path = output_dir / f"visual-slide-{page['slide_no']}.bundle.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(bundle, handle, ensure_ascii=False, indent=2)
        print(f"saved {output_path}")


if __name__ == "__main__":
    main()
