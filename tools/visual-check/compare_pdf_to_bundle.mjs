#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";

function usage() {
  console.error(
    "usage: node compare_pdf_to_bundle.mjs --reference-image <reference.png> --actual <bundle.json> --out-dir <dir> [--crop x,y,w,h]"
  );
  process.exit(1);
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const value = argv[i + 1];
    if (!value || value.startsWith("--")) {
      args[key] = true;
      i -= 1;
      continue;
    }
    args[key] = value;
  }
  return args;
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function esc(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;");
}

function rgbaFromFill(fill, fallback = { r: 1, g: 1, b: 1, a: 1 }) {
  if (!fill) return fallback;
  const color = fill.color || {};
  return {
    r: clamp(Math.round((color.r ?? fallback.r) * 255), 0, 255),
    g: clamp(Math.round((color.g ?? fallback.g) * 255), 0, 255),
    b: clamp(Math.round((color.b ?? fallback.b) * 255), 0, 255),
    a: fill.opacity ?? fill.alpha ?? fallback.a ?? 1
  };
}

function cssRgba(fill, fallback) {
  const { r, g, b, a } = rgbaFromFill(fill, fallback);
  return `rgba(${r},${g},${b},${a})`;
}

function parseCrop(value) {
  if (!value) return null;
  const parts = String(value).split(",").map((v) => Number(v.trim()));
  if (parts.length !== 4 || parts.some((v) => Number.isNaN(v))) return null;
  return { x: parts[0], y: parts[1], width: parts[2], height: parts[3] };
}

function parseNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function resolveFontConfig(fontFamily) {
  const family = String(fontFamily || "").trim();
  if (!family) return { family: "Malgun Gothic, sans-serif", scale: 1.0 };
  if (family.includes("LG스마트체")) {
    return { family: "Malgun Gothic, sans-serif", scale: 1.15 };
  }
  return { family, scale: 1.0 };
}

