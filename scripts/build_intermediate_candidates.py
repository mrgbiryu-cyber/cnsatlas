#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EMU_PER_PIXEL = 9525


def emu_bounds_to_px(bounds: dict[str, int] | None) -> dict[str, float] | None:
    if not bounds:
        return None
    return {
        "x": round(bounds.get("x", 0) / EMU_PER_PIXEL, 2),
        "y": round(bounds.get("y", 0) / EMU_PER_PIXEL, 2),
        "width": round(bounds.get("cx", 0) / EMU_PER_PIXEL, 2),
        "height": round(bounds.get("cy", 0) / EMU_PER_PIXEL, 2),
    }


def classify_group(element: dict[str, Any]) -> str:
    bounds = element.get("bounds") or {}
    child_count = len(element.get("children", []) or [])
    area = bounds.get("cx", 0) * bounds.get("cy", 0)
    if child_count >= 4 or area >= 10_000_000_000_000:
        return "section_block"
    return "group"


def classify_shape(element: dict[str, Any]) -> tuple[str, str]:
    text = (element.get("text") or "").strip()
    kind = element.get("shape_kind") or "shape"
    if element.get("element_type") == "connector":
        return "connector", "connector"
    if text and kind in {"rect", "roundRect", "ellipse"}:
        return "labeled_shape", kind
    if text:
        return "text_block", kind
    return "shape", kind


def make_candidate(
    *,
    candidate_id: str,
    parent_candidate_id: str | None,
    slide_no: int,
    node_type: str,
    subtype: str,
    title: str,
    text: str,
    source_path: str,
    source_node_id: str | None,
    bounds_emu: dict[str, int] | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "candidate_id": candidate_id,
        "parent_candidate_id": parent_candidate_id,
        "slide_no": slide_no,
        "node_type": node_type,
        "subtype": subtype,
        "title": title,
        "text": text,
        "source_path": source_path,
        "source_node_id": source_node_id,
        "bounds_emu": bounds_emu,
        "bounds_px": emu_bounds_to_px(bounds_emu),
    }
    if extra:
        payload["extra"] = extra
    return payload


