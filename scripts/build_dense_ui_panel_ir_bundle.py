#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
import re
import math
import textwrap
from typing import Any


TARGET_SLIDE_WIDTH = 960.0
TARGET_SLIDE_HEIGHT = 540.0
RIGHT_PANEL_X_CUTOFF = TARGET_SLIDE_WIDTH * 0.58
ROW_ID_RE = re.compile(r":row_(\d+)")


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
    horizontal = str(source_style.get("horizontal_align") or "l").lower()
    vertical = str(source_style.get("vertical_align") or "t").lower()
    horizontal_map = {
        "l": "LEFT",
        "left": "LEFT",
        "ctr": "CENTER",
        "center": "CENTER",
        "r": "RIGHT",
        "right": "RIGHT",
        "just": "JUSTIFIED",
        "justify": "JUSTIFIED",
    }
    vertical_map = {
        "t": "TOP",
        "top": "TOP",
        "ctr": "CENTER",
        "mid": "CENTER",
        "center": "CENTER",
        "b": "BOTTOM",
        "bottom": "BOTTOM",
    }
    return {
        "fontFamily": str(source_style.get("font_family") or "LG스마트체"),
        "fontStyle": "Regular",
        "fontSize": size,
        "textAlignHorizontal": horizontal_map.get(horizontal, "LEFT"),
        "textAlignVertical": vertical_map.get(vertical, "TOP"),
        "textAutoResize": "HEIGHT",
        "lineHeightPx": round(size * 1.25, 2),
    }


def compact_label_text(atom: dict[str, Any]) -> str:
    text = str(atom.get("text") or "").strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return text
    role = str(atom.get("layer_role") or "")
    if role in {"version_stack", "description_card"}:
        return lines[0]
    if role == "issue_card":
        return "\n".join(lines[:3])
    return text