function renderBundleNode(node, pieces, offset, assets) {
  const bbox = node.absoluteBoundingBox;
  const type = node.type;
  const x = bbox ? bbox.x - offset.x : 0;
  const y = bbox ? bbox.y - offset.y : 0;
  const w = bbox ? bbox.width : 0;
  const h = bbox ? bbox.height : 0;

  if (type === "SVG_BLOCK" && node.svgMarkup) {
    pieces.push(`<g transform="translate(${x},${y})">${node.svgMarkup}</g>`);
  } else if (type === "FRAME") {
    if (!bbox) return;
    const fill = (node.fills || [])[0];
    const stroke = (node.strokes || [])[0];
    const strokeWidth = Number(node.strokeWeight || node.stroke_weight || 0);
    const radius = Number(node.cornerRadius || node.corner_radius || 0);
    if (fill || stroke) {
      pieces.push(
        `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill ? cssRgba(fill) : "none"}" stroke="${
          stroke ? cssRgba(stroke) : "none"
        }" stroke-width="${strokeWidth}" rx="${radius}" />`
      );
    }
  } else if (type === "RECTANGLE") {
    if (!bbox) return;
    const fill = (node.fills || [])[0];
    const stroke = (node.strokes || [])[0];
    const strokeWidth = Number(node.strokeWeight || 0);
    if (fill && fill.type === "IMAGE" && fill.imageRef && assets?.[fill.imageRef]?.base64) {
      const asset = assets[fill.imageRef];
      const mime = asset.mime_type || "image/png";
      pieces.push(
        `<image x="${x}" y="${y}" width="${w}" height="${h}" preserveAspectRatio="none" href="data:${mime};base64,${asset.base64}" />`
      );
      if (stroke && strokeWidth > 0) {
        pieces.push(
          `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="none" stroke="${cssRgba(
            stroke
          )}" stroke-width="${strokeWidth}" />`
        );
      }
    } else {
      pieces.push(
        `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill ? cssRgba(fill) : "none"}" stroke="${
          stroke ? cssRgba(stroke) : "none"
        }" stroke-width="${strokeWidth}" />`
      );
    }
  } else if (type === "TEXT") {
    if (!bbox) return;
    const fill = (node.fills || [])[0];
    const style = node.style || {};
    const fontSize = Number(style.fontSize || 12);
    const font = resolveFontConfig(style.fontFamily);
    const fontFamily = font.family;
    const effectiveFontSize = fontSize * font.scale;
    const lines = String(node.characters || "").split("\n");
    lines.forEach((line, index) => {
      const dy = y + effectiveFontSize + index * (Number(style.lineHeightPx || effectiveFontSize * 1.2));
      pieces.push(
        `<text x="${x}" y="${dy}" font-family="${esc(fontFamily)}" font-size="${effectiveFontSize}" fill="${cssRgba(
          fill,
          { r: 0, g: 0, b: 0, a: 1 }
        )}">${esc(line)}</text>`
      );
    });
  } else if (type === "VECTOR" || type === "LINE" || type === "POLYGON") {
    const fill = (node.fills || [])[0];
    const stroke = (node.strokes || [])[0];
    const strokeWidth = Number(node.strokeWeight || 0);
    const fillGeometry = Array.isArray(node.fillGeometry) ? node.fillGeometry : [];
    const strokeGeometry = Array.isArray(node.strokeGeometry) ? node.strokeGeometry : [];
    if (fillGeometry.length > 0) {
      for (const part of fillGeometry) {
        const pathData = part?.path;
        if (!pathData) continue;
        pieces.push(
          `<path d="${pathData}" transform="translate(${x},${y})" fill="${fill ? cssRgba(fill) : "none"}" stroke="${
            stroke ? cssRgba(stroke) : "none"
          }" stroke-width="${strokeWidth}" />`
        );
      }
    } else if (strokeGeometry.length > 0) {
      for (const part of strokeGeometry) {
        const pathData = part?.path;
        if (!pathData) continue;
        pieces.push(
          `<path d="${pathData}" transform="translate(${x},${y})" fill="none" stroke="${
            stroke ? cssRgba(stroke) : "none"
          }" stroke-width="${strokeWidth || 1}" />`
        );
      }
    } else if (bbox) {
      pieces.push(
        `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill ? cssRgba(fill) : "none"}" stroke="${
          stroke ? cssRgba(stroke) : "none"
        }" stroke-width="${strokeWidth}" />`
      );
    }
  }

  for (const child of node.children || []) {
    renderBundleNode(child, pieces, offset, assets);
  }
}

