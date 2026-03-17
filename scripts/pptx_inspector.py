#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile
import xml.etree.ElementTree as ET


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"p": P_NS, "r": R_NS, "a": A_NS}
CORE_SLIDES = {12, 26, 29, 34}


@dataclass
class SlideInspection:
    slide_no: int
    slide_path: str
    rel_path: str | None
    title_or_label: str
    shape_count: int
    group_count: int
    image_count: int
    graphic_frame_count: int
    table_count: int
    text_node_count: int
    has_notes: bool
    hidden: bool


def _local_name(tag: str) -> str:
    return tag.split("}")[-1]


def _normalize_text(value: str | None, slide_no: int) -> str:
    if value is None:
        return f"Slide {slide_no}"
    normalized = " ".join(value.split()).strip()
    return normalized or f"Slide {slide_no}"


def _first_text(shape: ET.Element) -> str | None:
    texts: list[str] = []
    for node in shape.findall(".//a:t", NS):
        if node.text and node.text.strip():
            texts.append(node.text.strip())
    if texts:
        return " ".join(texts)
    return None


def _infer_title(shapes: Iterable[ET.Element], slide_no: int) -> str:
    for shape in shapes:
        text = _first_text(shape)
        if text:
            return _normalize_text(text, slide_no)
    return f"Slide {slide_no}"


def _extract_xfrm(node: ET.Element | None) -> dict[str, int] | None:
    if node is None:
        return None
    off = node.find("a:off", NS)
    ext = node.find("a:ext", NS)
    if off is None and ext is None:
        return None
    return {
        "x": int(off.attrib.get("x", "0")) if off is not None else 0,
        "y": int(off.attrib.get("y", "0")) if off is not None else 0,
        "cx": int(ext.attrib.get("cx", "0")) if ext is not None else 0,
        "cy": int(ext.attrib.get("cy", "0")) if ext is not None else 0,
    }


def _extract_cnvpr(container: ET.Element | None) -> dict[str, Any]:
    if container is None:
        return {"id": None, "name": None}
    c_nv_pr = container.find(".//p:cNvPr", NS)
    if c_nv_pr is None:
        return {"id": None, "name": None}
    return {
        "id": c_nv_pr.attrib.get("id"),
        "name": c_nv_pr.attrib.get("name"),
        "descr": c_nv_pr.attrib.get("descr"),
    }


def _extract_text_runs(node: ET.Element) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for paragraph in node.findall(".//a:p", NS):
        paragraph_runs: list[dict[str, Any]] = []
        for child in list(paragraph):
            tag = _local_name(child.tag)
            if tag not in {"r", "fld", "br"}:
                continue
            if tag == "br":
                paragraph_runs.append({"type": "line_break", "text": "\n"})
                continue
            text_node = child.find("a:t", NS)
            if text_node is None or not text_node.text:
                continue
            r_pr = child.find("a:rPr", NS)
            paragraph_runs.append(
                {
                    "type": "text",
                    "text": text_node.text,
                    "font_size": int(r_pr.attrib.get("sz", "0")) / 100 if r_pr is not None and r_pr.attrib.get("sz") else None,
                    "bold": r_pr.attrib.get("b") == "1" if r_pr is not None else False,
                    "italic": r_pr.attrib.get("i") == "1" if r_pr is not None else False,
                }
            )
        if paragraph_runs:
            runs.extend(paragraph_runs)
    return runs


def _extract_shape_kind(node: ET.Element) -> str | None:
    if _local_name(node.tag) == "cxnSp":
        return "connector"
    geom = node.find("p:spPr/a:prstGeom", NS)
    if geom is not None:
        return geom.attrib.get("prst")
    return None


def _extract_table(frame: ET.Element) -> dict[str, Any] | None:
    table = frame.find(".//a:tbl", NS)
    if table is None:
        return None
    rows_payload: list[dict[str, Any]] = []
    for row_index, row in enumerate(table.findall("a:tr", NS), start=1):
        cells_payload: list[dict[str, Any]] = []
        for cell_index, cell in enumerate(row.findall("a:tc", NS), start=1):
            texts = []
            for text_node in cell.findall(".//a:t", NS):
                if text_node.text and text_node.text.strip():
                    texts.append(text_node.text.strip())
            cells_payload.append(
                {
                    "cell_index": cell_index,
                    "text": " ".join(texts).strip(),
                    "grid_span": cell.attrib.get("gridSpan"),
                    "row_span": cell.attrib.get("rowSpan"),
                    "h_merge": cell.attrib.get("hMerge"),
                    "v_merge": cell.attrib.get("vMerge"),
                }
            )
        rows_payload.append(
            {
                "row_index": row_index,
                "height": row.attrib.get("h"),
                "cells": cells_payload,
            }
        )
    return {
        "row_count": len(rows_payload),
        "rows": rows_payload,
    }


