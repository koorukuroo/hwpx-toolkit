#!/usr/bin/env node
// hwpx-toolkit — HWP(5.x) → HWPX 변환 래퍼(rhwp 폴백 엔진). @rhwp/core(MIT, vendor/rhwp) 공개 API만 사용.
// 사용: node scripts/rhwp_convert.mjs <input.hwp> <output.hwpx>
//       node scripts/rhwp_convert.mjs --layout-info <input.hwp>   # 섹션별 원본 용지 설정(JSON 배열)
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const layoutInfo = args[0] === "--layout-info";
const input = layoutInfo ? args[1] : args[0];
const output = layoutInfo ? undefined : args[1];
if (!input || (!layoutInfo && !output)) {
  process.stderr.write("usage: rhwp_convert.mjs [--layout-info] <input.hwp> [output.hwpx]\n");
  process.exit(2);
}

try {
  const vendorDir = path.join(here, "..", "vendor", "rhwp");
  const mod = await import(pathToFileURL(path.join(vendorDir, "rhwp.js")).href);
  const wasm = fs.readFileSync(path.join(vendorDir, "rhwp_bg.wasm"));
  await mod.default({ module_or_path: wasm });
  const bytes = new Uint8Array(fs.readFileSync(input));
  if (bytes[0] === 0x50 && bytes[1] === 0x4b) {
    throw new Error("input is already a ZIP-based HWPX document");
  }
  const doc = new mod.HwpDocument(bytes);
  try {
    if (layoutInfo) {
      const defs = [];
      for (let s = 0; s < doc.getSectionCount(); s += 1) {
        defs.push(JSON.parse(doc.getPageDef(s)));
      }
      process.stdout.write(JSON.stringify(defs));
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