function renderPluginNode(node, pieces, offset = { x: 0, y: 0 }) {
  const bbox = node.bounds_relative_to_scope;
  const type = node.type;
  if (bbox) {
    const x = bbox.x - offset.x;
    const y = bbox.y - offset.y;
    const w = bbox.width;
    const h = bbox.height;
    const imageFill = (node.fills || []).find((item) => item && item.visible !== false && item.type === "IMAGE" && item.imageHash);
    if (type === "RECTANGLE") {
      const fill = (node.fills || []).find((item) => item.visible !== false);
      const stroke = (node.strokes || []).find((item) => item.visible !== false);
      if (imageFill) {
        pieces.push(
          `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#d8dde4" stroke="${
            stroke ? cssRgba(stroke) : "none"
          }" stroke-width="${Number(node.stroke_weight || 0)}" rx="${Number(node.corner_radius || 0)}" />`
        );
      } else {
        pieces.push(
          `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill ? cssRgba(fill) : "none"}" stroke="${
            stroke ? cssRgba(stroke) : "none"
          }" stroke-width="${Number(node.stroke_weight || 0)}" rx="${Number(node.corner_radius || 0)}" />`
        );
      }
    } else if (type === "ELLIPSE") {
      const fill = (node.fills || []).find((item) => item.visible !== false);
      const stroke = (node.strokes || []).find((item) => item.visible !== false);
      pieces.push(
        `<ellipse cx="${x + w / 2}" cy="${y + h / 2}" rx="${w / 2}" ry="${h / 2}" fill="${
          fill ? cssRgba(fill) : "none"
        }" stroke="${stroke ? cssRgba(stroke) : "none"}" stroke-width="${Number(node.stroke_weight || 0)}" />`
      );
    } else if (type === "VECTOR" || type === "LINE" || type === "POLYGON") {
      const fill = (node.fills || []).find((item) => item.visible !== false);
      const stroke = (node.strokes || []).find((item) => item.visible !== false);
      if (Array.isArray(node.vector_paths) && node.vector_paths.length > 0) {
        for (const part of node.vector_paths) {
          pieces.push(
            `<path d="${part.data}" fill="${fill ? cssRgba(fill) : "none"}" stroke="${
              stroke ? cssRgba(stroke) : "none"
            }" stroke-width="${Number(node.stroke_weight || 0)}" />`
          );
        }
      } else {
        pieces.push(
          `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill ? cssRgba(fill) : "none"}" stroke="${
            stroke ? cssRgba(stroke) : "none"
          }" stroke-width="${Number(node.stroke_weight || 0)}" />`
        );
      }
    } else if (type === "TEXT") {
      const fill = (node.fills || []).find((item) => item.visible !== false);
      const style = node.style || {};
      const fontSize = Number(style.fontSize || 12);
      const fontFamily = style.fontFamily || "sans-serif";
      const lines = String(node.characters || "").split("\n");
      lines.forEach((line, index) => {
        const dy = y + fontSize + index * (Number(style.lineHeightPx || fontSize * 1.2));
        pieces.push(
          `<text x="${x}" y="${dy}" font-family="${esc(fontFamily)}" font-size="${fontSize}" fill="${cssRgba(
            fill,
            { r: 0, g: 0, b: 0, a: 1 }
          )}">${esc(line)}</text>`
        );
      });
    } else if (type === "FRAME") {
      const fill = (node.fills || []).find((item) => item.visible !== false);
      const stroke = (node.strokes || []).find((item) => item.visible !== false);
      const strokeWidth = Number(node.stroke_weight || node.strokeWeight || 0);
      if (imageFill) {
        pieces.push(
          `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#d8dde4" stroke="${
            stroke ? cssRgba(stroke) : "none"
          }" stroke-width="${strokeWidth}" rx="${Number(node.corner_radius || node.cornerRadius || 0)}" />`
        );
      } else if (fill || stroke) {
        pieces.push(
          `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill ? cssRgba(fill) : "none"}" stroke="${
            stroke ? cssRgba(stroke) : "none"
          }" stroke-width="${strokeWidth}" rx="${Number(node.corner_radius || node.cornerRadius || 0)}" />`
        );
      }
    }
  }

  for (const child of node.children || []) {
    renderPluginNode(child, pieces, offset);
  }
}

function bundleToSvg(bundle, crop) {
  const doc = bundle.document;
  const pageBox = crop || doc.absoluteBoundingBox;
  const pieces = [];
  pieces.push(`<rect x="0" y="0" width="${pageBox.width}" height="${pageBox.height}" fill="white" />`);
  renderBundleNode(doc, pieces, { x: pageBox.x, y: pageBox.y }, bundle.assets || {});
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${pageBox.width}" height="${pageBox.height}" viewBox="0 0 ${pageBox.width} ${pageBox.height}">${pieces.join("")}</svg>`;
}

