const DEFAULT_FONT = { family: "Inter", style: "Regular" };
const SLIDE_GAP = 120;
const MIN_PAGE_WIDTH = 960;
const MIN_PAGE_HEIGHT = 540;
const ARROW_ROTATION_FLIP_IDS = new Set([
  "s12:slide_12/element_4",
  "s12:slide_12/element_7",
  "s12:slide_12/element_56",
  "s19:slide_19/element_7",
  "s19:slide_19/element_11",
]);
const FONT_FALLBACKS = {
  "LG스마트체": [{ family: "LG스마트체", style: "Regular" }, { family: "Malgun Gothic", style: "Regular" }, DEFAULT_FONT],
  "LG스마트체2.0": [{ family: "LG스마트체2.0", style: "Regular" }, { family: "Malgun Gothic", style: "Regular" }, DEFAULT_FONT],
  "LG Smart_H": [{ family: "LG Smart_H", style: "Regular" }, { family: "Malgun Gothic", style: "Regular" }, DEFAULT_FONT],
  "+mn-ea": [{ family: "Malgun Gothic", style: "Regular" }, DEFAULT_FONT],
  "+mj-ea": [{ family: "Malgun Gothic", style: "Regular" }, DEFAULT_FONT],
};

let fontLoaded = false;
const fontAvailability = new Map();
let activeRenderMode = "read-first";

figma.showUI(__html__, {
  width: 420,
  height: 360,
});

figma.ui.onmessage = async (message) => {
  if (message.type === "render-intermediate-json") {
    try {
      const payload = JSON.parse(message.jsonText);
      activeRenderMode = message.renderMode === "vector-heavy" ? "vector-heavy" : "read-first";
      if (payload && payload.kind === "figma-replay-bundle" && payload.document) {
        await renderFigmaReplayBundle(payload);
      } else {
        await renderIntermediatePayload(payload);
      }
      figma.ui.postMessage({
        type: "render-success",
        message: payload && payload.kind === "figma-replay-bundle"
          ? `Rendered figma replay bundle (${payload.page_name || "unknown page"})`
          : `Rendered ${payload.pages.length} slide previews (${activeRenderMode})`,
      });
    } catch (error) {
      figma.ui.postMessage({
        type: "render-error",
        message: error instanceof Error ? `${error.name}: ${error.message}\n${error.stack}` : String(error),
      });
    }
  }
};

function clearPreviousVisualTests() {
  for (const child of [...figma.currentPage.children]) {
    if (child.name && (child.name.startsWith("CNS Atlas Visual Test") || child.name.startsWith("CNS Atlas Replay"))) {
      child.remove();
    }
  }
}

function isVectorHeavyMode() {
  return activeRenderMode === "vector-heavy";
}

async function ensureFontLoaded() {
  if (!fontLoaded) {
    await figma.loadFontAsync(DEFAULT_FONT);
    fontAvailability.set(`${DEFAULT_FONT.family}::${DEFAULT_FONT.style}`, DEFAULT_FONT);
    fontLoaded = true;
  }
}

function normalizeFontCandidate(textStyle) {
  const rawFamily = textStyle && textStyle.font_family ? textStyle.font_family : "";
  if (!rawFamily) {
    return { family: DEFAULT_FONT.family, style: DEFAULT_FONT.style, fallbacks: [DEFAULT_FONT] };
  }

  let family = rawFamily;
  let style = "Regular";
  if (rawFamily.endsWith(" Bold")) {
    family = rawFamily.slice(0, -" Bold".length);
    style = "Bold";
  } else if (rawFamily.endsWith(" SemiBold")) {
    family = rawFamily.slice(0, -" SemiBold".length);
    style = "SemiBold";
  } else if (rawFamily.endsWith(" Light")) {
    family = rawFamily.slice(0, -" Light".length);
    style = "Light";
  } else if (rawFamily.endsWith(" Regular")) {
    family = rawFamily.slice(0, -" Regular".length);
    style = "Regular";
  }

  const chain = [{ family, style }];
  const fallbackFamily = FONT_FALLBACKS[family] || FONT_FALLBACKS[rawFamily];
  if (fallbackFamily) {
    chain.push(...fallbackFamily.map((item) => ({ family: item.family, style: style === "Bold" && item.family === "Malgun Gothic" ? "Bold" : item.style })));
  } else {
    chain.push({ family: "Malgun Gothic", style: style === "Bold" ? "Bold" : "Regular" });
    chain.push(DEFAULT_FONT);
  }

  return { family, style, fallbacks: chain };
}

async function resolveFontName(textStyle) {
  const candidate = normalizeFontCandidate(textStyle || {});
  for (const font of candidate.fallbacks) {
    const key = `${font.family}::${font.style}`;
    if (fontAvailability.has(key)) {
      const cached = fontAvailability.get(key);
      if (cached) return cached;
      continue;
    }
    try {
      await figma.loadFontAsync(font);
      fontAvailability.set(key, font);
      return font;
    } catch (error) {
      fontAvailability.set(key, null);
    }
  }
  return DEFAULT_FONT;
}

