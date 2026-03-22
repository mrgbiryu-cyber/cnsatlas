#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def key_by(rows, field):
    result = {}
    for row in rows:
        value = row.get(field)
        if value:
            result[value] = row
    return result


def normalize_bbox(bbox, origin):
    return {
        "x": float(bbox.get("x", 0) - origin.get("x", 0)),
        "y": float(bbox.get("y", 0) - origin.get("y", 0)),
        "width": float(bbox.get("width", 0)),
        "height": float(bbox.get("height", 0)),
    }


def mean(values):
    return round(sum(values) / len(values), 2) if values else None


def build_mapping(reference_rows, generated_rows):
    generated_by_semantic = {}
    generated_by_name_type = {}
    for row in generated_rows:
        generated_by_semantic.setdefault(row.get("semantic_key"), []).append(row)
        generated_by_name_type.setdefault((row.get("node_type"), row.get("node_name")), []).append(row)

    pairs = []
    used_generated = set()

    for ref in reference_rows:
        candidates = []
        semantic = ref.get("semantic_key")
        if semantic and semantic in generated_by_semantic:
            candidates.extend(generated_by_semantic[semantic])
        pair_key = (ref.get("node_type"), ref.get("node_name"))
        if pair_key in generated_by_name_type:
            candidates.extend(generated_by_name_type[pair_key])

        picked = None
        ref_bbox = ref.get("bbox_absolute") or {}
        for candidate in candidates:
            gen_id = candidate.get("reference_node_id")
            if gen_id in used_generated:
                continue
            if picked is None:
                picked = candidate
                continue
            cur_bbox = picked.get("bbox_absolute") or {}
            cand_bbox = candidate.get("bbox_absolute") or {}
            cur_score = abs(cur_bbox.get("x", 0) - ref_bbox.get("x", 0)) + abs(cur_bbox.get("y", 0) - ref_bbox.get("y", 0))
            cand_score = abs(cand_bbox.get("x", 0) - ref_bbox.get("x", 0)) + abs(cand_bbox.get("y", 0) - ref_bbox.get("y", 0))
            if cand_score < cur_score:
                picked = candidate

        if picked:
            used_generated.add(picked.get("reference_node_id"))
            pairs.append((ref, picked))
        else:
            pairs.append((ref, None))

    extra = [row for row in generated_rows if row.get("reference_node_id") not in used_generated]
    return pairs, extra


def canvas_metrics(reference_manifest, generated_manifest):
    ref = reference_manifest.get("page_bounds") or {}
    gen = generated_manifest.get("page_bounds") or {}
    size_match = round(abs(ref.get("width", 0) - gen.get("width", 0)), 2) == 0 and round(abs(ref.get("height", 0) - gen.get("height", 0)), 2) == 0
    return {
        "reference_page_bounds": ref,
        "generated_page_bounds": gen,
        "size_match": size_match,
        "width_delta": round(gen.get("width", 0) - ref.get("width", 0), 2),
        "height_delta": round(gen.get("height", 0) - ref.get("height", 0), 2),
    }


def score_canvas(metrics):
    return 100 if metrics["size_match"] else 0


def score_text(reference_rows, generated_rows, pairs):
    ref_text = [r for r in reference_rows if r.get("node_type") == "TEXT"]
    pair_text = [(r, g) for r, g in pairs if r.get("node_type") == "TEXT"]
    if not ref_text:
        return {"score": 100, "coverage_ratio": 1.0, "mean_bbox_delta": 0, "mean_font_size_delta": 0}

    coverage_ratio = round(sum(1 for _, g in pair_text if g) / len(ref_text), 2)
    bbox_deltas = []
    font_size_deltas = []
    for ref, gen in pair_text:
        if not gen:
            continue
        rb = ref.get("bbox_absolute") or {}
        gb = gen.get("bbox_absolute") or {}
        bbox_deltas.append(max(abs(gb.get("x", 0) - rb.get("x", 0)), abs(gb.get("y", 0) - rb.get("y", 0))))
        rf = ref.get("font_size")
        gf = gen.get("font_size")
        if rf is not None and gf is not None:
            font_size_deltas.append(abs(gf - rf))
    mean_bbox_delta = mean(bbox_deltas) or 999
    mean_font_size_delta = mean(font_size_deltas) or 999
    score = max(0, min(100, round((coverage_ratio * 55) + max(0, 25 - mean_bbox_delta * 2) + max(0, 20 - mean_font_size_delta * 5))))
    return {
        "score": score,
        "coverage_ratio": coverage_ratio,
        "mean_bbox_delta": mean_bbox_delta,
        "mean_font_size_delta": mean_font_size_delta,
    }