function pluginToSvg(plugin, crop) {
  const root = (plugin.nodes || [])[0];
  const pageBox = crop || plugin.scope_bounds || root?.bounds_relative_to_scope || { x: 0, y: 0, width: 1280, height: 720 };
  const pieces = [];
  pieces.push(`<rect x="0" y="0" width="${pageBox.width}" height="${pageBox.height}" fill="white" />`);
  for (const node of plugin.nodes || []) {
    renderPluginNode(node, pieces, { x: pageBox.x, y: pageBox.y });
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${pageBox.width}" height="${pageBox.height}" viewBox="0 0 ${pageBox.width} ${pageBox.height}">${pieces.join("")}</svg>`;
}

async function svgToPng(svg, outputPath) {
  await sharp(Buffer.from(svg)).png().toFile(outputPath);
}

function miniSvg(width, height, content) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${content}</svg>`;
}

async function svgBuffer(width, height, content) {
  return sharp(Buffer.from(miniSvg(width, height, content))).png().toBuffer();
}

async function rectangleOverlay(node) {
  const bbox = node.absoluteBoundingBox;
  const fill = (node.fills || [])[0];
  const stroke = (node.strokes || [])[0];
  const strokeWidth = Number(node.strokeWeight || 0);
  const content = `<rect x="0" y="0" width="${bbox.width}" height="${bbox.height}" fill="${
    fill ? cssRgba(fill) : "none"
  }" stroke="${stroke ? cssRgba(stroke) : "none"}" stroke-width="${strokeWidth}" />`;
  return svgBuffer(bbox.width, bbox.height, content);
}

async function textOverlay(node) {
  const bbox = node.absoluteBoundingBox;
  const fill = (node.fills || [])[0];
  const style = node.style || {};
  const font = resolveFontConfig(style.fontFamily);
  const fontSize = Number(style.fontSize || 12) * font.scale;
  const fontFamily = font.family;
  const lineHeight = Number(style.lineHeightPx || fontSize * 1.2);
  const lines = String(node.characters || "").split("\n");
  const alignH = String(style.textAlignHorizontal || "LEFT").toUpperCase();
  const alignV = String(style.textAlignVertical || "TOP").toUpperCase();
  const totalHeight = lines.length * lineHeight;
  let startY = fontSize;
  if (alignV === "CENTER") {
    startY = Math.max(fontSize, (bbox.height - totalHeight) / 2 + fontSize);
  } else if (alignV === "BOTTOM") {
    startY = Math.max(fontSize, bbox.height - totalHeight + fontSize);
  }
  let textAnchor = "start";
  let textX = 0;
  if (alignH === "CENTER") {
    textAnchor = "middle";
    textX = bbox.width / 2;
  } else if (alignH === "RIGHT") {
    textAnchor = "end";
    textX = bbox.width;
  }
  const content = lines
    .map((line, index) => {
      const dy = startY + index * lineHeight;
      return `<text x="${textX}" y="${dy}" text-anchor="${textAnchor}" font-family="${esc(fontFamily)}" font-size="${fontSize}" fill="${cssRgba(
        fill,
        { r: 0, g: 0, b: 0, a: 1 }
      )}">${esc(line)}</text>`;
    })
    .join("");
  return svgBuffer(Math.max(1, bbox.width), Math.max(1, bbox.height), content);
}

async function imageOverlay(node, assets) {
  const fill = (node.fills || [])[0];
  if (!fill?.imageRef || !assets?.[fill.imageRef]?.base64) return null;
  const asset = assets[fill.imageRef];
  return sharp(Buffer.from(asset.base64, "base64"))
    .resize(Math.max(1, Math.round(node.absoluteBoundingBox.width)), Math.max(1, Math.round(node.absoluteBoundingBox.height)), {
      fit: "fill"
    })
    .png()
    .toBuffer();
}

async function svgBlockOverlay(node) {
  const bbox = node.absoluteBoundingBox;
  if (!node.svgMarkup) return null;
  return svgBuffer(
    Math.max(1, bbox.width),
    Math.max(1, bbox.height),
    `<g transform="translate(0,0)">${node.svgMarkup}</g>`
  );
}

function intersectRect(a, b) {
  const left = Math.max(a.left, b.left);
  const top = Math.max(a.top, b.top);
  const right = Math.min(a.left + a.width, b.left + b.width);
  const bottom = Math.min(a.top + a.height, b.top + b.height);
  return {
    left,
    top,
    width: Math.max(0, right - left),
    height: Math.max(0, bottom - top)
  };
}

