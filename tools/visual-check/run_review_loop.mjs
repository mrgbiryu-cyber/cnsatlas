#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

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

function usage() {
  console.error(
    "usage: node run_review_loop.mjs --slides 9,12,19,29 [--pdf sampling/fulltest/figma-page-pdf.pdf] [--base-dir docs/render-diff/fulltest-pages-all] [--scale 1]"
  );
  process.exit(1);
}

function run(cmd, cmdArgs) {
  const result = spawnSync(cmd, cmdArgs, { stdio: "pipe", encoding: "utf-8" });
  if (result.status !== 0) {
    throw new Error(`${cmd} ${cmdArgs.join(" ")} failed\n${result.stderr || result.stdout}`);
  }
  return result.stdout;
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}

function parseSlides(value) {
  return String(value || "")
    .split(",")
    .map((token) => Number(token.trim()))
    .filter((v) => Number.isFinite(v) && v > 0);
}

function boardPath(baseDir, slideNo) {
  return path.join(baseDir, `slide${slideNo}-cmp`, "board.png");
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.slides) usage();

  const slides = parseSlides(args.slides);
  if (slides.length === 0) usage();

  const pdf = path.resolve(args.pdf || "sampling/fulltest/figma-page-pdf.pdf");
  const baseDir = path.resolve(args["base-dir"] || "docs/render-diff/fulltest-pages-all");
  const scale = String(args.scale || "1");
  ensureDir(baseDir);

  const summary = [];
  for (const slideNo of slides) {
    const referencePng = path.join(baseDir, `slide${slideNo}.png`);
    const actualJson = path.join(baseDir, `slide${slideNo}.json`);
    const cmpDir = path.join(baseDir, `slide${slideNo}-cmp`);
    ensureDir(cmpDir);

    run("node", [
      "tools/visual-check/render_pdf_page.mjs",
      "--pdf", pdf,
      "--page", String(slideNo),
      "--out", referencePng,
      "--scale", scale,
    ]);

    run("node", [
      "tools/visual-check/compare_pdf_to_bundle.mjs",
      "--reference-image", referencePng,
      "--actual", actualJson,
      "--out-dir", cmpDir,
    ]);

    run("node", [
      "tools/visual-check/build_review_board.mjs",
      "--dir", cmpDir,
      "--title", `Slide ${slideNo} Review`,
    ]);

    const metrics = readJson(path.join(cmpDir, "metrics.json"));
    summary.push({
      slide_no: slideNo,
      match_score: metrics.match_score,
      changed_ratio: metrics.changed_ratio,
      board_png: boardPath(baseDir, slideNo),
    });
    process.stdout.write(`slide ${slideNo}: ${Number(metrics.match_score || 0).toFixed(4)}\n`);
  }

  const outPath = path.join(baseDir, "review-loop-report.json");
  fs.writeFileSync(
    outPath,
    JSON.stringify(
      {
        kind: "review-loop-report",
        slides,
        scale: Number(scale),
        rows: summary,
      },
      null,
      2
    ),
    "utf-8"
  );
  process.stdout.write(`saved ${outPath}\n`);
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
