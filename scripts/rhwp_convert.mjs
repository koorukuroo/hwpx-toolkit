#!/usr/bin/env node
// hwpx-toolkit — @rhwp/core(MIT, vendor/rhwp) 래퍼. 공개 API만 사용.
// 사용: node scripts/rhwp_convert.mjs <input.hwp> <output.hwpx>              # HWP → HWPX (폴백 엔진)
//       node scripts/rhwp_convert.mjs --layout-info <input.hwp>              # 섹션별 원본 용지 설정(JSON 배열)
//       node scripts/rhwp_convert.mjs --render <in.hwpx|hwp> <outdir> [svg|html] [from-to]
//                                                                            # 쪽 미리보기 (page-N.svg|html)
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const mode = args[0] === "--layout-info" ? "layout" : args[0] === "--render" ? "render" : "convert";
const input = mode === "convert" ? args[0] : args[1];
const output = mode === "convert" ? args[1] : mode === "render" ? args[2] : undefined;
if (!input || (mode !== "layout" && !output)) {
  process.stderr.write("usage: rhwp_convert.mjs [--layout-info|--render] <input> [output] [svg|html] [from-to]\n");
  process.exit(2);
}

// rhwp의 SVG/HTML 렌더러는 호스트(브라우저 canvas)에 글자 폭 측정을 위임한다.
// Node에는 canvas가 없으므로 근사치(한글 1em, 영문 0.55em, 공백 0.3em)를 제공한다.
// 줄바꿈 위치가 한컴과 조금 다를 수 있다 — 미리보기 용도.
globalThis.measureTextWidth = (text, font) => {
  const m = /([\d.]+)px/.exec(font || "");
  const px = m ? parseFloat(m[1]) : 16;
  let w = 0;
  for (const ch of text) {
    const c = ch.codePointAt(0);
    w += (c < 128 ? (ch === " " ? 0.3 : 0.55) : 1.0) * px;
  }
  return w;
};

try {
  const vendorDir = path.join(here, "..", "vendor", "rhwp");
  const mod = await import(pathToFileURL(path.join(vendorDir, "rhwp.js")).href);
  const wasm = fs.readFileSync(path.join(vendorDir, "rhwp_bg.wasm"));
  await mod.default({ module_or_path: wasm });
  const bytes = new Uint8Array(fs.readFileSync(input));
  if (mode === "convert" && bytes[0] === 0x50 && bytes[1] === 0x4b) {
    throw new Error("input is already a ZIP-based HWPX document");
  }
  const doc = new mod.HwpDocument(bytes);
  try {
    if (mode === "layout") {
      const defs = [];
      for (let s = 0; s < doc.getSectionCount(); s += 1) {
        defs.push(JSON.parse(doc.getPageDef(s)));
      }
      process.stdout.write(JSON.stringify(defs));
    } else if (mode === "render") {
      const fmt = args[3] === "html" ? "html" : "svg";
      const total = doc.pageCount();
      let from = 1, to = total;
      if (args[4]) {
        const r = /^(\d+)(?:-(\d+))?$/.exec(args[4]);
        if (r) { from = parseInt(r[1], 10); to = r[2] ? parseInt(r[2], 10) : from; }
      }
      from = Math.max(1, from); to = Math.min(total, to);
      fs.mkdirSync(output, { recursive: true });
      const files = [];
      for (let i = from; i <= to; i += 1) {
        const body = fmt === "html" ? doc.renderPageHtml(i - 1) : doc.renderPageSvg(i - 1);
        const file = path.join(output, `page-${i}.${fmt}`);
        fs.writeFileSync(file, body);
        files.push(file);
      }
      process.stdout.write(JSON.stringify({ ok: true, pages: total, from, to, format: fmt, files }));
    } else {
      const hwpx = doc.exportHwpx();
      fs.writeFileSync(output, hwpx);
      process.stdout.write(JSON.stringify({ ok: true, output }));
    }
  } finally {
    doc.free();
  }
} catch (err) {
  process.stderr.write(`rhwp: ${err && err.message ? err.message : String(err)}\n`);
  process.exit(1);
}