def _extract_picture(node: ET.Element, rel_targets: dict[str, str]) -> dict[str, Any]:
    blip = node.find(".//a:blip", NS)
    embed = blip.attrib.get(f"{{{R_NS}}}embed") if blip is not None else None
    return {
        "image_rel_id": embed,
        "image_target": rel_targets.get(embed) if embed else None,
    }


def _extract_element(node: ET.Element, rel_targets: dict[str, str]) -> dict[str, Any]:
    tag = _local_name(node.tag)
    meta = _extract_cnvpr(node)

    if tag == "grpSp":
        children = [
            _extract_element(child, rel_targets)
            for child in list(node)
            if _local_name(child.tag) not in {"nvGrpSpPr", "grpSpPr"}
        ]
        return {
            "element_type": "group",
            "node_tag": tag,
            "node_id": meta.get("id"),
            "name": meta.get("name"),
            "descr": meta.get("descr"),
            "bounds": _extract_xfrm(node.find("p:grpSpPr/a:xfrm", NS)),
            "children": children,
        }

    payload: dict[str, Any] = {
        "element_type": {
            "sp": "shape",
            "cxnSp": "connector",
            "graphicFrame": "graphic_frame",
            "pic": "image",
        }.get(tag, tag),
        "node_tag": tag,
        "node_id": meta.get("id"),
        "name": meta.get("name"),
        "descr": meta.get("descr"),
        "children": [],
    }

    if tag in {"sp", "cxnSp"}:
        payload["bounds"] = _extract_xfrm(node.find("p:spPr/a:xfrm", NS))
        payload["shape_kind"] = _extract_shape_kind(node)
        payload["text_runs"] = _extract_text_runs(node)
        payload["text"] = "".join(run["text"] for run in payload["text_runs"] if run["type"] == "text").strip()
    elif tag == "graphicFrame":
        payload["bounds"] = _extract_xfrm(node.find("p:xfrm", NS))
        table_payload = _extract_table(node)
        payload["table"] = table_payload
        payload["frame_kind"] = "table" if table_payload else "graphic_frame"
    elif tag == "pic":
        payload["bounds"] = _extract_xfrm(node.find("p:spPr/a:xfrm", NS))
        payload.update(_extract_picture(node, rel_targets))
    else:
        payload["bounds"] = None

    return payload


def _slide_rel_targets(archive: ZipFile, slide_path: str) -> dict[str, str]:
    rel_path = slide_path.replace("/slides/", "/slides/_rels/") + ".rels"
    if rel_path not in archive.namelist():
        return {}
    rel_root = ET.fromstring(archive.read(rel_path))
    mapping: dict[str, str] = {}
    for rel in rel_root.findall("{*}Relationship"):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            mapping[rel_id] = target
    return mapping


def extract_slide_details(pptx_path: Path, slide_numbers: list[int]) -> dict[str, Any]:
    inspections = inspect_pptx(pptx_path)
    inspection_by_no = {item.slide_no: item for item in inspections}

    with ZipFile(pptx_path) as archive:
        slides_payload: list[dict[str, Any]] = []
        for slide_no in slide_numbers:
            inspection = inspection_by_no.get(slide_no)
            if inspection is None:
                raise ValueError(f"Slide {slide_no} not found in {pptx_path}")

            slide_root = ET.fromstring(archive.read(inspection.slide_path))
            sp_tree = slide_root.find("p:cSld/p:spTree", NS)
            if sp_tree is None:
                raise ValueError(f"Missing spTree in {inspection.slide_path}")

            rel_targets = _slide_rel_targets(archive, inspection.slide_path)
            elements = [
                _extract_element(child, rel_targets)
                for child in list(sp_tree)
                if _local_name(child.tag) not in {"nvGrpSpPr", "grpSpPr"}
            ]

            slides_payload.append(
                {
                    "slide_no": slide_no,
                    "title_or_label": inspection.title_or_label,
                    "slide_path": inspection.slide_path,
                    "summary": asdict(inspection),
                    "elements": elements,
                }
            )

        return {
            "pptxPath": str(pptx_path),
            "requestedSlides": slide_numbers,
            "slides": slides_payload,
        }


