#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
    } else {
      args[key] = next;
      i += 1;
    }
  }
  return args;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function defaultFailureTags(pageType, score) {
  const tags = [];
  if (score < 0.75) tags.push("needs_review");
  if (pageType === "table-heavy") tags.push("table_scaffold");
  if (pageType === "flow-process") tags.push("connector_or_order");
  if (pageType === "ui-mockup") tags.push("grouping_or_layout");
  if (pageType === "dense_ui_panel") tags.push("panel_layering");
  return tags;
}

function bucketForSlide(slideNo) {
  if (slideNo <= 10) return "01-10";
  if (slideNo <= 20) return "11-20";
  if (slideNo <= 30) return "21-30";
  return "31-39";
}

function main() {
  const args = parseArgs(process.argv);
  const baseDir = path.resolve(args["base-dir"] || "docs/render-diff/fulltest-pages-all");
  const patternScore = readJson(path.join(baseDir, "pattern-score-report.json"));
  const outDir = path.join(baseDir, "batch-manifests");
  ensureDir(outDir);

  const batches = new Map();
  for (const row of patternScore.rows || []) {
    const bucket = bucketForSlide(Number(row.slide_no));
    if (!batches.has(bucket)) batches.set(bucket, []);
    batches.get(bucket).push({
      slide_no: row.slide_no,
      title: row.title,
      page_type: row.page_type,
      match_score: row.match_score,
      board_png: row.board_png,
      failure_tags: defaultFailureTags(row.page_type, Number(row.match_score || 0)),
      notes: "",
      status: "pending",
    });
  }

  for (const [bucket, rows] of batches.entries()) {
    rows.sort((a, b) => a.slide_no - b.slide_no);
    const payload = {
      kind: "fulltest-batch-review-manifest",
      batch: bucket,
      count: rows.length,
      rows,
    };
    fs.writeFileSync(
      path.join(outDir, `batch-${bucket}.json`),
      JSON.stringify(payload, null, 2),
      "utf-8"
    );
  }
}

main();