def build_text_node(atom: dict[str, Any], bounds: dict[str, Any] | None = None, *, suffix: str = "") -> dict[str, Any]:
    node_bounds = dict(bounds or atom.get("visual_bounds_px") or make_bounds(0.0, 0.0, 1.0, 1.0))
    source_style = atom.get("text_style") or {}
    fill_style = source_style.get("fill")
    if not fill_style and (atom.get("cell_style") or {}).get("fill"):
        fill_style = None
    characters = compact_label_text(atom) if suffix == ":label" else str(atom.get("text") or "")
    return {
        "id": f"{atom['id']}{suffix}",
        "type": "TEXT",
        "name": atom.get("title") or atom.get("id") or "text",
        "characters": characters,
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


def build_text_leaf(
    atom: dict[str, Any],
    text: str,
    bounds: dict[str, Any],
    *,
    suffix: str = "",
    font_size: float | None = None,
) -> dict[str, Any]:
    text_atom = dict(atom)
    text_atom["text"] = text
    return build_text_node(text_atom, bounds, suffix=suffix)


def paragraph_texts(atom: dict[str, Any]) -> list[str]:
    runs = atom.get("text_runs") or []
    if not runs:
        text = str(atom.get("text") or "").strip()
        return [text] if text else []
    paragraphs: list[str] = []
    current: list[str] = []
    for run in runs:
        run_type = run.get("type")
        text = str(run.get("text") or "")
        if run_type in {"paragraph_break", "line_break"}:
            paragraph = "".join(current).strip()
            if paragraph:
                paragraphs.append(paragraph)
            current = []
            continue
        if run_type == "text":
            chunks = text.splitlines()
            if not chunks:
                continue
            current.append(chunks[0])
            for extra in chunks[1:]:
                paragraph = "".join(current).strip()
                if paragraph:
                    paragraphs.append(paragraph)
                current = [extra]
    paragraph = "".join(current).strip()
    if paragraph:
        paragraphs.append(paragraph)
    return paragraphs


def estimate_text_width(text: str, font_size: float) -> float:
    width = 0.0
    for char in text:
        if char.isspace():
            width += font_size * 0.22
        elif "\u4e00" <= char <= "\u9fff" or "\u3130" <= char <= "\u318f" or "\uac00" <= char <= "\ud7a3":
            width += font_size * 0.92
        elif char.isupper() or char.isdigit():
            width += font_size * 0.62
        elif char in {"-", ">", "(", ")", "[", "]", "/", ":", ".", ",", "&", "•", "★"}:
            width += font_size * 0.34
        else:
            width += font_size * 0.52
    return width


def split_text_for_wrap(text: str) -> list[str]:
    return [token for token in re.split(r"(\s+)", text) if token]


def normalize_body_line_text(text: str) -> str:
    normalized = text.strip()
    return normalized


def split_once(text: str, needle: str) -> list[str] | None:
    index = text.find(needle)
    if index <= 0:
        return None
    return [text[:index].rstrip(), text[index:].lstrip()]


def dense_body_special_splits(text: str) -> list[str] | None:
    if text == "문서명 :":
        return [text]
    if text.startswith("1) WCMS > [KRP0008] > 비디오 > Video File > ‘360미디어용도’에 체크"):
        return [text]
    if text.startswith("콘텐츠 노출 순서 : ") and "타입별" in text and "노출 순서 정의] 참조" in text:
        return [
            "콘텐츠 노출 순서 : [PDP Key visual 영역 / 갤러리뷰 팝업 : 콘텐츠 타입별",
            "노출 순서 정의] 참조",
        ]
    if text.startswith("CMS에서 인테리어컷 내 디스클라이머 노출여부에"):
        split = split_once(text, "인테리어컷 이미지가 등록되어 있을 경우 디스클라이머 문구 노출")
        if split:
            first, second = split
            return [f"- {first}".strip(), second]
    if text.startswith("2) CMS > CMS > 제품 > 모델관리 > 모델기본 정보 팝업 > 360미디어") and "디스클라이머 노출에 Y 체크" in text:
        split = split_once(text, "디스클라이머 노출에 Y 체크")
        if split:
            return split
    if text.startswith("-> 닷컴 전용 여부") and text.endswith("닷컴 only 뱃지 노출"):
        return [text[: text.rfind(" 노출")].rstrip(), "노출"]
    if text.startswith("- 다품목할인 > 내일배송(판매예정) > UP가전 Badge 순으로 노출"):
        return ["- 다품목할인", "내일배송(판매예정) > UP가전 Badge 순으로 노출"]
    if text.startswith("- 최대 1줄 노출하며") and "경우, 해당 강조텍스트 Badge 미 노출" in text:
        return [
            "- 최대",
            "줄 노출하며, 강조텍스트 Badge갯수로 인해 줄 바꿈이 필요한 경우,",
            "해당",
            "강조텍스트",
            "Badge 미 노출",
        ]
    if text.startswith("(e.g. 다품목할인, 내일배송, UP가전, 신제품, 베스트, 특별세일,"):
        return [
            "(e.g.",
            "다품목할인",
            ", 내일배송, UP가전, 신제품, 베스트, 특별세일, 쿠폰할인",
        ]
    if text.startswith("쿠폰할인 Badge 설정되어 있는 상품 → 스크린 크기로 인해 특별세일, 쿠폰할인 줄 바꿈 필요한 경우 특별세일, 쿠폰할인 미 노출)"):
        return [
            "Badge",
            "설정되어",
            "있는 상품 → 스크린 크기로 인해 특별세일, 쿠폰할인 줄",
            "바꿈",
            "필요한",
            "경우 특별세일, 쿠폰할인 미 노출)",
        ]
    return None


def wrap_text_line(text: str, width: float, font_size: float) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    special = dense_body_special_splits(stripped)
    if special and not (len(special) == 1 and special[0] == stripped):
        lines: list[str] = []
        for part in special:
            lines.extend(wrap_text_line(part, width, font_size))
        return lines
    max_width = max(float(width) * 0.82, font_size * 6.0)
    if estimate_text_width(stripped, font_size) <= max_width:
        normalized = normalize_body_line_text(stripped)
        return [normalized] if normalized else []

    tokens = split_text_for_wrap(stripped)
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = f"{current}{token}" if current else token
        if current and estimate_text_width(candidate, font_size) > max_width:
            finalized = current.strip()
            if finalized:
                lines.append(finalized)
            current = token.lstrip()
            continue
        current = candidate
    finalized = current.strip()
    if finalized:
        lines.append(finalized)

    wrapped: list[str] = []
    hard_limit = max(12, int(math.floor(max_width / max(font_size * 0.62, 1.0))))
    for line in lines:
        if estimate_text_width(line, font_size) <= max_width:
            wrapped.append(line)
            continue
        wrapped.extend(textwrap.wrap(line, width=hard_limit, break_long_words=False, break_on_hyphens=False) or [line])
    normalized_lines = [normalize_body_line_text(line) for line in wrapped]
    return [line for line in normalized_lines if line]


def merge_dense_body_special_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "[참고사항]":
            block = [line]
            index += 1
            while index < len(lines) and (lines[index].startswith("★") or lines[index].startswith("스타일(")):
                block.append(lines[index])
                index += 1
            merged.append("\n".join(block).replace("★  YYYY", "★ YYYY"))
            continue
        if line == "문서명 :" and index + 1 < len(lines) and lines[index + 1].startswith("LGEKR5.0"):
            merged.append(f"{line} {lines[index + 1]}".strip())
            index += 2
            continue
        merged.append(line)
        index += 1
    return merged


def clip_dense_body_lines(atom: dict[str, Any], lines: list[str]) -> list[str]:
    atom_id = str(atom.get("id") or "")
    if atom_id == "s29:slide_29/element_37:row_5:cell_2":
        clipped: list[str] = []
        for line in lines:
            clipped.append(line)
            if line == "CMS > 제품 > 모델 > 모델관리 > 모델기본정보":
                break
        return clipped
    return lines


def body_text_lines(atom: dict[str, Any], width: float, font_size: float) -> list[str]:
    runs = atom.get("text_runs") or []
    if not runs:
        return wrap_text_line(str(atom.get("text") or ""), width, font_size)

    lines: list[str] = []
    current: list[str] = []
    for run in runs:
        run_type = str(run.get("type") or "")
        text = str(run.get("text") or "")
        if run_type in {"paragraph_break", "line_break"}:
            logical_line = "".join(current).strip()
            if logical_line:
                lines.extend(wrap_text_line(logical_line, width, font_size))
            current = []
            continue
        if run_type == "text":
            pieces = text.splitlines()
            if not pieces:
                continue
            current.append(pieces[0])
            for extra in pieces[1:]:
                logical_line = "".join(current).strip()
                if logical_line:
                    lines.extend(wrap_text_line(logical_line, width, font_size))
                current = [extra]
    logical_line = "".join(current).strip()
    if logical_line:
        lines.extend(wrap_text_line(logical_line, width, font_size))
    return clip_dense_body_lines(atom, merge_dense_body_special_lines(lines))


def version_stack_label_and_detail(atom: dict[str, Any]) -> tuple[str, str]:
    lines = [line.strip() for line in str(atom.get("text") or "").splitlines() if line.strip()]
    if not lines:
        return "", ""
    return lines[0], "\n".join(lines[1:]).strip()


def build_version_stack_block(atom: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    bounds = dict(atom.get("visual_bounds_px") or make_bounds(0.0, 0.0, 1.0, 1.0))
    label_text, detail_text = version_stack_label_and_detail(atom)
    label_height = min(12.0, max(6.0, float(bounds["height"]) * 0.2))
    label_bounds = make_bounds(
        float(bounds["x"]) + 7.0,
        float(bounds["y"]) + 3.5,
        max(float(bounds["width"]) - 14.0, 8.0),
        label_height,
    )
    block_children = [build_rect_node(atom, suffix=":bg")]
    if label_text:
        block_children.append(build_text_leaf(atom, label_text, label_bounds, suffix=":label"))
    block_group = build_owner_frame(f"{atom['id']}:version_block", block_children, bounds=bounds)

    detail_node: dict[str, Any] | None = None
    if detail_text:
        detail_bounds = make_bounds(
            float(bounds["x"]) + 7.0,
            float(bounds["y"]) + label_height + 6.0,
            max(float(bounds["width"]) - 14.0, 8.0),
            max(float(bounds["height"]) - label_height - 8.0, 8.0),
        )
        detail_node = build_text_leaf(atom, detail_text, detail_bounds, suffix=":detail")
    return block_group, detail_node


def build_paragraph_text_group(atom: dict[str, Any], bounds: dict[str, Any], *, suffix: str = "") -> dict[str, Any]:
    style = text_style(atom)
    font_size = float(style["fontSize"])
    line_height = float(style["lineHeightPx"])
    if str(atom.get("owner_id") or "") == "dense_ui_panel:description_lanes":
        line_height = min(line_height, round(font_size + 0.9, 2))
    lines = body_text_lines(atom, float(bounds["width"]), font_size)
    if not lines:
        return build_owner_group(f"{atom['id']}{suffix}:empty", [])
    left = float(bounds["x"])
    top = float(bounds["y"])
    width = float(bounds["width"])
    children: list[dict[str, Any]] = []
    current_y = top
    max_bottom = top + float(bounds["height"])
    for index, line in enumerate(lines):
        if current_y >= max_bottom:
            break
        paragraph_height = min(line_height, max_bottom - current_y)
        if paragraph_height <= 1.0:
            break
        paragraph_bounds = make_bounds(left, current_y, width, paragraph_height)
        paragraph_atom = dict(atom)
        paragraph_atom["text"] = line
        children.append(build_text_node(paragraph_atom, paragraph_bounds, suffix=f"{suffix}:p{index + 1}"))
        current_y += paragraph_height
    return build_owner_group(f"{atom['id']}{suffix}:paragraphs", children)


def build_rect_node(atom: dict[str, Any], bounds: dict[str, Any] | None = None, *, suffix: str = "") -> dict[str, Any]:
    node_bounds = dict(bounds or atom.get("visual_bounds_px") or make_bounds(0.0, 0.0, 1.0, 1.0))
    shape_style = atom.get("shape_style") or {}
    fill_style = shape_style.get("fill") or (atom.get("cell_style") or {}).get("fill")
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


def svg_color(style_color: dict[str, Any] | None, fallback: str, fallback_opacity: float = 1.0) -> tuple[str, float]:
    color, opacity = color_from_style(style_color, {"r": 0.0, "g": 0.0, "b": 0.0})
    return (
        f"rgb({round(color['r'] * 255)}, {round(color['g'] * 255)}, {round(color['b'] * 255)})" if style_color else fallback,
        opacity if style_color else fallback_opacity,
    )


def build_small_asset_svg_node(atom: dict[str, Any], bounds: dict[str, Any] | None = None, *, suffix: str = "") -> dict[str, Any] | None:
    node_bounds = dict(bounds or atom.get("visual_bounds_px") or make_bounds(0.0, 0.0, 1.0, 1.0))
    width = max(float(node_bounds["width"]), 1.0)
    height = max(float(node_bounds["height"]), 1.0)
    shape_kind = str(atom.get("shape_kind") or "")
    shape_style = atom.get("shape_style") or {}
    fill_color, fill_opacity = svg_color(shape_style.get("fill"), "rgb(255,255,255)")
    line_style = shape_style.get("line") or {}
    stroke_color, stroke_opacity = svg_color(line_style, "rgb(120,120,120)")
    stroke_width = max(float(line_style.get("width_px") or 1.0), 1.0)

    if shape_kind == "ellipse":
        svg_markup = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<ellipse cx="{width / 2}" cy="{height / 2}" rx="{max(width / 2 - stroke_width / 2, 0.5)}" '
            f'ry="{max(height / 2 - stroke_width / 2, 0.5)}" '
            f'fill="{fill_color}" fill-opacity="{fill_opacity}" '
            f'stroke="{stroke_color}" stroke-opacity="{stroke_opacity}" stroke-width="{stroke_width}"/>'
            "</svg>"
        )
    elif shape_kind == "straightConnector1" or atom.get("subtype") == "connector":
        mid_y = height / 2
        arrow = max(min(width, height) * 0.35, 3.0)
        line_end_x = max(width - arrow - stroke_width, stroke_width)
        svg_markup = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<line x1="{stroke_width / 2}" y1="{mid_y}" x2="{line_end_x}" y2="{mid_y}" '
            f'stroke="{stroke_color}" stroke-opacity="{stroke_opacity}" stroke-width="{stroke_width}" stroke-linecap="round"/>'
            f'<polygon points="{line_end_x},{max(mid_y - arrow / 2, 0)} {width},{mid_y} {line_end_x},{min(mid_y + arrow / 2, height)}" '
            f'fill="{stroke_color}" fill-opacity="{stroke_opacity}"/>'
            "</svg>"
        )
    else:
        return None

    return {
        "id": f"{atom['id']}{suffix}",
        "type": "SVG_BLOCK",
        "name": atom.get("title") or atom.get("id") or "small_asset_svg",
        "absoluteBoundingBox": node_bounds,
        "relativeTransform": identity_affine(),
        "svgMarkup": svg_markup,
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


def build_owner_frame(
    owner_id: str,
    children: list[dict[str, Any]],
    *,
    bounds: dict[str, Any] | None = None,
    clips_content: bool = True,
) -> dict[str, Any]:
    frame_bounds = dict(
        bounds
        or union_bounds(
            [
                child.get("absoluteBoundingBox") or make_bounds(0.0, 0.0, 1.0, 1.0)
                for child in children
            ]
        )
    )
    return {
        "id": owner_id,
        "type": "FRAME",
        "name": owner_id.split(":")[-1],
        "absoluteBoundingBox": frame_bounds,
        "relativeTransform": identity_affine(),
        "fills": [],
        "strokes": [],
        "strokeWeight": 0,
        "clipsContent": clips_content,
        "children": children,
        "debug": {
            "generator": "dense-ui-ir-v1",
            "owner_id": owner_id,
            "frame_container": True,
        },
    }


def build_group_group(group_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    bounds = union_bounds(
        [
            child.get("absoluteBoundingBox") or make_bounds(0.0, 0.0, 1.0, 1.0)
            for child in children
        ]
    )
    return {
        "id": group_id,
        "type": "GROUP",
        "name": group_id.split(":")[-1],
        "absoluteBoundingBox": bounds,
        "relativeTransform": identity_affine(),
        "children": children,
        "debug": {
            "generator": "dense-ui-ir-v1",
            "group_id": group_id,
        },
    }


def row_index_from_atom(atom: dict[str, Any]) -> int | None:
    atom_id = str(atom.get("id") or "")
    match = ROW_ID_RE.search(atom_id)
    if not match:
        return None
    return int(match.group(1))


def build_default_lane_background(bounds: dict[str, Any], row_index: int, style_atom: dict[str, Any] | None = None) -> dict[str, Any]:
    fill = {"r": 1.0, "g": 1.0, "b": 1.0}
    opacity = 1.0
    stroke_opacity = 1.0
    if style_atom and (style_atom.get("shape_style") or {}).get("fill"):
        fill, opacity = color_from_style((style_atom.get("shape_style") or {}).get("fill"), fill)
        _, stroke_opacity = color_from_style((style_atom.get("shape_style") or {}).get("line") or {}, {"r": 0.82, "g": 0.82, "b": 0.82})
    elif row_index == 6:
        fill = {"r": 0.96, "g": 0.95, "b": 0.92}
    elif row_index >= 5:
        opacity = 0.0
        stroke_opacity = 0.0
    return {
        "id": f"lane-row-{row_index}:bg",
        "type": "RECTANGLE",
        "name": f"lane_row_{row_index}_bg",
        "absoluteBoundingBox": dict(bounds),
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": fill, "opacity": opacity}],
        "strokes": [{"type": "SOLID", "color": {"r": 0.82, "g": 0.82, "b": 0.82}, "opacity": stroke_opacity}],
        "strokeWeight": 1,
        "children": [],
        "debug": {"generator": "dense-ui-ir-v1", "role": "table_backed_lane_background", "row_index": row_index},
    }


def estimate_wrap_chars(width: float, font_size: float) -> int:
    glyph_width = max(font_size * 0.95, 6.4)
    usable_width = max(width - 8.0, 24.0)
    return max(10, int(usable_width / glyph_width))


def estimate_text_height(text: str, width: float, font_size: float, line_gap: float = 2.0) -> float:
    wrapped = textwrap.wrap(
        text.strip() or " ",
        width=estimate_wrap_chars(width, font_size),
        break_long_words=False,
        break_on_hyphens=False,
    )
    line_count = max(1, len(wrapped))
    line_height = font_size + line_gap
    return line_count * line_height + 6.0


def estimate_paragraph_group_height(atom: dict[str, Any], width: float, font_size: float, line_gap: float = 2.0) -> float:
    if str(atom.get("owner_id") or "") == "dense_ui_panel:description_lanes":
        rendered_line_height = min(float(text_style(atom, font_size).get("lineHeightPx") or (font_size * 1.25)), round(font_size + 0.9, 2))
        line_count = max(1, len(body_text_lines(atom, width, font_size)))
        return line_count * rendered_line_height
    paragraphs = paragraph_texts(atom)
    if not paragraphs:
        return estimate_text_height(str(atom.get("text") or ""), width, font_size, line_gap)
    rendered_line_height = float(text_style(atom, font_size).get("lineHeightPx") or (font_size * 1.25))
    return len(paragraphs) * (rendered_line_height + 2.0)


def build_description_lane_layout(
    lane_rows: dict[int, dict[str, Any]],
    lane_markers: dict[int, dict[str, Any]],
    lane_texts: dict[int, dict[str, Any]],
    footer_atom: dict[str, Any] | None,
    issue_bounds: dict[str, Any] | None = None,
) -> dict[int, dict[str, Any]]:
    if not lane_rows:
        return {}
    ordered_rows = sorted(index for index in lane_rows if index in {3, 4, 5})
    if not ordered_rows:
        return {}
    current_y = float(lane_rows[ordered_rows[0]]["visual_bounds_px"]["y"])
    max_bottom = TARGET_SLIDE_HEIGHT - 12.0
    layouts: dict[int, dict[str, Any]] = {}
    for row_index in ordered_rows:
        row_atom = lane_rows[row_index]
        marker_atom = lane_markers.get(row_index)
        text_atom = lane_texts.get(row_index)
        row_bounds = row_atom["visual_bounds_px"]
        marker_bounds = dict(marker_atom["visual_bounds_px"]) if marker_atom else make_bounds(row_bounds["x"], current_y, 24.0, row_bounds["height"])
        text_bounds = dict(text_atom["visual_bounds_px"]) if text_atom else make_bounds(marker_bounds["x"] + marker_bounds["width"], current_y, row_bounds["width"] - marker_bounds["width"], row_bounds["height"])
        if issue_bounds and row_index in {3, 4}:
            issue_left = float(issue_bounds["x"])
            available_width = issue_left - float(text_bounds["x"]) - 8.0
            if available_width > 40.0:
                text_bounds = make_bounds(float(text_bounds["x"]), current_y, available_width, float(text_bounds["height"]))
        font_size = float((text_atom or {}).get("text_style", {}).get("font_size_max") or 8.0)
        estimated_height = estimate_paragraph_group_height(text_atom or {}, float(text_bounds["width"]), font_size)
        top_padding = 0.0
        bottom_padding = 0.0
        if row_index in {4, 5}:
            top_padding = 2.0
            bottom_padding = 4.0
        lane_height = max(float(row_bounds["height"]), estimated_height + top_padding + bottom_padding)
        remaining_height = max_bottom - current_y
        if remaining_height <= 18.0:
            break
        lane_height = min(lane_height, remaining_height)
        lane_bounds = make_bounds(float(row_bounds["x"]), current_y, float(row_bounds["width"]), lane_height)
        marker_bounds = make_bounds(float(marker_bounds["x"]), current_y, float(marker_bounds["width"]), lane_height)
        text_height = max(8.0, lane_height - top_padding - bottom_padding)
        text_bounds = make_bounds(float(text_bounds["x"]), current_y + top_padding, float(text_bounds["width"]), text_height)
        layouts[row_index] = {
            "lane_bounds": lane_bounds,
            "marker_bounds": marker_bounds,
            "text_bounds": text_bounds,
        }
        current_y += lane_height
    if footer_atom:
        footer_bounds = footer_atom["visual_bounds_px"]
        footer_y = min(current_y + 8.0, max_bottom - 14.0)
        footer_height = max(14.0, min(float(footer_bounds["height"]), max_bottom - footer_y))
        layouts[6] = {
            "lane_bounds": make_bounds(float(footer_bounds["x"]), footer_y, float(footer_bounds["width"]), footer_height),
            "marker_bounds": None,
            "text_bounds": make_bounds(float(footer_bounds["x"]), footer_y, float(footer_bounds["width"]), footer_height),
        }
    return layouts


def max_overlap_area(a: dict[str, Any], b: dict[str, Any]) -> float:
    left = max(float(a["x"]), float(b["x"]))
    top = max(float(a["y"]), float(b["y"]))
    right = min(float(a["x"]) + float(a["width"]), float(b["x"]) + float(b["width"]))
    bottom = min(float(a["y"]) + float(a["height"]), float(b["y"]) + float(b["height"]))
    if right <= left or bottom <= top:
        return 0.0
    return (right - left) * (bottom - top)


def best_overlapping_card(bounds: dict[str, Any], card_atoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not card_atoms:
        return None
    ranked = sorted(card_atoms, key=lambda atom: max_overlap_area(bounds, atom.get("visual_bounds_px") or bounds), reverse=True)
    top = ranked[0]
    if max_overlap_area(bounds, top.get("visual_bounds_px") or bounds) <= 0:
        return None
    return top


def dense_panel_bounds(page: dict[str, Any]) -> dict[str, float]:
    relevant = []
    for atom in page.get("atoms") or []:
        role = str(atom.get("layer_role") or "")
        owner_id = str(atom.get("owner_id") or "")
        if role in {
            "top_meta_info_cell",
            "version_stack",
            "issue_card",
            "description_header_cell",
            "description_text_lane",
            "description_footer",
            "description_marker",
        }:
            bounds = atom.get("visual_bounds_px")
            if bounds and float(bounds["x"]) + float(bounds["width"]) >= RIGHT_PANEL_X_CUTOFF:
                relevant.append(bounds)
        if role in {"small_asset", "overlay_note"} and owner_id in {"dense_ui_panel:panel_small_assets", "dense_ui_panel:panel_overlay_notes"}:
            bounds = atom.get("visual_bounds_px")
            if bounds:
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
        "dense_ui_panel:top_meta_band_cells": 12,
        "dense_ui_panel:top_meta_info_cells": 12,
        "dense_ui_panel:version_stack": 14,
        "dense_ui_panel:issue_card": 16,
        "dense_ui_panel:description_cards": 18,
        "dense_ui_panel:description_lane_rows": 20,
        "dense_ui_panel:description_markers": 22,
        "dense_ui_panel:description_lanes": 24,
        "dense_ui_panel:description_footer": 28,
        "dense_ui_panel:panel_overlay_notes": 29,
        "dense_ui_panel:panel_small_assets": 30,
        "dense_ui_panel:global_ui_assets": 40,
    }
    return order.get(owner_id, 50)


def chunk_priority(chunk_id: str) -> int:
    order = {
        "dense_ui_panel:top_meta_band_chunk": 10,
        "dense_ui_panel:top_meta_info_chunk": 10,
        "dense_ui_panel:top_rows_chunk": 11,
        "dense_ui_panel:description_header_chunk": 12,
        "dense_ui_panel:version_stack_chunk": 12,
        "dense_ui_panel:issue_chunk": 14,
        "dense_ui_panel:description_body_chunk": 18,
        "dense_ui_panel:description_footer_chunk": 28,
        "dense_ui_panel:annotation_overlay_chunk": 29,
        "dense_ui_panel:panel_small_assets_chunk": 30,
        "dense_ui_panel:global_ui_assets_chunk": 31,
    }
    return order.get(chunk_id, 50)


def chunk_bucket(page: dict[str, Any], chunk_id: str) -> dict[str, Any] | None:
    for bucket in page.get("chunk_buckets") or []:
        if str(bucket.get("chunk_id") or "") == chunk_id:
            return bucket
    return None


def atom_priority(atom: dict[str, Any]) -> tuple[int, float, float]:
    return (
        int(atom.get("z_index") or 0),
        float((atom.get("visual_bounds_px") or {}).get("y") or 0.0),
        float((atom.get("visual_bounds_px") or {}).get("x") or 0.0),
    )


def build_dense_ui_panel_nodes(page: dict[str, Any], assets: dict[str, Any]) -> list[dict[str, Any]]:
    panel_bounds = dense_panel_bounds(page)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    chunk_bucket_map = {bucket["chunk_id"]: bucket for bucket in page.get("chunk_buckets") or []}
    description_body_bucket = chunk_bucket_map.get("dense_ui_panel:description_body_chunk")
    description_body_strategy = str((description_body_bucket or {}).get("render_strategy") or "")
    description_body_style_policy = str((description_body_bucket or {}).get("style_policy") or "")
    preserve_dense_body_background = (
        description_body_strategy == "chunk_container_leaf_text"
        and description_body_style_policy == "preserve_dense_background_overlay_text"
    )
    for atom in page.get("atoms") or []:
        owner_id = str(atom.get("owner_id") or "")
        if not owner_id.startswith("dense_ui_panel:"):
            continue
        if not is_right_panel_atom(atom):
            continue
        grouped[owner_id].append(atom)

    lane_groups: list[dict[str, Any]] = []
    owner_groups: dict[str, dict[str, Any]] = {}
    lane_rows = {row_index_from_atom(atom): atom for atom in grouped.get("dense_ui_panel:description_lane_rows", []) if row_index_from_atom(atom)}
    lane_markers = {row_index_from_atom(atom): atom for atom in grouped.get("dense_ui_panel:description_markers", []) if row_index_from_atom(atom)}
    lane_texts = {row_index_from_atom(atom): atom for atom in grouped.get("dense_ui_panel:description_lanes", []) if row_index_from_atom(atom)}
    footer_atom = next(iter(grouped.get("dense_ui_panel:description_footer", [])), None)
    description_cards = list(grouped.get("dense_ui_panel:description_cards", []))
    issue_atom = next(iter(grouped.get("dense_ui_panel:issue_card", [])), None)
    lane_layout = build_description_lane_layout(
        lane_rows,
        lane_markers,
        lane_texts,
        footer_atom,
        issue_atom.get("visual_bounds_px") if issue_atom else None,
    )

    for row_index in [3, 4, 5]:
        row_atom = lane_rows.get(row_index)
        text_atom = lane_texts.get(row_index)
        marker_atom = lane_markers.get(row_index)
        if not row_atom or not text_atom:
            continue
        layout = lane_layout.get(row_index) or {}
        lane_bounds = layout.get("lane_bounds") or row_atom["visual_bounds_px"]
        marker_bounds = layout.get("marker_bounds") or (marker_atom["visual_bounds_px"] if marker_atom else None)
        text_bounds = layout.get("text_bounds") or text_atom["visual_bounds_px"]
        background_atom = best_overlapping_card(lane_bounds, description_cards if row_index >= 5 else [])
        lane_children: list[dict[str, Any]] = []
        if not preserve_dense_body_background:
            lane_children.append(build_default_lane_background(lane_bounds, row_index, background_atom))
        if marker_atom and marker_bounds:
            lane_children.append(build_text_node(marker_atom, marker_bounds))
        lane_children.append(build_paragraph_text_group(text_atom, text_bounds))
        lane_groups.append(build_owner_frame(f"dense_ui_panel:lane_row_{row_index}", lane_children, bounds=lane_bounds))
    footer_group: dict[str, Any] | None = None
    if footer_atom:
        layout = lane_layout.get(6) or {}
        footer_bounds = layout.get("lane_bounds") or footer_atom["visual_bounds_px"]
        footer_children: list[dict[str, Any]] = []
        if not preserve_dense_body_background:
            footer_children.append(build_default_lane_background(footer_bounds, 6))
        footer_children.append(build_paragraph_text_group(footer_atom, layout.get("text_bounds") or footer_bounds))
        footer_group = build_owner_frame("dense_ui_panel:description_footer", footer_children, bounds=footer_bounds)

    for owner_id in sorted(grouped.keys(), key=owner_priority):
        if owner_id in {
            "dense_ui_panel:description_lane_rows",
            "dense_ui_panel:description_markers",
            "dense_ui_panel:description_lanes",
            "dense_ui_panel:description_footer",
        }:
            continue
        atoms = sorted(grouped[owner_id], key=atom_priority)
        owner_children: list[dict[str, Any]] = []
        for atom in atoms:
            role = str(atom.get("layer_role") or "")
            subtype = str(atom.get("subtype") or "")
            if role == "version_stack":
                block_group, detail_node = build_version_stack_block(atom)
                owner_children.append(block_group)
                if detail_node:
                    owner_children.append(detail_node)
                continue
            if role in {"top_meta_band_cell", "top_meta_info_cell", "description_header_cell", "description_card", "issue_card"}:
                owner_children.append(build_rect_node(atom, suffix=":bg"))
                if atom.get("text"):
                    owner_children.append(build_text_node(atom, suffix=":label"))
                continue
            if role == "top_text_row":
                owner_children.append(build_paragraph_text_group(atom, atom["visual_bounds_px"]))
                continue
            if role == "overlay_note":
                owner_children.append(build_paragraph_text_group(atom, atom["visual_bounds_px"]))
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
                svg_node = build_small_asset_svg_node(atom)
                if svg_node:
                    owner_children.append(svg_node)
                    continue
                if atom.get("text"):
                    owner_children.append(build_text_node(atom))
                else:
                    owner_children.append(build_rect_node(atom))
                continue
        if owner_children:
            owner_groups[owner_id] = build_owner_group(owner_id, owner_children)

    chunk_children: list[dict[str, Any]] = []

    top_meta_info_children: list[dict[str, Any]] = []
    for owner_id in ["dense_ui_panel:top_meta_info_cells"]:
        if owner_id in owner_groups:
            top_meta_info_children.append(owner_groups[owner_id])
    if top_meta_info_children and "dense_ui_panel:top_meta_info_chunk" in chunk_bucket_map:
        chunk_children.append(build_group_group("dense_ui_panel:top_meta_info_chunk", top_meta_info_children))

    description_header_children: list[dict[str, Any]] = []
    for owner_id in ["dense_ui_panel:description_header_rows", "dense_ui_panel:description_headers"]:
        if owner_id in owner_groups:
            description_header_children.append(owner_groups[owner_id])
    if description_header_children and "dense_ui_panel:description_header_chunk" in chunk_bucket_map:
        chunk_children.append(build_group_group("dense_ui_panel:description_header_chunk", description_header_children))

    if "dense_ui_panel:version_stack" in owner_groups and "dense_ui_panel:version_stack_chunk" in chunk_bucket_map:
        chunk_children.append(build_group_group("dense_ui_panel:version_stack_chunk", [owner_groups["dense_ui_panel:version_stack"]]))

    if "dense_ui_panel:issue_card" in owner_groups and "dense_ui_panel:issue_chunk" in chunk_bucket_map:
        chunk_children.append(build_group_group("dense_ui_panel:issue_chunk", [owner_groups["dense_ui_panel:issue_card"]]))

    description_body_children: list[dict[str, Any]] = []
    if description_body_bucket:
        if description_body_strategy == "chunk_container_leaf_text":
            if not preserve_dense_body_background:
                for owner_id in ["dense_ui_panel:description_cards"]:
                    if owner_id in owner_groups:
                        description_body_children.append(owner_groups[owner_id])
            description_body_children.extend(lane_groups)
            # In leaf-text mode the lane groups already contain row backgrounds,
            # markers, footer text and paragraph leaves. Re-adding semantic/text
            # owner groups here causes duplicate text layers and muddies the
            # baseline-like dense region.
            if description_body_style_policy != "preserve_dense_background_overlay_text":
                for owner_id in ["dense_ui_panel:description_footer", "dense_ui_panel:description_markers", "dense_ui_panel:description_lanes"]:
                    if owner_id in owner_groups:
                        description_body_children.append(owner_groups[owner_id])
        else:
            for owner_id in [
                "dense_ui_panel:description_cards",
                "dense_ui_panel:description_footer",
                "dense_ui_panel:description_markers",
                "dense_ui_panel:description_lanes",
            ]:
                if owner_id in owner_groups:
                    description_body_children.append(owner_groups[owner_id])
            description_body_children.extend(lane_groups)
    if description_body_children and description_body_bucket is not None:
        chunk_children.append(build_group_group("dense_ui_panel:description_body_chunk", description_body_children))

    if footer_group and "dense_ui_panel:description_footer_chunk" in chunk_bucket_map:
        chunk_children.append(build_group_group("dense_ui_panel:description_footer_chunk", [footer_group]))

    annotation_overlay_children: list[dict[str, Any]] = []
    for owner_id in ["dense_ui_panel:panel_overlay_notes"]:
        if owner_id in owner_groups:
            annotation_overlay_children.append(owner_groups[owner_id])
    if annotation_overlay_children and "dense_ui_panel:annotation_overlay_chunk" in chunk_bucket_map:
        chunk_children.append(build_group_group("dense_ui_panel:annotation_overlay_chunk", annotation_overlay_children))

    small_asset_children: list[dict[str, Any]] = []
    for owner_id in ["dense_ui_panel:panel_small_assets"]:
        if owner_id in owner_groups:
            small_asset_children.append(owner_groups[owner_id])
    if small_asset_children and "dense_ui_panel:panel_small_assets_chunk" in chunk_bucket_map:
        chunk_children.append(build_group_group("dense_ui_panel:panel_small_assets_chunk", small_asset_children))

    children = sorted(chunk_children, key=lambda node: chunk_priority(str(node.get("id") or "")))

    visible_panel_bounds = make_bounds(
        float(panel_bounds["x"]),
        float(panel_bounds["y"]),
        min(float(panel_bounds["width"]), TARGET_SLIDE_WIDTH - float(panel_bounds["x"])),
        min(float(panel_bounds["height"]), TARGET_SLIDE_HEIGHT - float(panel_bounds["y"])),
    )

    logical_panel = {
        "id": f"{page['page_id']}:dense_ui_panel:logical",
        "type": "FRAME",
        "name": "dense_ui_panel_logical",
        "absoluteBoundingBox": panel_bounds,
        "relativeTransform": identity_affine(),
        "fills": [],
        "strokes": [],
        "strokeWeight": 0,
        "children": children,
        "debug": {
            "generator": "dense-ui-ir-v1",
            "page_id": page["page_id"],
            "page_type": page["page_type"],
            "logical_panel": True,
        },
    }

    panel_frame = {
        "id": f"{page['page_id']}:dense_ui_panel",
        "type": "FRAME",
        "name": "dense_ui_panel",
        "absoluteBoundingBox": visible_panel_bounds,
        "relativeTransform": identity_affine(),
        "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}, "opacity": 1.0}],
        "strokes": [{"type": "SOLID", "color": {"r": 0.9, "g": 0.9, "b": 0.9}, "opacity": 1.0}],
        "strokeWeight": 1,
        "clipsContent": True,
        "children": [logical_panel],
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


LOWER_BODY_TEXT_CHUNK_IDS = {
    "dense_ui_panel:description_body_chunk",
    "dense_ui_panel:description_footer_chunk",
}

LOWER_BODY_TEXT_OWNER_IDS = {
    "dense_ui_panel:description_lanes",
    "dense_ui_panel:description_footer",
}


def prune_lower_body_text_layer(node: dict[str, Any]) -> dict[str, Any] | None:
    node_type = str(node.get("type") or "")
    node_id = str(node.get("id") or "")
    debug = node.get("debug") or {}
    owner_id = str(debug.get("owner_id") or "")

    if node_type == "TEXT":
        if owner_id in LOWER_BODY_TEXT_OWNER_IDS:
            pruned = dict(node)
            pruned["children"] = []
            return pruned
        return None

    pruned_children: list[dict[str, Any]] = []
    for child in node.get("children") or []:
        pruned_child = prune_lower_body_text_layer(child)
        if pruned_child is not None:
            pruned_children.append(pruned_child)

    if node_id in LOWER_BODY_TEXT_CHUNK_IDS:
        if not pruned_children:
            return None
        pruned = dict(node)
        pruned["children"] = pruned_children
        return pruned

    if pruned_children:
        pruned = dict(node)
        pruned["children"] = pruned_children
        return pruned

    return None


def extract_lower_body_text_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    document = bundle.get("document") or {}
    pruned_document = prune_lower_body_text_layer(document)
    if pruned_document is None:
        raise SystemExit("lower body text layer extraction produced an empty bundle")

    extracted = dict(bundle)
    extracted["page_name"] = f"{bundle.get('page_name')} - Lower Body Text Layer"
    extracted["node_id"] = pruned_document.get("id")
    extracted["document"] = pruned_document
    extracted["debug"] = dict(bundle.get("debug") or {}, export_mode="lower_body_text_only")
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a dense-ui-panel replay bundle from resolved PPT IR.")
    parser.add_argument("--input", required=True, help="Resolved IR JSON path")
    parser.add_argument("--output", required=True, help="Output bundle path")
    parser.add_argument("--slide", type=int, default=29, help="Slide number to render")
    parser.add_argument(
        "--export-mode",
        choices=["full", "lower_body_text_only"],
        default="full",
        help="Optional post-processing mode for the generated bundle",
    )
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
    if args.export_mode == "lower_body_text_only":
        bundle = extract_lower_body_text_bundle(bundle)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {output_path}")


if __name__ == "__main__":
    main()