async function resolveFigmaFontName(style) {
  const family = style && style.fontFamily ? style.fontFamily : DEFAULT_FONT.family;
  const fontStyle = style && style.fontStyle ? style.fontStyle : DEFAULT_FONT.style;
  const postScript = style && style.fontPostScriptName ? style.fontPostScriptName : null;
  const candidates = [];
  candidates.push({ family, style: fontStyle });
  if (postScript && postScript.toLowerCase().includes("bold")) {
    candidates.push({ family, style: "Bold" });
  }
  candidates.push(...(FONT_FALLBACKS[family] || []));
  candidates.push(DEFAULT_FONT);

  for (const font of candidates) {
    const key = `${font.family}::${font.style}`;
    if (fontAvailability.has(key)) {
      const cached = fontAvailability.get(key);
      if (cached) {
        return cached;
      }
      continue;
    }
    try {
      await figma.loadFontAsync(font);
      fontAvailability.set(key, font);
      return font;
    } catch (error) {
      fontAvailability.set(key, null);
    }
  }
  return DEFAULT_FONT;
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

function colorFromHex(value, fallback) {
  if (!value || value.length !== 6) {
    return fallback;
  }
  return {
    r: parseInt(value.slice(0, 2), 16) / 255,
    g: parseInt(value.slice(2, 4), 16) / 255,
    b: parseInt(value.slice(4, 6), 16) / 255,
  };
}

function makeSolidPaint(styleColor, fallback, defaultOpacity) {
  const resolvedHex = styleColor && (styleColor.resolved_value || styleColor.value);
  const paint = {
    type: "SOLID",
    color: resolvedHex ? colorFromHex(resolvedHex, fallback) : fallback,
  };
  const opacity = styleColor && typeof styleColor.alpha === "number" ? styleColor.alpha : defaultOpacity;
  if (typeof opacity === "number") {
    paint.opacity = opacity;
  }
  return paint;
}

function getShapeStyle(candidate) {
  return candidate.extra && candidate.extra.shape_style ? candidate.extra.shape_style : {};
}

function getTextStyle(candidate) {
  return candidate.extra && candidate.extra.text_style ? candidate.extra.text_style : {};
}

function getRendering(candidate) {
  return candidate && candidate.rendering ? candidate.rendering : {};
}

function getReplacement(candidate) {
  const rendering = getRendering(candidate);
  return rendering && rendering.replacement ? rendering.replacement : null;
}

function prefixedNodeName(candidate) {
  const replacement = getReplacement(candidate);
  if (!replacement) {
    return candidate.title || candidate.subtype;
  }
  return `VF/${replacement.candidate_type}/${candidate.title || candidate.subtype}`;
}

function applyRenderingMetadata(node, candidate) {
  if (!node || !candidate || typeof node.setPluginData !== "function") {
    return;
  }
  const rendering = getRendering(candidate);
  const replacement = getReplacement(candidate);
  node.setPluginData("candidate_id", candidate.candidate_id || "");
  node.setPluginData("source_path", candidate.source_path || "");
  node.setPluginData("current_mode", rendering.current_mode || "native");
  node.setPluginData("preferred_mode", rendering.preferred_mode || "native");
  node.setPluginData("replacement_candidate", rendering.replacement_candidate ? "true" : "false");
  if (replacement) {
    node.setPluginData("replacement_candidate_type", replacement.candidate_type || "");
    node.setPluginData("replacement_strategy", replacement.strategy || "");
    node.setPluginData("replacement_confidence", replacement.confidence || "");
    node.name = prefixedNodeName(candidate);
  }
}

function pageCanvasSize(page) {
  const slideSize = page.slide_size || {};
  const width = slideSize.width_px ? Math.ceil(slideSize.width_px) : null;
  const height = slideSize.height_px ? Math.ceil(slideSize.height_px) : null;
  if (width && height) {
    return { width, height };
  }
  return computePageBounds(page.candidates);
}

function alignTextNode(node, bounds, textStyle, horizontalFallback, verticalFallback) {
  const horizontal = textStyle.horizontal_align || horizontalFallback || "l";
  const vertical = textStyle.vertical_align || verticalFallback || "ctr";

  const leftInset = typeof textStyle.lIns === "number" ? textStyle.lIns : 6;
  const rightInset = typeof textStyle.rIns === "number" ? textStyle.rIns : 6;
  const topInset = typeof textStyle.tIns === "number" ? textStyle.tIns : 4;
  const bottomInset = typeof textStyle.bIns === "number" ? textStyle.bIns : 4;

  if (horizontal === "ctr" || horizontal === "center") {
    node.x = Math.max((bounds.width - node.width) / 2, 4);
  } else if (horizontal === "r" || horizontal === "right") {
    node.x = Math.max(bounds.width - node.width - rightInset, 4);
  } else {
    node.x = leftInset;
  }

  if (vertical === "ctr" || vertical === "mid" || vertical === "center") {
    node.y = Math.max((bounds.height - node.height) / 2, 4);
  } else if (vertical === "b" || vertical === "bottom") {
    node.y = Math.max(bounds.height - node.height - bottomInset, 4);
  } else {
    node.y = topInset;
  }
}

function mapHorizontalAlign(value, fallback) {
  const align = value || fallback || "l";
  if (align === "ctr" || align === "center") {
    return "CENTER";
  }
  if (align === "r" || align === "right") {
    return "RIGHT";
  }
  if (align === "just" || align === "justify") {
    return "JUSTIFIED";
  }
  return "LEFT";
}

function mapVerticalAlign(value, fallback) {
  const align = value || fallback || "t";
  if (align === "ctr" || align === "mid" || align === "center") {
    return "CENTER";
  }
  if (align === "b" || align === "bottom") {
    return "BOTTOM";
  }
  return "TOP";
}

function deriveWrapMode(textValue, textStyle, bounds, options) {
  const text = typeof textValue === "string" ? textValue : "";
  const explicitLineBreak = text.includes("\n");
  if (explicitLineBreak) {
    return "square";
  }

  const wrap = textStyle && textStyle.wrap ? textStyle.wrap : null;
  const fontSize = clampFontSize(
    (textStyle && (textStyle.font_size_max || textStyle.font_size_avg)) || (bounds ? bounds.height * 0.45 : 12)
  );
  const boxWidth = bounds ? bounds.width : 120;
  const boxHeight = bounds ? bounds.height : fontSize * 1.4;
  const roughCharCapacity = Math.max(Math.floor((boxWidth - 12) / Math.max(fontSize * 0.55, 4)), 4);
  const needsWrapByLength = text.length > roughCharCapacity;
  const canVisuallyHoldMultipleLines = boxHeight >= fontSize * 1.9;

  if (options && options.forceWrap) {
    return "square";
  }
  if (wrap === "none") {
    return "none";
  }
  if (wrap && wrap !== "none" && canVisuallyHoldMultipleLines && needsWrapByLength) {
    return "square";
  }
  if (canVisuallyHoldMultipleLines && needsWrapByLength) {
    return "square";
  }
  return "none";
}

function createTransparentFrame(bounds, name) {
  const frame = figma.createFrame();
  frame.name = name;
  frame.x = bounds.x;
  frame.y = bounds.y;
  frame.resize(bounds.width, bounds.height);
  frame.fills = [];
  frame.strokes = [];
  frame.clipsContent = false;
  if (bounds.rotation) {
    frame.rotation = bounds.rotation;
  }
  return frame;
}

function shouldFlattenVisual(candidate) {
  if (!isVectorHeavyMode()) {
    return false;
  }
  const replacement = getReplacement(candidate);
  if (candidate.subtype === "connector") {
    return true;
  }
  if (replacement && (replacement.candidate_type === "decision_diamond" || replacement.candidate_type === "complex_shape")) {
    return true;
  }
  if (candidate.subtype === "shape") {
    return true;
  }
  return false;
}

function finalizeVectorHeavyVisual(frame, candidate) {
  if (!shouldFlattenVisual(candidate)) {
    return frame;
  }
  const flattenTargets = frame.children.filter((child) => child.type !== "TEXT");
  if (flattenTargets.length === 0) {
    return frame;
  }
  try {
    const flattened = figma.flatten(flattenTargets, frame);
    flattened.name = `${candidate.title || candidate.subtype} vector`;
    if (typeof flattened.setPluginData === "function") {
      flattened.setPluginData("vector_heavy", "true");
      flattened.setPluginData("candidate_id", candidate.candidate_id || "");
    }
  } catch (error) {
    console.warn(`vector-heavy flatten skipped for ${candidate.candidate_id}:`, error);
  }
  return frame;
}

async function appendTextIntoContainer(container, candidate, textValue, textStyle, bounds, horizontalFallback, verticalFallback) {
  const text = figma.createText();
  text.name = `${container.name} text`;
  text.fontName = await resolveFontName(textStyle);
  text.characters = textValue || candidate.title || "";
  text.fills = [makeSolidPaint(textStyle.fill, { r: 0.12, g: 0.12, b: 0.12 }, 1)];
  text.fontSize = clampFontSize(textStyle.font_size_max || textStyle.font_size_avg || bounds.height * 0.45);
  text.textAlignHorizontal = mapHorizontalAlign(textStyle.horizontal_align, horizontalFallback);
  text.textAlignVertical = mapVerticalAlign(textStyle.vertical_align, verticalFallback);
  const wrapMode = deriveWrapMode(text.characters, textStyle, bounds, { forceWrap: false });
  text.textAutoResize = wrapMode === "none" ? "WIDTH_AND_HEIGHT" : "HEIGHT";

  const leftInset = typeof textStyle.lIns === "number" ? textStyle.lIns : 6;
  const rightInset = typeof textStyle.rIns === "number" ? textStyle.rIns : 6;
  const contentWidth = Math.max(bounds.width - leftInset - rightInset, 12);
  if (wrapMode !== "none") {
    text.resize(contentWidth, Math.max(bounds.height, 16));
  }

  container.appendChild(text);
  alignTextNode(
    text,
    {
      width: bounds.width,
      height: Math.max(bounds.height, text.height),
    },
    textStyle,
    horizontalFallback,
    verticalFallback
  );
  return text;
}

function base64ToBytes(base64) {
  if (typeof atob === "function") {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }
  throw new Error("Base64 decoder is unavailable in this Figma runtime.");
}

function addArrowHeadIfNeeded(candidate, parentNode, bounds, lineColor, direction, tipPoint) {
  const shapeStyle = getShapeStyle(candidate);
  const line = shapeStyle.line || {};
  const tailEnd = line.tail_end || {};
  if (tailEnd.type !== "triangle") {
    return;
  }

  const arrow = figma.createPolygon();
  arrow.pointCount = 3;
  arrow.resize(10, 10);
  arrow.fills = [{ type: "SOLID", color: lineColor }];
  arrow.strokes = [];

  if (direction && (direction.dx !== 0 || direction.dy !== 0)) {
    const angle = Math.atan2(direction.dy, direction.dx) * (180 / Math.PI);
    arrow.rotation = angle + 90 + (ARROW_ROTATION_FLIP_IDS.has(candidate.candidate_id) ? 180 : 0);
    const radians = Math.atan2(direction.dy, direction.dx);
    if (tipPoint) {
      const centerX = tipPoint.x - Math.cos(radians) * 5;
      const centerY = tipPoint.y - Math.sin(radians) * 5;
      arrow.x = centerX - 5;
      arrow.y = centerY - 5;
    } else {
      const centerX = bounds.x + Math.cos(radians) * 5;
      const centerY = bounds.y + Math.sin(radians) * 5;
      arrow.x = centerX - 5;
      arrow.y = centerY - 5;
    }
  } else {
    const rotation = ((bounds.rotation || 0) % 360 + 360) % 360;
    const horizontalLike = bounds.width >= bounds.height;
    if (rotation >= 45 && rotation < 135) {
      arrow.rotation = 180;
      arrow.x = bounds.x - 4;
      arrow.y = bounds.y + Math.max(bounds.height - 5, 0);
    } else if (rotation >= 225 && rotation < 315) {
      arrow.rotation = 0;
      arrow.x = bounds.x - 4;
      arrow.y = bounds.y - 4;
    } else if (horizontalLike) {
      arrow.rotation = 90;
      arrow.x = bounds.x + Math.max(bounds.width - 5, 0);
      arrow.y = bounds.y - 4;
    } else {
      arrow.rotation = 180;
      arrow.x = bounds.x - 4;
      arrow.y = bounds.y + Math.max(bounds.height - 5, 0);
    }
  }

  parentNode.appendChild(arrow);
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

  clearPreviousVisualTests();

  const rootFrame = figma.createFrame();
  rootFrame.name = `CNS Atlas Visual Test (${activeRenderMode})`;
  rootFrame.fills = [];
  rootFrame.strokes = [];

  let cursorX = 0;
  let maxHeight = MIN_PAGE_HEIGHT;

  for (const page of payload.pages) {
    const pageFrame = figma.createFrame();
    const pageBounds = pageCanvasSize(page);
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
    maxHeight = Math.max(maxHeight, pageBounds.height);
  }

  rootFrame.resize(Math.max(cursorX - SLIDE_GAP, 1), maxHeight);
  figma.currentPage.appendChild(rootFrame);
  figma.viewport.scrollAndZoomIntoView([rootFrame]);
}

function colorToSvg(color, opacity) {
  const r = Math.round((color.r || 0) * 255);
  const g = Math.round((color.g || 0) * 255);
  const b = Math.round((color.b || 0) * 255);
  const a = typeof opacity === "number" ? opacity : (typeof color.a === "number" ? color.a : 1);
  return { rgb: `rgb(${r}, ${g}, ${b})`, opacity: a };
}

function getReplayBounds(node) {
  return node.absoluteBoundingBox || node.absoluteRenderBounds || null;
}

function hasVisibleSolidPaint(node) {
  const fills = node && node.fills ? node.fills : [];
  for (const fill of fills) {
    if (!fill || fill.visible === false) {
      continue;
    }
    if (fill.type === "SOLID") {
      const opacity = typeof fill.opacity === "number"
        ? fill.opacity
        : (fill.color && typeof fill.color.a === "number" ? fill.color.a : 1);
      if (opacity > 0) {
        return true;
      }
    }
    if (fill.type === "IMAGE") {
      return true;
    }
  }
  return false;
}

function hasVisibleStroke(node) {
  const strokes = node && node.strokes ? node.strokes : [];
  for (const stroke of strokes) {
    if (!stroke || stroke.visible === false) {
      continue;
    }
    const opacity = typeof stroke.opacity === "number"
      ? stroke.opacity
      : (stroke.color && typeof stroke.color.a === "number" ? stroke.color.a : 1);
    if (opacity > 0) {
      return true;
    }
  }
  return false;
}

function boundsRelativeToOrigin(bounds, origin) {
  return {
    x: bounds.x - origin.x,
    y: bounds.y - origin.y,
    width: Math.max(bounds.width || 1, 1),
    height: Math.max(bounds.height || 1, 1),
  };
}

function computeReplayRootBounds(node) {
  const fallback = getReplayBounds(node) || { x: 0, y: 0, width: MIN_PAGE_WIDTH, height: MIN_PAGE_HEIGHT };
  let minX = fallback.x;
  let minY = fallback.y;
  let maxX = fallback.x + fallback.width;
  let maxY = fallback.y + fallback.height;

  function walk(current) {
    if (!current || typeof current !== "object") {
      return;
    }
    const bounds = getReplayBounds(current);
    if (bounds) {
      minX = Math.min(minX, bounds.x);
      minY = Math.min(minY, bounds.y);
      maxX = Math.max(maxX, bounds.x + bounds.width);
      maxY = Math.max(maxY, bounds.y + bounds.height);
    }
    for (const child of current.children || []) {
      walk(child);
    }
  }

  walk(node);
  return { x: minX, y: minY, width: Math.max(maxX - minX, 1), height: Math.max(maxY - minY, 1) };
}

function mapReplayHorizontalAlign(value) {
  if (value === "CENTER") return "CENTER";
  if (value === "RIGHT") return "RIGHT";
  if (value === "JUSTIFIED") return "JUSTIFIED";
  return "LEFT";
}

function mapReplayVerticalAlign(value) {
  if (value === "CENTER") return "CENTER";
  if (value === "BOTTOM") return "BOTTOM";
  return "TOP";
}

function buildVectorSvg(node, bounds) {
  const fillGeometry = node.fillGeometry || [];
  const strokeGeometry = node.strokeGeometry || [];
  const solidFill = (node.fills || []).find((fill) => fill && fill.type === "SOLID");
  const solidStroke = (node.strokes || []).find((stroke) => stroke && stroke.type === "SOLID");
  const fillInfo = solidFill ? colorToSvg(solidFill.color || {}, solidFill.opacity) : null;
  const strokeInfo = solidStroke ? colorToSvg(solidStroke.color || {}, solidStroke.opacity) : null;
  const strokeWidth = node.strokeWeight || 1;
  const fillRule = fillGeometry[0] && fillGeometry[0].windingRule === "NONZERO" ? "nonzero" : "evenodd";

  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${bounds.width}" height="${bounds.height}" viewBox="0 0 ${bounds.width} ${bounds.height}">`,
  ];

  for (const geometry of fillGeometry) {
    if (!geometry.path) continue;
    const fillAttrs = fillInfo
      ? `fill="${fillInfo.rgb}" fill-opacity="${fillInfo.opacity}"`
      : 'fill="none"';
    parts.push(`<path d="${geometry.path}" ${fillAttrs} fill-rule="${fillRule}" />`);
  }

  for (const geometry of strokeGeometry) {
    if (!geometry.path) continue;
    const strokeAttrs = strokeInfo
      ? `stroke="${strokeInfo.rgb}" stroke-opacity="${strokeInfo.opacity}" stroke-width="${strokeWidth}"`
      : `stroke="rgb(0,0,0)" stroke-width="${strokeWidth}"`;
    parts.push(`<path d="${geometry.path}" fill="none" ${strokeAttrs} />`);
  }

  parts.push("</svg>");
  return parts.join("");
}

