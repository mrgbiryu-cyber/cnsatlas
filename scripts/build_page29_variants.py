#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_block_replay_bundle import build_bundle_from_page
from ppt_source_extractor import iter_selected_pages, load_intermediate_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build page 29 comparison variants for block replay bundle.")
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "ppt-intermediate-candidates-12-19-29.json"),
        help="Intermediate candidates JSON path",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "block-bundles"),
        help="Output directory",
    )
    parser.add_argument("--slide", type=int, default=29, help="Slide number to export variants for")
    args = parser.parse_args()

    payload = load_intermediate_payload(args.input)
    selected = list(iter_selected_pages(payload, {args.slide}))
    if not selected:
        raise SystemExit(f"slide {args.slide} not found in {args.input}")
    page = selected[0]

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("1", "v1"),
        ("2", "v2"),
        ("3", "v3"),
    ]
    source_file = str(Path(args.input).resolve())
    for label, variant in variants:
        bundle = build_bundle_from_page(page, source_file, variant)
        output_path = output_dir / f"block-slide-{args.slide}-{label}.bundle.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(bundle, handle, ensure_ascii=False, indent=2)
        print(f"saved {output_path}")


if __name__ == "__main__":
    main()
