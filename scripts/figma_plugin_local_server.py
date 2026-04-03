#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from build_intermediate_candidates import build_intermediate_model
from build_dense_ui_panel_ir_bundle import build_bundle as build_dense_ui_panel_bundle
from build_resolved_ppt_ir import build_page_ir
from build_visual_first_replay_bundle import build_bundle_from_page
from pptx_inspector import extract_slide_details


def parse_slides(raw: Any) -> list[int]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [int(item) for item in raw]
    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",")]
        return [int(item) for item in values if item]
    raise ValueError("slides must be a list or comma-separated string")


def _to_windows_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt":
        return resolved
    try:
        converted = subprocess.run(
            ["wslpath", "-w", resolved],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if converted:
            return converted
    except Exception:
        pass
    return resolved


def _pick_slide_export_size(intermediate: dict[str, Any]) -> tuple[int, int]:
    for page in intermediate.get("pages") or []:
        slide_size = page.get("slide_size") or {}
        width = int(round(float(slide_size.get("width_px") or 0)))
        height = int(round(float(slide_size.get("height_px") or 0)))
        if width > 0 and height > 0:
            return width, height
    return 0, 0


def try_render_slide_pngs(
    *,
    pptx_path: Path,
    slide_numbers: list[int],
    output_dir: Path,
    width: int,
    height: int,
) -> tuple[dict[int, dict[str, Any]], str]:
    script_path = Path(__file__).resolve().parent / "export_pptx_slides_png.ps1"
    if not script_path.exists():
        return {}, "missing-export-script"
    if not slide_numbers:
        return {}, "no-slides"

    output_dir.mkdir(parents=True, exist_ok=True)
    slides_csv = ",".join(str(int(slide)) for slide in slide_numbers)
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        _to_windows_path(script_path),
        "-InputPptx",
        _to_windows_path(pptx_path),
        "-OutputDir",
        _to_windows_path(output_dir),
        "-Slides",
        slides_csv,
    ]
    if width > 0 and height > 0:
        cmd.extend(["-Width", str(width), "-Height", str(height)])

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )
    except Exception:
        return {}, "powershell-export-failed"

    rendered: dict[int, dict[str, Any]] = {}
    for slide_no in slide_numbers:
        image_path = output_dir / f"slide-{int(slide_no)}.png"
        if not image_path.exists():
            continue
        rendered[int(slide_no)] = {
            "filename": image_path.name,
            "mime_type": "image/png",
            "base64": base64.b64encode(image_path.read_bytes()).decode("ascii"),
            "source": "pptx-slide-export",
        }
    return rendered, ("ok" if rendered else "no-images")


def attach_slide_background_to_bundle(bundle: dict[str, Any], slide_background: dict[str, Any] | None) -> dict[str, Any]:
    if not slide_background or not slide_background.get("base64"):
        return bundle
    document = bundle.get("document") or {}
    doc_bounds = document.get("absoluteBoundingBox") or {}
    slide_no = (document.get("debug") or {}).get("source_slide_no")
    if not isinstance(slide_no, int):
        slide_no = 0
    width = float(doc_bounds.get("width") or 0)
    height = float(doc_bounds.get("height") or 0)
    if width <= 0 or height <= 0:
        return bundle

    frame = None
    if document.get("type") == "FRAME" and isinstance(document.get("children"), list) and document["children"]:
        first_child = document["children"][0]
        if isinstance(first_child, dict) and first_child.get("type") == "FRAME":
            frame = first_child
    if frame is None:
        return bundle

    image_ref = f"slide-bg-{slide_no}" if slide_no > 0 else "slide-bg"
    assets = bundle.setdefault("assets", {})
    assets[image_ref] = {
        "filename": slide_background.get("filename") or (f"slide-{slide_no}.png" if slide_no > 0 else "slide.png"),
        "mime_type": slide_background.get("mime_type") or "image/png",
        "base64": slide_background.get("base64"),
    }

    frame_children = frame.setdefault("children", [])
    frame_children = [
        child
        for child in frame_children
        if not (
            str(child.get("name") or "") == "slide_background"
            or str((child.get("debug") or {}).get("role") or "") == "slide_background"
        )
    ]
    frame["children"] = frame_children
    frame["children"].insert(
        0,
        {
            "id": f"{document.get('id')}:slide_background",
            "type": "RECTANGLE",
            "name": "slide_background",
            "absoluteBoundingBox": {
                "x": float(doc_bounds.get("x") or 0.0),
                "y": float(doc_bounds.get("y") or 0.0),
                "width": width,
                "height": height,
            },
            "relativeTransform": [[1, 0, 0], [0, 1, 0]],
            "fills": [{"type": "IMAGE", "imageRef": image_ref, "scaleMode": "FILL"}],
            "strokes": [],
            "strokeWeight": 0,
            "locked": True,
            "debug": {
                "generator": "local-server-hybrid",
                "role": "slide_background",
                "source": slide_background.get("source") or "unknown",
            },
        },
    )
    bundle_debug = bundle.setdefault("debug", {})
    bundle_debug["hybrid_background"] = True
    return bundle