function findAssetBytes(bundle, imageRef) {
  if (!bundle || !bundle.assets || !bundle.assets[imageRef]) {
    return null;
  }
  return base64ToBytes(bundle.assets[imageRef].base64);
}

function createReplayContainer(node, parentNode, origin) {
  const bounds = getReplayBounds(node);
  if (!bounds) {
    return parentNode;
  }
  const local = boundsRelativeToOrigin(bounds, origin);
  const frame = figma.createFrame();
  frame.name = node.name || node.type || "container";
  frame.x = local.x;
  frame.y = local.y;
  frame.resize(local.width, local.height);
  frame.fills = [];
  frame.strokes = [];
  frame.clipsContent = false;
  parentNode.appendChild(frame);
  return frame;
}

function createReplayFrameShell(node, parentNode, origin) {
  const bounds = getReplayBounds(node);
  if (!bounds) {
    return null;
  }
  const local = boundsRelativeToOrigin(bounds, origin);
  const shell = figma.createRectangle();
  shell.name = node.name || node.type || "frame-shell";
  shell.x = local.x;
  shell.y = local.y;
  shell.resize(local.width, local.height);
  shell.fills = (node.fills || []).filter((fill) => fill && (fill.type === "SOLID" || fill.type === "IMAGE")).map((fill) => {
    if (fill.type === "SOLID") {
      return {
        type: "SOLID",
        color: fill.color,
        opacity: typeof fill.opacity === "number" ? fill.opacity : (fill.color && typeof fill.color.a === "number" ? fill.color.a : 1),
      };
    }
    if (fill.type === "IMAGE") {
      return fill;
    }
    return null;
  }).filter(Boolean);
  shell.strokes = (node.strokes || []).filter((stroke) => stroke && stroke.type === "SOLID").map((stroke) => ({
    type: "SOLID",
    color: stroke.color,
    opacity: typeof stroke.opacity === "number" ? stroke.opacity : (stroke.color && typeof stroke.color.a === "number" ? stroke.color.a : 1),
  }));
  shell.strokeWeight = node.strokeWeight || 1;
  parentNode.appendChild(shell);
  return shell;
}

