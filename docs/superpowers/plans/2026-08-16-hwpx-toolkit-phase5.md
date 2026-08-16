# hwpx-toolkit Phase 5 (변환·특화) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** HWP→HWPX 변환(`from-hwp`, MIT rhwp WASM 연동), 공문서 작성법 검수(`lint`), 파생 템플릿(`report`)을 추가하고 Phase 4 파킹 항목을 정리한다.

**Architecture:** `vendor/rhwp/`에 @rhwp/core(MIT)의 WASM 런타임을 동봉하고 `scripts/rhwp_convert.mjs`(자체 작성 Node 래퍼)를 `core/convert.py`가 subprocess로 호출한다 — Node 부재/실패는 `PackageError`로 CLI JSON 계약에 편입되고, 변환 산출물은 `check`를 통과해야 한다. `core/lint.py`는 행정안전부 공문서 작성 원칙(날짜·시간·금액 표기, 붙임·끝 표기, 항목 기호 체계, 쌍점 띄어쓰기)을 정규식 규칙으로 검사한다 — 자체 규칙 정의(클린룸). 파생 템플릿은 생성기를 `gen_templates.py`로 일반화해 base+report를 만들고, 템플릿별 `styles.json`으로 마크다운 렌더러의 제목 스타일 매핑을 데이터화한다.

**Tech Stack:** Python 3.9+ stdlib (subprocess, shutil, re, json). Node.js 18+ (from-hwp 한정, 선택 의존성). pytest.

**Spec:** `docs/superpowers/specs/2026-08-13-hwpx-toolkit-design.md`

## Global Constraints

- 의존성: 코어와 CLI는 Python 3.9+ 표준 라이브러리만; `from-hwp`만 Node.js 18+ + vendored rhwp WASM(MIT). Node 미설치 시 from-hwp만 비활성(PackageError), 나머지 정상 (스펙 §9).
- 클린룸: 외부 저장소의 코드·XML·lint 규칙 문구 복사 금지. rhwp는 MIT — `vendor/rhwp/LICENSE` 보존, `THIRD_PARTY_NOTICES.md` 고지 (스펙 §2 3항). Node 래퍼(.mjs)는 자체 작성 (@rhwp/core 공개 API만 사용).
- `.hwp` 입력은 사용자가 명시적으로 변환을 요청한 경우에만 from-hwp (스펙 §7).
- 변환 산출물은 전달 전 `check` 통과 필수; CLI 실패 시 JSON `{"ok": false}` + exit 2.
- 템플릿 파일 직접 편집 금지 — 생성기(`scripts/dev/gen_templates.py`) 수정 후 재실행 (idempotency 테스트).
- 테스트: `python3.13 -m pytest tests/ -q` (plain python3에 pytest 없음; venv 금지). 현재 137개 green 유지. from-hwp 통합 테스트는 `node`가 없으면 skip.
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- rhwp 벤더 파일 출처: 이 저장소 밖 `<@rhwp/core 배포본 경로>/` 의 `rhwp.js`, `rhwp_bg.wasm`, `LICENSE`, `package.json` 4개 파일을 **그대로 복사**(MIT 재배포 — 코드 아닌 런타임 바이너리·라이선스). 그 폴더의 다른 파일(rhwp_convert.mjs 등)은 읽지도 복사하지도 않는다.

---

### Task 1: Phase 4 파킹 정리 (errors 모듈, 이미지 가드, check 이미지 참조, JPEG 패딩)

**Files:**
- Create: `core/errors.py`
- Modify: `core/package.py`, `core/edit.py`, `core/images.py`, `core/header.py`, `core/guards.py` (import 경로), `core/edit.py`(delete_image 가드), `core/images.py`(JPEG 0xFF 패딩), `core/guards.py`(이미지 참조 정합)
- Test: `tests/test_carryover5.py`

**Interfaces:**
- Produces:
  - `core/errors.py`: `PackageError(Exception)`, `UnsupportedZipError(PackageError)`, `EditError(PackageError)` — 정의를 여기로 이동. 기존 모듈은 `from core.errors import ...`로 재노출(`core.package.PackageError`, `core.edit.EditError`는 그대로 import 가능해야 함 — 기존 테스트 불변).
  - `SectionEditor.delete_image`: 그림 전용 문단이 `hp:subList` 안(셀 내부)이면 문단을 제거하지 않고 빈 `<hp:run charPrIDRef="0"><hp:t/></hp:run>`만 남긴다(빈 subList 방지).
  - `images.image_size`: JPEG 마커 스캔에서 `0xFF` 패딩 바이트(연속 FF)를 건너뜀; 잘린 PNG(IHDR 부족)는 `EditError`.
  - `guards.check_package`: 섹션의 모든 `hc:img@binaryItemIDRef`가 content.hpf manifest의 `opf:item id`에 존재하고 그 href 엔트리가 패키지에 있어야 함 — 아니면 `image-ref-broken: <id>` error, `signals["image_ref_broken"]: bool` 추가.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_carryover5.py
import struct
import zlib
import zipfile
import pytest
from core.errors import PackageError, EditError, UnsupportedZipError
from core.package import HwpxPackage
from core.edit import edit_file
from core.images import image_size
from core.guards import check_package
from tests.fixture import build_form_hwpx, build_minimal_hwpx


def test_errors_module_is_single_source():
    import core.package, core.edit
    assert core.package.PackageError is PackageError
    assert core.edit.EditError is EditError
    assert issubclass(EditError, PackageError)
    assert issubclass(UnsupportedZipError, PackageError)


def _png(w, h):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _jpeg_with_padding(w, h):
    # SOI, APP0(짧게), 패딩 FF FF, SOF0, EOI
    app0 = b"\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00"
    sof0 = b"\xff\xc0" + struct.pack(">H", 11) + b"\x08" + struct.pack(">HH", h, w) + b"\x01\x01\x11\x00"
    return b"\xff\xd8" + app0 + b"\xff\xff" + sof0 + b"\xff\xd9"


