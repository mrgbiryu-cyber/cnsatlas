(function (global) {
  "use strict";

  var P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main";
  var R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
  var A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main";
  var EMU_PER_PIXEL = 9525;

  function localName(node) {
    if (!node || !node.nodeName) return "";
    var value = node.localName || node.nodeName;
    var idx = value.indexOf(":");
    return idx >= 0 ? value.slice(idx + 1) : value;
  }

  function childElements(node, name) {
    var result = [];
    if (!node || !node.childNodes) return result;
    for (var i = 0; i < node.childNodes.length; i += 1) {
      var child = node.childNodes[i];
      if (child.nodeType === 1 && localName(child) === name) {
        result.push(child);
      }
    }
    return result;
  }

  function firstChild(node, name) {
    var items = childElements(node, name);
    return items.length > 0 ? items[0] : null;
  }

  function findPath(node, parts) {
    var current = node;
    for (var i = 0; i < parts.length; i += 1) {
      current = firstChild(current, parts[i]);
      if (!current) return null;
    }
    return current;
  }

  function descendants(node, name) {
    var result = [];
    if (!node || !node.getElementsByTagName) return result;
    var all = node.getElementsByTagName("*");
    for (var i = 0; i < all.length; i += 1) {
      if (localName(all[i]) === name) {
        result.push(all[i]);
      }
    }
    return result;
  }

  function firstDescendant(node, name) {
    var items = descendants(node, name);
    return items.length > 0 ? items[0] : null;
  }

  function attr(node, name) {
    if (!node || !node.attributes) return null;
    if (node.hasAttribute && node.hasAttribute(name)) {
      return node.getAttribute(name);
    }
    for (var i = 0; i < node.attributes.length; i += 1) {
      var attribute = node.attributes[i];
      var attrName = attribute.localName || attribute.name;
      if (attrName === name) {
        return attribute.value;
      }
    }
    return null;
  }

  function parseXml(text) {
    return new DOMParser().parseFromString(text, "application/xml");
  }

  function textContentOf(node) {
    return node && typeof node.textContent === "string" ? node.textContent : "";
  }

  function normalizeText(value, fallback) {
    var normalized = String(value || "").replace(/\s+/g, " ").trim();
    return normalized || fallback;
  }

  function emuToPx(value) {
    if (value === null || value === undefined || value === "") return null;
    return Math.round((Number(value) / EMU_PER_PIXEL) * 100) / 100;
  }

  function bytesToBase64(uint8Array) {
    var binary = "";
    var chunk = 0x8000;
    for (var i = 0; i < uint8Array.length; i += chunk) {
      var slice = uint8Array.subarray(i, Math.min(i + chunk, uint8Array.length));
      binary += String.fromCharCode.apply(null, slice);
    }
    return btoa(binary);
  }

  function inferMimeType(path) {
    var lower = String(path || "").toLowerCase();
    if (lower.endsWith(".png")) return "image/png";
    if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
    if (lower.endsWith(".gif")) return "image/gif";
    return null;
  }

  function readZipFile(zip, path) {
    return zip.file(path);
  }

  async function readZipText(zip, path, message) {
    var file = readZipFile(zip, path);
    if (!file) {
      throw new Error(message || ("PPTX 내부 파일을 찾을 수 없습니다: " + path));
    }
    return file.async("string");
  }

  function resolvePartPath(basePath, target) {
    var baseParts = String(basePath || "").split("/");
    baseParts.pop();
    var targetParts = String(target || "").split("/");
    var stack = baseParts;
    for (var i = 0; i < targetParts.length; i += 1) {
      var part = targetParts[i];
      if (!part || part === ".") continue;
      if (part === "..") {
        if (stack.length > 0) stack.pop();
        continue;
      }
      stack.push(part);
    }
    return stack.join("/");
  }

  function extractColorPayload(node, themeColors) {
    if (!node) return null;
    var srgb = firstChild(node, "srgbClr");
    if (srgb) {
      return {
        type: "srgb",
        value: attr(srgb, "val"),
        alpha: extractAlpha(srgb),
      };
    }
    var scheme = firstChild(node, "schemeClr");
    if (scheme) {
      var schemeValue = attr(scheme, "val");
      return {
        type: "scheme",
        value: schemeValue,
        resolved_value: schemeValue && themeColors ? themeColors[schemeValue] : null,
        alpha: extractAlpha(scheme),
      };
    }
    var sysClr = firstChild(node, "sysClr");
    if (sysClr) {
      return {
        type: "system",
        value: attr(sysClr, "val"),
        resolved_value: attr(sysClr, "lastClr"),
        alpha: extractAlpha(sysClr),
      };
    }
    return null;
  }

  function extractAlpha(node) {
    var alpha = firstChild(node, "alpha");
    if (!alpha) return null;
    var value = attr(alpha, "val");
    if (value === null) return null;
    return Math.round((Number(value) / 100000) * 10000) / 10000;
  }

  function extractTextAlignment(shapeNode) {
    var txBody = firstDescendant(shapeNode, "txBody");
    if (!txBody) return {};
    var bodyPr = firstChild(txBody, "bodyPr");
    var paragraph = firstChild(txBody, "p");
    var pPr = paragraph ? firstChild(paragraph, "pPr") : null;
    var result = {};
    if (pPr && attr(pPr, "algn")) result.horizontal_align = attr(pPr, "algn");
    if (bodyPr && attr(bodyPr, "anchor")) result.vertical_align = attr(bodyPr, "anchor");
    if (bodyPr) {
      ["lIns", "rIns", "tIns", "bIns"].forEach(function (key) {
        if (attr(bodyPr, key)) result[key] = emuToPx(attr(bodyPr, key));
      });
      if (attr(bodyPr, "wrap")) result.wrap = attr(bodyPr, "wrap");
    }
    return result;
  }

  function extractTextRuns(shapeNode, themeColors) {
    var runs = [];
    var paragraphs = descendants(shapeNode, "p");
    for (var i = 0; i < paragraphs.length; i += 1) {
      var paragraph = paragraphs[i];
      for (var j = 0; j < paragraph.childNodes.length; j += 1) {
        var child = paragraph.childNodes[j];
        if (child.nodeType !== 1) continue;
        var tag = localName(child);
        if (tag === "br") {
          runs.push({ type: "line_break", text: "\n" });
          continue;
        }
        if (tag !== "r" && tag !== "fld") continue;
        var t = firstChild(child, "t");
        if (!t || !textContentOf(t)) continue;
        var rPr = firstChild(child, "rPr");
        runs.push({
          type: "text",
          text: textContentOf(t),
          font_size: rPr && attr(rPr, "sz") ? Number(attr(rPr, "sz")) / 100 : null,
          bold: !!(rPr && attr(rPr, "b") === "1"),
          italic: !!(rPr && attr(rPr, "i") === "1"),
          font_family: extractFontFamily(rPr),
          fill: rPr ? extractColorPayload(firstChild(rPr, "solidFill"), themeColors) : null,
        });
      }
      if (i < paragraphs.length - 1) {
        runs.push({ type: "paragraph_break", text: "\n" });
      }
    }
    return runs;
  }

  function extractFontFamily(rPr) {
    if (!rPr) return null;
    var latin = firstChild(rPr, "latin");
    if (latin && attr(latin, "typeface")) return attr(latin, "typeface");
    var ea = firstChild(rPr, "ea");
    if (ea && attr(ea, "typeface")) return attr(ea, "typeface");
    return null;
  }

  function buildTextFromRuns(textRuns) {
    var parts = [];
    for (var i = 0; i < textRuns.length; i += 1) {
      var run = textRuns[i];
      if (run.type === "text" || run.type === "line_break" || run.type === "paragraph_break") {
        parts.push(run.text || "");
      }
    }
    return parts.join("").trim();
  }

  function summarizeTextStyle(textRuns, alignment) {
    var sizes = [];
    var fill = null;
    var family = null;
    for (var i = 0; i < textRuns.length; i += 1) {
      var run = textRuns[i];
      if (run.type !== "text") continue;
      if (run.font_size) sizes.push(run.font_size);
      if (!fill && run.fill) fill = run.fill;
      if (!family && run.font_family) family = run.font_family;
    }
    var result = {
      font_size_max: sizes.length ? Math.max.apply(null, sizes) : null,
      font_size_min: sizes.length ? Math.min.apply(null, sizes) : null,
      font_size_avg: sizes.length ? Math.round((sizes.reduce(function (a, b) { return a + b; }, 0) / sizes.length) * 100) / 100 : null,
      font_family: family,
      fill: fill,
    };
    for (var key in alignment) result[key] = alignment[key];
    return result;
  }

  function extractShapeKind(node) {
    var spPr = firstChild(node, "spPr");
    var geom = spPr ? firstChild(spPr, "prstGeom") : null;
    if (localName(node) === "cxnSp") {
      return geom && attr(geom, "prst") ? attr(geom, "prst") : "connector";
    }
    return geom && attr(geom, "prst") ? attr(geom, "prst") : null;
  }

  function extractConnectorAdjusts(node) {
    var spPr = firstChild(node, "spPr");
    var geom = spPr ? firstChild(spPr, "prstGeom") : null;
    var avLst = geom ? firstChild(geom, "avLst") : null;
    var result = {};
    if (!avLst) return result;
    var gds = childElements(avLst, "gd");
    for (var i = 0; i < gds.length; i += 1) {
      var gd = gds[i];
      var name = attr(gd, "name");
      var fmla = attr(gd, "fmla") || "";
      if (!name || fmla.indexOf("val ") !== 0) continue;
      result[name] = Number(fmla.split(" ")[1]);
    }
    return result;
  }

  function extractConnectorLinks(node) {
    var result = {};
    var nv = firstChild(node, "nvCxnSpPr");
    var cNv = nv ? firstChild(nv, "cNvCxnSpPr") : null;
    if (!cNv) return result;
    var start = firstChild(cNv, "stCxn");
    var end = firstChild(cNv, "endCxn");
    if (start) {
      result.start_connection = {
        id: attr(start, "id"),
        idx: attr(start, "idx") ? Number(attr(start, "idx")) : null,
      };
    }
    if (end) {
      result.end_connection = {
        id: attr(end, "id"),
        idx: attr(end, "idx") ? Number(attr(end, "idx")) : null,
      };
    }
    return result;
  }

  function extractShapeStyle(node, themeColors) {
    var spPr = firstChild(node, "spPr");
    if (!spPr) return {};
    var fillPayload = null;
    var solidFill = firstChild(spPr, "solidFill");
    if (solidFill) {
      fillPayload = extractColorPayload(solidFill, themeColors);
      if (fillPayload) fillPayload.kind = "solid";
    } else if (firstChild(spPr, "noFill")) {
      fillPayload = { kind: "none" };
    }
    var linePayload = null;
    var line = firstChild(spPr, "ln");
    if (line) {
      linePayload = extractColorPayload(firstChild(line, "solidFill"), themeColors) || { kind: "default" };
      linePayload.width_emu = attr(line, "w") ? Number(attr(line, "w")) : null;
      linePayload.width_px = linePayload.width_emu ? emuToPx(linePayload.width_emu) : null;
      var headEnd = firstChild(line, "headEnd");
      var tailEnd = firstChild(line, "tailEnd");
      if (headEnd) linePayload.head_end = collectAttributes(headEnd);
      if (tailEnd) linePayload.tail_end = collectAttributes(tailEnd);
    }
    return {
      fill: fillPayload,
      line: linePayload,
    };
  }

  function collectAttributes(node) {
    var result = {};
    if (!node || !node.attributes) return result;
    for (var i = 0; i < node.attributes.length; i += 1) {
      result[node.attributes[i].name] = node.attributes[i].value;
    }
    return result;
  }

  function extractXfrm(node) {
    if (!node) return null;
    var off = firstChild(node, "off");
    var ext = firstChild(node, "ext");
    if (!off && !ext) return null;
    return {
      x: off && attr(off, "x") ? Number(attr(off, "x")) : 0,
      y: off && attr(off, "y") ? Number(attr(off, "y")) : 0,
      cx: ext && attr(ext, "cx") ? Number(attr(ext, "cx")) : 0,
      cy: ext && attr(ext, "cy") ? Number(attr(ext, "cy")) : 0,
      rot: attr(node, "rot") ? Number(attr(node, "rot")) : 0,
      flipH: attr(node, "flipH") === "1",
      flipV: attr(node, "flipV") === "1",
    };
  }

  function extractGroupContext(node) {
    if (!node) return null;
    var off = firstChild(node, "off");
    var ext = firstChild(node, "ext");
    var chOff = firstChild(node, "chOff");
    var chExt = firstChild(node, "chExt");
    if (!off && !ext) return null;
    return {
      x: off && attr(off, "x") ? Number(attr(off, "x")) : 0,
      y: off && attr(off, "y") ? Number(attr(off, "y")) : 0,
      cx: ext && attr(ext, "cx") ? Number(attr(ext, "cx")) : 0,
      cy: ext && attr(ext, "cy") ? Number(attr(ext, "cy")) : 0,
      chOffX: chOff && attr(chOff, "x") ? Number(attr(chOff, "x")) : 0,
      chOffY: chOff && attr(chOff, "y") ? Number(attr(chOff, "y")) : 0,
      chExtCx: chExt && attr(chExt, "cx") ? Number(attr(chExt, "cx")) : (ext && attr(ext, "cx") ? Number(attr(ext, "cx")) : 0),
      chExtCy: chExt && attr(chExt, "cy") ? Number(attr(chExt, "cy")) : (ext && attr(ext, "cy") ? Number(attr(ext, "cy")) : 0),
      rot: attr(node, "rot") ? Number(attr(node, "rot")) : 0,
      flipH: attr(node, "flipH") === "1",
      flipV: attr(node, "flipV") === "1",
    };
  }

  function applyGroupTransform(bounds, groupContext) {
    if (!bounds || !groupContext) return bounds;
    var scaleX = groupContext.chExtCx ? groupContext.cx / groupContext.chExtCx : 1;
    var scaleY = groupContext.chExtCy ? groupContext.cy / groupContext.chExtCy : 1;
    return {
      x: Math.round(groupContext.x + (bounds.x - groupContext.chOffX) * scaleX),
      y: Math.round(groupContext.y + (bounds.y - groupContext.chOffY) * scaleY),
      cx: Math.round(bounds.cx * scaleX),
      cy: Math.round(bounds.cy * scaleY),
      rot: bounds.rot || 0,
      flipH: !!bounds.flipH,
      flipV: !!bounds.flipV,
    };
  }

  function extractCnvPr(node) {
    var cNvPr = firstDescendant(node, "cNvPr");
    if (!cNvPr) return { id: null, name: null, descr: null };
    return {
      id: attr(cNvPr, "id"),
      name: attr(cNvPr, "name"),
      descr: attr(cNvPr, "descr"),
    };
  }

  function extractTable(frameNode) {
    var table = firstDescendant(frameNode, "tbl");
    if (!table) return null;
    var grid = firstChild(table, "tblGrid");
    var gridColumns = [];
    if (grid) {
      var cols = childElements(grid, "gridCol");
      for (var i = 0; i < cols.length; i += 1) {
        var widthEmu = attr(cols[i], "w") ? Number(attr(cols[i], "w")) : 0;
        gridColumns.push({
          column_index: i + 1,
          width_emu: widthEmu,
          width_px: emuToPx(widthEmu),
        });
      }
    }
    var rows = [];
    var trList = childElements(table, "tr");
    for (var r = 0; r < trList.length; r += 1) {
      var tr = trList[r];
      var cells = [];
      var runningCol = 0;
      var tcList = childElements(tr, "tc");
      for (var c = 0; c < tcList.length; c += 1) {
        var tc = tcList[c];
        var texts = descendants(tc, "t").map(textContentOf).filter(Boolean).map(function (t) { return t.trim(); }).filter(Boolean);
        var tcPr = firstChild(tc, "tcPr");
        var gridSpan = attr(tc, "gridSpan") ? Number(attr(tc, "gridSpan")) : 1;
        var rowSpan = attr(tc, "rowSpan") ? Number(attr(tc, "rowSpan")) : 1;
        var columns = gridColumns.slice(runningCol, runningCol + gridSpan);
        var widthEmu = columns.reduce(function (sum, item) { return sum + (item.width_emu || 0); }, 0);
        cells.push({
          cell_index: c + 1,
          text: texts.join(" ").trim(),
          grid_span: gridSpan,
          row_span: rowSpan,
          h_merge: attr(tc, "hMerge"),
          v_merge: attr(tc, "vMerge"),
          start_column_index: runningCol + 1,
          width_emu: widthEmu,
          width_px: emuToPx(widthEmu),
          style: {
            fill: tcPr ? extractColorPayload(firstChild(tcPr, "solidFill"), null) : null,
            anchor: tcPr ? attr(tcPr, "anchor") : null,
            marL: tcPr && attr(tcPr, "marL") ? emuToPx(attr(tcPr, "marL")) : null,
            marR: tcPr && attr(tcPr, "marR") ? emuToPx(attr(tcPr, "marR")) : null,
            marT: tcPr && attr(tcPr, "marT") ? emuToPx(attr(tcPr, "marT")) : null,
            marB: tcPr && attr(tcPr, "marB") ? emuToPx(attr(tcPr, "marB")) : null,
          },
        });
        runningCol += gridSpan;
      }
      rows.push({
        row_index: r + 1,
        height: attr(tr, "h"),
        height_px: attr(tr, "h") ? emuToPx(attr(tr, "h")) : null,
        cells: cells,
      });
    }
    return {
      row_count: rows.length,
      grid_columns: gridColumns,
      rows: rows,
    };
  }

  function extractPicture(node, relTargets, zip, slidePath) {
    var blip = firstDescendant(node, "blip");
    var embed = blip ? (blip.getAttributeNS && blip.getAttributeNS(R_NS, "embed")) || attr(blip, "embed") : null;
    var imageTarget = embed ? relTargets[embed] : null;
    var resolvedTarget = imageTarget ? resolvePartPath(slidePath, imageTarget) : null;
    var mimeType = inferMimeType(resolvedTarget);
    return readZipFile(zip, resolvedTarget || "") ? readZipFile(zip, resolvedTarget).async("uint8array").then(function (bytes) {
      return {
        image_rel_id: embed,
        image_target: imageTarget,
        resolved_target: resolvedTarget,
        mime_type: mimeType,
        image_base64: mimeType ? bytesToBase64(bytes) : null,
      };
    }) : Promise.resolve({
      image_rel_id: embed,
      image_target: imageTarget,
      resolved_target: resolvedTarget,
      mime_type: mimeType,
      image_base64: null,
    });
  }

  async function extractElement(node, relTargets, zip, slidePath, themeColors, groupContext) {
    var tag = localName(node);
    var meta = extractCnvPr(node);

    if (tag === "grpSp") {
      var rawGroupXfrm = extractGroupContext(findPath(node, ["grpSpPr", "xfrm"]));
      var absoluteGroupBounds = applyGroupTransform(rawGroupXfrm, groupContext);
      var childGroupContext = rawGroupXfrm ? {
        x: absoluteGroupBounds ? absoluteGroupBounds.x : 0,
        y: absoluteGroupBounds ? absoluteGroupBounds.y : 0,
        cx: absoluteGroupBounds ? absoluteGroupBounds.cx : 0,
        cy: absoluteGroupBounds ? absoluteGroupBounds.cy : 0,
        chOffX: rawGroupXfrm.chOffX || 0,
        chOffY: rawGroupXfrm.chOffY || 0,
        chExtCx: rawGroupXfrm.chExtCx || rawGroupXfrm.cx || 0,
        chExtCy: rawGroupXfrm.chExtCy || rawGroupXfrm.cy || 0,
      } : null;
      var children = [];
      for (var i = 0; i < node.childNodes.length; i += 1) {
        var child = node.childNodes[i];
        var childTag = localName(child);
        if (child.nodeType !== 1 || childTag === "nvGrpSpPr" || childTag === "grpSpPr") continue;
        children.push(await extractElement(child, relTargets, zip, slidePath, themeColors, childGroupContext));
      }
      return {
        element_type: "group",
        node_tag: tag,
        node_id: meta.id,
        name: meta.name,
        descr: meta.descr,
        bounds: absoluteGroupBounds,
        children: children,
      };
    }

    var payload = {
      element_type: tag === "sp" ? "shape" : tag === "cxnSp" ? "connector" : tag === "graphicFrame" ? "graphic_frame" : tag === "pic" ? "image" : tag,
      node_tag: tag,
      node_id: meta.id,
      name: meta.name,
      descr: meta.descr,
      children: [],
    };

    if (tag === "sp" || tag === "cxnSp") {
      payload.bounds = applyGroupTransform(extractXfrm(findPath(node, ["spPr", "xfrm"])), groupContext);
      payload.shape_kind = extractShapeKind(node);
      payload.text_runs = extractTextRuns(node, themeColors);
      payload.shape_style = extractShapeStyle(node, themeColors);
      payload.text_alignment = extractTextAlignment(node);
      payload.text_style = summarizeTextStyle(payload.text_runs, payload.text_alignment);
      payload.text = buildTextFromRuns(payload.text_runs);
      if (tag === "cxnSp") {
        payload.connector_adjusts = extractConnectorAdjusts(node);
        var links = extractConnectorLinks(node);
        for (var lk in links) payload[lk] = links[lk];
      }
    } else if (tag === "graphicFrame") {
      payload.bounds = applyGroupTransform(extractXfrm(firstChild(node, "xfrm")), groupContext);
      payload.table = extractTable(node);
      payload.frame_kind = payload.table ? "table" : "graphic_frame";
    } else if (tag === "pic") {
      payload.bounds = applyGroupTransform(extractXfrm(findPath(node, ["spPr", "xfrm"])), groupContext);
      var picture = await extractPicture(node, relTargets, zip, slidePath);
      for (var pk in picture) payload[pk] = picture[pk];
    } else {
      payload.bounds = null;
    }
    return payload;
  }

  function presentationSlideSize(presentationRoot) {
    var sldSz = firstDescendant(presentationRoot, "sldSz");
    if (!sldSz) return {};
    var cx = attr(sldSz, "cx") ? Number(attr(sldSz, "cx")) : 0;
    var cy = attr(sldSz, "cy") ? Number(attr(sldSz, "cy")) : 0;
    return {
      cx: cx,
      cy: cy,
      width_px: emuToPx(cx),
      height_px: emuToPx(cy),
    };
  }

  function extractThemeColors(themeRoot) {
    var scheme = firstDescendant(themeRoot, "clrScheme");
    var colors = {};
    if (!scheme) return colors;
    var kids = childElements(scheme);
    for (var i = 0; i < scheme.childNodes.length; i += 1) {
      var child = scheme.childNodes[i];
      if (child.nodeType !== 1) continue;
      var key = localName(child);
      var first = child.firstElementChild || null;
      if (!first) continue;
      var firstName = localName(first);
      if (firstName === "srgbClr") {
        colors[key] = attr(first, "val") || "";
      } else if (firstName === "sysClr") {
        colors[key] = attr(first, "lastClr") || "";
      }
    }
    return colors;
  }

  function buildRelationshipTargets(relDoc) {
    var map = {};
    var all = relDoc.getElementsByTagName("*");
    for (var i = 0; i < all.length; i += 1) {
      if (localName(all[i]) !== "Relationship") continue;
      var id = attr(all[i], "Id");
      var target = attr(all[i], "Target");
      if (id && target) map[id] = target;
    }
    return map;
  }

  function inspectPptxSlides(presentationRoot, relsMap, zip) {
    var slideRefs = descendants(presentationRoot, "sldId");
    return slideRefs.map(function (slideRef, index) {
      var relId = (slideRef.getAttributeNS && slideRef.getAttributeNS(R_NS, "id")) || attr(slideRef, "id");
      var target = relsMap[relId];
      return {
        slide_no: index + 1,
        slide_path: "ppt/" + String(target || "").replace(/^\/+/, ""),
      };
    });
  }

  function buildElementIndex(elements) {
    var index = {};
    function walk(items) {
      for (var i = 0; i < items.length; i += 1) {
        var element = items[i];
        if (element.node_id) index[String(element.node_id)] = element;
        if (element.children && element.children.length) walk(element.children);
      }
    }
    walk(elements);
    return index;
  }

  function hasVisibleFill(shapeStyle) {
    if (!shapeStyle || !shapeStyle.fill || shapeStyle.fill.kind === "none") return false;
    return shapeStyle.fill.alpha === null || shapeStyle.fill.alpha === undefined || shapeStyle.fill.alpha > 0;
  }

  function hasVisibleLine(shapeStyle) {
    if (!shapeStyle || !shapeStyle.line || shapeStyle.line.kind === "none" || shapeStyle.line.kind === "default") return false;
    if (shapeStyle.line.alpha !== null && shapeStyle.line.alpha !== undefined && shapeStyle.line.alpha <= 0) return false;
    if (shapeStyle.line.width_px !== null && shapeStyle.line.width_px !== undefined && shapeStyle.line.width_px <= 0) return false;
    return true;
  }

  function classifyGroup(element) {
    var bounds = element.bounds || {};
    var area = (bounds.cx || 0) * (bounds.cy || 0);
    var childCount = (element.children || []).length;
    if (childCount >= 4 || area >= 10000000000000) return "section_block";
    return "group";
  }

  function classifyShape(element) {
    var text = String(element.text || "").trim();
    var kind = element.shape_kind || "shape";
    var style = element.shape_style || {};
    if (element.element_type === "connector") return ["connector", kind];
    if (text && (kind === "rect" || kind === "roundRect" || kind === "ellipse")) {
      if (!hasVisibleFill(style) && !hasVisibleLine(style)) return ["text_block", kind];
      return ["labeled_shape", kind];
    }
    if (text) return ["text_block", kind];
    return ["shape", kind];
  }

  function connectionPointPx(bounds, idx) {
    var px = emuBoundsToPx(bounds);
    if (!px || idx === null || idx === undefined) return null;
    var x = px.x;
    var y = px.y;
    var w = px.width;
    var h = px.height;
    var cx = x + w / 2;
    var cy = y + h / 2;
    var map = {
      0: { x: cx, y: y },
      1: { x: x, y: cy },
      2: { x: cx, y: y + h },
      3: { x: x + w, y: cy },
      4: { x: x, y: y },
      5: { x: x + w, y: y },
      6: { x: x, y: y + h },
      7: { x: x + w, y: y + h },
    };
    return map[idx] || { x: cx, y: cy };
  }

  function emuBoundsToPx(bounds) {
    if (!bounds) return null;
    var payload = {
      x: Math.round((bounds.x || 0) / EMU_PER_PIXEL * 100) / 100,
      y: Math.round((bounds.y || 0) / EMU_PER_PIXEL * 100) / 100,
      width: Math.round((bounds.cx || 0) / EMU_PER_PIXEL * 100) / 100,
      height: Math.round((bounds.cy || 0) / EMU_PER_PIXEL * 100) / 100,
    };
    if (bounds.rot) payload.rotation = Math.round((bounds.rot / 60000) * 100) / 100;
    if (bounds.flipH) payload.flipH = true;
    if (bounds.flipV) payload.flipV = true;
    return payload;
  }

  function inferConnectorEndpoints(element, elementIndex) {
    var connectorBounds = emuBoundsToPx(element.bounds);
    if (!connectorBounds) return [null, null];
    var horizontal = connectorBounds.width >= connectorBounds.height;
    var centerX = connectorBounds.x + connectorBounds.width / 2;
    var centerY = connectorBounds.y + connectorBounds.height / 2;
    var candidates = [];
    Object.keys(elementIndex).forEach(function (key) {
      var other = elementIndex[key];
      if (other === element || other.element_type === "connector") return;
      if (String(other.text || "").trim() && !hasVisibleFill(other.shape_style) && !hasVisibleLine(other.shape_style)) return;
      var otherBounds = emuBoundsToPx(other.bounds);
      if (!otherBounds) return;
      var otherCenterX = otherBounds.x + otherBounds.width / 2;
      var otherCenterY = otherBounds.y + otherBounds.height / 2;
      var score = horizontal
        ? Math.abs(otherCenterY - centerY) + Math.abs(otherCenterX - centerX)
        : Math.abs(otherCenterX - centerX) + Math.abs(otherCenterY - centerY);
      candidates.push({
        score: score,
        x: otherBounds.x,
        y: otherBounds.y,
        width: otherBounds.width,
        height: otherBounds.height,
      });
    });
    candidates.sort(function (a, b) { return a.score - b.score; });
    if (candidates.length < 2) return [null, null];
    var first = candidates[0];
    var second = candidates[1];
    if (horizontal) {
      var left = first.x <= second.x ? first : second;
      var right = left === first ? second : first;
      return [
        { x: left.x + left.width, y: left.y + left.height / 2 },
        { x: right.x, y: right.y + right.height / 2 },
      ];
    }
    var top = first.y <= second.y ? first : second;
    var bottom = top === first ? second : first;
    return [
      { x: top.x + top.width / 2, y: top.y + top.height },
      { x: bottom.x + bottom.width / 2, y: bottom.y },
    ];
  }

  function inferRenderingMetadata(params) {
    var rendering = {
      current_mode: "native",
      preferred_mode: "native",
      replacement_candidate: false,
    };
    var replacement = null;
    if (params.subtype === "connector") {
      rendering.preferred_mode = "vector_fallback";
      rendering.replacement_candidate = true;
      replacement = {
        candidate_type: "process_flow_connector",
        strategy: "vector_then_component_replace",
        confidence: "high",
        reason: "connector_fidelity_and_directionality",
      };
    } else if (params.node_type === "asset" && params.subtype === "image") {
      rendering.replacement_candidate = true;
      replacement = {
        candidate_type: "image_asset",
        strategy: "native_asset_replace",
        confidence: "low",
        reason: "asset_swap_or_design_asset_upgrade",
      };
    } else if (params.subtype === "labeled_shape" && params.text) {
      rendering.replacement_candidate = true;
      replacement = {
        candidate_type: "labeled_ui_box",
        strategy: "native_then_component_replace",
        confidence: "medium",
        reason: "repeated_labeled_box_pattern",
      };
    }
    if (replacement) rendering.replacement = replacement;
    return rendering;
  }

  function makeCandidate(params) {
    var candidate = {
      candidate_id: params.candidate_id,
      parent_candidate_id: params.parent_candidate_id,
      slide_no: params.slide_no,
      node_type: params.node_type,
      subtype: params.subtype,
      title: params.title,
      text: params.text,
      source_path: params.source_path,
      source_node_id: params.source_node_id,
      bounds_emu: params.bounds_emu,
      bounds_px: emuBoundsToPx(params.bounds_emu),
    };
    if (params.extra) candidate.extra = params.extra;
    candidate.rendering = inferRenderingMetadata({
      node_type: params.node_type,
      subtype: params.subtype,
      shape_kind: params.extra && params.extra.shape_kind ? params.extra.shape_kind : params.subtype,
      text: params.text,
    });
    return candidate;
  }

  function appendElementCandidates(params) {
    var slideNo = params.slide_no;
    var element = params.element;
    var sourcePath = params.source_path;
    var parentCandidateId = params.parent_candidate_id;
    var candidates = params.candidates;
    var elementIndex = params.element_index;
    var candidateId = "s" + slideNo + ":" + sourcePath;
    var title = element.name || element.text || element.element_type || "element";
    var text = String(element.text || "").trim();

    if (element.element_type === "group") {
      var subtype = classifyGroup(element);
      candidates.push(makeCandidate({
        candidate_id: candidateId,
        parent_candidate_id: parentCandidateId,
        slide_no: slideNo,
        node_type: "node",
        subtype: subtype,
        title: title,
        text: text,
        source_path: sourcePath,
        source_node_id: element.node_id,
        bounds_emu: element.bounds,
        extra: {
          child_count: (element.children || []).length,
          shape_style: element.shape_style,
          transform: emuBoundsToPx(element.bounds),
        },
      }));
      (element.children || []).forEach(function (child, index) {
        appendElementCandidates({
          slide_no: slideNo,
          element: child,
          source_path: sourcePath + "/child_" + (index + 1),
          parent_candidate_id: candidateId,
          candidates: candidates,
          element_index: elementIndex,
        });
      });
      return;
    }

    if (element.element_type === "graphic_frame" && element.table) {
      var table = element.table;
      candidates.push(makeCandidate({
        candidate_id: candidateId,
        parent_candidate_id: parentCandidateId,
        slide_no: slideNo,
        node_type: "node",
        subtype: "table",
        title: title,
        text: "",
        source_path: sourcePath,
        source_node_id: element.node_id,
        bounds_emu: element.bounds,
        extra: {
          row_count: table.row_count || 0,
          column_count: (table.grid_columns || []).length,
          grid_columns: table.grid_columns || [],
        },
      }));
      (table.rows || []).forEach(function (row) {
        var rowId = candidateId + ":row_" + row.row_index;
        candidates.push(makeCandidate({
          candidate_id: rowId,
          parent_candidate_id: candidateId,
          slide_no: slideNo,
          node_type: "node",
          subtype: "table_row",
          title: "row " + row.row_index,
          text: "",
          source_path: sourcePath + "/row_" + row.row_index,
          source_node_id: element.node_id,
          bounds_emu: null,
          extra: {
            height: row.height,
            row_height_px: row.height_px,
            cell_count: (row.cells || []).length,
          },
        }));
        (row.cells || []).forEach(function (cell) {
          if (cell.h_merge || cell.v_merge) return;
          candidates.push(makeCandidate({
            candidate_id: rowId + ":cell_" + cell.cell_index,
            parent_candidate_id: rowId,
            slide_no: slideNo,
            node_type: "node",
            subtype: "table_cell",
            title: "cell " + row.row_index + "-" + cell.cell_index,
            text: cell.text || "",
            source_path: sourcePath + "/row_" + row.row_index + "/cell_" + cell.cell_index,
            source_node_id: element.node_id,
            bounds_emu: null,
            extra: {
              row_height_emu: row.height,
              row_height_px: row.height ? emuToPx(row.height) : null,
              grid_span: cell.grid_span,
              row_span: cell.row_span,
              h_merge: cell.h_merge,
              v_merge: cell.v_merge,
              start_column_index: cell.start_column_index,
              width_px: cell.width_px,
              cell_style: cell.style,
            },
          }));
        });
      });
      return;
    }

    if (element.element_type === "image") {
      candidates.push(makeCandidate({
        candidate_id: candidateId,
        parent_candidate_id: parentCandidateId,
        slide_no: slideNo,
        node_type: "asset",
        subtype: "image",
        title: title,
        text: "",
        source_path: sourcePath,
        source_node_id: element.node_id,
        bounds_emu: element.bounds,
        extra: {
          image_target: element.image_target,
          resolved_target: element.resolved_target,
          mime_type: element.mime_type,
          image_base64: element.image_base64,
        },
      }));
      return;
    }

    var shapeInfo = classifyShape(element);
    var nodeSubtype = shapeInfo[0];
    var shapeSubtype = shapeInfo[1];
    var connectorExtra = {};
    if (nodeSubtype === "connector") {
      if (element.start_connection) {
        connectorExtra.start_connection = element.start_connection;
        var startTarget = elementIndex[String(element.start_connection.id)];
        connectorExtra.start_point_px = connectionPointPx(startTarget ? startTarget.bounds : null, element.start_connection.idx);
      }
      if (element.end_connection) {
        connectorExtra.end_connection = element.end_connection;
        var endTarget = elementIndex[String(element.end_connection.id)];
        connectorExtra.end_point_px = connectionPointPx(endTarget ? endTarget.bounds : null, element.end_connection.idx);
      }
      if (!connectorExtra.start_point_px || !connectorExtra.end_point_px) {
        var inferred = inferConnectorEndpoints(element, elementIndex);
        if (inferred[0] && !connectorExtra.start_point_px) {
          connectorExtra.start_point_px = inferred[0];
          connectorExtra.inferred_start_point = true;
        }
        if (inferred[1] && !connectorExtra.end_point_px) {
          connectorExtra.end_point_px = inferred[1];
          connectorExtra.inferred_end_point = true;
        }
      }
      if (element.connector_adjusts) connectorExtra.connector_adjusts = element.connector_adjusts;
    }

    candidates.push(makeCandidate({
      candidate_id: candidateId,
      parent_candidate_id: parentCandidateId,
      slide_no: slideNo,
      node_type: "node",
      subtype: nodeSubtype,
      title: title,
      text: text,
      source_path: sourcePath,
      source_node_id: element.node_id,
      bounds_emu: element.bounds,
      extra: Object.assign({
        shape_kind: shapeSubtype,
        shape_style: element.shape_style,
        text_style: element.text_style,
      }, connectorExtra),
    }));
  }

  async function buildIntermediateModelFromZip(zip, pptxName) {
    var presentationXml = await readZipText(zip, "ppt/presentation.xml", "현재는 표준 PPTX(OOXML)만 지원합니다. presentation.xml을 찾을 수 없습니다.");
    var presentationRelsXml = await readZipText(zip, "ppt/_rels/presentation.xml.rels", "현재는 표준 PPTX(OOXML)만 지원합니다. presentation.xml.rels를 찾을 수 없습니다.");
    var presentationRoot = parseXml(presentationXml).documentElement;
    var relsRoot = parseXml(presentationRelsXml).documentElement;
    var relTargets = buildRelationshipTargets(relsRoot);
    var slideSize = presentationSlideSize(presentationRoot);
    var themeColors = {};
    if (zip.file("ppt/theme/theme1.xml")) {
      var themeXml = await readZipText(zip, "ppt/theme/theme1.xml");
      themeColors = extractThemeColors(parseXml(themeXml).documentElement);
    }
    var slides = inspectPptxSlides(presentationRoot, relTargets, zip);
    var pages = [];

    for (var i = 0; i < slides.length; i += 1) {
      var slideInfo = slides[i];
      var slideXml = await readZipText(zip, slideInfo.slide_path, "슬라이드 XML을 찾을 수 없습니다: " + slideInfo.slide_path);
      var slideDoc = parseXml(slideXml).documentElement;
      var spTree = findPath(slideDoc, ["cSld", "spTree"]);
      if (!spTree) continue;
      var slideRelPath = slideInfo.slide_path.replace("/slides/", "/slides/_rels/") + ".rels";
      var slideRelTargets = {};
      if (readZipFile(zip, slideRelPath)) {
        var slideRelXml = await readZipText(zip, slideRelPath);
        slideRelTargets = buildRelationshipTargets(parseXml(slideRelXml).documentElement);
      }

      var elements = [];
      for (var c = 0; c < spTree.childNodes.length; c += 1) {
        var child = spTree.childNodes[c];
        var childTag = localName(child);
        if (child.nodeType !== 1 || childTag === "nvGrpSpPr" || childTag === "grpSpPr") continue;
        elements.push(await extractElement(child, slideRelTargets, zip, slideInfo.slide_path, themeColors, null));
      }

      var elementIndex = buildElementIndex(elements);
      var candidates = [];
      for (var e = 0; e < elements.length; e += 1) {
        appendElementCandidates({
          slide_no: slideInfo.slide_no,
          element: elements[e],
          source_path: "slide_" + slideInfo.slide_no + "/element_" + (e + 1),
          parent_candidate_id: "page:" + slideInfo.slide_no,
          candidates: candidates,
          element_index: elementIndex,
        });
      }

      pages.push({
        page_id: "page:" + slideInfo.slide_no,
        slide_no: slideInfo.slide_no,
        title_or_label: "Slide " + slideInfo.slide_no,
        source_path: slideInfo.slide_path,
        slide_size: slideSize,
        theme_colors: themeColors,
        summary: {
          slide_no: slideInfo.slide_no,
          slide_path: slideInfo.slide_path,
          title_or_label: "Slide " + slideInfo.slide_no,
        },
        candidates: candidates,
      });
    }

    return {
      pptxPath: pptxName || "uploaded.pptx",
      requestedSlides: pages.map(function (page) { return page.slide_no; }),
      pages: pages,
    };
  }

  async function parsePptxArrayBuffer(arrayBuffer, fileName) {
    if (!global.JSZip) {
      throw new Error("JSZip is not loaded.");
    }
    var zip = await global.JSZip.loadAsync(arrayBuffer).catch(function () {
      throw new Error("현재는 .pptx 파일만 지원합니다. 파일이 손상되었거나 legacy .ppt 형식일 수 있습니다.");
    });
    return buildIntermediateModelFromZip(zip, fileName || "uploaded.pptx");
  }

  var api = {
    parsePptxArrayBuffer: parsePptxArrayBuffer,
  };

  global.CnsPptxParser = api;
})(typeof window !== "undefined" ? window : this);