async function renderReplayText(node, parentNode, origin) {
  const bounds = getReplayBounds(node);
  if (!bounds) {
    return;
  }
  const local = boundsRelativeToOrigin(bounds, origin);
  const text = figma.createText();
  text.name = node.name || "Text";
  text.fontName = await resolveFigmaFontName(node.style || {});
  text.characters = node.characters || "";
  text.fontSize = node.style && node.style.fontSize ? node.style.fontSize : 12;
  text.textAlignHorizontal = mapReplayHorizontalAlign(node.style && node.style.textAlignHorizontal);
  text.textAlignVertical = mapReplayVerticalAlign(node.style && node.style.textAlignVertical);
  if ((node.style && node.style.textAutoResize) === "HEIGHT") {
    text.textAutoResize = "HEIGHT";
    text.resize(Math.max(local.width, 12), Math.max(local.height, 16));
  } else {
    text.textAutoResize = "WIDTH_AND_HEIGHT";
  }
  if (node.style && typeof node.style.letterSpacing === "number") {
    text.letterSpacing = { value: node.style.letterSpacing, unit: "PIXELS" };
  }
  if (node.style && typeof node.style.lineHeightPx === "number") {
    text.lineHeight = { unit: "PIXELS", value: node.style.lineHeightPx };
  }
  text.fills = (node.fills || []).filter((fill) => fill && fill.type === "SOLID").map((fill) => ({
    type: "SOLID",
    color: { r: fill.color.r || 0, g: fill.color.g || 0, b: fill.color.b || 0 },
    opacity: typeof fill.opacity === "number" ? fill.opacity : (fill.color && typeof fill.color.a === "number" ? fill.color.a : 1),
  }));
  if (text.fills.length === 0) {
    text.fills = [{ type: "SOLID", color: { r: 0, g: 0, b: 0 } }];
  }
  text.x = local.x;
  text.y = local.y;
  parentNode.appendChild(text);
}

function renderReplayRectangle(node, parentNode, origin, bundle) {
  const bounds = getReplayBounds(node);
  if (!bounds) {
    return;
  }
  const local = boundsRelativeToOrigin(bounds, origin);
  const rect = figma.createRectangle();
  rect.name = node.name || "Rectangle";
  rect.x = local.x;
  rect.y = local.y;
  rect.resize(local.width, local.height);
  if (typeof node.cornerRadius === "number") {
    rect.cornerRadius = node.cornerRadius;
  }
  const imageFill = (node.fills || []).find((fill) => fill && fill.type === "IMAGE" && fill.imageRef);
  if (imageFill) {
    const bytes = findAssetBytes(bundle, imageFill.imageRef);
    if (bytes) {
      const image = figma.createImage(bytes);
      rect.fills = [{
        type: "IMAGE",
        scaleMode: imageFill.scaleMode || "FIT",
        imageHash: image.hash,
      }];
    }
  }
  if (!rect.fills || rect.fills.length === 0) {
    const solidFills = (node.fills || []).filter((fill) => fill && fill.type === "SOLID");
    rect.fills = solidFills.length > 0 ? solidFills.map((fill) => ({
      type: "SOLID",
      color: { r: fill.color.r || 0, g: fill.color.g || 0, b: fill.color.b || 0 },
      opacity: typeof fill.opacity === "number" ? fill.opacity : (fill.color && typeof fill.color.a === "number" ? fill.color.a : 1),
    })) : [];
  }
  rect.strokes = (node.strokes || []).filter((stroke) => stroke && stroke.type === "SOLID").map((stroke) => ({
    type: "SOLID",
    color: { r: stroke.color.r || 0, g: stroke.color.g || 0, b: stroke.color.b || 0 },
    opacity: typeof stroke.opacity === "number" ? stroke.opacity : (stroke.color && typeof stroke.color.a === "number" ? stroke.color.a : 1),
  }));
  rect.strokeWeight = node.strokeWeight || 1;
  parentNode.appendChild(rect);
}

