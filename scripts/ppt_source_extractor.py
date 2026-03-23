#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


TARGET_SLIDE_WIDTH = 960.0
TARGET_SLIDE_HEIGHT = 540.0


def load_intermediate_payload(input_path: str | Path) -> dict[str, Any]:
    path = Path(input_path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def identity_affine() -> list[list[float]]:
    return [[1, 0, 0], [0, 1, 0]]


def make_bounds(x: float, y: float, width: float, height: float) -> dict[str, float]:
    return {
        "x": round(float(x), 2),
        "y": round(float(y), 2),
        "width": round(max(float(width), 1.0), 2),
        "height": round(max(float(height), 1.0), 2),
    }


def normalize_degrees(value: float | int | None) -> float:
    degrees = float(value or 0)
    while degrees > 180:
        degrees -= 360
    while degrees <= -180:
        degrees += 360
    return round(degrees, 2)


def relative_transform_from_bounds(bounds: dict[str, Any] | None) -> list[list[float]]:
    if not bounds:
        return identity_affine()
    rotation = normalize_degrees(bounds.get("rotation", 0))
    radians = math.radians(rotation)
    scale_x = -1.0 if bounds.get("flipH") else 1.0
    scale_y = -1.0 if bounds.get("flipV") else 1.0
    cos_v = math.cos(radians)
    sin_v = math.sin(radians)
    return [
        [round(cos_v * scale_x, 6), round(-sin_v * scale_y, 6), 0],
        [round(sin_v * scale_x, 6), round(cos_v * scale_y, 6), 0],
    ]


def build_page_scale(page: dict[str, Any]) -> tuple[float, float]:
    slide_size = page.get("slide_size") or {}
    width = float(slide_size.get("width_px") or TARGET_SLIDE_WIDTH)
    height = float(slide_size.get("height_px") or TARGET_SLIDE_HEIGHT)
    scale_x = TARGET_SLIDE_WIDTH / width if width else 1.0
    scale_y = TARGET_SLIDE_HEIGHT / height if height else 1.0
    return scale_x, scale_y


def scale_value(value: float | int | None, scale: float) -> float:
    return float(value or 0) * scale


def scale_bounds(bounds: dict[str, Any] | None, scale_x: float, scale_y: float) -> dict[str, float]:
    bounds = bounds or {}
    return make_bounds(
        scale_value(bounds.get("x"), scale_x),
        scale_value(bounds.get("y"), scale_y),
        scale_value(bounds.get("width", 120), scale_x),
        scale_value(bounds.get("height", 24), scale_y),
    )


def scale_point(point: dict[str, Any] | None, scale_x: float, scale_y: float) -> dict[str, float] | None:
    if not point:
        return None
    return {
        "x": round(scale_value(point.get("x"), scale_x), 2),
        "y": round(scale_value(point.get("y"), scale_y), 2),
    }


def sort_by_position_key(candidate: dict[str, Any]) -> tuple[float, float]:
    bounds = candidate.get("bounds_px") or {}
    return (float(bounds.get("y", 0)), float(bounds.get("x", 0)))


def build_children_map(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_parent.setdefault(candidate.get("parent_candidate_id", ""), []).append(candidate)
    return by_parent


def build_page_context(page: dict[str, Any]) -> dict[str, Any]:
    scale_x, scale_y = build_page_scale(page)
    candidates = page.get("candidates") or []
    return {
        "page": page,
        "page_id": page.get("page_id") or f"page:{page.get('slide_no')}",
        "slide_no": page.get("slide_no"),
        "title": page.get("title_or_label") or f"Slide {page.get('slide_no')}",
        "scale_x": scale_x,
        "scale_y": scale_y,
        "width": TARGET_SLIDE_WIDTH,
        "height": TARGET_SLIDE_HEIGHT,
        "candidates": candidates,
        "children_map": build_children_map(candidates),
        "roots": sorted(build_children_map(candidates).get(page.get("page_id"), []), key=sort_by_position_key),
    }


def build_source_debug(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": candidate.get("source_path", ""),
        "source_node_id": candidate.get("source_node_id", ""),
        "source_subtype": candidate.get("subtype", ""),
    }


def iter_selected_pages(payload: dict[str, Any], slide_numbers: set[int] | None = None) -> list[dict[str, Any]]:
    pages = payload.get("pages") or []
    if not slide_numbers:
        return pages
    return [page for page in pages if int(page.get("slide_no") or 0) in slide_numbers]
