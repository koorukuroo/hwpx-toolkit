# hwpx-toolkit Phase 6 (게이트 완성) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검증 게이트가 "문제를 검출만 하고 끝나는" 구멍을 메운다 — 검출한 결함을 고치는 `fix-borders`, 셀 넘침을 사전 예측하는 수용량 추정, `guard`의 내용 검사 확장, `lint` 규칙 보강.

**Architecture:** 새 모듈 두 개를 추가한다. `core/repair.py`는 `check`가 검출한 사고 패턴을 실제로 고치고(header.xml만 교체, 바이트 보존), `core/capacity.py`는 표 셀의 기하 정보(폭·높이·여백·글자 크기·줄간격)로 수용 가능한 글자 수를 추정한다. 추정값은 `fill --analyze` 타겟에 실려 LLM이 쓰기 전에 여유를 알 수 있게 하고, `check`에서는 경고로 보고한다. `guard`와 `lint`는 기존 함수에 규칙만 추가한다.

**Tech Stack:** Python 3.9+ stdlib (xml.etree, re, copy). pytest.

**Spec:** `docs/superpowers/specs/2026-08-13-hwpx-toolkit-design.md`

## Global Constraints

- 의존성: 코어와 CLI는 Python 3.9+ 표준 라이브러리만 (스펙 §9).
- 클린룸: 다른 스킬의 코드를 복사하지 않는다 (스펙 §2). 이 계획의 아이디어(수용량 추정, placeholder 검사 등)는 기능 개념이며, 구현은 전부 자체 작성이다.
- 바이트 보존: 편집은 변경 엔트리 외 바이트 동일 (스펙 §5) — `write_replaced` 경유 필수.
- 게이트 출력 계약: `check`/`guard`는 `{"ok", "errors", "warnings", ...}`, 편집·수리 CLI는 실패 시 JSON + exit 2 (Phase 3~5 확립).
- **경고는 error가 아니다**: 수용량 초과는 추정이므로 `warnings`에만 넣고 `ok`를 false로 만들지 않는다.
- 테스트: `python3.13 -m pytest tests/ -q` (plain python3에 pytest 없음; venv 금지). 현재 162 passed + 1 skipped 유지.
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- 네임스페이스: hh=`http://www.hancom.co.kr/hwpml/2011/head`, hp=`.../2011/paragraph`.

## 현재 코드 사실 (구현자가 알아야 할 것)

- `core/guards.py`: `validate_package(path)`, `check_package(path)` — `signals` dict는 `{"char_border_bug", "vertical_misconvert", "image_ref_broken"}`, `guard_against_reference(output, reference, *, rules=None, max_growth=None)`.
- `check_package`가 `char_border_bug`를 판정하는 기준: header.xml의 borderFill 중 4변(`leftBorder`/`rightBorder`/`topBorder`/`bottomBorder`) 하나라도 `type`이 `NONE`이 아닌 것을 "실선"으로 보고, charPr의 과반이 그 borderFill을 참조하면 참.
- `core/header.py`: `HeaderEditor(xml_bytes)` — `.root`(ET Element), `.dirty`, `.serialize() -> bytes`, `.from_package(pkg)`. import 시 `core.edit`를 거쳐 ET 네임스페이스 접두사(hh/hp/hs/hc)가 등록된다.
- `core/analyze.py`: `fill_targets(path)`가 label-cell 타겟에 `{"key","kind","label","table","row","col","section"}`을 담는다. `_sections(pkg)`는 `[(name, root)]`, `_q(tag)`는 hp 네임스페이스 수식자.
- `core/lint.py`: `lint_text(text) -> {"findings":[{"rule","line","text","message","suggest"}], "count"}`, 헬퍼 `_add(findings, rule, lineno, text, message, suggest=None)`, `_URL`, `_TIME_OK` 상수 존재.
- `tests/fixture.py`: `build_form_hwpx(path)` — 2×2 표(cellSz width=21260 height=2400, cellMargin 141 사방), charPr 0 height=1000, paraPr 0 lineSpacing 160%.

---

### Task 1: core/repair.py — fix-borders

**Files:**
- Create: `core/repair.py`
- Modify: `scripts/hwpx.py`
- Test: `tests/test_repair.py`

**Interfaces:**
- Consumes: `HwpxPackage.write_replaced`, `core.header.HeaderEditor`, `core.errors.PackageError`
- Produces:
  - `repair.fix_char_borders(src, dst) -> dict` — `{"changed": bool, "fixed": int, "borderfill_id": str, "created": bool}`.
    - header.xml의 borderFill 중 4변이 모두 `NONE`인 것을 찾아 "테두리 없음" id로 삼는다. 없으면 첫 borderFill을 복제해 4변을 `NONE`으로 바꿔 추가하고 `itemCnt`를 보정한다(`created: true`).
    - 실선 borderFill을 참조하는 모든 charPr의 `borderFillIDRef`를 그 id로 바꾼다. 바꾼 개수가 `fixed`.
    - 고칠 게 없어도 `dst`는 항상 만든다(`changed: false`, 원본과 바이트 동일).
    - borderFills 컬렉션이나 borderFill이 하나도 없으면 `PackageError`.
  - CLI: `fix-borders <src> <dst>` — 수리 후 `check_package(dst)` 실행, `{"ok", "output", "report", "gate"}` 출력, gate ok면 exit 0 아니면 2.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_repair.py