function renderReplayVector(node, parentNode, origin) {
  const bounds = getReplayBounds(node);
  if (!bounds) {
    return;
  }
  const local = boundsRelativeToOrigin(bounds, origin);
  const svg = buildVectorSvg(node, local);
  const svgNode = figma.createNodeFromSvg(svg);
  svgNode.name = node.name || "Vector";
  svgNode.x = local.x;
  svgNode.y = local.y;
  parentNode.appendChild(svgNode);
}

async function renderReplayNode(node, parentNode, origin, bundle) {
  if (!node || typeof node !== "object") {
    return;
  }

  switch (node.type) {
    case "TEXT":
      await renderReplayText(node, parentNode, origin);
      return;
    case "VECTOR":
      renderReplayVector(node, parentNode, origin);
      return;
    case "RECTANGLE":
      renderReplayRectangle(node, parentNode, origin, bundle);
      return;
    case "FRAME":
      if (hasVisibleSolidPaint(node) || hasVisibleStroke(node)) {
        createReplayFrameShell(node, parentNode, origin);
      }
      for (const child of node.children || []) {
        await renderReplayNode(child, parentNode, origin, bundle);
      }
      return;
    case "GROUP":
      for (const child of node.children || []) {
        await renderReplayNode(child, parentNode, origin, bundle);
      }
      return;
    default:
      for (const child of node.children || []) {
        await renderReplayNode(child, parentNode, origin, bundle);
      }
  }
}

async function renderFigmaReplayBundle(bundle) {
  await ensureFontLoaded();
  clearPreviousVisualTests();

  const rootBounds = computeReplayRootBounds(bundle.document);
  const rootFrame = figma.createFrame();
  rootFrame.name = `CNS Atlas Replay (${bundle.page_name || bundle.node_id || "page"})`;
  rootFrame.x = 0;
  rootFrame.y = 0;
  rootFrame.resize(rootBounds.width, rootBounds.height);
  rootFrame.fills = [];
  rootFrame.strokes = [{ type: "SOLID", color: { r: 0.82, g: 0.82, b: 0.82 } }];
  rootFrame.strokeWeight = 1;

  const documentNode = bundle.document;
  if (documentNode && documentNode.type === "FRAME") {
    for (const child of documentNode.children || []) {
      await renderReplayNode(child, rootFrame, rootBounds, bundle);
    }
  } else {
    await renderReplayNode(documentNode, rootFrame, rootBounds, bundle);
  }

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
    rotation: bounds.rotation || 0,
    flipH: Boolean(bounds.flipH),
    flipV: Boolean(bounds.flipV),
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
  const textStyle = getTextStyle(candidate);
  const bounds = relativeBounds(candidate, origin);
  if (bounds) {
    const frame = createTransparentFrame(bounds, candidate.title || candidate.subtype);
    applyRenderingMetadata(frame, candidate);
    parentNode.appendChild(frame);
    await appendTextIntoContainer(
      frame,
      candidate,
      candidate.text || candidate.title || "",
      Object.assign({}, textStyle, { wrap: bounds ? textStyle.wrap : "none" }),
      bounds,
      "l",
      "t"
    );
    return frame;
  }

  const fallbackBounds = {
    x: 20,
    y: 20 + fallbackIndex * 20,
    width: 720,
    height: 28,
  };
  const frame = createTransparentFrame(fallbackBounds, candidate.title || candidate.subtype);
  applyRenderingMetadata(frame, candidate);
  parentNode.appendChild(frame);
  await appendTextIntoContainer(
    frame,
    candidate,
    candidate.text || candidate.title || "",
    Object.assign({}, textStyle, { wrap: "none" }),
    fallbackBounds,
    "l",
    "t"
  );
  return frame;
}

async function createLabeledShape(candidate, parentNode, origin, fallbackIndex) {
  const bounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 24,
    width: 120,
    height: 32,
  };
  const shapeStyle = getShapeStyle(candidate);
  const textStyle = getTextStyle(candidate);
  const shapeKind = candidate.extra && candidate.extra.shape_kind ? candidate.extra.shape_kind : "";
  const frame = createTransparentFrame(bounds, candidate.title || candidate.subtype);
  applyRenderingMetadata(frame, candidate);
  parentNode.appendChild(frame);

  let visualShape;
  if (shapeKind === "ellipse") {
    visualShape = figma.createEllipse();
  } else if (shapeKind === "flowChartDecision") {
    visualShape = figma.createPolygon();
    visualShape.pointCount = 4;
    const shapeWidth = Math.max(bounds.width * 0.88, 24);
    const shapeHeight = Math.max(bounds.height * 0.88, 24);
    visualShape.resize(shapeWidth, shapeHeight);
    visualShape.x = (bounds.width - shapeWidth) / 2;
    visualShape.y = (bounds.height - shapeHeight) / 2;
  } else {
    visualShape = figma.createRectangle();
    visualShape.resize(bounds.width, bounds.height);
    visualShape.x = 0;
    visualShape.y = 0;
    if (shapeKind === "roundRect") {
      visualShape.cornerRadius = 8;
    } else if (shapeKind === "rightBracket") {
      visualShape.fills = [];
      visualShape.strokes = [makeSolidPaint(shapeStyle.line, { r: 0.2, g: 0.2, b: 0.2 }, 1)];
      visualShape.strokeWeight = 2;
    }
  }
  if (shapeKind === "ellipse") {
    visualShape.resize(bounds.width, bounds.height);
    visualShape.x = 0;
    visualShape.y = 0;
  }
  if (shapeKind !== "rightBracket") {
    visualShape.fills = [makeSolidPaint(shapeStyle.fill, { r: 1, g: 1, b: 1 }, shapeStyle.fill && shapeStyle.fill.kind === "none" ? 0 : 1)];
    if (shapeStyle.fill && shapeStyle.fill.kind === "none") {
      visualShape.fills = [];
    }
    visualShape.strokes = [makeSolidPaint(shapeStyle.line, { r: 0.28, g: 0.28, b: 0.28 }, 1)];
    visualShape.strokeWeight = shapeStyle.line && shapeStyle.line.width_px ? Math.max(shapeStyle.line.width_px, 1) : 1;
  }
  frame.appendChild(visualShape);

  await appendTextIntoContainer(frame, candidate, candidate.text || candidate.title || "", textStyle, bounds, "ctr", "ctr");
  finalizeVectorHeavyVisual(frame, candidate);
  return frame;
}

