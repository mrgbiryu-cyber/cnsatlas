const DEFAULT_FONT = { family: "Inter", style: "Regular" };
const SLIDE_GAP = 120;
const MIN_PAGE_WIDTH = 960;
const MIN_PAGE_HEIGHT = 540;

let fontLoaded = false;

figma.showUI(__html__, {
  width: 420,
  height: 360,
});

figma.ui.onmessage = async (message) => {
  if (message.type === "render-intermediate-json") {
    try {
      const payload = JSON.parse(message.jsonText);
      await renderIntermediatePayload(payload);
      figma.ui.postMessage({
        type: "render-success",
        message: `Rendered ${payload.pages.length} slide previews`,
      });
    } catch (error) {
      figma.ui.postMessage({
        type: "render-error",
        message: error instanceof Error ? `${error.name}: ${error.message}\n${error.stack}` : String(error),
      });
    }
  }
};

async function ensureFontLoaded() {
  if (!fontLoaded) {
    await figma.loadFontAsync(DEFAULT_FONT);
    fontLoaded = true;
  }
}

function computePageBounds(candidates) {
  let maxRight = 0;
  let maxBottom = 0;

  for (const candidate of candidates) {
    const bounds = candidate.bounds_px;
    if (!bounds) {
      continue;
    }
    maxRight = Math.max(maxRight, bounds.x + bounds.width);
    maxBottom = Math.max(maxBottom, bounds.y + bounds.height);
  }

  return {
    width: Math.max(MIN_PAGE_WIDTH, Math.ceil(maxRight + 40)),
    height: Math.max(MIN_PAGE_HEIGHT, Math.ceil(maxBottom + 40)),
  };
}

function buildChildrenMap(candidates) {
  const byParent = new Map();
  for (const candidate of candidates) {
    const parentId = candidate.parent_candidate_id;
    if (!byParent.has(parentId)) {
      byParent.set(parentId, []);
    }
    byParent.get(parentId).push(candidate);
  }
  return byParent;
}

async function renderIntermediatePayload(payload) {
  await ensureFontLoaded();

  const rootFrame = figma.createFrame();
  rootFrame.name = "CNS Atlas Visual Test";
  rootFrame.fills = [];
  rootFrame.strokes = [];

  let cursorX = 0;

  for (const page of payload.pages) {
    const pageFrame = figma.createFrame();
    const pageBounds = computePageBounds(page.candidates);
    pageFrame.name = `Slide ${page.slide_no} - ${page.title_or_label}`;
    pageFrame.resize(pageBounds.width, pageBounds.height);
    pageFrame.x = cursorX;
    pageFrame.y = 0;
    pageFrame.fills = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }];
    pageFrame.strokes = [{ type: "SOLID", color: { r: 0.82, g: 0.82, b: 0.82 } }];
    pageFrame.strokeWeight = 1;
    rootFrame.appendChild(pageFrame);

    const childrenMap = buildChildrenMap(page.candidates);
    const roots = [...(childrenMap.get(page.page_id) || [])].sort(sortByPosition);
    for (const candidate of roots) {
      await renderCandidateTree(candidate, childrenMap, pageFrame, { x: 0, y: 0 }, 0);
    }

    cursorX += pageBounds.width + SLIDE_GAP;
  }

  rootFrame.resize(Math.max(cursorX - SLIDE_GAP, 1), MIN_PAGE_HEIGHT + 80);
  figma.currentPage.appendChild(rootFrame);
  figma.viewport.scrollAndZoomIntoView([rootFrame]);
}

function sortByPosition(a, b) {
  const ay = a.bounds_px ? a.bounds_px.y : Number.MAX_SAFE_INTEGER;
  const by = b.bounds_px ? b.bounds_px.y : Number.MAX_SAFE_INTEGER;
  if (ay !== by) {
    return ay - by;
  }
  const ax = a.bounds_px ? a.bounds_px.x : Number.MAX_SAFE_INTEGER;
  const bx = b.bounds_px ? b.bounds_px.x : Number.MAX_SAFE_INTEGER;
  return ax - bx;
}

function relativeBounds(candidate, origin) {
  const bounds = candidate.bounds_px;
  if (!bounds) {
    return null;
  }
  return {
    x: bounds.x - origin.x,
    y: bounds.y - origin.y,
    width: Math.max(bounds.width || 1, 1),
    height: Math.max(bounds.height || 1, 1),
  };
}

async function renderCandidateTree(candidate, childrenMap, parentNode, origin, fallbackIndex) {
  const node = await createNodeForCandidate(candidate, parentNode, origin, fallbackIndex);
  const children = [...(childrenMap.get(candidate.candidate_id) || [])].sort(sortByPosition);

  if (children.length === 0) {
    return node;
  }

  const nextOrigin = candidate.bounds_px || origin;
  let childFallbackIndex = 0;
  for (const child of children) {
    try {
      await renderCandidateTree(child, childrenMap, node, nextOrigin, childFallbackIndex);
    } catch (err) {
      console.error(`Error rendering child ${child.candidate_id}`, err);
      throw err;
    }
    childFallbackIndex += 1;
  }
  return node;
}