async function clipOverlay(input, left, top, width, height, canvasWidth, canvasHeight) {
  const visible = intersectRect(
    { left, top, width, height },
    { left: 0, top: 0, width: canvasWidth, height: canvasHeight }
  );
  if (visible.width <= 0 || visible.height <= 0) return null;
  const extract = {
    left: Math.max(0, Math.round(visible.left - left)),
    top: Math.max(0, Math.round(visible.top - top)),
    width: Math.max(1, Math.round(visible.width)),
    height: Math.max(1, Math.round(visible.height))
  };
  const clipped = await sharp(input).extract(extract).png().toBuffer();
  return { input: clipped, left: Math.round(visible.left), top: Math.round(visible.top) };
}

async function collectCompositeOps(node, offset, assets, ops, canvasWidth, canvasHeight) {
  const bbox = node.absoluteBoundingBox;
  if (!bbox) return;
  const left = Math.round(bbox.x - offset.x);
  const top = Math.round(bbox.y - offset.y);
  const width = Math.max(1, Math.round(bbox.width));
  const height = Math.max(1, Math.round(bbox.height));
  const type = node.type;

  if (type === "SVG_BLOCK" && node.svgMarkup) {
    const input = await svgBlockOverlay(node);
    if (input) {
      const clipped = await clipOverlay(input, left, top, width, height, canvasWidth, canvasHeight);
      if (clipped) ops.push(clipped);
    }
  } else if (type === "RECTANGLE") {
    const fill = (node.fills || [])[0];
    if (fill?.type === "IMAGE") {
      const image = await imageOverlay(node, assets);
      if (image) {
        const clipped = await clipOverlay(image, left, top, width, height, canvasWidth, canvasHeight);
        if (clipped) ops.push(clipped);
      }
      const stroke = (node.strokes || [])[0];
      const strokeWidth = Number(node.strokeWeight || 0);
      if (stroke && strokeWidth > 0) {
        const input = await rectangleOverlay({
          ...node,
          fills: [],
          strokes: [stroke],
          strokeWeight
        });
        const clipped = await clipOverlay(input, left, top, width, height, canvasWidth, canvasHeight);
        if (clipped) ops.push(clipped);
      }
    } else {
      const input = await rectangleOverlay(node);
      const clipped = await clipOverlay(input, left, top, width, height, canvasWidth, canvasHeight);
      if (clipped) ops.push(clipped);
    }
  } else if (type === "TEXT") {
    const input = await textOverlay(node);
    const clipped = await clipOverlay(input, left, top, width, height, canvasWidth, canvasHeight);
    if (clipped) ops.push(clipped);
  }

  for (const child of node.children || []) {
    await collectCompositeOps(child, offset, assets, ops, canvasWidth, canvasHeight);
  }
}

async function renderBundleToPng(bundle, crop, outputPath) {
  const doc = bundle.document;
  const pageBox = crop || doc.absoluteBoundingBox;
  const width = Math.max(1, Math.round(pageBox.width));
  const height = Math.max(1, Math.round(pageBox.height));
  const ops = [];
  await collectCompositeOps(doc, { x: pageBox.x, y: pageBox.y }, bundle.assets || {}, ops, width, height);
  await sharp({
    create: {
      width,
      height,
      channels: 4,
      background: { r: 255, g: 255, b: 255, alpha: 1 }
    }
  })
    .composite(ops)
    .png()
    .toFile(outputPath);
}

async function cropOrCopyReference(referenceImagePath, outPath, crop, referenceBaseBox = null) {
  let image = sharp(referenceImagePath);
  if (crop) {
    const meta = await image.metadata();
    const baseWidth = Math.max(1, Math.round(referenceBaseBox?.width || 960));
    const baseHeight = Math.max(1, Math.round(referenceBaseBox?.height || 540));
    const scaleX = (meta.width || crop.width) / baseWidth;
    const scaleY = (meta.height || crop.height) / baseHeight;
    image = image.extract({
      left: Math.max(0, Math.round(crop.x * scaleX)),
      top: Math.max(0, Math.round(crop.y * scaleY)),
      width: Math.round(crop.width * scaleX),
      height: Math.round(crop.height * scaleY)
    });
  }
  await image.png().toFile(outPath);
}

