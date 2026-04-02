import fs from "fs";
import path from "path";
import { spawnSync } from "child_process";

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

async function main() {
  const args = parseArgs(process.argv);
  const pdf = path.resolve(args.pdf || "sampling/fulltest/figma-page-pdf.pdf");
  const base = path.resolve(args["base-dir"] || "docs/render-diff/fulltest-pages-all");
  const start = Number(args.start || 1);
  const end = Number(args.end || 39);
  const scale = String(args.scale || "1");
  const resume = Boolean(args.resume);
  const sleepMs = Number(args["sleep-ms"] || 150);

  ensureDir(base);

  const results = [];
  const partialPath = path.join(base, "report.partial.json");
  if (resume && fs.existsSync(partialPath)) {
    const partial = readJson(partialPath);
    for (const row of partial.results || []) results.push(row);
  }

  for (let i = start; i <= end; i += 1) {
    const metricsPath = path.join(base, `slide${i}-cmp`, "metrics.json");
    if (resume && fs.existsSync(metricsPath)) {
      const metrics = readJson(metricsPath);
      if (!results.find((row) => row.slide_no === i)) {
        results.push({ slide_no: i, match_score: metrics.match_score, changed_ratio: metrics.changed_ratio });
      }
      continue;
    }

    const png = path.join(base, `slide${i}.png`);
    const actual = path.join(base, `slide${i}.json`);
    const outDir = path.join(base, `slide${i}-cmp`);

    run("node", ["tools/visual-check/render_pdf_page.mjs", "--pdf", pdf, "--page", String(i), "--out", png, "--scale", scale]);
    run("node", ["tools/visual-check/compare_pdf_to_bundle.mjs", "--reference-image", png, "--actual", actual, "--out-dir", outDir]);
    const metrics = readJson(metricsPath);
    results.push({ slide_no: i, match_score: metrics.match_score, changed_ratio: metrics.changed_ratio });
    results.sort((a, b) => a.slide_no - b.slide_no);
    fs.writeFileSync(partialPath, JSON.stringify({ completed: results.length, start, end, scale: Number(scale), results }, null, 2), "utf-8");
    process.stdout.write(`done ${i} ${metrics.match_score.toFixed(4)}\n`);

    if (sleepMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, sleepMs));
    }
  }

  fs.writeFileSync(path.join(base, "report.json"), JSON.stringify({ completed: results.length, start, end, scale: Number(scale), results }, null, 2), "utf-8");
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