async function createNodeForCandidate(candidate, parentNode, origin, fallbackIndex) {
  switch (candidate.subtype) {
    case "text_block":
      return createTextBlock(candidate, parentNode, origin, fallbackIndex);
    case "labeled_shape":
      return createLabeledShape(candidate, parentNode, origin, fallbackIndex);
    case "shape":
      return createShape(candidate, parentNode, origin, fallbackIndex);
    case "connector":
      return createConnector(candidate, parentNode, origin, fallbackIndex);
    case "group":
    case "section_block":
      return createGroupFrame(candidate, parentNode, origin, fallbackIndex);
    case "table":
      return createTableFrame(candidate, parentNode, origin, fallbackIndex);
    case "table_row":
      return createTableRow(candidate, parentNode);
    case "table_cell":
      return createTableCell(candidate, parentNode);
    case "image":
      return createImagePlaceholder(candidate, parentNode, origin, fallbackIndex);
    default:
      return createShape(candidate, parentNode, origin, fallbackIndex);
  }
}

async function createTextBlock(candidate, parentNode, origin, fallbackIndex) {
  const node = figma.createText();
  node.name = candidate.title || candidate.subtype;
  node.fontName = DEFAULT_FONT;
  node.characters = candidate.text || candidate.title || "";
  node.fills = [{ type: "SOLID", color: { r: 0.15, g: 0.15, b: 0.15 } }];
  const bounds = relativeBounds(candidate, origin);
  if (bounds) {
    node.x = bounds.x;
    node.y = bounds.y;
    node.resize(Math.max(bounds.width, 24), Math.max(bounds.height, 16));
    node.fontSize = clampFontSize(bounds.height || 16);
  } else {
    node.x = 20;
    node.y = 20 + fallbackIndex * 20;
    node.fontSize = 18;
  }
  parentNode.appendChild(node);
  return node;
}

async function createLabeledShape(candidate, parentNode, origin, fallbackIndex) {
  const bounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 24,
    width: 120,
    height: 32,
  };
  const frame = figma.createFrame();
  frame.name = candidate.title || candidate.subtype;
  frame.x = bounds.x;
  frame.y = bounds.y;
  frame.resize(bounds.width, bounds.height);
  frame.fills = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }];
  frame.strokes = [{ type: "SOLID", color: { r: 0.28, g: 0.28, b: 0.28 } }];
  frame.strokeWeight = 1;
  frame.clipsContent = false;
  const shapeKind = candidate.extra && candidate.extra.shape_kind ? candidate.extra.shape_kind : "";
  frame.cornerRadius = shapeKind === "ellipse" ? Math.min(bounds.width, bounds.height) / 2 : 6;
  parentNode.appendChild(frame);

  const text = figma.createText();
  text.name = `${frame.name} label`;
  text.fontName = DEFAULT_FONT;
  text.characters = candidate.text || candidate.title || "";
  text.fills = [{ type: "SOLID", color: { r: 0.12, g: 0.12, b: 0.12 } }];
  text.fontSize = clampFontSize(bounds.height * 0.45);
  frame.appendChild(text);
  text.x = Math.max((bounds.width - text.width) / 2, 6);
  text.y = Math.max((bounds.height - text.height) / 2, 4);
  return frame;
}

function createShape(candidate, parentNode, origin, fallbackIndex) {
  const bounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 20,
    width: 120,
    height: 24,
  };
  const node = figma.createRectangle();
  node.name = candidate.title || candidate.subtype;
  node.x = bounds.x;
  node.y = bounds.y;
  node.resize(bounds.width, bounds.height);
  node.fills = [{ type: "SOLID", color: { r: 0.94, g: 0.95, b: 0.97 } }];
  node.strokes = [{ type: "SOLID", color: { r: 0.75, g: 0.78, b: 0.82 } }];
  node.strokeWeight = 1;
  parentNode.appendChild(node);
  return node;
}

function createConnector(candidate, parentNode, origin, fallbackIndex) {
  const bounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 20,
    width: 80,
    height: 2,
  };
  const line = figma.createLine();
  line.name = candidate.title || "connector";
  line.x = bounds.x;
  line.y = bounds.y;
  line.resize(Math.max(bounds.width, 10), Math.max(bounds.height, 1));
  line.strokes = [{ type: "SOLID", color: { r: 0.35, g: 0.35, b: 0.35 } }];
  line.strokeWeight = 1;
  parentNode.appendChild(line);
  return line;
}