import xml.etree.ElementTree as ET
import zipfile
import pytest
from core.errors import PackageError
from core.package import HwpxPackage
from core.guards import check_package
from core.repair import fix_char_borders
from tests.fixture import build_minimal_hwpx

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _make_bordered(tmp_path, name="bad.hwpx"):
    """charPr 0이 실선 borderFill을 참조하도록 조작한 문서."""
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    pkg = HwpxPackage.open(src)
    header = pkg.read_text("Contents/header.xml").replace(
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>',
        '<hh:leftBorder type="SOLID" width="0.1 mm" color="#000000"/>')
    bad = tmp_path / name
    pkg.write_replaced(bad, {"Contents/header.xml": header.encode("utf-8")})
    return bad


def test_check_detects_then_repair_fixes(tmp_path):
    bad = _make_bordered(tmp_path)
    assert check_package(bad)["signals"]["char_border_bug"] is True

    out = tmp_path / "fixed.hwpx"
    report = fix_char_borders(bad, out)
    assert report["changed"] is True
    assert report["fixed"] >= 1
    assert report["created"] is True          # 픽스처엔 무테두리 borderFill이 없음

    after = check_package(out)
    assert after["signals"]["char_border_bug"] is False
    assert after["ok"], after["errors"]


def test_repair_adds_borderless_fill_and_fixes_itemcnt(tmp_path):
    bad = _make_bordered(tmp_path)
    out = tmp_path / "fixed.hwpx"
    report = fix_char_borders(bad, out)
    root = ET.fromstring(HwpxPackage.open(out).read("Contents/header.xml"))
    coll = root.find(f".//{{{NS_HH}}}borderFills")
    fills = coll.findall(f"{{{NS_HH}}}borderFill")
    assert coll.get("itemCnt") == str(len(fills))
    new = [b for b in fills if b.get("id") == report["borderfill_id"]][0]
    for edge in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
        assert new.find(f"{{{NS_HH}}}{edge}").get("type") == "NONE"
    for cp in root.iter(f"{{{NS_HH}}}charPr"):
        assert cp.get("borderFillIDRef") == report["borderfill_id"]


def test_repair_preserves_other_entries(tmp_path):
    bad = _make_bordered(tmp_path)
    out = tmp_path / "fixed.hwpx"
    fix_char_borders(bad, out)
    with zipfile.ZipFile(bad) as a, zipfile.ZipFile(out) as b:
        for name in a.namelist():
            if name == "Contents/header.xml":
                continue
            assert a.read(name) == b.read(name), name


def test_repair_noop_on_clean_document(tmp_path):
    clean = build_minimal_hwpx(tmp_path / "clean.hwpx")
    out = tmp_path / "same.hwpx"
    report = fix_char_borders(clean, out)
    assert report["changed"] is False and report["fixed"] == 0
    assert out.read_bytes() == clean.read_bytes()      # 완전 동일 복사