def score_vector(reference_rows, generated_rows):
    ref_vectors = [r for r in reference_rows if r.get("node_type") == "VECTOR"]
    gen_vectors = [r for r in generated_rows if r.get("node_type") == "VECTOR"]
    if not ref_vectors:
        return {"score": 100, "vector_count_ratio": 1.0}
    ratio = round(len(gen_vectors) / len(ref_vectors), 2)
    score = max(0, min(100, round(min(ratio, 1.0) * 100)))
    return {
        "score": score,
        "reference_vector_count": len(ref_vectors),
        "generated_vector_count": len(gen_vectors),
        "vector_count_ratio": ratio,
    }


def score_connector(reference_rows, generated_rows):
    ref_connectors = [r for r in reference_rows if r.get("node_type") == "VECTOR" and r.get("bbox_aspect_bucket") in {"ULTRA_WIDE", "WIDE"}]
    gen_connectors = [r for r in generated_rows if r.get("node_type") == "VECTOR" and r.get("bbox_aspect_bucket") in {"ULTRA_WIDE", "WIDE"}]
    if not ref_connectors:
        return {"score": 100, "missing_connector_ratio": 0.0}
    ratio = round(len(gen_connectors) / len(ref_connectors), 2)
    missing_ratio = round(max(0, 1.0 - ratio), 2)
    score = max(0, min(100, round((1.0 - missing_ratio) * 100)))
    return {
        "score": score,
        "reference_connector_proxy_count": len(ref_connectors),
        "generated_connector_proxy_count": len(gen_connectors),
        "missing_connector_ratio": missing_ratio,
    }


def score_table(reference_rows, generated_rows):
    ref_cells = [r for r in reference_rows if r.get("node_name", "").startswith("cell ")]
    gen_cells = [r for r in generated_rows if r.get("node_name", "").startswith("cell ")]
    if not ref_cells and not gen_cells:
        return {"score": 100, "cell_presence_ratio": 1.0}
    if not ref_cells:
        return {"score": 0, "cell_presence_ratio": 0.0}
    ratio = round(len(gen_cells) / len(ref_cells), 2)
    score = max(0, min(100, round(min(ratio, 1.0) * 100)))
    return {
        "score": score,
        "reference_cell_count": len(ref_cells),
        "generated_cell_count": len(gen_cells),
        "cell_presence_ratio": ratio,
    }


def score_shape(reference_rows, generated_rows):
    ref_diamond = [r for r in reference_rows if r.get("node_type") == "VECTOR" and "Google Shape;472" in (r.get("node_name") or "")]
    gen_diamond = [r for r in generated_rows if "Google Shape;472" in (r.get("node_name") or "")]
    if not ref_diamond:
        return {"score": 100, "decision_shape_present": True}
    present = bool(gen_diamond)
    center_delta = None
    if present:
        rb = ref_diamond[0].get("bbox_absolute") or {}
        gb = gen_diamond[0].get("bbox_absolute") or {}
        rcx = rb.get("x", 0) + rb.get("width", 0) / 2
        rcy = rb.get("y", 0) + rb.get("height", 0) / 2
        gcx = gb.get("x", 0) + gb.get("width", 0) / 2
        gcy = gb.get("y", 0) + gb.get("height", 0) / 2
        center_delta = round(max(abs(gcx - rcx), abs(gcy - rcy)), 2)
    score = 100 if present and (center_delta is None or center_delta <= 10) else 40 if present else 0
    return {
        "score": score,
        "decision_shape_present": present,
        "decision_center_delta": center_delta,
    }