def inspect_pptx(pptx_path: Path) -> list[SlideInspection]:
    with ZipFile(pptx_path) as archive:
        presentation_root = ET.fromstring(archive.read("ppt/presentation.xml"))
        presentation_rels_root = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))

        rel_by_id: dict[str, str] = {}
        for rel in presentation_rels_root.findall("{*}Relationship"):
            rel_id = rel.attrib.get("Id")
            target = rel.attrib.get("Target")
            if rel_id and target:
                rel_by_id[rel_id] = target

        slide_refs = presentation_root.findall("p:sldIdLst/p:sldId", NS)
        inspections: list[SlideInspection] = []

        for index, slide_ref in enumerate(slide_refs, start=1):
            rel_id = slide_ref.attrib.get(f"{{{R_NS}}}id")
            if not rel_id or rel_id not in rel_by_id:
                raise ValueError(f"Missing relationship target for slide {index}")

            target = rel_by_id[rel_id].lstrip("/")
            slide_path = f"ppt/{target}"
            rel_path = slide_path.replace("/slides/", "/slides/_rels/") + ".rels"
            slide_root = ET.fromstring(archive.read(slide_path))
            sp_tree = slide_root.find("p:cSld/p:spTree", NS)
            if sp_tree is None:
                raise ValueError(f"Missing spTree in {slide_path}")

            shapes = sp_tree.findall("p:sp", NS)
            groups = sp_tree.findall("p:grpSp", NS)
            pictures = sp_tree.findall("p:pic", NS)
            graphic_frames = sp_tree.findall("p:graphicFrame", NS)
            tables = [frame for frame in graphic_frames if frame.find(".//a:tbl", NS) is not None]
            text_node_count = sum(1 for shape in shapes if _first_text(shape))
            title_or_label = _infer_title(shapes, index)
            notes_path = f"ppt/notesSlides/notesSlide{index}.xml"

            inspections.append(
                SlideInspection(
                    slide_no=index,
                    slide_path=slide_path,
                    rel_path=rel_path if rel_path in archive.namelist() else None,
                    title_or_label=title_or_label,
                    shape_count=len(shapes),
                    group_count=len(groups),
                    image_count=len(pictures),
                    graphic_frame_count=len(graphic_frames),
                    table_count=len(tables),
                    text_node_count=text_node_count,
                    has_notes=notes_path in archive.namelist(),
                    hidden=slide_root.attrib.get("show") == "0",
                )
            )

        return inspections


def _infer_structure_tags(slide: SlideInspection) -> list[str]:
    tags: list[str] = []
    if slide.table_count > 0:
        tags.extend(["table", "cell"])
    if slide.group_count > 0:
        tags.extend(["group", "section"])
    if slide.image_count > 0:
        tags.append("image")
    if slide.text_node_count > 1:
        tags.append("mixed_text")
    if slide.shape_count >= 10:
        tags.append("complex_layout")
    return sorted(set(tags))


def _infer_difficulty(slide: SlideInspection) -> str:
    complexity = slide.table_count * 3 + slide.group_count * 2 + slide.image_count + slide.shape_count // 8
    if complexity >= 5:
        return "high"
    if complexity >= 2:
        return "medium"
    return "low"


def _infer_risk_notes(slide: SlideInspection) -> list[str]:
    notes: list[str] = []
    if slide.table_count > 0:
        notes.append("table/cell preservation risk")
    if slide.group_count > 0:
        notes.append("group/section hierarchy flattening risk")
    if slide.image_count > 0:
        notes.append("image asset positioning risk")
    if slide.text_node_count > 3:
        notes.append("mixed text and font handling risk")
    if slide.hidden:
        notes.append("hidden slide state detected")
    return notes


def build_benchmark_metadata(slides: list[SlideInspection], pptx_path: Path) -> dict:
    return {
        "benchmarkFile": str(pptx_path),
        "detectedSlideCount": len(slides),
        "coreSlides": sorted(CORE_SLIDES),
        "slides": [
            {
                "slide_no": slide.slide_no,
                "title_or_label": slide.title_or_label,
                "difficulty": _infer_difficulty(slide),
                "structure_tags": _infer_structure_tags(slide),
                "risk_notes": _infer_risk_notes(slide),
                "must_pass": "yes" if slide.slide_no in CORE_SLIDES else "no",
                "human_review_required": "yes" if slide.slide_no in CORE_SLIDES else "no",
                "auto_result": "",
                "human_result": "",
                "notes": "core benchmark slide" if slide.slide_no in CORE_SLIDES else "",
            }
            for slide in slides
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a PPTX file and optionally generate benchmark metadata.")
    parser.add_argument("pptx_path", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, help="Write benchmark metadata JSON to this path.")
    parser.add_argument("--detail-slides", dest="detail_slides", help="Comma-separated slide numbers for detailed extraction.")
    parser.add_argument("--detail-json", dest="detail_json_path", type=Path, help="Write detailed slide extraction JSON to this path.")
    args = parser.parse_args()

    slides = inspect_pptx(args.pptx_path)
    payload = {
        "pptxPath": str(args.pptx_path),
        "slideCount": len(slides),
        "slides": [asdict(slide) for slide in slides],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.json_path:
        metadata = build_benchmark_metadata(slides, args.pptx_path)
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nGenerated benchmark metadata: {args.json_path}")

    if args.detail_slides:
        slide_numbers = [int(part.strip()) for part in args.detail_slides.split(",") if part.strip()]
        detail_payload = extract_slide_details(args.pptx_path, slide_numbers)
        serialized = json.dumps(detail_payload, ensure_ascii=False, indent=2)
        if args.detail_json_path:
            args.detail_json_path.parent.mkdir(parents=True, exist_ok=True)
            args.detail_json_path.write_text(serialized + "\n", encoding="utf-8")
            print(f"\nGenerated detailed extraction: {args.detail_json_path}")
        else:
            print(f"\n{serialized}")


if __name__ == "__main__":
    main()
