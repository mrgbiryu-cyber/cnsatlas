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

function upsertResult(results, row) {
  const idx = results.findIndex((r) => Number(r.slide_no) === Number(row.slide_no));
  if (idx >= 0) {
    results[idx] = row;
  } else {
    results.push(row);
  }
  results.sort((a, b) => Number(a.slide_no) - Number(b.slide_no));
}

function resolvedRange(results, fallbackStart, fallbackEnd) {
  if (!results.length) return { start: fallbackStart, end: fallbackEnd };
  const ordered = [...results].sort((a, b) => Number(a.slide_no) - Number(b.slide_no));
  return {
    start: Number(ordered[0].slide_no),
    end: Number(ordered[ordered.length - 1].slide_no),
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const pptx = path.resolve(args.pptx || "sampling/pptsample.pptx");
  const pdf = path.resolve(args.pdf || "sampling/fulltest/figma-page-pdf.pdf");
  const base = path.resolve(args["base-dir"] || "docs/render-diff/current-fulltest-pages-all");
  const start = Number(args.start || 1);
  const end = Number(args.end || 39);
  const scale = String(args.scale || "1");
  const resume = Boolean(args.resume);
  const sleepMs = Number(args["sleep-ms"] || 150);

  ensureDir(base);

  const partialPath = path.join(base, "report.partial.json");
  const results = [];
  if (resume && fs.existsSync(partialPath)) {
    const partial = readJson(partialPath);
    for (const row of partial.results || []) {
      upsertResult(results, row);
    }
  }

  for (let slideNo = start; slideNo <= end; slideNo += 1) {
    const referencePng = path.join(base, `slide${slideNo}.png`);
    const actualJson = path.join(base, `slide${slideNo}.json`);
    const cmpDir = path.join(base, `slide${slideNo}-cmp`);
    const metricsPath = path.join(cmpDir, "metrics.json");
    ensureDir(cmpDir);

    if (resume && fs.existsSync(metricsPath) && fs.existsSync(actualJson) && fs.existsSync(referencePng)) {
      const metrics = readJson(metricsPath);
      upsertResult(results, {
        slide_no: slideNo,
        match_score: metrics.match_score,
        changed_ratio: metrics.changed_ratio,
      });
      process.stdout.write(`skip ${slideNo} ${Number(metrics.match_score || 0).toFixed(4)}\n`);
      continue;
    }

    run("node", [
      "tools/visual-check/render_pdf_page.mjs",
      "--pdf", pdf,
      "--page", String(slideNo),
      "--out", referencePng,
      "--scale", scale,
    ]);

    run("python3", [
      "scripts/export_current_replay_bundle.py",
      "--pptx", pptx,
      "--slide", String(slideNo),
      "--out", actualJson,
    ]);

    run("node", [
      "tools/visual-check/compare_pdf_to_bundle.mjs",
      "--reference-image", referencePng,
      "--actual", actualJson,
      "--out-dir", cmpDir,
    ]);

    const metrics = readJson(metricsPath);
    upsertResult(results, {
      slide_no: slideNo,
      match_score: metrics.match_score,
      changed_ratio: metrics.changed_ratio,
    });

    fs.writeFileSync(
      partialPath,
      JSON.stringify(
        {
          kind: "current-fulltest-scan-partial",
          completed: results.length,
          ...resolvedRange(results, start, end),
          requested_start: start,
          requested_end: end,
          scale: Number(scale),
          results,
        },
        null,
        2
      ),
      "utf-8"
    );

    process.stdout.write(`done ${slideNo} ${Number(metrics.match_score || 0).toFixed(4)}\n`);

    if (sleepMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, sleepMs));
    }
  }

  fs.writeFileSync(
    path.join(base, "report.json"),
    JSON.stringify(
      {
        kind: "current-fulltest-scan-report",
        completed: results.length,
        ...resolvedRange(results, start, end),
        requested_start: start,
        requested_end: end,
        scale: Number(scale),
        results,
      },
      null,
      2
    ),
    "utf-8"
  );
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
