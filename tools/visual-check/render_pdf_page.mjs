import fs from 'fs/promises';
import path from 'path';
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key.startsWith('--')) {
      args[key.slice(2)] = value;
      i += 1;
    }
  }
  return args;
}

class NodeCanvasFactory {
  create(width, height) {
    const canvas = createCanvas(width, height);
    const context = canvas.getContext('2d');
    return { canvas, context };
  }
  reset(canvasAndContext, width, height) {
    canvasAndContext.canvas.width = width;
    canvasAndContext.canvas.height = height;
  }
  destroy(canvasAndContext) {
    canvasAndContext.canvas.width = 0;
    canvasAndContext.canvas.height = 0;
    canvasAndContext.canvas = null;
    canvasAndContext.context = null;
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const pdfPath = args.pdf;
  const out = args.out;
  const pageNum = Number(args.page || 1);
  const scale = Number(args.scale || 2);
  if (!pdfPath || !out) throw new Error('Usage: --pdf path --page N --out file [--scale 2]');

  const data = await fs.readFile(pdfPath);
  const loadingTask = getDocument({ data: new Uint8Array(data) });
  const pdf = await loadingTask.promise;
  const page = await pdf.getPage(pageNum);
  const viewport = page.getViewport({ scale });
  const factory = new NodeCanvasFactory();
  const { canvas, context } = factory.create(Math.ceil(viewport.width), Math.ceil(viewport.height));
  await page.render({ canvasContext: context, viewport, canvasFactory: factory }).promise;
  const png = canvas.toBuffer('image/png');
  await fs.mkdir(path.dirname(out), { recursive: true });
  await fs.writeFile(out, png);
  console.log(JSON.stringify({ page: pageNum, width: canvas.width, height: canvas.height, out }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