function getActualBaseBox(actual) {
  if (actual?.kind === "figma-analysis-export") {
    return actual.scope_bounds || actual.nodes?.[0]?.bounds_relative_to_scope || null;
  }
  return actual?.document?.absoluteBoundingBox || null;
}

async function renderActualToPng(actual, crop, outputPath) {
  if (actual?.kind === "figma-analysis-export") {
    const svg = pluginToSvg(actual, crop);
    await sharp(Buffer.from(svg)).png().toFile(outputPath);
    return svg;
  }
  const svg = bundleToSvg(actual, crop);
  await renderBundleToPng(actual, crop, outputPath);
  return svg;
}

async function diffPng(referencePng, actualPng, outPath, options = {}) {
  const blurSigma = parseNumber(options.blurSigma, 1.2);
  const deltaThreshold = parseNumber(options.deltaThreshold, 40);
  let ref = sharp(referencePng);
  let act = sharp(actualPng);
  const refMeta = await ref.metadata();
  const actMeta = await act.metadata();
  const width = Math.max(refMeta.width || 0, actMeta.width || 0);
  const height = Math.max(refMeta.height || 0, actMeta.height || 0);
  if (blurSigma > 0) {
    ref = ref.clone().blur(blurSigma);
    act = act.clone().blur(blurSigma);
  }
  const refBuf = await ref.resize(width, height).ensureAlpha().raw().toBuffer();
  const actBuf = await act.resize(width, height).ensureAlpha().raw().toBuffer();

  const diff = Buffer.alloc(refBuf.length);
  let changed = 0;
  for (let i = 0; i < refBuf.length; i += 4) {
    const dr = Math.abs(refBuf[i] - actBuf[i]);
    const dg = Math.abs(refBuf[i + 1] - actBuf[i + 1]);
    const db = Math.abs(refBuf[i + 2] - actBuf[i + 2]);
    const da = Math.abs(refBuf[i + 3] - actBuf[i + 3]);
    const delta = dr + dg + db + da;
    if (delta > deltaThreshold) {
      changed += 1;
      diff[i] = 255;
      diff[i + 1] = 0;
      diff[i + 2] = 0;
      diff[i + 3] = 180;
    } else {
      diff[i] = refBuf[i];
      diff[i + 1] = refBuf[i + 1];
      diff[i + 2] = refBuf[i + 2];
      diff[i + 3] = 70;
    }
  }
  await sharp(diff, { raw: { width, height, channels: 4 } }).png().toFile(outPath);
  return {
    width,
    height,
    blur_sigma: blurSigma,
    delta_threshold: deltaThreshold,
    changed_pixels: changed,
    changed_ratio: width * height ? changed / (width * height) : 0,
    match_score: width * height ? 1 - changed / (width * height) : 0
  };
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args["reference-image"] || !args.actual || !args["out-dir"]) usage();

  const outDir = path.resolve(args["out-dir"]);
  ensureDir(outDir);
  const crop = parseCrop(args.crop);
  const actual = loadJson(path.resolve(args.actual));
  const actualDocBox = getActualBaseBox(actual);
  const referencePngPath = path.join(outDir, "reference.png");
  const actualSvgPath = path.join(outDir, "actual.svg");
  const actualPngPath = path.join(outDir, "actual.png");
  const diffPngPath = path.join(outDir, "diff.png");
  const metricsPath = path.join(outDir, "metrics.json");

  await cropOrCopyReference(path.resolve(args["reference-image"]), referencePngPath, crop, actualDocBox);
  const actualSvg = actual?.kind === "figma-analysis-export" ? pluginToSvg(actual, crop) : bundleToSvg(actual, crop);
  fs.writeFileSync(actualSvgPath, actualSvg, "utf-8");
  await renderActualToPng(actual, crop, actualPngPath);
  const metrics = await diffPng(referencePngPath, actualPngPath, diffPngPath, {
    blurSigma: args["blur-sigma"],
    deltaThreshold: args["delta-threshold"]
  });
  fs.writeFileSync(metricsPath, JSON.stringify({ crop, ...metrics }, null, 2), "utf-8");
  console.log(JSON.stringify({ outDir, metrics }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