def score_overlay(reference_rows, generated_rows):
    overlays = [r for r in generated_rows if r.get("is_fullpage_overlay_candidate")]
    blocking = len(overlays)
    return {
        "score": 100 if blocking == 0 else 0,
        "blocking_overlay_count": blocking,
    }


def evaluate_page(reference_manifest, generated_manifest):
    reference_rows = [row for row in reference_manifest.get("nodes", []) if row.get("comparison_target")]
    generated_rows = [row for row in generated_manifest.get("nodes", []) if row.get("comparison_target")]
    pairs, extra_rows = build_mapping(reference_rows, generated_rows)

    metrics = {
        "canvas": canvas_metrics(reference_manifest, generated_manifest),
        "text": score_text(reference_rows, generated_rows, pairs),
        "vector": score_vector(reference_rows, generated_rows),
        "connector": score_connector(reference_rows, generated_rows),
        "table": score_table(reference_rows, generated_rows),
        "shape": score_shape(reference_rows, generated_rows),
        "overlay": score_overlay(reference_rows, generated_rows),
    }
    metrics["canvas"]["score"] = score_canvas(metrics["canvas"])

    weights = {
        "canvas": 10,
        "text": 20,
        "vector": 15,
        "connector": 20,
        "table": 20,
        "shape": 10,
        "overlay": 5,
    }
    total_score = round(sum(metrics[name]["score"] * weight for name, weight in weights.items()) / 100, 2)

    fail_reasons = []
    if not metrics["canvas"]["size_match"]:
        fail_reasons.append("canvas_size_mismatch")
    if metrics["overlay"]["blocking_overlay_count"] > 0:
        fail_reasons.append("blocking_overlay_present")
    if metrics["connector"]["missing_connector_ratio"] > 0.2:
        fail_reasons.append("connector_missing_ratio_high")
    if metrics["table"].get("cell_presence_ratio", 1.0) < 0.9:
        fail_reasons.append("table_cell_presence_low")
    if not metrics["shape"]["decision_shape_present"]:
        fail_reasons.append("decision_shape_missing")

    if fail_reasons:
        status = "FAIL"
    elif total_score < 80:
        status = "HOLD"
    else:
        status = "PASS"

    return {
        "page_id": reference_manifest.get("page_id"),
        "page_name": reference_manifest.get("page_name"),
        "status": status,
        "score": total_score,
        "fail_reasons": fail_reasons,
        "counts": {
            "reference_target_nodes": len(reference_rows),
            "generated_target_nodes": len(generated_rows),
            "extra_generated_nodes": len(extra_rows),
            "matched_proxy_count": sum(1 for _, row in pairs if row),
        },
        "metrics": metrics,
    }


def main():
    parser = argparse.ArgumentParser(description="Run replay generator QA gate against reference/generated page manifests.")
    parser.add_argument("--reference", nargs="+", required=True, help="Reference manifest JSON paths")
    parser.add_argument("--generated", nargs="+", required=True, help="Generated manifest JSON paths")
    parser.add_argument("--output", required=True, help="Output QA report path")
    args = parser.parse_args()

    reference_paths = [Path(path).resolve() for path in args.reference]
    generated_paths = [Path(path).resolve() for path in args.generated]
    if len(reference_paths) != len(generated_paths):
        raise SystemExit("reference/generated file count must match")

    page_reports = []
    for ref_path, gen_path in zip(reference_paths, generated_paths):
        reference_manifest = load_json(ref_path)
        generated_manifest = load_json(gen_path)
        page_reports.append(evaluate_page(reference_manifest, generated_manifest))

    status = "PASS"
    if any(page["status"] == "FAIL" for page in page_reports):
        status = "FAIL"
    elif any(page["status"] == "HOLD" for page in page_reports):
        status = "HOLD"

    report = {
        "kind": "replay-generator-qa-gate",
        "status": status,
        "page_reports": page_reports,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(f"saved {output_path}")
    print(f"status={status}")
    for page in page_reports:
        print(f"{page['page_name']}: {page['status']} score={page['score']}")


if __name__ == "__main__":
    main()