function createShape(candidate, parentNode, origin, fallbackIndex) {
  const bounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 20,
    width: 120,
    height: 24,
  };
  const shapeStyle = getShapeStyle(candidate);
  const shapeKind = candidate.extra && candidate.extra.shape_kind ? candidate.extra.shape_kind : "";
  let node;
  if (shapeKind === "ellipse") {
    node = figma.createEllipse();
  } else if (shapeKind === "flowChartDecision") {
    node = figma.createPolygon();
    node.pointCount = 4;
  } else {
    node = figma.createRectangle();
  }
  node.name = candidate.title || candidate.subtype;
  node.x = bounds.x;
  node.y = bounds.y;
  node.resize(bounds.width, bounds.height);
  if (shapeKind === "roundRect") {
    node.cornerRadius = 8;
  }
  if (shapeKind === "rightBracket") {
    node.fills = [];
    node.strokes = [makeSolidPaint(shapeStyle.line, { r: 0.2, g: 0.2, b: 0.2 }, 1)];
    node.strokeWeight = 2;
  } else {
    node.fills = [makeSolidPaint(shapeStyle.fill, { r: 0.94, g: 0.95, b: 0.97 }, shapeStyle.fill && shapeStyle.fill.kind === "none" ? 0 : 1)];
    if (shapeStyle.fill && shapeStyle.fill.kind === "none") {
      node.fills = [];
    }
    node.strokes = [makeSolidPaint(shapeStyle.line, { r: 0.75, g: 0.78, b: 0.82 }, 1)];
    node.strokeWeight = shapeStyle.line && shapeStyle.line.width_px ? Math.max(shapeStyle.line.width_px, 1) : 1;
  }
  if (bounds.rotation && shapeKind !== "flowChartDecision") {
    node.rotation = bounds.rotation;
  }
  parentNode.appendChild(node);
  applyRenderingMetadata(node, candidate);
  if (shouldFlattenVisual(candidate)) {
    const wrapper = createTransparentFrame(bounds, candidate.title || candidate.subtype);
    applyRenderingMetadata(wrapper, candidate);
    node.x = 0;
    node.y = 0;
    wrapper.appendChild(node);
    parentNode.appendChild(wrapper);
    finalizeVectorHeavyVisual(wrapper, candidate);
    return wrapper;
  }
  return node;
}