class LocalHandler(BaseHTTPRequestHandler):
    server_version = "CNSAtlasLocalPlugin/2026-04-03b"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/render-pptx":
            self._send_json(404, {"error": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            filename = str(payload.get("filename") or "upload.pptx")
            pptx_bytes = base64.b64decode(str(payload.get("fileBase64") or ""))
            slides = parse_slides(payload.get("slides"))

            with tempfile.TemporaryDirectory(prefix="cnsatlas-pptx-") as temp_dir:
                pptx_path = Path(temp_dir) / filename
                pptx_path.write_bytes(pptx_bytes)

                detail_payload = extract_slide_details(pptx_path, slides)
                intermediate = build_intermediate_model(detail_payload)
                requested_slide_numbers = [
                    int(page.get("slide_no") or 0)
                    for page in intermediate.get("pages") or []
                    if int(page.get("slide_no") or 0) > 0
                ]
                export_width, export_height = _pick_slide_export_size(intermediate)
                slide_pngs, slide_png_status = try_render_slide_pngs(
                    pptx_path=pptx_path,
                    slide_numbers=requested_slide_numbers,
                    output_dir=Path(temp_dir) / "slide-png",
                    width=export_width,
                    height=export_height,
                )
                bundles = []
                for page in intermediate.get("pages") or []:
                    resolved_page = build_page_ir(page)
                    slide_no = int(page.get("slide_no") or 0)
                    slide_background = slide_pngs.get(slide_no)
                    if str(resolved_page.get("page_type") or "") == "dense_ui_panel":
                        bundle = build_dense_ui_panel_bundle(resolved_page, str(pptx_path))
                    else:
                        bundle = build_bundle_from_page(
                            page,
                            str(pptx_path),
                            preserve_native_size=True,
                            slide_background=slide_background,
                        )
                    bundle = attach_slide_background_to_bundle(bundle, slide_background)
                    bundles.append(bundle)
                collection = {
                    "kind": "figma-replay-collection",
                    "source_kind": "pptx-upload-visual-first",
                    "source_file": filename,
                    "pages": bundles,
                }
                page_sizes = []
                for bundle in bundles:
                    doc = bundle.get("document") or {}
                    bounds = doc.get("absoluteBoundingBox") or {}
                    slide_no = ((doc.get("debug") or {}).get("source_slide_no"))
                    if not isinstance(slide_no, int):
                        slide_no = None
                    page_sizes.append(
                        {
                            "slide": slide_no,
                            "width": bounds.get("width"),
                            "height": bounds.get("height"),
                            "pageName": bundle.get("page_name"),
                        }
                    )

            self._send_json(
                200,
                {
                    "ok": True,
                    "kind": "figma-replay-collection",
                    "serverVersion": self.server_version,
                    "requestedSlides": slides,
                    "pageCount": len(intermediate.get("pages") or []),
                    "payload": collection,
                    "slides": [page.get("slide_no") for page in intermediate.get("pages") or []],
                    "pageSizes": page_sizes,
                    "nativeSizeEnabled": True,
                    "hybridBackgroundEnabled": bool(slide_pngs),
                    "hybridBackgroundStatus": slide_png_status,
                },
            )
        except Exception as error:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": f"{type(error).__name__}: {error}"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Local helper server for Figma plugin PPTX upload.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=27184)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), LocalHandler)
    print(f"listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