def append_element_candidates(
    *,
    slide_no: int,
    element: dict[str, Any],
    source_path: str,
    parent_candidate_id: str | None,
    candidates: list[dict[str, Any]],
) -> None:
    element_type = element.get("element_type")
    candidate_id = f"s{slide_no}:{source_path}"
    title = element.get("name") or element.get("text") or element_type or "element"
    text = (element.get("text") or "").strip()

    if element_type == "group":
        subtype = classify_group(element)
        candidates.append(
            make_candidate(
                candidate_id=candidate_id,
                parent_candidate_id=parent_candidate_id,
                slide_no=slide_no,
                node_type="node",
                subtype=subtype,
                title=title,
                text=text,
                source_path=source_path,
                source_node_id=element.get("node_id"),
                bounds_emu=element.get("bounds"),
                extra={
                    "child_count": len(element.get("children", []) or []),
                    "shape_style": element.get("shape_style"),
                },
            )
        )
        for index, child in enumerate(element.get("children", []) or [], start=1):
            append_element_candidates(
                slide_no=slide_no,
                element=child,
                source_path=f"{source_path}/child_{index}",
                parent_candidate_id=candidate_id,
                candidates=candidates,
            )
        return

    if element_type == "graphic_frame" and element.get("table"):
        table = element["table"]
        candidates.append(
            make_candidate(
                candidate_id=candidate_id,
                parent_candidate_id=parent_candidate_id,
                slide_no=slide_no,
                node_type="node",
                subtype="table",
                title=title,
                text="",
                source_path=source_path,
                source_node_id=element.get("node_id"),
                bounds_emu=element.get("bounds"),
                extra={
                    "row_count": table.get("row_count", 0),
                },
            )
        )
        for row in table.get("rows", []):
            row_id = f"{candidate_id}:row_{row['row_index']}"
            candidates.append(
                make_candidate(
                    candidate_id=row_id,
                    parent_candidate_id=candidate_id,
                    slide_no=slide_no,
                    node_type="node",
                    subtype="table_row",
                    title=f"row {row['row_index']}",
                    text="",
                    source_path=f"{source_path}/row_{row['row_index']}",
                    source_node_id=element.get("node_id"),
                    bounds_emu=None,
                    extra={"height": row.get("height"), "cell_count": len(row.get("cells", []))},
                )
            )
            for cell in row.get("cells", []):
                candidates.append(
                    make_candidate(
                        candidate_id=f"{row_id}:cell_{cell['cell_index']}",
                        parent_candidate_id=row_id,
                        slide_no=slide_no,
                        node_type="node",
                        subtype="table_cell",
                        title=f"cell {row['row_index']}-{cell['cell_index']}",
                        text=cell.get("text", ""),
                        source_path=f"{source_path}/row_{row['row_index']}/cell_{cell['cell_index']}",
                        source_node_id=element.get("node_id"),
                        bounds_emu=None,
                        extra={
                            "row_height_emu": row.get("height"),
                            "row_height_px": round(int(row["height"]) / EMU_PER_PIXEL, 2) if row.get("height") else None,
                            "grid_span": cell.get("grid_span"),
                            "row_span": cell.get("row_span"),
                            "h_merge": cell.get("h_merge"),
                            "v_merge": cell.get("v_merge"),
                        },
                    )
                )
        return

    if element_type == "image":
        candidates.append(
            make_candidate(
                candidate_id=candidate_id,
                parent_candidate_id=parent_candidate_id,
                slide_no=slide_no,
                node_type="asset",
                subtype="image",
                title=title,
                text="",
                source_path=source_path,
                source_node_id=element.get("node_id"),
                bounds_emu=element.get("bounds"),
                extra={"image_target": element.get("image_target")},
            )
        )
        return

    node_subtype, shape_subtype = classify_shape(element)
    candidates.append(
        make_candidate(
            candidate_id=candidate_id,
            parent_candidate_id=parent_candidate_id,
            slide_no=slide_no,
            node_type="node",
            subtype=node_subtype,
            title=title,
            text=text,
            source_path=source_path,
            source_node_id=element.get("node_id"),
            bounds_emu=element.get("bounds"),
            extra={
                "shape_kind": shape_subtype,
                "shape_style": element.get("shape_style"),
                "text_style": element.get("text_style"),
            },
        )
    )


def build_intermediate_model(detail_payload: dict[str, Any]) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []

    for slide in detail_payload["slides"]:
        slide_no = slide["slide_no"]
        page_id = f"page:{slide_no}"
        candidates: list[dict[str, Any]] = []

        for index, element in enumerate(slide["elements"], start=1):
            append_element_candidates(
                slide_no=slide_no,
                element=element,
                source_path=f"slide_{slide_no}/element_{index}",
                parent_candidate_id=page_id,
                candidates=candidates,
            )

        pages.append(
            {
                "page_id": page_id,
                "slide_no": slide_no,
                "title_or_label": slide["title_or_label"],
                "source_path": slide["slide_path"],
                "slide_size": slide.get("slide_size"),
                "summary": slide["summary"],
                "candidates": candidates,
            }
        )

    return {
        "pptxPath": detail_payload["pptxPath"],
        "requestedSlides": detail_payload["requestedSlides"],
        "pages": pages,
    }


def summarize_page(page: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for candidate in page["candidates"]:
        counts[candidate["subtype"]] = counts.get(candidate["subtype"], 0) + 1
    return {
        "slide_no": page["slide_no"],
        "title_or_label": page["title_or_label"],
        "candidate_count": len(page["candidates"]),
        "candidate_subtypes": counts,
    }


def main() -> None:
    input_path = Path("docs/ppt-slide-details-12-19-29.json")
    output_path = Path("docs/ppt-intermediate-candidates-12-19-29.json")
    summary_path = Path("docs/ppt-intermediate-candidates-summary-12-19-29.json")

    detail_payload = json.loads(input_path.read_text(encoding="utf-8"))
    intermediate = build_intermediate_model(detail_payload)
    output_path.write_text(json.dumps(intermediate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "pptxPath": intermediate["pptxPath"],
        "requestedSlides": intermediate["requestedSlides"],
        "pages": [summarize_page(page) for page in intermediate["pages"]],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Generated intermediate candidates: {output_path}")
    print(f"Generated summary: {summary_path}")


if __name__ == "__main__":
    main()