def test_repair_rejects_header_without_borderfills(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    pkg = HwpxPackage.open(src)
    header = pkg.read_text("Contents/header.xml")
    start = header.index("<hh:borderFills")
    end = header.index("</hh:borderFills>") + len("</hh:borderFills>")
    broken = tmp_path / "broken.hwpx"
    pkg.write_replaced(broken, {"Contents/header.xml":
                                (header[:start] + header[end:]).encode("utf-8")})
    with pytest.raises(PackageError):
        fix_char_borders(broken, tmp_path / "x.hwpx")


def test_cli_fix_borders(tmp_path, capsys):
    import json
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    bad = _make_bordered(tmp_path)
    out = tmp_path / "cli.hwpx"
    rc = hwpx_cli.main(["fix-borders", str(bad), str(out)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    assert payload["report"]["fixed"] >= 1
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_repair.py -v`
Expected: FAIL (`ModuleNotFoundError: core.repair`)

- [ ] **Step 3: core/repair.py 구현**

```python
# core/repair.py
"""문서 복구 — check가 검출한 사고 패턴을 실제로 고친다."""
import copy

from core.errors import PackageError
from core.header import HeaderEditor, NS_HH
from core.package import HwpxPackage

_EDGES = ("leftBorder", "rightBorder", "topBorder", "bottomBorder")


def _h(tag):
    return f"{{{NS_HH}}}{tag}"


def _is_borderless(bf):
    for edge in _EDGES:
        e = bf.find(_h(edge))
        if e is not None and e.get("type") not in (None, "NONE"):
            return False
    return True


def fix_char_borders(src, dst):
    """글자마다 테두리가 그려지는 charPr borderFill 참조를 무테두리로 되돌린다."""
    pkg = HwpxPackage.open(src)
    he = HeaderEditor.from_package(pkg)
    coll = he.root.find(f".//{_h('borderFills')}")
    if coll is None:
        raise PackageError("header.xml에 borderFills 컬렉션이 없음")
    fills = coll.findall(_h("borderFill"))
    if not fills:
        raise PackageError("header.xml에 borderFill 정의가 없음")

    solid = {bf.get("id") for bf in fills if not _is_borderless(bf)}
    plain = next((bf.get("id") for bf in fills if _is_borderless(bf)), None)
    created = False
    if plain is None:
        new = copy.deepcopy(fills[0])
        next_id = max((int(b.get("id")) for b in fills
                       if (b.get("id") or "").isdigit()), default=0) + 1
        new.set("id", str(next_id))
        for edge in _EDGES:
            e = new.find(_h(edge))
            if e is not None:
                e.set("type", "NONE")
        coll.append(new)
        coll.set("itemCnt", str(len(coll.findall(_h("borderFill")))))
        plain = new.get("id")
        created = True

    fixed = 0
    for cp in he.root.iter(_h("charPr")):
        if cp.get("borderFillIDRef") in solid:
            cp.set("borderFillIDRef", plain)
            fixed += 1

    changed = bool(fixed or created)
    replacements = {"Contents/header.xml": he.serialize()} if changed else {}
    pkg.write_replaced(dst, replacements)
    return {"changed": changed, "fixed": fixed, "borderfill_id": plain,
            "created": created}
```

주의: `core/header.py`는 모듈 수준에 `NS_HH`를 정의하고 있으므로(`core/header.py:8`) 위 import가 그대로 동작한다. 무테두리 borderFill을 새로 만들었지만 고칠 charPr이 없는 경우(`fixed == 0`, `created == True`)에도 header가 바뀌므로 `changed`는 True다 — 위 코드가 그렇게 되어 있다.

- [ ] **Step 4: CLI 구현 (scripts/hwpx.py)**

상단 import에 추가:

```python
from core import repair as repair_mod
```

커맨드 함수와 파서:

```python
def cmd_fix_borders(args):
    report = repair_mod.fix_char_borders(args.src, args.dst)
    return _finish_edited(args.dst, report)

# build_parser() 안:
    fb = sub.add_parser("fix-borders", help="글자 테두리 버그 수리 (check 검출 시)")
    fb.add_argument("src")
    fb.add_argument("dst")
    fb.set_defaults(func=cmd_fix_borders)
```

(`_finish_edited(dst, report)`는 이미 `check_package`를 게이트로 쓰고 `{"ok","output","report","gate"}`를 출력한다.)

- [ ] **Step 5: 통과 확인**

Run: `python3.13 -m pytest tests/test_repair.py tests/ -q`
Expected: 전체 green (162 + 6)

- [ ] **Step 6: Commit**

```bash
git add core/repair.py scripts/hwpx.py tests/test_repair.py
git commit -m "feat: fix-borders — 글자 테두리 버그 수리

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: core/capacity.py — 셀 수용량 추정과 넘침 경고

**Files:**
- Create: `core/capacity.py`
- Modify: `core/analyze.py` (fill_targets의 label-cell 타겟에 `capacity` 추가)
- Modify: `core/guards.py` (check_package에 넘침 경고)
- Test: `tests/test_capacity.py`

**Interfaces:**
- Consumes: `HwpxPackage`, `analyze._sections`, `analyze._q`, `analyze._para_direct_text`
- Produces:
  - `capacity.estimate_chars(cell_w, cell_h, margins, font_hwp, line_spacing_pct) -> int`
    - `margins`는 `{"left","right","top","bottom"}` (HWPUNIT). 한 글자 폭은 한글 전각 기준 글자 높이와 같다고 본다(함초롬 계열 한글 글리프는 em 정사각형). 줄 높이는 글자 높이 × 줄간격%.
    - `chars_per_line = max(1, 가용폭 // 글자폭)`, `lines = max(1, 가용높이 // 줄높이)`, 반환값 = 둘의 곱. 폰트 크기가 0 이하이면 `0`을 반환(추정 불가).
  - `capacity.cell_report(path) -> {"cells": [...]}` — 각 셀에 대해
    `{"section","table","row","col","capacity","used","over": bool}`.
    `used`는 셀 전체 텍스트의 **공백 제외** 글자 수. `over`는 `used > capacity * OVER_MARGIN`(`OVER_MARGIN = 1.15`, 추정 오차 여유). `capacity == 0`이면 `over`는 항상 False.
  - `capacity.for_cell(path, table, row, col, section=None) -> int | None` — 특정 셀의 추정치(없으면 None). `fill_targets`가 사용.
  - `analyze.fill_targets`의 label-cell 타겟에 `"capacity": int` 추가 (값 셀 기준).
  - `guards.check_package`의 `warnings`에 `cell-overflow-risk: 표 T (R,C) 추정 수용 N자 < 실제 M자` 추가. 최대 20건까지 나열하고 초과분은 `cell-overflow-risk: 외 K건 더` 한 줄로 요약. `errors`에는 넣지 않는다(ok 불변).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_capacity.py
from core.capacity import estimate_chars, cell_report, for_cell, OVER_MARGIN
from core.analyze import fill_targets
from core.guards import check_package
from core.edit import edit_file
from tests.fixture import build_form_hwpx, build_minimal_hwpx

M141 = {"left": 141, "right": 141, "top": 141, "bottom": 141}


def test_estimate_basic_geometry():
    # 폭 21260, 높이 2400, 여백 141 사방, 10pt(1000), 줄간격 160%
    # 가용폭 20978 // 1000 = 20자/줄, 가용높이 2118 // 1600 = 1줄 → 20
    assert estimate_chars(21260, 2400, M141, 1000, 160) == 20


def test_estimate_multiline_and_guards():
    # 높이를 3배로 → 줄 수 증가
    assert estimate_chars(21260, 7200, M141, 1000, 160) == 20 * 4
    # 아주 좁아도 최소 1자 1줄
    assert estimate_chars(300, 300, M141, 1000, 160) == 1
    # 폰트 크기 불명 → 추정 불가
    assert estimate_chars(21260, 2400, M141, 0, 160) == 0


def test_cell_report_on_form_fixture(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    cells = cell_report(p)["cells"]
    assert len(cells) == 4                       # 2×2 표
    first = next(c for c in cells if (c["row"], c["col"]) == (0, 0))
    assert first["capacity"] == 20
    assert first["used"] == 2                    # "성명"
    assert first["over"] is False
    assert first["table"] == 0


def test_for_cell_lookup(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    assert for_cell(p, 0, 0, 1) == 20
    assert for_cell(p, 5, 0, 0) is None


def test_fill_targets_carry_capacity(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    labels = [t for t in fill_targets(p)["targets"] if t["kind"] == "label-cell"]
    assert labels and all(t["capacity"] == 20 for t in labels)


def test_overflow_detected_and_reported_as_warning(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "over.hwpx"
    long_text = "가" * 60                        # 추정 20자 셀에 60자
    edit_file(src, dst, lambda ed: ed.set_cell_text(0, 0, 1, long_text))

    cells = cell_report(dst)["cells"]
    target = next(c for c in cells if (c["row"], c["col"]) == (0, 1))
    assert target["used"] == 60 and target["over"] is True

    r = check_package(dst)
    assert r["ok"] is True                       # 경고이지 오류가 아님
    assert any(w.startswith("cell-overflow-risk") for w in r["warnings"])


def test_no_false_overflow_on_clean_fixtures(tmp_path):
    for p in (build_form_hwpx(tmp_path / "f.hwpx"),
              build_minimal_hwpx(tmp_path / "m.hwpx", with_table=True)):
        r = check_package(p)
        assert not [w for w in r["warnings"] if w.startswith("cell-overflow-risk")]


def test_margin_constant_is_lenient():
    assert OVER_MARGIN >= 1.1
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_capacity.py -v`
Expected: FAIL (`ModuleNotFoundError: core.capacity`)

- [ ] **Step 3: core/capacity.py 구현**

```python
# core/capacity.py
"""표 셀 수용량 추정 — 폭·높이·여백·글자 크기·줄간격으로 들어갈 글자 수를 가늠한다.

한글(함초롬 계열) 글리프는 em 정사각형에 가까워 글자 폭 ≈ 글자 높이로 본다.
줄 높이는 글자 높이 × 문단 줄간격(%)이다. 추정이므로 결과는 경고에만 쓴다.
"""
import re
import xml.etree.ElementTree as ET

from core.analyze import _para_direct_text, _q, _sections
from core.package import HwpxPackage

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"

#: 추정 오차 여유 — 실제 글자 수가 추정치의 이 배수를 넘어야 경고한다.
OVER_MARGIN = 1.15

_DEFAULT_LINE_SPACING = 160


def estimate_chars(cell_w, cell_h, margins, font_hwp, line_spacing_pct):
    if not font_hwp or font_hwp <= 0:
        return 0
    usable_w = int(cell_w) - int(margins.get("left", 0)) - int(margins.get("right", 0))
    usable_h = int(cell_h) - int(margins.get("top", 0)) - int(margins.get("bottom", 0))
    glyph_w = int(font_hwp)
    line_h = max(1, int(round(font_hwp * (line_spacing_pct or 100) / 100)))
    per_line = max(1, usable_w // glyph_w)
    lines = max(1, usable_h // line_h)
    return per_line * lines


def _style_maps(pkg):
    """header.xml에서 charPr id → 글자 높이, paraPr id → 줄간격(%)."""
    root = ET.fromstring(pkg.read("Contents/header.xml"))
    chars, paras = {}, {}
    for cp in root.iter(f"{{{NS_HH}}}charPr"):
        h = cp.get("height")
        if cp.get("id") is not None and h and h.isdigit():
            chars[cp.get("id")] = int(h)
    for pp in root.iter(f"{{{NS_HH}}}paraPr"):
        ls = next(iter(pp.iter(f"{{{NS_HH}}}lineSpacing")), None)
        if pp.get("id") is not None:
            value = ls.get("value") if ls is not None else None
            paras[pp.get("id")] = (int(value) if value and value.isdigit()
                                   else _DEFAULT_LINE_SPACING)
    return chars, paras


def _int_attr(el, name, default=0):
    if el is None:
        return default
    v = el.get(name)
    return int(v) if v and v.lstrip("-").isdigit() else default


def cell_report(path):
    pkg = HwpxPackage.open(path)
    chars, paras = _style_maps(pkg)
    out = []
    for name, root in _sections(pkg):
        table_index = 0
        for p in root.findall(_q("p")):
            tbls = [t for run in p.findall(_q("run"))
                    for t in run.findall(_q("tbl"))]
            if not tbls:
                continue
            for tbl in tbls:
                for tc in tbl.iter(_q("tc")):
                    addr = tc.find(_q("cellAddr"))
                    if addr is None:
                        continue
                    sz = tc.find(_q("cellSz"))
                    margin_el = tc.find(_q("cellMargin"))
                    margins = {k: _int_attr(margin_el, k)
                               for k in ("left", "right", "top", "bottom")}
                    sub = tc.find(_q("subList"))
                    cell_paras = sub.findall(_q("p")) if sub is not None else []
                    text = " ".join(_para_direct_text(cp) for cp in cell_paras)
                    font = 0
                    spacing = _DEFAULT_LINE_SPACING
                    if cell_paras:
                        first = cell_paras[0]
                        spacing = paras.get(first.get("paraPrIDRef"),
                                            _DEFAULT_LINE_SPACING)
                        run = first.find(_q("run"))
                        if run is not None:
                            font = chars.get(run.get("charPrIDRef"), 0)
                    capacity = estimate_chars(_int_attr(sz, "width"),
                                              _int_attr(sz, "height"),
                                              margins, font, spacing)
                    used = len(re.sub(r"\s", "", text))
                    out.append({
                        "section": name, "table": table_index,
                        "row": _int_attr(addr, "rowAddr"),
                        "col": _int_attr(addr, "colAddr"),
                        "capacity": capacity, "used": used,
                        "over": bool(capacity and used > capacity * OVER_MARGIN),
                    })
                table_index += 1
    return {"cells": out}


def for_cell(path, table, row, col, section=None):
    for c in cell_report(path)["cells"]:
        if (c["table"] == table and c["row"] == row and c["col"] == col
                and (section is None or c["section"] == section)):
            return c["capacity"]
    return None
```

주의: `_sections`/`_q`/`_para_direct_text`는 `core/analyze.py`의 밑줄 헬퍼다. `core.capacity`가 `core.analyze`를 import하고, Step 4에서 `core.analyze`가 `core.capacity`를 import하면 순환이 된다 — 그래서 Step 4의 `fill_targets`는 **함수 안에서 지역 import**한다(계획대로 구현할 것).

- [ ] **Step 4: fill_targets에 capacity 싣기 (core/analyze.py)**

`fill_targets` 안, label-cell 타겟을 append하는 부분을 수정한다. 함수 시작부에 지역 import를 두고(순환 회피), 섹션 루프 전에 셀 보고를 한 번만 만들어 조회한다:

```python
def fill_targets(path):
    from core.capacity import cell_report          # 순환 import 회피
    caps = {(c["section"], c["table"], c["row"], c["col"]): c["capacity"]
            for c in cell_report(path)["cells"]}
    pkg = HwpxPackage.open(path)
    ...
                            targets.append({
                                "key": _norm_label(cell_text),
                                "kind": "label-cell", "label": cell_text,
                                "table": table_index, "row": r, "col": c + 1,
                                "section": name,
                                "capacity": caps.get((name, table_index, r, c + 1), 0)})
```

- [ ] **Step 5: check_package에 넘침 경고 (core/guards.py)**

`check_package`의 try 블록 안, 이미지 참조 검사 뒤에 추가한다:

```python
        from core.capacity import cell_report      # 순환 import 회피
        over = [c for c in cell_report(path)["cells"] if c["over"]]
        for c in over[:20]:
            warnings.append(
                f"cell-overflow-risk: 표 {c['table']} ({c['row']},{c['col']}) "
                f"추정 수용 {c['capacity']}자 < 실제 {c['used']}자")
        if len(over) > 20:
            warnings.append(f"cell-overflow-risk: 외 {len(over) - 20}건 더")
```

- [ ] **Step 6: 통과 확인 + 실물 노이즈 점검**

Run: `python3.13 -m pytest tests/test_capacity.py tests/ -q` → 전체 green

실제 변환 문서에서 경고가 과도하지 않은지 확인한다(표 43개 문서):

```bash
python3 scripts/hwpx.py from-hwp "<샘플 .hwp 경로>" -o /private/tmp/p6.hwpx >/dev/null
python3 scripts/hwpx.py check /private/tmp/p6.hwpx | python3 -c "
import json,sys
d=json.load(sys.stdin)
w=[x for x in d['warnings'] if x.startswith('cell-overflow-risk')]
print('ok:', d['ok'], '| 넘침 경고:', len(w))
for line in w[:5]: print(' ', line)
"
```

경고가 셀 총수의 30%를 넘으면 `OVER_MARGIN`을 1.3으로 올리고 테스트의 `test_margin_constant_is_lenient`가 여전히 통과하는지 확인한 뒤 그 값으로 커밋한다. 조정했다면 보고서에 근거(셀 총수/경고 수)를 남긴다.

- [ ] **Step 7: Commit**

```bash
git add core/capacity.py core/analyze.py core/guards.py tests/test_capacity.py
git commit -m "feat: 셀 수용량 추정과 넘침 경고

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: guard 내용 검사 확장

**Files:**
- Modify: `core/guards.py` (`guard_against_reference`)
- Modify: `scripts/hwpx.py` (guard 플래그 추가)
- Test: `tests/test_guard_content.py`

**Interfaces:**
- Consumes: 기존 `guard_against_reference(output, reference, *, rules=None, max_growth=None)`
- Produces:
  - `guard_against_reference(output, reference, *, rules=None, max_growth=None, max_unchanged_ratio=None, no_default_placeholders=False) -> dict`
    - rules에 `require_regex`(리스트) 지원 — 매치 없으면 `require-regex-missing: <pat>`.
    - rules에 `placeholder_regex`(리스트) 지원 — 기본 패턴에 추가.
    - **기본 placeholder 패턴**(`no_default_placeholders=True`면 생략): `○` 2자 이상 연속, `{{...}}`, `<<...>>`, 단어 `TODO`, 단어 `TBD`, `. . .`(공백 낀 말줄임). 매치 시 `placeholder-found: <패턴> → <매치 텍스트>`.
    - `max_unchanged_ratio`가 주어지면: 출력 텍스트의 "긴 줄"(공백 제거 12자 이상)을 공백 정규화해 레퍼런스의 같은 기준 줄 집합과 대조, 그대로인 비율이 임계값을 넘으면 `unchanged-too-high: 0.82 > 0.35`. 긴 줄이 하나도 없으면 검사하지 않는다.
    - 반환 dict에 `"unchanged_ratio": float | None` 추가.
  - CLI: `guard`에 `--max-unchanged-ratio FLOAT`, `--no-default-placeholders` 추가.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_guard_content.py
import json
from core.guards import guard_against_reference
from core.edit import edit_file
from tests.fixture import build_minimal_hwpx


def _doc(tmp_path, name, texts):
    return build_minimal_hwpx(tmp_path / name, body_texts=texts)


def test_default_placeholders_detected(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["기관명 자리"])
    out = _doc(tmp_path, "out.hwpx", ["기관명 ○○○○ 확인", "담당 {{name}}", "TODO 확인"])
    r = guard_against_reference(out, ref)
    found = " ".join(e for e in r["errors"] if e.startswith("placeholder-found"))
    assert "○" in found and "{{name}}" in found and "TODO" in found
    assert r["ok"] is False


def test_default_placeholders_can_be_disabled(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["기관명 자리"])
    out = _doc(tmp_path, "out.hwpx", ["담당 {{name}}"])
    r = guard_against_reference(out, ref, no_default_placeholders=True)
    assert not [e for e in r["errors"] if e.startswith("placeholder-found")]


def test_extra_placeholder_regex(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["본문"])
    out = _doc(tmp_path, "out.hwpx", ["금액 XXX원"])
    r = guard_against_reference(out, ref, rules={"placeholder_regex": [r"X{3,}"]})
    assert any(e.startswith("placeholder-found") for e in r["errors"])


def test_require_regex(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["본문"])
    out = _doc(tmp_path, "out.hwpx", ["2026. 8. 16. 시행"])
    ok = guard_against_reference(out, ref,
                                 rules={"require_regex": [r"\d{4}\. \d{1,2}\. \d{1,2}\."]})
    assert not [e for e in ok["errors"] if e.startswith("require-regex-missing")]
    bad = guard_against_reference(out, ref, rules={"require_regex": [r"별지 제\d+호"]})
    assert any(e.startswith("require-regex-missing") for e in bad["errors"])


def test_unchanged_ratio_flags_lazy_rewrite(tmp_path):
    long_a = "이것은 충분히 긴 첫 번째 문장입니다"
    long_b = "이것은 충분히 긴 두 번째 문장입니다"
    long_c = "이것은 충분히 긴 세 번째 문장입니다"
    ref = _doc(tmp_path, "ref.hwpx", [long_a, long_b, long_c])
    lazy = tmp_path / "lazy.hwpx"
    edit_file(ref, lazy, lambda ed: ed.replace_text({long_a: "완전히 새로 쓴 첫 문장입니다"}))

    r = guard_against_reference(lazy, ref, max_unchanged_ratio=0.35)
    assert r["unchanged_ratio"] > 0.35
    assert any(e.startswith("unchanged-too-high") for e in r["errors"])

    lenient = guard_against_reference(lazy, ref, max_unchanged_ratio=0.9)
    assert not [e for e in lenient["errors"] if e.startswith("unchanged-too-high")]


def test_unchanged_ratio_absent_when_not_requested(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["본문"])
    r = guard_against_reference(ref, ref)
    assert r["unchanged_ratio"] is None


def test_cli_guard_new_flags(tmp_path, capsys):
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    ref = _doc(tmp_path, "ref.hwpx", ["담당 {{name}}"])
    rc = hwpx_cli.main(["guard", str(ref), "--reference", str(ref),
                        "--no-default-placeholders"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_guard_content.py -v`
Expected: FAIL (`TypeError: unexpected keyword argument 'no_default_placeholders'`)

- [ ] **Step 3: 구현 (core/guards.py)**

모듈 상단에 기본 패턴 상수를 추가한다:

```python
_DEFAULT_PLACEHOLDERS = [
    r"○{2,}",
    r"\{\{[^}]*\}\}",
    r"<<[^>]*>>",
    r"\bTODO\b",
    r"\bTBD\b",
    r"\.\s\.\s\.",
]
_LONG_LINE_MIN = 12


def _long_lines(text):
    out = set()
    for line in text.splitlines():
        norm = " ".join(line.split())
        if len(re.sub(r"\s", "", norm)) >= _LONG_LINE_MIN:
            out.add(norm)
    return out
```

`guard_against_reference` 시그니처와 본문을 확장한다(기존 엔트리/require/forbid/growth 로직은 그대로 두고 아래를 추가):

```python
def guard_against_reference(output, reference, *, rules=None, max_growth=None,
                            max_unchanged_ratio=None,
                            no_default_placeholders=False):
    ...
    # 기존 require / forbid / forbid_regex 뒤에 추가
    for pat in rules.get("require_regex", []):
        if not re.search(pat, text):
            errors.append(f"require-regex-missing: {pat}")

    patterns = list(rules.get("placeholder_regex", []))
    if not no_default_placeholders:
        patterns = _DEFAULT_PLACEHOLDERS + patterns
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            errors.append(f"placeholder-found: {pat} → {m.group(0)[:30]}")

    unchanged_ratio = None
    if max_unchanged_ratio is not None:
        ref_lines = _long_lines(extract_text(reference))
        out_lines = [ln for ln in _long_lines(text)]
        if out_lines:
            same = sum(1 for ln in out_lines if ln in ref_lines)
            unchanged_ratio = round(same / len(out_lines), 3)
            if unchanged_ratio > max_unchanged_ratio:
                errors.append(
                    f"unchanged-too-high: {unchanged_ratio} > {max_unchanged_ratio}")
    ...
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "growth": round(growth, 3), "unchanged_ratio": unchanged_ratio}
```

- [ ] **Step 4: CLI 플래그 (scripts/hwpx.py)**

```python
def cmd_guard(args):
    rules = json.loads(_read_text_utf8(args.rules)) if args.rules else None
    result = guards.guard_against_reference(
        args.output, args.reference, rules=rules, max_growth=args.max_growth,
        max_unchanged_ratio=args.max_unchanged_ratio,
        no_default_placeholders=args.no_default_placeholders)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2

# build_parser()의 guard 파서에 추가:
    g.add_argument("--max-unchanged-ratio", type=float, default=None,
                   help="원문 그대로인 긴 줄 비율 상한 (전면 재작성 검사)")
    g.add_argument("--no-default-placeholders", action="store_true",
                   help="기본 placeholder 패턴 검사 끄기")
```

- [ ] **Step 5: 통과 확인 + Commit**

Run: `python3.13 -m pytest tests/test_guard_content.py tests/ -q` → 전체 green

```bash
git add core/guards.py scripts/hwpx.py tests/test_guard_content.py
git commit -m "feat: guard placeholder·require_regex·unchanged 비율 검사

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: lint 규칙 6종 추가

**Files:**
- Modify: `core/lint.py`
- Modify: `references/gonmun-rules.md`
- Test: `tests/test_lint_rules.py`

**Interfaces:**
- Consumes: `lint._add`, `lint._URL`, `lint._TIME_OK`
- Produces: `lint_text`가 아래 규칙을 추가로 보고한다(기존 7규칙 동작 불변).

| rule | 검출 | suggest |
|------|------|---------|
| `date-padding` | `2026. 01. 05.`처럼 월/일이 0으로 시작(2자리) | `2026. 1. 5.` |
| `year-2digit` | `26. 8. 16.`처럼 2자리 연도로 시작하는 날짜 | `20%s. 8. 16.` 형태 안내(연도 4자리) |
| `amount-abbrev` | 금액 단위 약어 `천원`·`백만원`·`억원` 사용 | 아라비아 숫자 전액 표기 안내(suggest 없음) |
| `attach-colon` | `붙임:` 또는 `붙임 :` | `붙임  ` (콜론 없이 두 칸) |
| `range-redundant` | `~`/`∼` 범위와 `까지` 동시 사용 | 둘 중 하나만 |
| `foreign-order` | 영문 약어 뒤 괄호 안 한글(`AI(인공지능)`) | `인공지능(AI)` |

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_lint_rules.py
from core.lint import lint_text


def _rules(text):
    return {f["rule"] for f in lint_text(text)["findings"]}


def _find(text, rule):
    return next(f for f in lint_text(text)["findings"] if f["rule"] == rule)


def test_date_padding():
    assert "date-padding" in _rules("접수 2026. 01. 05. 마감")
    assert _find("접수 2026. 01. 05. 마감", "date-padding")["suggest"] == "2026. 1. 5."
    assert "date-padding" not in _rules("접수 2026. 1. 5. 마감")


def test_year_2digit():
    assert "year-2digit" in _rules("26. 8. 16. 개최")
    assert "year-2digit" not in _rules("2026. 8. 16. 개최")
    assert "year-2digit" not in _rules("14:30 개최")


def test_amount_abbrev():
    assert "amount-abbrev" in _rules("예산 1,500천원 지원")
    assert "amount-abbrev" in _rules("총 30억원 규모")
    assert "amount-abbrev" not in _rules("금1,500,000원(금일백오십만원)")


def test_attach_colon():
    assert "attach-colon" in _rules("붙임: 사업계획서 1부.  끝.")
    assert "attach-colon" in _rules("붙임 : 사업계획서 1부.  끝.")
    assert "attach-colon" not in _rules("붙임  사업계획서 1부.  끝.")


def test_range_redundant():
    assert "range-redundant" in _rules("2026. 8. 1.~2026. 8. 16.까지 접수")
    assert "range-redundant" not in _rules("2026. 8. 1.~2026. 8. 16. 접수")
    assert "range-redundant" not in _rules("2026. 8. 16.까지 접수")


def test_foreign_order():
    assert "foreign-order" in _rules("AI(인공지능) 기반 서비스")
    assert _find("AI(인공지능) 기반", "foreign-order")["suggest"] == "인공지능(AI)"
    assert "foreign-order" not in _rules("인공지능(AI) 기반 서비스")
    assert "foreign-order" not in _rules("http://a.kr/AI(x) 참고")


def test_existing_rules_unaffected():
    assert "date-format" in _rules("회의는 2026.8.16 개최")
    assert "colon-spacing" in _rules("성명 : 홍길동")
    assert "end-mark" in _rules("본문입니다")
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_lint_rules.py -v`
Expected: FAIL (새 rule 이름이 findings에 없음)

- [ ] **Step 3: 구현 (core/lint.py)**

상단 상수에 추가:

```python
_DATE_PADDED = re.compile(r"\b(\d{4})\.\s*(0\d|\d{1,2})\.\s*(0\d|\d{1,2})\.")
_YEAR_2DIGIT = re.compile(r"(?<![\d:.])(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.")
_AMOUNT_ABBREV = re.compile(r"[\d,]+\s*(천원|백만원|억원|만원)")
_ATTACH_COLON = re.compile(r"붙임\s*:")
_RANGE_TILDE = re.compile(r"[~∼]")
_FOREIGN_ORDER = re.compile(r"(?<![\w/])([A-Z]{2,})\(([가-힣]{2,})\)")
```

`lint_text`의 줄 루프 안(기존 날짜 검사 뒤)에 추가한다. URL은 이미 만들어 둔 `line_no_url`을 재사용한다:

```python
        for m in _DATE_PADDED.finditer(line):
            y, mo, d = m.group(1), m.group(2), m.group(3)
            if mo.startswith("0") or d.startswith("0"):
                _add(findings, "date-padding", i, line,
                     "월·일은 0을 붙이지 않는다",
                     f"{y}. {int(mo)}. {int(d)}.")
        for m in _YEAR_2DIGIT.finditer(line):
            _add(findings, "year-2digit", i, line,
                 "연도는 4자리로 쓴다", f"20{m.group(1)}. {int(m.group(2))}. {int(m.group(3))}.")
        for m in _AMOUNT_ABBREV.finditer(line):
            _add(findings, "amount-abbrev", i, line,
                 f"금액 단위 약어('{m.group(1)}') 대신 아라비아 숫자로 전액 표기")
        if _ATTACH_COLON.search(line):
            _add(findings, "attach-colon", i, line,
                 "'붙임' 뒤에는 쌍점 없이 두 칸 띄운다", "붙임  ")
        if _RANGE_TILDE.search(line) and "까지" in line:
            _add(findings, "range-redundant", i, line,
                 "물결표 범위와 '까지'는 함께 쓰지 않는다")
        for m in _FOREIGN_ORDER.finditer(line_no_url):
            _add(findings, "foreign-order", i, line,
                 "한글을 먼저 쓰고 외국어를 괄호 안에 넣는다",
                 f"{m.group(2)}({m.group(1)})")
```

주의: `line_no_url`은 기존 쌍점 검사가 쓰는 변수로 `core/lint.py:63`에서 만들어진다. `foreign-order` 검사는 그 줄보다 **뒤에** 두어야 한다. 나머지 5개 규칙은 `line`을 쓰므로 위치 제약이 없다.

- [ ] **Step 4: references/gonmun-rules.md 갱신**

기존 규칙 표에 6줄을 추가한다:

```markdown
| date-padding | 월·일에 0을 붙이지 않음 | `2026. 1. 5.` |
| year-2digit | 연도는 4자리 | `2026. 8. 16.` |
| amount-abbrev | 금액은 단위 약어 없이 아라비아 숫자 전액 | `1,500,000원` |
| attach-colon | `붙임` 뒤 쌍점 없이 두 칸 | `붙임  계획서 1부.` |
| range-redundant | 물결표 범위와 `까지` 중복 금지 | `8. 1.~8. 16.` |
| foreign-order | 한글 먼저, 외국어는 괄호 안 | `인공지능(AI)` |
```

- [ ] **Step 5: 통과 확인 + 실물 재확인**

Run: `python3.13 -m pytest tests/test_lint_rules.py tests/ -q` → 전체 green

실제 변환 문서에서 규칙별 건수를 확인해 오탐이 급증하지 않는지 본다:

```bash
python3 scripts/hwpx.py lint /private/tmp/p6.hwpx | python3 -c "
import json,sys,collections
d=json.load(sys.stdin)
print('총', d['count'], collections.Counter(f['rule'] for f in d['findings']))
"
```

새 규칙 중 한 규칙이 단독으로 30건을 넘으면 그 규칙의 정규식을 좁히고(예: `foreign-order`에서 널리 쓰이는 약어 화이트리스트 제외) 근거를 보고서에 남긴다.

- [ ] **Step 6: Commit**

```bash
git add core/lint.py references/gonmun-rules.md tests/test_lint_rules.py
git commit -m "feat: lint 규칙 6종 추가 (날짜 0패딩·2자리 연도·금액 약어·붙임 콜론·범위 중복·외래어 순서)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 문서 갱신

**Files:**
- Modify: `SKILL.md`, `README.md`

- [ ] **Step 1: SKILL.md 갱신**

워크플로우 트리에 분기 추가:

```
     ├─ check가 char_border_bug 보고 → fix-borders 실행 후 재check
```

커맨드 블록에 추가:

```markdown
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" fix-borders 원본.hwpx 결과.hwpx   # 글자 테두리 버그 수리
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" guard 결과.hwpx --reference 원본.hwpx --max-unchanged-ratio 0.35
```

필수 규칙 추가:

```markdown
15. check가 `char-border-bug`를 보고하면 `fix-borders`로 수리한 뒤 다시 check한다.
    수리는 header.xml만 바꾸므로 본문은 그대로다.
16. check의 `cell-overflow-risk` 경고는 추정이라 ok를 막지 않는다. 양식을 채울 때는
    `fill --analyze`가 알려주는 각 타겟의 `capacity`(추정 수용 글자 수)를 보고
    값 길이를 맞추거나, 넘칠 수밖에 없으면 사용자에게 알린다.
17. 문서 전체를 새 관점으로 재작성하는 작업(기관 교체 등)은 guard에
    `--max-unchanged-ratio 0.35`를 붙여 원문이 그대로 남지 않았는지 확인한다.
    guard는 `○○`, `{{...}}`, `TODO`, `TBD` 같은 미완성 표시도 기본 검사한다.
```

- [ ] **Step 2: README 갱신**

검수 표에 `fix-borders` 행을 추가하고, `guard` 행의 설명에 새 플래그를 반영한다:

```markdown
| `fix-borders <src> <dst>` | `check`가 검출한 글자 테두리 버그 수리 (header.xml만 변경) |
```

`guard` 행 설명을 다음으로 교체:

```markdown
| `guard <out> --reference <원본> [--rules r.json] [--max-growth 1.1] [--max-unchanged-ratio 0.35] [--no-default-placeholders]` | 원본 대비 검사 — 비변경 엔트리 바이트 동일, 필수/금지 키워드, 미완성 표시(`○○`·`{{}}`·TODO), 글자 수 증가, 원문 잔존 비율 |
```

"알려진 한계"에 한 줄 추가:

```markdown
- 셀 넘침(`cell-overflow-risk`)은 글자 크기·셀 크기 기반 **추정**이라 실제 렌더링과 다를 수 있습니다. 경고일 뿐 차단하지 않습니다.
```

- [ ] **Step 3: 전체 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add SKILL.md README.md
git commit -m "docs: Phase 6 수리·수용량·guard 확장 워크플로우

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 6 이후

- B그룹(각주·하이퍼링크·책갈피·목록 전환·도형·파생 템플릿)은 한컴 렌더링 검증 결과를 본 뒤 착수 여부를 정한다.
- 문서 유형 생성기(보도자료·계획서 등)는 레퍼런스 `.hwpx` 에셋 라이선스 문제로 도입하지 않는다. 필요하면 우리 생성기(`scripts/dev/gen_templates.py`)로 템플릿을 자체 제작한다.