def test_jpeg_padding_and_truncated_png():
    assert image_size(_jpeg_with_padding(30, 20)) == (30, 20, "jpg")
    with pytest.raises(EditError):
        image_size(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4)


def test_delete_image_in_cell_keeps_paragraph(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(_png(8, 8))
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    # 셀 (0,0,1)에 그림을 넣기 위해 셀 문단을 앵커로 삽입할 수 없으므로(본문 전용)
    # 편집기 내부 API로 셀 subList에 그림 문단을 직접 구성한다
    def put_pic_in_cell(ed):
        import xml.etree.ElementTree as ET
        from core import images
        _, tc = ed._find_cell(0, 0, 1)
        sub = tc.find(ed_q("subList"))
        p = sub.findall(ed_q("p"))[0]
        run = p.find(ed_q("run"))
        bin_id = ed._stage_new_image(img.read_bytes(), "png")
        pic = ET.fromstring(images.pic_xml(str(ed._max_id() + 1), bin_id, 1000, 1000, 8, 8))
        for t in run.findall(ed_q("t")):
            run.remove(t)
        run.append(pic)
        ed._mark(p)
    from core.edit import _q as ed_q
    edit_file(src, d1, put_pic_in_cell)
    d2 = tmp_path / "2.hwpx"
    edit_file(d1, d2, lambda ed: ed.delete_image(0))
    import xml.etree.ElementTree as ET
    root = ET.fromstring(HwpxPackage.open(d2).read("Contents/section0.xml"))
    NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
    subs = list(root.iter(f"{{{NS}}}subList"))
    assert all(s.find(f"{{{NS}}}p") is not None for s in subs)   # 빈 subList 없음
    assert check_package(d2)["ok"]


def test_check_detects_broken_image_ref(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    pkg = HwpxPackage.open(src)
    sec = pkg.read_text("Contents/section0.xml").replace(
        "</hs:sec>",
        '<hp:p id="1000009999" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
        '<hp:pic id="1" zOrder="0" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" '
        'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" '
        'instid="0" reverse="0" xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core">'
        '<hc:img binaryItemIDRef="ghost" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
        '</hp:pic></hp:run></hp:p></hs:sec>')
    bad = tmp_path / "bad.hwpx"
    pkg.write_replaced(bad, {"Contents/section0.xml": sec.encode("utf-8")})
    r = check_package(bad)
    assert r["signals"]["image_ref_broken"] is True
    assert any(e.startswith("image-ref-broken: ghost") for e in r["errors"])
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_carryover5.py -v`
Expected: FAIL (`ModuleNotFoundError: core.errors`)

- [ ] **Step 3: 구현**

`core/errors.py`:

```python
"""hwpx-toolkit 예외 계층 — 순환 import 없이 어디서든 참조."""


class PackageError(Exception):
    pass


class UnsupportedZipError(PackageError):
    pass


class EditError(PackageError):
    pass
```

`core/package.py`: 기존 `class PackageError`/`class UnsupportedZipError` 정의를 삭제하고 상단에 `from core.errors import PackageError, UnsupportedZipError  # noqa: F401 (재노출)`. `core/edit.py`: `class EditError` 정의 삭제, `from core.errors import PackageError, EditError  # noqa: F401`. `core/images.py`, `core/header.py`: `from core.errors import EditError`. `core/guards.py`: `from core.errors import PackageError` (기존 `from core.package import ... PackageError`도 동작하지만 통일).

`core/images.py` JPEG 루프 수정:

```python
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker == 0xFF:          # 패딩 바이트
                i += 1
                continue
            ...
```

PNG 가드:

```python
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if len(data) < 24:
            raise EditError("잘린 PNG (IHDR 없음)")
        w, h = struct.unpack(">II", data[16:24])
        return w, h, "png"
```

`core/edit.py` `delete_image` 마지막 분기:

```python
        if not p.findall(_q("run")):
            gp = parents[p]
            if gp.tag == _q("subList"):
                # 셀 내부: 빈 subList를 만들지 않도록 빈 run을 남긴다
                run = ET.SubElement(p, _q("run"), {"charPrIDRef": "0"})
                ET.SubElement(run, _q("t"))
                self._mark(p)
            else:
                gp.remove(p)
        else:
            self._mark(p)
```

`core/guards.py` `check_package`에 이미지 참조 검사 추가 (`signals`에 `"image_ref_broken": False` 초기화):

```python
        # 이미지 참조 정합: hc:img@binaryItemIDRef ↔ content.hpf manifest ↔ 엔트리
        hpf = pkg.read_text("Contents/content.hpf")
        manifest = dict(re.findall(r'<opf:item[^>]*\bid="([^"]+)"[^>]*\bhref="([^"]+)"', hpf))
        names_set = set(pkg.names())
        NS_HC = "http://www.hancom.co.kr/hwpml/2011/core"
        for name in section_names(pkg.names()):
            root = ET.fromstring(pkg.read(name))
            for img in root.iter(f"{{{NS_HC}}}img"):
                ref = img.get("binaryItemIDRef")
                href = manifest.get(ref)
                if ref is None or href is None or href not in names_set:
                    signals["image_ref_broken"] = True
                    errors.append(f"image-ref-broken: {ref} (manifest/BinData 불일치)")
```

(manifest 정규식은 속성 순서가 id→href인 우리 생성물과 실물(id, href 순) 모두에 맞음. 순서가 다를 수 있으므로 더 견고하게: `for m in re.finditer(r"<opf:item\b[^>]*>", hpf)`로 태그를 잡고 그 안에서 `id="..."`와 `href="..."`를 각각 검색해 dict를 만든다 — 구현 시 이 방식을 쓴다.)

- [ ] **Step 4: 통과 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green (137 + 4)

```bash
git add core/errors.py core/package.py core/edit.py core/images.py core/header.py core/guards.py tests/test_carryover5.py
git commit -m "refactor: 예외 모듈 분리, 셀 내부 그림 삭제 가드, 이미지 참조 검사, JPEG 패딩

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: from-hwp — rhwp 벤더링 + Node 래퍼 + core/convert.py + CLI

**Files:**
- Create: `vendor/rhwp/rhwp.js`, `vendor/rhwp/rhwp_bg.wasm`, `vendor/rhwp/LICENSE`, `vendor/rhwp/package.json` (복사), `vendor/rhwp/README.md`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `scripts/rhwp_convert.mjs`
- Create: `core/convert.py`
- Modify: `scripts/hwpx.py`, `.gitignore`(변경 없음 확인 — `*.hwpx`만 무시, wasm은 추적)
- Test: `tests/test_convert.py`

**Interfaces:**
- Produces:
  - `convert.node_available() -> str | None` — `shutil.which("node")` 결과
  - `convert.hwp_to_hwpx(src, dst, *, timeout=120) -> dict` — `{"ok": True, "output": str, "check": {...}}`. Node 없으면 `PackageError("Node.js 18+가 필요합니다 (from-hwp 전용) ...")`, 입력 부재/확장자 `.hwp` 아님 → `PackageError`, 변환 실패(비0 종료) → `PackageError(stderr 요약)`. 성공 후 `guards.check_package(dst)` 실행 결과를 포함(게이트는 CLI에서 exit 판정).
  - `scripts/rhwp_convert.mjs <in.hwp> <out.hwpx>` — 자체 작성: `import(vendor/rhwp/rhwp.js)` → `await mod.default({module_or_path: wasmBytes})` → `new mod.HwpDocument(bytes)` → `exportHwpx()` → 파일 저장 → `free()`. 실패 시 stderr 메시지 + exit 1.
  - CLI: `from-hwp <input.hwp> -o <out.hwpx>` — JSON `{"ok", "output", "check"}`; check ok면 exit 0 아니면 2.

- [ ] **Step 1: 벤더 복사 + 고지 파일**

```bash
mkdir -p vendor/rhwp
SRC=<@rhwp/core 배포본 경로>
cp "$SRC/rhwp.js" "$SRC/rhwp_bg.wasm" "$SRC/LICENSE" "$SRC/package.json" vendor/rhwp/
```

`vendor/rhwp/README.md`:

```markdown
# vendored: @rhwp/core (MIT)

- 출처: @rhwp/core — Copyright (c) 2025-2026 Edward Kim, MIT License (LICENSE 참조)
- 용도: `scripts/rhwp_convert.mjs`가 HWP(5.x 바이너리)→HWPX 변환에 사용하는 WASM 런타임
- 갱신: 파일 4개(rhwp.js, rhwp_bg.wasm, LICENSE, package.json)를 상위 릴리즈로 교체.
  hwpx-toolkit 코드는 `HwpDocument`/`exportHwpx`/`free` 공개 API만 사용한다.
```

`THIRD_PARTY_NOTICES.md`:

```markdown
# Third-Party Notices

hwpx-toolkit 자체 코드는 MIT (LICENSE 참조). 아래 외부 컴포넌트를 동봉한다.

## @rhwp/core (vendor/rhwp/)

- 저작권: Copyright (c) 2025-2026 Edward Kim
- 라이선스: MIT — 전문은 `vendor/rhwp/LICENSE`
- 사용 범위: `from-hwp` 커맨드의 HWP→HWPX 변환 런타임(WASM). 선택 의존성이며
  Node.js 18+ 환경에서만 로드된다. hwpx-toolkit은 이 라이브러리의 공개 API를
  `scripts/rhwp_convert.mjs`(자체 작성)에서 호출할 뿐 소스를 수정하지 않는다.
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_convert.py
import os
import shutil
import pytest
from pathlib import Path
from core.errors import PackageError
from core import convert

ROOT = Path(__file__).resolve().parent.parent


def test_vendor_files_and_notice_present():
    for rel in ("vendor/rhwp/rhwp.js", "vendor/rhwp/rhwp_bg.wasm",
                "vendor/rhwp/LICENSE", "scripts/rhwp_convert.mjs",
                "THIRD_PARTY_NOTICES.md"):
        assert (ROOT / rel).is_file(), rel
    assert "MIT" in (ROOT / "vendor/rhwp/LICENSE").read_text(encoding="utf-8")
    assert "@rhwp/core" in (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")


def test_rejects_non_hwp_and_missing(tmp_path):
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(tmp_path / "없음.hwp", tmp_path / "o.hwpx")
    bad = tmp_path / "x.txt"
    bad.write_text("x")
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(bad, tmp_path / "o.hwpx")


def test_missing_node_reports_package_error(tmp_path, monkeypatch):
    f = tmp_path / "a.hwp"
    f.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 64)
    monkeypatch.setattr(convert, "node_available", lambda: None)
    with pytest.raises(PackageError) as ei:
        convert.hwp_to_hwpx(f, tmp_path / "o.hwpx")
    assert "Node" in str(ei.value)


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_conversion_failure_on_garbage_input(tmp_path):
    f = tmp_path / "garbage.hwp"
    f.write_bytes(b"not a real hwp file at all" * 10)
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(f, tmp_path / "o.hwpx")


@pytest.mark.skipif(shutil.which("node") is None or not os.environ.get("HWPX_TEST_HWP"),
                    reason="node 또는 HWPX_TEST_HWP 샘플 없음")
def test_real_conversion_passes_check(tmp_path):
    from core.analyze import extract_text
    out = tmp_path / "conv.hwpx"
    r = convert.hwp_to_hwpx(os.environ["HWPX_TEST_HWP"], out)
    assert r["check"]["ok"], r["check"]["errors"]
    assert extract_text(out).strip()
```

- [ ] **Step 3: 실패 확인**

Run: `python3.13 -m pytest tests/test_convert.py -v`
Expected: FAIL (`ModuleNotFoundError: core.convert`)

- [ ] **Step 4: scripts/rhwp_convert.mjs 작성 (자체)**

```javascript
#!/usr/bin/env node
// hwpx-toolkit — HWP(5.x) → HWPX 변환 래퍼. @rhwp/core(MIT, vendor/rhwp) 공개 API만 사용.
// 사용: node scripts/rhwp_convert.mjs <input.hwp> <output.hwpx>
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const [input, output] = process.argv.slice(2);
if (!input || !output) {
  process.stderr.write("usage: rhwp_convert.mjs <input.hwp> <output.hwpx>\n");
  process.exit(2);
}

try {
  const vendorDir = path.join(here, "..", "vendor", "rhwp");
  const mod = await import(path.join(vendorDir, "rhwp.js"));
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
```

- [ ] **Step 5: core/convert.py 작성**

```python
# core/convert.py
"""HWP(바이너리) → HWPX 변환 — Node.js + vendored rhwp WASM (선택 의존성)."""
import shutil
import subprocess
from pathlib import Path

from core.errors import PackageError
from core import guards

ROOT = Path(__file__).resolve().parent.parent
WRAPPER = ROOT / "scripts" / "rhwp_convert.mjs"


def node_available():
    return shutil.which("node")


def hwp_to_hwpx(src, dst, *, timeout=120):
    src = Path(src)
    dst = Path(dst)
    if not src.is_file():
        raise PackageError(f"입력 파일 없음: {src}")
    if src.suffix.lower() != ".hwp":
        raise PackageError(f"from-hwp는 .hwp 입력만 받습니다: {src.name}")
    node = node_available()
    if not node:
        raise PackageError(
            "Node.js 18+가 필요합니다 (from-hwp 전용, 다른 커맨드는 영향 없음). "
            "설치 후 다시 시도하세요.")
    try:
        proc = subprocess.run(
            [node, str(WRAPPER), str(src), str(dst)],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise PackageError(f"변환 시간 초과({timeout}s): {src.name}")
    if proc.returncode != 0 or not dst.is_file():
        msg = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise PackageError("HWP 변환 실패: " + (msg[-1] if msg else f"exit {proc.returncode}"))
    check = guards.check_package(dst)
    return {"ok": check["ok"], "output": str(dst), "check": check}
```

- [ ] **Step 6: CLI (scripts/hwpx.py)**

```python
from core import convert as convert_mod  # 상단 import


def cmd_from_hwp(args):
    result = convert_mod.hwp_to_hwpx(args.input, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2

# build_parser():
    fh = sub.add_parser("from-hwp", help="HWP(5.x) → HWPX 변환 (Node.js 18+ 필요)")
    fh.add_argument("input")
    fh.add_argument("-o", "--output", required=True)
    fh.set_defaults(func=cmd_from_hwp)
```

- [ ] **Step 7: 통과 확인 + 실물 스모크**

Run: `python3.13 -m pytest tests/test_convert.py tests/ -q` → 전체 green (node 있으면 garbage 테스트 실행, 실물 테스트는 env 없으면 skip)
Run: `HWPX_TEST_HWP="<샘플 .hwp 경로>" python3.13 -m pytest tests/test_convert.py::test_real_conversion_passes_check -v` → PASS (파일이 있으면)
Run: `python3 scripts/hwpx.py from-hwp <위 파일> -o /private/tmp/hwpx-smoke/p5.hwpx | head -5` → ok true

- [ ] **Step 8: Commit**

```bash
git add vendor/rhwp THIRD_PARTY_NOTICES.md scripts/rhwp_convert.mjs core/convert.py scripts/hwpx.py tests/test_convert.py
git commit -m "feat: from-hwp (rhwp WASM 연동, MIT 벤더링)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 공문서 작성법 lint — core/lint.py + CLI

**Files:**
- Create: `core/lint.py`
- Modify: `scripts/hwpx.py`
- Create: `references/gonmun-rules.md`
- Test: `tests/test_lint.py`

**Interfaces:**
- Produces:
  - `lint.lint_text(text: str) -> dict` — `{"findings": [{"rule", "line", "text", "message", "suggest"}], "count": N}`. 규칙(자체 정의; 행정안전부 행정업무운영 편람의 공문서 작성 원칙 요지):
    - `date-format`: 날짜는 `YYYY. M. D.` (숫자, 온점 뒤 한 칸, 마지막 온점). 검출: `2026.8.16`(공백 없음), `2026-08-16`, `2026/8/16`, `2026년 8월 16일`(본문 내 한글 단위 표기) → suggest 정규 표기.
    - `time-format`: 24시각제 `HH:MM`. 검출: `오전 9시`, `오후 2시 30분`, `14시` → suggest `09:00`, `14:30`, `14:00`.
    - `amount-hangul`: 금액은 아라비아 숫자 + 괄호 안 한글 병기 `금113,560원(금일십일만삼천오백육십원)`. 검출: `\d{1,3}(,\d{3})+원` 뒤에 `(금...원)`이 없으면 warning suggest 병기.
    - `attachment-format`: `붙임` 항목은 `1부.`로 끝나야 함; `붙임` 뒤 항목이 `부.` 없이 끝나면 지적.
    - `end-mark`: 본문(마지막 비어있지 않은 줄)이 `끝.`으로 끝나야 함(붙임이 있으면 붙임 마지막 항목 뒤에 `끝.`). 마지막 줄이 `끝.`으로 끝나지 않으면 지적. `끝.` 앞은 한 칸 띄움(`1부.  끝.`은 두 칸) — 띄어쓰기 없으면 지적.
    - `item-hierarchy`: 항목 기호 순서 `1.` → `가.` → `1)` → `가)` → `(1)` → `(가)` → `①`. 줄 머리 기호를 인식해 깊이 n+2가 n+1 없이 등장하면 지적.
    - `colon-spacing`: 쌍점(:) 왼쪽 붙이고 오른쪽 한 칸: `성명 : 홍길동`(왼쪽 공백) 또는 `성명:홍길동`(오른쪽 공백 없음; 단 `HH:MM` 시간은 예외) 지적.
  - `lint.lint_file(path) -> dict` — `.hwpx`면 `extract_text`, 그 외 텍스트 파일 읽기 후 `lint_text`
  - CLI: `lint <file>` — JSON, 항상 exit 0 (검수는 게이트가 아님; findings 유무는 count로 판단)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_lint.py
from core.lint import lint_text, lint_file
from tests.fixture import build_minimal_hwpx


def _rules(text):
    return {f["rule"] for f in lint_text(text)["findings"]}


def test_date_rules():
    assert "date-format" in _rules("회의는 2026.8.16 개최")
    assert "date-format" in _rules("2026-08-16 제출")
    assert "date-format" in _rules("2026년 8월 16일까지")
    assert "date-format" not in _rules("2026. 8. 16. 개최")


def test_time_rules():
    assert "time-format" in _rules("오후 2시 30분 시작")
    assert "time-format" in _rules("오전 9시 개회")
    assert "time-format" not in _rules("14:30 시작")
    f = next(x for x in lint_text("오후 2시 30분")["findings"] if x["rule"] == "time-format")
    assert f["suggest"] == "14:30"


def test_amount_rule():
    assert "amount-hangul" in _rules("예산 1,500,000원 지원")
    assert "amount-hangul" not in _rules("금1,500,000원(금일백오십만원)")


def test_attachment_and_end_mark():
    ok = "붙임  1. 사업계획서 1부.\n      2. 예산서 1부.  끝."
    assert not ({"attachment-format", "end-mark"} & _rules(ok))
    assert "attachment-format" in _rules("붙임  1. 사업계획서\n  끝.")
    assert "end-mark" in _rules("본문입니다.\n붙임  1. 계획서 1부.")
    assert "end-mark" in _rules("본문입니다.끝.")       # 띄어쓰기 없음


def test_item_hierarchy_and_colon():
    assert "item-hierarchy" in _rules("1. 개요\n1) 세부")     # 가. 건너뜀
    assert "item-hierarchy" not in _rules("1. 개요\n가. 세부\n1) 상세")
    assert "colon-spacing" in _rules("성명 : 홍길동")
    assert "colon-spacing" in _rules("성명:홍길동")
    assert "colon-spacing" not in _rules("성명: 홍길동")
    assert "colon-spacing" not in _rules("14:30 시작")


def test_lint_file_hwpx(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx", body_texts=["회의 2026.8.16 개최"])
    r = lint_file(p)
    assert r["count"] >= 1 and r["findings"][0]["rule"] == "date-format"
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_lint.py -v`
Expected: FAIL (`ModuleNotFoundError: core.lint`)

- [ ] **Step 3: core/lint.py 구현**

```python
# core/lint.py
"""공문서 작성법 검수 — 행정안전부 행정업무운영 편람의 표기 원칙을 규칙화(자체 정의)."""
import re
from pathlib import Path

_DATE_BAD = [
    (re.compile(r"\b(\d{4})\.(\d{1,2})\.(\d{1,2})"), "온점 뒤 한 칸 띄움"),
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "하이픈 대신 온점"),
    (re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b"), "빗금 대신 온점"),
    (re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일"), "한글 단위 대신 온점"),
]
_DATE_OK = re.compile(r"\d{4}\. \d{1,2}\. \d{1,2}\.")
_TIME_BAD = re.compile(r"(오전|오후)?\s*(\d{1,2})시(?!간|점|기|험)(?:\s*(\d{1,2})분)?")
_AMOUNT = re.compile(r"(?<![\d,])(\d{1,3}(?:,\d{3})+)원(?!\()")
_HANGUL_AMOUNT = re.compile(r"\(금[가-힣]+원\)")
_ATTACH_LINE = re.compile(r"^\s*붙임\s+")
_ITEM = [
    (0, re.compile(r"^\s*\d+\.\s")), (1, re.compile(r"^\s*[가-힣]\.\s")),
    (2, re.compile(r"^\s*\d+\)\s")), (3, re.compile(r"^\s*[가-힣]\)\s")),
    (4, re.compile(r"^\s*\(\d+\)\s")), (5, re.compile(r"^\s*\([가-힣]\)\s")),
    (6, re.compile(r"^\s*[①-⑳]\s?")),
]
_COLON_LEFT_SPACE = re.compile(r"\S\s+:\s")
_COLON_NO_RIGHT = re.compile(r"[가-힣A-Za-z)\]]:(?=\S)(?!\d{2}\b)")
_TIME_OK = re.compile(r"\b\d{1,2}:\d{2}\b")


def _add(findings, rule, lineno, text, message, suggest=None):
    findings.append({"rule": rule, "line": lineno, "text": text.strip(),
                     "message": message, "suggest": suggest})


def _time_suggest(m):
    ampm, hh, mm = m.group(1), int(m.group(2)), m.group(3)
    if ampm == "오후" and hh < 12:
        hh += 12
    return f"{hh:02d}:{int(mm or 0):02d}"


def lint_text(text):
    findings = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for rx, why in _DATE_BAD:
            for m in rx.finditer(line):
                y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
                _add(findings, "date-format", i, line, f"날짜 표기: {why}",
                     f"{y}. {mo}. {d}.")
        for m in _TIME_BAD.finditer(line):
            _add(findings, "time-format", i, line, "시간은 24시각제 HH:MM",
                 _time_suggest(m))
        if _AMOUNT.search(line) and not _HANGUL_AMOUNT.search(line):
            m = _AMOUNT.search(line)
            _add(findings, "amount-hangul", i, line,
                 "금액은 아라비아 숫자 뒤 괄호에 한글 병기",
                 f"금{m.group(1)}원(금…원)")
        if _COLON_LEFT_SPACE.search(line):
            _add(findings, "colon-spacing", i, line, "쌍점 왼쪽은 붙이고 오른쪽만 한 칸")
        stripped_times = _TIME_OK.sub("", line)
        if _COLON_NO_RIGHT.search(stripped_times):
            _add(findings, "colon-spacing", i, line, "쌍점 오른쪽 한 칸 띄움")

    # 붙임 / 끝.
    nonempty = [(i, l) for i, l in enumerate(lines, 1) if l.strip()]
    if nonempty:
        in_attach = False
        for i, l in nonempty:
            if _ATTACH_LINE.match(l):
                in_attach = True
            if in_attach:
                body = re.sub(r"\s*끝\.\s*$", "", l)
                body = _ATTACH_LINE.sub("", body).strip()
                if body and not re.search(r"\d+\s*부\.$", body):
                    _add(findings, "attachment-format", i, l, "붙임 항목은 'N부.'로 끝남")
        last_i, last = nonempty[-1]
        if not last.rstrip().endswith("끝."):
            _add(findings, "end-mark", last_i, last, "본문(또는 붙임) 마지막에 ' 끝.' 표기")
        elif not re.search(r"(\s|^)끝\.$", last.rstrip()):
            _add(findings, "end-mark", last_i, last, "'끝.' 앞은 한 칸(붙임 뒤는 두 칸) 띄움")

    # 항목 기호 체계
    seen_levels = []
    for i, l in enumerate(lines, 1):
        for level, rx in _ITEM:
            if rx.match(l):
                if level > 0 and (not seen_levels or level > max(seen_levels) + 1):
                    _add(findings, "item-hierarchy", i, l,
                         "항목 기호는 1. → 가. → 1) → 가) → (1) → (가) → ① 순서")
                seen_levels = [x for x in seen_levels if x < level] + [level]
                break
    return {"findings": findings, "count": len(findings)}


def lint_file(path):
    path = Path(path)
    if path.suffix.lower() == ".hwpx":
        from core.analyze import extract_text
        text = extract_text(path)
    else:
        text = path.read_text(encoding="utf-8")
    return lint_text(text)
```

- [ ] **Step 4: CLI + references**

```python
from core import lint as lint_mod  # 상단 import


def cmd_lint(args):
    result = lint_mod.lint_file(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

# build_parser():
    ln = sub.add_parser("lint", help="공문서 작성법 검수 (hwpx 또는 텍스트)")
    ln.add_argument("file")
    ln.set_defaults(func=cmd_lint)
```

`references/gonmun-rules.md`:

```markdown
# 공문서 작성법 검수 규칙 (lint)

행정안전부 「행정업무운영 편람」의 공문서 표기 원칙을 자체 규칙으로 정리했다.
검수는 게이트가 아니라 안내이며, 결과 JSON의 findings를 보고 사용자가 판단한다.

| 규칙 | 원칙 | 예 |
|------|------|-----|
| date-format | 연월일은 숫자와 온점, 온점 뒤 한 칸, 마지막에도 온점 | `2026. 8. 16.` |
| time-format | 24시각제, 시·분은 쌍점 | `14:30` |
| amount-hangul | 아라비아 숫자 뒤 괄호에 한글 병기 | `금1,500,000원(금일백오십만원)` |
| attachment-format | 붙임 항목은 `N부.`로 끝냄 | `붙임  1. 계획서 1부.` |
| end-mark | 본문(붙임이 있으면 붙임) 끝에 한 칸 띄고 `끝.` (붙임 뒤는 두 칸) | `... 1부.  끝.` |
| item-hierarchy | 1. → 가. → 1) → 가) → (1) → (가) → ① | |
| colon-spacing | 쌍점 왼쪽 붙임, 오른쪽 한 칸 (시각 표기 예외) | `성명: 홍길동` |
```

- [ ] **Step 5: 통과 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add core/lint.py scripts/hwpx.py references/gonmun-rules.md tests/test_lint.py
git commit -m "feat: 공문서 작성법 lint

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 파생 템플릿 report + 템플릿별 스타일 맵

**Files:**
- Rename/Create: `scripts/dev/gen_templates.py` (기존 `gen_base_template.py` 대체 — 함수 재사용, `--only base|report` 옵션 없이 항상 둘 다 생성), 기존 파일 삭제
- Create: `templates/base/styles.json`, `templates/report/` 전체 (생성 산출물)
- Modify: `core/owpml.py` (`heading_para(level, text, alloc, style_map=None)`, `load_style_map(template)`), `core/markdown.py` (템플릿 스타일 맵 사용)
- Modify: `tests/test_base_template.py` (생성기 경로 변경), `docs/hancom-verification.md`
- Test: `tests/test_report_template.py`

**Interfaces:**
- Produces:
  - `templates/<t>/styles.json`: `{"heading": {"1": ["charPr","paraPr"], "2": [...], "default": [...]}, "body": ["0","0"], "bullet_para": "4", "table": {"header_char": "4", "header_border": "4", "body_border": "3", "cell_para": "5"}}`
  - base styles.json: heading 1→["1","1"], 2→["2","2"], default→["3","3"], body ["0","0"], bullet_para "4", table {…4/4/3/5}
  - report 템플릿 = base 스타일 + charPr 5(16pt 돋움 굵게 — 문서 제목), charPr 6(12pt 돋움 굵게 흰색 `#FFFFFF` — 섹션 바 글자), borderFill 5(SOLID 0.12mm 4면 + 진남색 `#1F3864` 배경 — 섹션 바 셀), paraPr 6(LEFT, prev 600 next 200, borderFill 2 유지). report styles.json: heading 1→["5","1"], 2→["2","6"], default→["3","3"], `"section_bar": {"char": "6", "border": "5"}`.
  - `owpml.load_style_map(template) -> dict`, `owpml.heading_para(level, text, alloc, style_map=None)`(None이면 base 동작), `owpml.section_bar(text, alloc, style_map)` — 1×1 표(폭 42520, 높이 1200)에 흰 글자 제목: report의 H2 렌더에 사용
  - `markdown.render_to_section(md, template)`: `load_style_map(template)`을 읽어 heading/bullet/table 스타일 적용; report에서 `## 제목`은 `section_bar`
  - `hwpx.py new --template report` 동작

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_report_template.py
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from core import owpml
from core.markdown import render_to_section
from core.template import build_from_template, TEMPLATES_DIR
from core.guards import check_package
from core.analyze import extract_text, analyze_document

ROOT = Path(__file__).resolve().parent.parent
NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def test_style_maps_exist_and_generator_idempotent():
    for t in ("base", "report"):
        m = json.loads((TEMPLATES_DIR / t / "styles.json").read_text("utf-8"))
        assert "heading" in m and "table" in m
    files = {p: p.read_bytes() for p in (TEMPLATES_DIR).rglob("*") if p.is_file()}
    subprocess.run([sys.executable, str(ROOT / "scripts/dev/gen_templates.py")], check=True)
    after = {p: p.read_bytes() for p in (TEMPLATES_DIR).rglob("*") if p.is_file()}
    assert files == after
    assert not (ROOT / "scripts/dev/gen_base_template.py").exists()


def test_report_header_has_extra_styles():
    root = ET.fromstring((TEMPLATES_DIR / "report/Contents/header.xml").read_bytes())
    chars = root.find(f".//{{{NS_HH}}}charProperties")
    assert chars.get("itemCnt") == "7"
    c6 = root.find(f".//{{{NS_HH}}}charPr[@id='6']")
    assert c6.get("textColor") == "#FFFFFF"
    bf5 = root.find(f".//{{{NS_HH}}}borderFill[@id='5']")
    assert b"1F3864" in ET.tostring(bf5)


def test_report_markdown_uses_section_bar(tmp_path):
    md = "# 보고서\n\n## 1. 개요\n\n본문\n\n- 항목\n"
    xml = render_to_section(md, template="report")
    out = build_from_template(tmp_path / "r.hwpx", template="report", section_xml=xml,
                              title="보고서")
    assert check_package(out)["ok"]
    doc = analyze_document(out)
    assert doc["sections"][0]["tables"] == [{"index": 0, "rows": 1, "cols": 1}]  # 섹션 바
    text = extract_text(out)
    assert "1. 개요" in text and "• 항목" in text
    assert 'charPrIDRef="5"' in xml          # H1 = report 제목 스타일


def test_base_rendering_unchanged(tmp_path):
    md = "# 제목\n\n## 소제목\n\n본문"
    xml = render_to_section(md, template="base")
    assert 'charPrIDRef="1"' in xml and 'paraPrIDRef="2"' in xml
    assert "<hp:tbl" not in xml
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_report_template.py -v`
Expected: FAIL (styles.json 없음)

- [ ] **Step 3: 생성기 일반화 (scripts/dev/gen_templates.py)**

`gen_base_template.py`를 `git mv scripts/dev/gen_base_template.py scripts/dev/gen_templates.py`로 옮기고 다음을 수정:
- 모듈 docstring: "templates/base, templates/report 생성기".
- `header_xml(extra_border_fills=(), extra_char_prs=(), extra_para_prs=())`로 확장: 기본 항목 뒤에 추가 항목을 붙이고 itemCnt를 실제 개수로 계산.
- `char_pr(cid, height, font=0, bold=False, color="000000")` — `textColor="#{color}"`.
- `border_fill(bid, edge_type, width, fill)` 그대로.
- `main()`:

```python
BASE_STYLES = {
    "heading": {"1": ["1", "1"], "2": ["2", "2"], "default": ["3", "3"]},
    "body": ["0", "0"], "bullet_para": "4",
    "table": {"header_char": "4", "header_border": "4", "body_border": "3",
              "cell_para": "5"},
}
REPORT_STYLES = {
    "heading": {"1": ["5", "1"], "2": ["2", "6"], "default": ["3", "3"]},
    "body": ["0", "0"], "bullet_para": "4",
    "table": {"header_char": "4", "header_border": "4", "body_border": "3",
              "cell_para": "5"},
    "section_bar": {"char": "6", "border": "5"},
}


def write_template(name, header, styles):
    tdir = ROOT / "templates" / name
    files = {
        "mimetype": "application/hwp+zip",
        "version.xml": VERSION_XML,
        "settings.xml": SETTINGS_XML,
        "META-INF/container.xml": CONTAINER_XML,
        "META-INF/manifest.xml": MANIFEST_XML,
        "Contents/content.hpf": CONTENT_HPF,
        "Contents/header.xml": header,
        "Contents/section0.xml": section0_xml(),
        "styles.json": json.dumps(styles, ensure_ascii=False, indent=2) + "\n",
    }
    for rel, text in files.items():
        path = tdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files to {tdir}")


def main():
    write_template("base", header_xml(), BASE_STYLES)
    write_template("report", header_xml(
        extra_border_fills=[border_fill(5, edge_type="SOLID", width="0.12 mm",
                                        fill="1F3864")],
        extra_char_prs=[char_pr(5, 1600, font=1, bold=True),
                        char_pr(6, 1200, font=1, bold=True, color="FFFFFF")],
        extra_para_prs=[para_pr(6, align="LEFT", prev=600, nxt=200)],
    ), REPORT_STYLES)
```

(`import json` 추가. `tests/test_base_template.py`의 생성기 경로를 `scripts/dev/gen_templates.py`로 수정하고, base 파일 목록에 `styles.json`이 추가되므로 idempotency 비교 대상 REQUIRED에 `styles.json`을 넣거나 rglob 방식으로 바꾼다.)

- [ ] **Step 4: owpml/markdown 스타일 맵**

`core/owpml.py`:

```python
import json  # 상단

def load_style_map(template="base"):
    p = TEMPLATES_DIR / template / "styles.json"
    if not p.is_file():
        raise ValueError(f"styles.json 없음: {template}")
    return json.loads(p.read_text("utf-8"))


def heading_para(level, text, alloc, style_map=None):
    if style_map is None:
        char_pr, para_pr = _HEADING_MAP.get(level, ("3", "3"))
    else:
        h = style_map["heading"]
        char_pr, para_pr = h.get(str(level), h["default"])
    return _para(alloc.next(), xml_escape(text), char_pr, para_pr, False)


def section_bar(text, alloc, style_map, total_width=42520, height=1200):
    sb = style_map["section_bar"]
    cell = _cell(0, 0, text, total_width, height, alloc, header_cell=False)
    cell = cell.replace('borderFillIDRef="3"', f'borderFillIDRef="{sb["border"]}"', 1)
    cell = cell.replace('charPrIDRef="0"', f'charPrIDRef="{sb["char"]}"', 1)
    tbl_id = alloc.next()
    return (
        f'<hp:p id="{alloc.next()}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
        f'<hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" '
        f'repeatHeader="0" rowCnt="1" colCnt="1" cellSpacing="0" borderFillIDRef="{sb["border"]}" noAdjust="0">'
        f'<hp:sz width="{total_width}" widthRelTo="ABSOLUTE" height="{height}" heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
        'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="283" bottom="141"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        f'<hp:tr>{cell}</hp:tr></hp:tbl></hp:run></hp:p>')
```

(`_cell`의 시그니처가 `_cell(row, col, text, width, height, alloc, *, header_cell)`임을 확인하고, `header_cell=False`일 때 borderFill "3"/charPr "0"이 문자열에 들어가므로 위 replace가 정확히 한 번 맞는다. `_cell` 출력에 xmlns 선언이 있으면 replace 대상 문자열은 그대로 유지된다.)

`core/markdown.py` `render_to_section`:

```python
def render_to_section(md_text, template="base"):
    first, sec_open = owpml.load_skeleton(template)
    style = owpml.load_style_map(template)
    alloc = owpml.IdAllocator()
    parts = []
    for block in parse_markdown(md_text):
        if block["type"] == "heading":
            if block["level"] == 2 and "section_bar" in style:
                parts.append(owpml.section_bar(block["text"], alloc, style))
            else:
                parts.append(owpml.heading_para(block["level"], block["text"], alloc,
                                                style_map=style))
        elif block["type"] == "paragraph":
            parts.append(owpml.text_para(block["text"], alloc,
                                         char_pr=style["body"][0], para_pr=style["body"][1]))
        elif block["type"] == "bullet":
            for item in block["items"]:
                parts.append(owpml.bullet_para(item, alloc))
        elif block["type"] == "ordered":
            for item in block["items"]:
                parts.append(owpml.text_para(item, alloc, para_pr=style["bullet_para"]))
        elif block["type"] == "table":
            parts.append(owpml.table(block["rows"], alloc))
    return owpml.sec_document(first, parts, sec_open)
```

(`bullet_para`는 paraPr "4" 고정 — base/report 모두 "4"라 그대로 둔다.)

- [ ] **Step 5: 한컴 검증 항목 + 통과 확인 + Commit**

`docs/hancom-verification.md`에 추가:

```markdown
## Phase 5 추가 검증 항목

- [ ] `new --template report` 산출물: 제목 16pt 굵게, `##` 절 제목이 진남색 바 위 흰 글자로 보이는가
- [ ] `from-hwp` 산출물이 원본 .hwp와 동일한 내용/서식으로 열리는가 (rhwp 품질)
```

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add scripts/dev/gen_templates.py templates core/owpml.py core/markdown.py tests/test_report_template.py tests/test_base_template.py docs/hancom-verification.md
git rm -q --cached scripts/dev/gen_base_template.py 2>/dev/null; git add -A scripts/dev
git commit -m "feat: report 템플릿과 템플릿별 스타일 맵

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 문서 갱신 (SKILL.md / README / references)

**Files:**
- Modify: `SKILL.md`, `README.md`, `references/owpml-format.md`(템플릿 스타일 맵 절), `references/base-template-styles.md`(report 스타일 추가)

- [ ] **Step 1: SKILL.md 갱신**

frontmatter description에 "HWP→HWPX 변환(사용자 명시 요청 시)"과 "공문서 검수" 추가. 워크플로우 트리의 `.hwp` 분기를 교체:

```
     ├─ .hwp 파일 + "HWPX로 변환해줘"(명시) → from-hwp → check 통과 후 전달
     ├─ .hwp 파일 + 그 외 요청 → 변환 여부 먼저 확인 (자동 변환 금지)
     ├─ "공문서 작성법 검수/맞춤법 표기 확인" → lint
     ├─ "보고서 양식으로 만들어줘" → new --template report
```

커맨드 블록에 추가:

```markdown
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" from-hwp 원본.hwp -o 변환.hwpx      # Node.js 18+ 필요
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" lint 문서.hwpx                       # 공문서 표기 검수 (JSON)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" new 입력.md -o 결과.hwpx --template report
```

필수 규칙 추가:

```markdown
13. .hwp는 사용자가 HWPX 변환을 명시적으로 요청한 경우에만 from-hwp로 변환한다.
    변환본은 별도 파일이며 원본 .hwp는 건드리지 않는다. Node.js가 없으면 설치를
    안내하고, 다른 커맨드는 그대로 쓸 수 있다.
14. lint는 게이트가 아니다. findings를 요약해 사용자에게 보여주고 수정 여부는
    사용자가 정한다(공문 표기 규칙은 references/gonmun-rules.md).
```

규칙 4(.hwp 미지원 안내)를 위 13과 모순 없이 수정: "읽기·편집은 미지원, 변환은 명시 요청 시 from-hwp".

- [ ] **Step 2: README / references**

README 사용법에 3줄(from-hwp / lint / --template report), 라이선스 절에 "THIRD_PARTY_NOTICES.md 참조 (rhwp MIT 동봉)" 한 줄. `references/base-template-styles.md`에 report 추가 스타일(charPr 5·6, borderFill 5, paraPr 6)과 `styles.json` 설명. `references/owpml-format.md`에 "템플릿 스타일 맵(styles.json)" 절 2~3줄.

- [ ] **Step 3: 전체 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add SKILL.md README.md references/
git commit -m "docs: Phase 5 변환·검수·report 템플릿 워크플로우

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 5 이후

- 한컴 검증(Phase 4·5 항목) 사용자 1회 수행.
- Phase 4b(연기 항목: 각주·하이퍼링크·책갈피·도형·글상자)는 hansol 실물 표본에 해당 구조가 있으면 근거 있게 진행 가능.
- LICENSE 저작권 명의 확정.
