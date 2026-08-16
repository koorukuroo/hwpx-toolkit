#!/usr/bin/env node
// hwpx-toolkit — HWP(5.x) → HWPX 변환 래퍼. @rhwp/core(MIT, vendor/rhwp) 공개 API만 사용.
// 사용: node scripts/rhwp_convert.mjs <input.hwp> <output.hwpx>
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const [input, output] = process.argv.slice(2);
if (!input || !output) {
  process.stderr.write("usage: rhwp_convert.mjs <input.hwp> <output.hwpx>\n");
  process.exit(2);
}

try {
  const vendorDir = path.join(here, "..", "vendor", "rhwp");
  const mod = await import(pathToFileURL(path.join(vendorDir, "rhwp.js")).href);
  const wasm = fs.readFileSync(path.join(vendorDir, "rhwp_bg.wasm"));
  await mod.default({ module_or_path: wasm });
  const bytes = new Uint8Array(fs.readFileSync(input));
  const doc = new mod.HwpDocument(bytes);
  try {
    const hwpx = doc.exportHwpx();
    fs.writeFileSync(output, hwpx);
  } finally {
    doc.free();
  }
  process.stdout.write(JSON.stringify({ ok: true, output }));
} catch (err) {
  process.stderr.write(`rhwp: ${err && err.message ? err.message : String(err)}\n`);
  process.exit(1);
}