function createConnector(candidate, parentNode, origin, fallbackIndex) {
  const fallbackBounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 20,
    width: 80,
    height: 2,
  };
  const shapeStyle = getShapeStyle(candidate);
  const linePaint = makeSolidPaint(shapeStyle.line, { r: 0.35, g: 0.35, b: 0.35 }, 1);
  const strokeWeight = shapeStyle.line && shapeStyle.line.width_px ? Math.max(shapeStyle.line.width_px, 1) : 1;
  const kind = candidate.extra && candidate.extra.shape_kind ? candidate.extra.shape_kind : "connector";
  const localWidth = Math.max(fallbackBounds.width, 6);
  const localHeight = Math.max(fallbackBounds.height, 6);
  const flipH = Boolean(fallbackBounds.flipH);
  const flipV = Boolean(fallbackBounds.flipV);
  const startPointPx = candidate.extra && candidate.extra.start_point_px ? candidate.extra.start_point_px : null;
  const endPointPx = candidate.extra && candidate.extra.end_point_px ? candidate.extra.end_point_px : null;
  const connectorAdjusts = candidate.extra && candidate.extra.connector_adjusts ? candidate.extra.connector_adjusts : {};
  const startIdx = candidate.extra && candidate.extra.start_connection ? candidate.extra.start_connection.idx : null;
  const endIdx = candidate.extra && candidate.extra.end_connection ? candidate.extra.end_connection.idx : null;

  function mapPoint(x, y) {
    return {
      x: flipH ? localWidth - x : x,
      y: flipV ? localHeight - y : y,
    };
  }

  function localPointFromIdx(idx) {
    const centerX = localWidth / 2;
    const centerY = localHeight / 2;
    const mapping = {
      0: { x: centerX, y: 0 },
      1: { x: 0, y: centerY },
      2: { x: centerX, y: localHeight },
      3: { x: localWidth, y: centerY },
      4: { x: 0, y: 0 },
      5: { x: localWidth, y: 0 },
      6: { x: 0, y: localHeight },
      7: { x: localWidth, y: localHeight },
    };
    const point = mapping[idx];
    if (!point) {
      return null;
    }
    return mapPoint(point.x, point.y);
  }

  function pointFromAbsolute(point) {
    return {
      x: point.x - fallbackBounds.x,
      y: point.y - fallbackBounds.y,
    };
  }

  function sideFromIdx(idx) {
    if (idx === 0) return "top";
    if (idx === 1) return "left";
    if (idx === 2) return "bottom";
    if (idx === 3) return "right";
    if (idx === 4) return "top-left";
    if (idx === 5) return "top-right";
    if (idx === 6) return "bottom-left";
    if (idx === 7) return "bottom-right";
    return "unknown";
  }

  function inferSideFromDelta(dx, dy, role) {
    if (Math.abs(dx) >= Math.abs(dy)) {
      if (role === "start") {
        return dx >= 0 ? "right" : "left";
      }
      return dx >= 0 ? "left" : "right";
    }
    if (role === "start") {
      return dy >= 0 ? "bottom" : "top";
    }
    return dy >= 0 ? "top" : "bottom";
  }

  function chooseConnectorSide(rawSide, inferredSide) {
    if (rawSide === "unknown") {
      return inferredSide;
    }
    if (rawSide.includes("-")) {
      return inferredSide;
    }
    return rawSide;
  }

  function offsetFromSide(point, side, margin) {
    if (side === "left" || side === "top-left" || side === "bottom-left") {
      return { x: point.x - margin, y: point.y };
    }
    if (side === "right" || side === "top-right" || side === "bottom-right") {
      return { x: point.x + margin, y: point.y };
    }
    if (side === "top") {
      return { x: point.x, y: point.y - margin };
    }
    if (side === "bottom") {
      return { x: point.x, y: point.y + margin };
    }
    return { x: point.x, y: point.y };
  }

  function pathUsingReadableElbow(start, end, startSide, endSide, kindName, adjusts) {
    const leadMargin = 16;
    const startLead = offsetFromSide(start, startSide, leadMargin);
    const endLead = offsetFromSide(end, endSide, leadMargin);
    const startOrientation = (startSide === "left" || startSide === "right") ? "horizontal" : "vertical";
    const endOrientation = (endSide === "left" || endSide === "right") ? "horizontal" : "vertical";
    const adj1 = typeof adjusts.adj1 === "number" ? adjusts.adj1 / 100000 : 0.5;
    const adj2 = typeof adjusts.adj2 === "number" ? adjusts.adj2 / 100000 : 0.5;

    if (kindName === "straightConnector1") {
      if (Math.abs(start.y - end.y) <= 3 || Math.abs(start.x - end.x) <= 3) {
        return [start, end];
      }
      if (Math.abs(end.x - start.x) >= Math.abs(end.y - start.y)) {
        return [start, { x: end.x, y: start.y }, end];
      }
      return [start, { x: start.x, y: end.y }, end];
    }

    if (startOrientation === "horizontal" && endOrientation === "horizontal") {
      const routeRight = Math.max(startLead.x, endLead.x) + 18;
      const routeLeft = Math.min(startLead.x, endLead.x) - 18;
      const preferRight = startSide === "right" || endSide === "left";
      const routeX = preferRight ? routeRight : routeLeft;
      return [start, startLead, { x: routeX, y: startLead.y }, { x: routeX, y: endLead.y }, endLead, end];
    }

    if (startOrientation === "vertical" && endOrientation === "vertical") {
      const routeBottom = Math.max(startLead.y, endLead.y) + 18;
      const routeTop = Math.min(startLead.y, endLead.y) - 18;
      const preferBottom = startSide === "bottom" || endSide === "top";
      const routeY = preferBottom ? routeBottom : routeTop;
      return [start, startLead, { x: startLead.x, y: routeY }, { x: endLead.x, y: routeY }, endLead, end];
    }

    if (kindName === "bentConnector4") {
      const midX = startLead.x + (endLead.x - startLead.x) * adj1;
      const midY = startLead.y + (endLead.y - startLead.y) * adj2;
      if (startOrientation === "horizontal") {
        return [start, startLead, { x: midX, y: startLead.y }, { x: midX, y: midY }, { x: endLead.x, y: midY }, endLead, end];
      }
      return [start, startLead, { x: startLead.x, y: midY }, { x: midX, y: midY }, { x: midX, y: endLead.y }, endLead, end];
    }

    if (startOrientation === "horizontal" && endOrientation === "vertical") {
      return [start, startLead, { x: endLead.x, y: startLead.y }, endLead, end];
    }
    if (startOrientation === "vertical" && endOrientation === "horizontal") {
      return [start, startLead, { x: startLead.x, y: endLead.y }, endLead, end];
    }

    if (startOrientation === "horizontal") {
      const midX = startLead.x + (endLead.x - startLead.x) * adj1;
      return [start, startLead, { x: midX, y: startLead.y }, { x: midX, y: endLead.y }, endLead, end];
    }
    const midY = startLead.y + (endLead.y - startLead.y) * adj1;
    return [start, startLead, { x: startLead.x, y: midY }, { x: endLead.x, y: midY }, endLead, end];
  }

  function appendSegment(frame, start, end) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const isHorizontal = Math.abs(dy) <= 0.5;
    const isVertical = Math.abs(dx) <= 0.5;
    let segment;
    if (isHorizontal || isVertical) {
      segment = figma.createRectangle();
      segment.fills = [linePaint];
      segment.strokes = [];
      if (isHorizontal) {
        segment.x = Math.min(start.x, end.x);
        segment.y = start.y - strokeWeight / 2;
        segment.resize(Math.max(Math.abs(dx), 1), strokeWeight);
      } else {
        segment.x = start.x - strokeWeight / 2;
        segment.y = Math.min(start.y, end.y);
        segment.resize(strokeWeight, Math.max(Math.abs(dy), 1));
      }
    } else {
      segment = figma.createLine();
      segment.x = start.x;
      segment.y = start.y;
      segment.strokes = [linePaint];
      segment.strokeWeight = strokeWeight;
      segment.resize(Math.max(Math.abs(dx), 1), Math.max(Math.abs(dy), 1));
      segment.rotation = Math.atan2(dy, dx) * (180 / Math.PI);
    }
    frame.appendChild(segment);
  }

  let points;
  const localStart = localPointFromIdx(startIdx);
  const localEnd = localPointFromIdx(endIdx);
  if (localStart && localEnd) {
    const start = localStart;
    const end = localEnd;
    const deltaX = end.x - start.x;
    const deltaY = end.y - start.y;
    const startSide = chooseConnectorSide(sideFromIdx(startIdx), inferSideFromDelta(deltaX, deltaY, "start"));
    const endSide = chooseConnectorSide(sideFromIdx(endIdx), inferSideFromDelta(deltaX, deltaY, "end"));
    points = pathUsingReadableElbow(start, end, startSide, endSide, kind, connectorAdjusts);
  } else if (startPointPx && endPointPx) {
    const start = pointFromAbsolute(startPointPx);
    const end = pointFromAbsolute(endPointPx);
    const deltaX = end.x - start.x;
    const deltaY = end.y - start.y;
    const startSide = chooseConnectorSide(sideFromIdx(startIdx), inferSideFromDelta(deltaX, deltaY, "start"));
    const endSide = chooseConnectorSide(sideFromIdx(endIdx), inferSideFromDelta(deltaX, deltaY, "end"));
    points = pathUsingReadableElbow(start, end, startSide, endSide, kind, connectorAdjusts);
  } else if (kind === "straightConnector1") {
    points = [mapPoint(0, localHeight / 2), mapPoint(localWidth, localHeight / 2)];
  } else if (kind === "bentConnector2") {
    points = [mapPoint(0, 0), mapPoint(0, localHeight), mapPoint(localWidth, localHeight)];
  } else if (kind === "bentConnector4") {
    points = [
      mapPoint(0, 0),
      mapPoint(0, localHeight * 0.35),
      mapPoint(localWidth * 0.5, localHeight * 0.35),
      mapPoint(localWidth * 0.5, localHeight),
      mapPoint(localWidth, localHeight),
    ];
  } else {
    points = [
      mapPoint(0, 0),
      mapPoint(0, localHeight * 0.5),
      mapPoint(localWidth, localHeight * 0.5),
      mapPoint(localWidth, localHeight),
    ];
  }

  const filteredPoints = [];
  for (const point of points) {
    const previous = filteredPoints[filteredPoints.length - 1];
    if (!previous || Math.abs(previous.x - point.x) > 0.1 || Math.abs(previous.y - point.y) > 0.1) {
      filteredPoints.push({ x: point.x, y: point.y });
    }
  }
  const originalTipPoint = filteredPoints[filteredPoints.length - 1];
  const adjustedPoints = filteredPoints.map((point) => ({ x: point.x, y: point.y }));
  if (adjustedPoints.length >= 2) {
    const arrowInset = 8;
    const lastPoint = adjustedPoints[adjustedPoints.length - 1];
    const prevPoint = adjustedPoints[adjustedPoints.length - 2];
    const dx = lastPoint.x - prevPoint.x;
    const dy = lastPoint.y - prevPoint.y;
    if (Math.abs(dx) >= Math.abs(dy) && Math.abs(dx) > arrowInset) {
      lastPoint.x += dx > 0 ? -arrowInset : arrowInset;
    } else if (Math.abs(dy) > arrowInset) {
      lastPoint.y += dy > 0 ? -arrowInset : arrowInset;
    }
  }

  const minX = Math.min(...adjustedPoints.map((point) => point.x));
  const minY = Math.min(...adjustedPoints.map((point) => point.y));
  const maxX = Math.max(...adjustedPoints.map((point) => point.x));
  const maxY = Math.max(...adjustedPoints.map((point) => point.y));
  const frame = createTransparentFrame(
    {
      x: fallbackBounds.x + minX,
      y: fallbackBounds.y + minY,
      width: Math.max(maxX - minX, strokeWeight + 2, 6),
      height: Math.max(maxY - minY, strokeWeight + 2, 6),
      rotation: 0,
      flipH: false,
      flipV: false,
    },
    candidate.title || "connector"
  );
  applyRenderingMetadata(frame, candidate);
  parentNode.appendChild(frame);

  const localizedPoints = adjustedPoints.map((point) => ({
    x: point.x - minX,
    y: point.y - minY,
  }));

  for (let index = 0; index < localizedPoints.length - 1; index += 1) {
    appendSegment(frame, localizedPoints[index], localizedPoints[index + 1]);
  }

  const endPoint = localizedPoints[localizedPoints.length - 1];
  const prevPoint = localizedPoints[localizedPoints.length - 2] || localizedPoints[0];
  addArrowHeadIfNeeded(
    candidate,
    frame,
    { x: endPoint.x, y: endPoint.y, width: 1, height: 1, rotation: 0 },
    linePaint.color,
    { dx: endPoint.x - prevPoint.x, dy: endPoint.y - prevPoint.y },
    originalTipPoint
      ? {
        x: originalTipPoint.x - minX,
        y: originalTipPoint.y - minY,
      }
      : null
  );
  finalizeVectorHeavyVisual(frame, candidate);
  return frame;
}