function createGroupFrame(candidate, parentNode, origin, fallbackIndex) {
  const bounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 24,
    width: 160,
    height: 60,
  };
  const frame = figma.createFrame();
  frame.name = candidate.title || candidate.subtype;
  frame.x = bounds.x;
  frame.y = bounds.y;
  frame.resize(bounds.width, bounds.height);
  frame.fills = [];
  frame.strokes = [{
    type: "SOLID",
    color: candidate.subtype === "section_block"
      ? { r: 0.22, g: 0.47, b: 0.86 }
      : { r: 0.79, g: 0.53, b: 0.18 },
  }];
  frame.strokeWeight = candidate.subtype === "section_block" ? 2 : 1;
  frame.dashPattern = candidate.subtype === "section_block" ? [8, 4] : [4, 4];
  frame.clipsContent = false;
  parentNode.appendChild(frame);
  return frame;
}

function createTableFrame(candidate, parentNode, origin, fallbackIndex) {
  const bounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 24,
    width: 400,
    height: 240,
  };
  const frame = figma.createFrame();
  frame.name = candidate.title || "table";
  frame.x = bounds.x;
  frame.y = bounds.y;
  frame.resize(bounds.width, bounds.height);
  frame.fills = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }];
  frame.strokes = [{ type: "SOLID", color: { r: 0.45, g: 0.45, b: 0.45 } }];
  frame.strokeWeight = 1;
  frame.clipsContent = false;
  const rowCount = candidate.extra && candidate.extra.row_count ? candidate.extra.row_count : 1;
  frame.setPluginData("rowCount", String(rowCount));
  parentNode.appendChild(frame);
  return frame;
}

function createTableRow(candidate, parentNode) {
  const row = figma.createFrame();
  row.name = candidate.title || candidate.subtype;
  row.fills = [];
  row.strokes = [];
  row.clipsContent = false;

  const extra = candidate.extra || {};
  const cellCount = extra.cell_count || 1;
  const siblings = parentNode.children.filter((child) => child.type === "FRAME").length;
  const rowCount = Number(parentNode.getPluginData("rowCount") || "1");
  const rowHeight = Math.max(parentNode.height / Math.max(rowCount, 1), 24);
  row.x = 0;
  row.y = siblings * rowHeight;
  row.resize(parentNode.width, rowHeight);
  parentNode.appendChild(row);
  row.setPluginData("cellCount", String(cellCount));
  return row;
}

async function createTableCell(candidate, parentNode) {
  const cell = figma.createFrame();
  cell.name = candidate.title || candidate.subtype;
  const cellCount = Number(parentNode.getPluginData("cellCount") || "1");
  const siblings = parentNode.children.filter((child) => child.type === "FRAME").length;
  const width = parentNode.width / Math.max(cellCount, 1);
  cell.x = siblings * width;
  cell.y = 0;
  cell.resize(width, parentNode.height);
  cell.fills = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }];
  cell.strokes = [{ type: "SOLID", color: { r: 0.75, g: 0.75, b: 0.75 } }];
  cell.strokeWeight = 1;
  parentNode.appendChild(cell);

  const text = figma.createText();
  text.name = `${cell.name} text`;
  text.fontName = DEFAULT_FONT;
  text.characters = candidate.text || "";
  text.fontSize = 10;
  text.fills = [{ type: "SOLID", color: { r: 0.15, g: 0.15, b: 0.15 } }];
  cell.appendChild(text);
  text.x = 6;
  text.y = 4;
  return cell;
}

async function createImagePlaceholder(candidate, parentNode, origin, fallbackIndex) {
  const bounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 24,
    width: 80,
    height: 80,
  };
  const frame = figma.createFrame();
  frame.name = candidate.title || candidate.subtype;
  frame.x = bounds.x;
  frame.y = bounds.y;
  frame.resize(bounds.width, bounds.height);
  frame.fills = [{ type: "SOLID", color: { r: 0.93, g: 0.94, b: 0.96 } }];
  frame.strokes = [{ type: "SOLID", color: { r: 0.64, g: 0.68, b: 0.74 } }];
  frame.strokeWeight = 1;
  parentNode.appendChild(frame);

  const text = figma.createText();
  text.name = `${frame.name} placeholder`;
  text.fontName = DEFAULT_FONT;
  text.characters = "IMAGE";
  text.fontSize = clampFontSize(bounds.height * 0.22);
  text.fills = [{ type: "SOLID", color: { r: 0.32, g: 0.36, b: 0.42 } }];
  frame.appendChild(text);
  text.x = Math.max((bounds.width - text.width) / 2, 6);
  text.y = Math.max((bounds.height - text.height) / 2, 4);
  return frame;
}

function clampFontSize(value) {
  return Math.max(10, Math.min(Math.round(value), 28));
}
