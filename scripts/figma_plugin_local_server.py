#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from build_intermediate_candidates import build_intermediate_model
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


class LocalHandler(BaseHTTPRequestHandler):
    server_version = "CNSAtlasLocalPlugin/0.1"

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

            self._send_json(
                200,
                {
                    "ok": True,
                    "kind": "intermediate",
                    "serverVersion": self.server_version,
                    "requestedSlides": slides,
                    "pageCount": len(intermediate.get("pages") or []),
                    "payload": intermediate,
                    "slides": [page.get("slide_no") for page in intermediate.get("pages") or []],
                },
            )
        except Exception as error:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": f"{type(error).__name__}: {error}"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Local helper server for Figma plugin PPTX upload.")
    parser.add_argument("--host", default="127.0.0.1")
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