function createGroupFrame(candidate, parentNode, origin, fallbackIndex) {
  const bounds = relativeBounds(candidate, origin) || {
    x: 20,
    y: 20 + fallbackIndex * 24,
    width: 160,
    height: 60,
  };
  const frame = createTransparentFrame(bounds, candidate.title || candidate.subtype);
  applyRenderingMetadata(frame, candidate);
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
  const shapeStyle = getShapeStyle(candidate);
  frame.name = candidate.title || "table";
  frame.x = bounds.x;
  frame.y = bounds.y;
  frame.resize(bounds.width, bounds.height);
  frame.fills = [makeSolidPaint(shapeStyle.fill, { r: 1, g: 1, b: 1 }, 1)];
  frame.strokes = [makeSolidPaint(shapeStyle.line, { r: 0.45, g: 0.45, b: 0.45 }, 1)];
  frame.strokeWeight = shapeStyle.line && shapeStyle.line.width_px ? Math.max(shapeStyle.line.width_px, 1) : 1;
  frame.clipsContent = false;
  const rowCount = candidate.extra && candidate.extra.row_count ? candidate.extra.row_count : 1;
  const gridColumns = candidate.extra && candidate.extra.grid_columns ? candidate.extra.grid_columns : [];
  frame.setPluginData("rowCount", String(rowCount));
  frame.setPluginData("gridColumns", JSON.stringify(gridColumns));
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
  const siblings = parentNode.children.filter((child) => child.type === "FRAME");
  const rowY = siblings.reduce((sum, child) => sum + child.height, 0);
  const rowCount = Number(parentNode.getPluginData("rowCount") || "1");
  const rowHeight = Math.max(extra.row_height_px || (parentNode.height / Math.max(rowCount, 1)), 24);
  row.x = 0;
  row.y = rowY;
  row.resize(parentNode.width, rowHeight);
  parentNode.appendChild(row);
  row.setPluginData("cellCount", String(cellCount));
  return row;
}

async function createTableCell(candidate, parentNode) {
  const extra = candidate.extra || {};
  if (extra.h_merge || extra.v_merge) {
    const placeholder = figma.createFrame();
    placeholder.name = `${candidate.title || candidate.subtype} merged-skip`;
    placeholder.resize(0.01, 0.01);
    placeholder.fills = [];
    placeholder.strokes = [];
    parentNode.appendChild(placeholder);
    return placeholder;
  }

  const cell = figma.createFrame();
  const textStyle = getTextStyle(candidate);
  cell.name = candidate.title || candidate.subtype;
  const cellCount = Number(parentNode.getPluginData("cellCount") || "1");
  const tableFrame = parentNode.parent;
  const gridColumns = tableFrame && tableFrame.type === "FRAME"
    ? JSON.parse(tableFrame.getPluginData("gridColumns") || "[]")
    : [];
  const startColumnIndex = Number(extra.start_column_index || 1);
  const width = extra.width_px || (parentNode.width / Math.max(cellCount, 1));
  const cellX = gridColumns.length
    ? gridColumns
      .filter((column) => column.column_index < startColumnIndex)
      .reduce((sum, column) => sum + (column.width_px || 0), 0)
    : parentNode.children.filter((child) => child.type === "FRAME").reduce((sum, child) => sum + child.width, 0);
  cell.x = cellX;
  cell.y = 0;
  cell.resize(width, parentNode.height);
  const cellStyle = extra.cell_style || {};
  const fill = cellStyle.fill ? makeSolidPaint(cellStyle.fill, { r: 1, g: 1, b: 1 }, 1) : { type: "SOLID", color: { r: 1, g: 1, b: 1 } };
  cell.fills = [fill];
  cell.strokes = [{ type: "SOLID", color: { r: 0.75, g: 0.75, b: 0.75 } }];
  cell.strokeWeight = 1;
  parentNode.appendChild(cell);

  const text = figma.createText();
  text.name = `${cell.name} text`;
  text.fontName = await resolveFontName(textStyle);
  text.characters = candidate.text || "";
  text.fontSize = clampFontSize(textStyle.font_size_max || textStyle.font_size_avg || 10);
  text.fills = [makeSolidPaint(textStyle.fill, { r: 0.15, g: 0.15, b: 0.15 }, 1)];
  text.textAlignHorizontal = mapHorizontalAlign(textStyle.horizontal_align, "l");
  text.textAlignVertical = mapVerticalAlign(cellStyle.anchor, "ctr");
  const leftInset = typeof cellStyle.marL === "number" ? cellStyle.marL : 6;
  const rightInset = typeof cellStyle.marR === "number" ? cellStyle.marR : 6;
  const availableWidth = Math.max(width - leftInset - rightInset, 12);
  const wrapMode = deriveWrapMode(text.characters, Object.assign({}, textStyle, cellStyle), { width, height: parentNode.height }, { forceWrap: true });
  text.textAutoResize = wrapMode === "none" ? "WIDTH_AND_HEIGHT" : "HEIGHT";
  text.resize(availableWidth, Math.max(parentNode.height, 16));
  cell.appendChild(text);
  alignTextNode(text, { width, height: parentNode.height }, Object.assign({}, textStyle, cellStyle), "l", cellStyle.anchor || "ctr");
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
  const extra = candidate.extra || {};
  frame.name = candidate.title || candidate.subtype;
  frame.x = bounds.x;
  frame.y = bounds.y;
  frame.resize(bounds.width, bounds.height);
  if (extra.image_base64 && extra.mime_type) {
    try {
      const image = figma.createImage(base64ToBytes(extra.image_base64));
      frame.fills = [{
        type: "IMAGE",
        scaleMode: "FILL",
        imageHash: image.hash,
      }];
    } catch (error) {
      frame.fills = [{ type: "SOLID", color: { r: 0.93, g: 0.94, b: 0.96 } }];
    }
  } else {
    frame.fills = [{ type: "SOLID", color: { r: 0.93, g: 0.94, b: 0.96 } }];
  }
  frame.strokes = [{ type: "SOLID", color: { r: 0.64, g: 0.68, b: 0.74 } }];
  frame.strokeWeight = 1;
  parentNode.appendChild(frame);

  if (!extra.image_base64 || !extra.mime_type) {
    const text = figma.createText();
    text.name = `${frame.name} placeholder`;
    text.fontName = await resolveFontName({});
    text.characters = extra.resolved_target && extra.resolved_target.endsWith(".emf") ? "EMF IMAGE" : "IMAGE";
    text.fontSize = clampFontSize(bounds.height * 0.22);
    text.fills = [{ type: "SOLID", color: { r: 0.32, g: 0.36, b: 0.42 } }];
    frame.appendChild(text);
    text.x = Math.max((bounds.width - text.width) / 2, 6);
    text.y = Math.max((bounds.height - text.height) / 2, 4);
  }
  return frame;
}

function clampFontSize(value) {
  return Math.max(10, Math.min(Math.round(value), 28));
}
