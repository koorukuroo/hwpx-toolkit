# hwpx-toolkit Phase 4 (개체·고급 서식) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 HWPX에 서식(글자/문단 스타일, 페이지·다단, 머리말·꼬리말·쪽번호), 표 고급 편집(셀 병합·열 추가), 이미지 삽입/교체/삭제를 원본 보존 방식으로 추가하고, Phase 3 이월 결함(슬롯 키 충돌·체크박스 오탐)을 정리한다.

**Architecture:** `core/header.py`의 `HeaderEditor`가 header.xml의 charPr/paraPr를 복제·변형(itemCnt 보정)해 새 id를 발급하고, `SectionEditor`가 대상 문단의 IDRef를 새 id로 repoint한다 — 대상 문단만 영향. `edit_file`은 편집 컨텍스트(`EditContext`)로 섹션·헤더·추가 엔트리(BinData)·content.hpf를 한 번에 `write_replaced`(추가 엔트리 지원으로 확장)로 저장한다. 이미지·머리말 XML은 실제 한컴 문서(2026-08-15 검증 샘플)에서 확인한 OWPML 구조를 따르며, 머리말·꼬리말은 한컴 샘플이 없어 별도 한컴 검증 항목으로 표시한다.

**Tech Stack:** Python 3.9+ stdlib (xml.etree, struct, zlib, zipfile, copy, re, struct 기반 이미지 크기 판독). pytest.

**Spec:** `docs/superpowers/specs/2026-08-13-hwpx-toolkit-design.md`

## Global Constraints

- 의존성: 코어와 CLI는 Python 3.9+ 표준 라이브러리만 (스펙 §9). 이미지 크기 판독도 stdlib(struct)로 PNG/JPEG만 지원.
- 클린룸: 외부 코드·XML 복사 금지 (스펙 §2). OWPML 구조는 표준·실제 한컴 문서 관찰 기반.
- 바이트 보존: 변경된 엔트리(섹션·header.xml·content.hpf·추가 BinData) 외 모든 엔트리는 바이트 동일 (스펙 §5). 스타일을 건드리지 않은 편집에서는 header.xml도 바이트 동일해야 함.
- 모든 편집 CLI는 `check` 자동 게이트, 실패 시 exit 2 (Phase 3 계약). 새 커맨드도 `_finish_edited` 사용.
- `hp:t` 자식 컨트롤 삭제 금지; 수정 문단 linesegarray 제거 규칙 유지.
- 테스트: `python3.13 -m pytest tests/ -q` (plain python3에 pytest 없음; venv 금지). 현재 107개 green 유지.
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- 네임스페이스: hs/hp/hh/hc = `http://www.hancom.co.kr/hwpml/2011/{section,paragraph,head,core}`.

## Phase 4 범위 밖 (명시적 연기 — 한컴 샘플로 구조 확인 후 4b에서)

각주·미주, 하이퍼링크·책갈피, 도형·글상자, 차트. 이유: 검증 샘플에 실물 구조가 없어 XML을 근거 없이 작성하게 됨. 이미지·머리말은 각각 실물 확인/표준 구조로 진행.

---

### Task 1: Phase 3 이월 — 슬롯 키 섹션 접두사 + 체크박스 오탐 수정

**Files:**
- Modify: `core/analyze.py`
- Test: `tests/test_carryover4.py`

**Interfaces:**
- Consumes: 기존 `extract_slots`, `fill_targets`, `_CHECKBOX_RE`
- Produces:
  - `extract_slots`의 셀 키: section0은 기존 `cell:{t}:{r}:{c}` 유지, 그 외 섹션은 `sec{N}:cell:{t}:{r}:{c}` (N은 섹션 파일 번호). 문서 전체에서 키 고유.
  - `_CHECKBOX_RE`: `□` **바로 뒤**에 공백 없이 단어가 오는 경우만 체크박스 (`□동의`). `□ 사업목적`(□+공백)은 공문 항목 머리표로 보고 제외. `☐`도 체크박스 기호로 인정.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_carryover4.py
import zipfile
from core.analyze import extract_slots, fill_targets
from core.package import HwpxPackage
from tests.fixture import build_minimal_hwpx, build_form_hwpx


def _two_section_with_tables(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx", with_table=True)
    pkg = HwpxPackage.open(src)
    sec0 = pkg.read("Contents/section0.xml")
    out = tmp_path / "two.hwpx"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            zout.writestr(info, zin.read(info.filename))
        zout.writestr("Contents/section1.xml",
                      sec0.decode("utf-8").replace("셀00", "둘째섹션셀"))
    return out


def test_slot_cell_keys_unique_across_sections(tmp_path):
    p = _two_section_with_tables(tmp_path)
    slots = extract_slots(p)["slots"]
    keys = [s["key"] for s in slots]
    assert len(keys) == len(set(keys))
    assert "cell:0:0:0" in keys
    assert "sec1:cell:0:0:0" in keys
    sec1 = next(s for s in slots if s["key"] == "sec1:cell:0:0:0")
    assert sec1["text"] == "둘째섹션셀"


def test_checkbox_heuristic_excludes_bullet_markers(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx", body_texts=[
        "□ 사업목적",          # 공문 항목 머리표 → 제외
        "□동의 □비동의",       # 체크박스 → 2개
        "☐확인",               # 대체 기호 → 1개
    ])
    boxes = [t for t in fill_targets(p)["targets"] if t["kind"] == "checkbox"]
    literals = {t["literal"] for t in boxes}
    assert literals == {"□동의", "□비동의", "☐확인"}


def test_form_fixture_still_detects_checkboxes(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    boxes = {t["literal"] for t in fill_targets(p)["targets"]
             if t["kind"] == "checkbox"}
    assert boxes == {"□동의", "□비동의"}
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_carryover4.py -v`
Expected: FAIL (키 중복 / `□ 사업목적` 오탐)

- [ ] **Step 3: 구현 (core/analyze.py 수정)**

`_CHECKBOX_RE`를 교체:

```python
_CHECKBOX_RE = re.compile(r"[□☐](\S{1,10})")
```

`_scan_checkbox_paren`의 checkbox literal 처리는 `m.group(0)`이 이미 `□동의` 형태이므로 변경 없음(공백 미허용으로 `□ 사업목적`은 매치되지 않는다).

`extract_slots`의 셀 키 생성 부분을 수정 — 섹션 루프에서 섹션 번호를 구해 접두사를 붙인다:

```python
# extract_slots 안, for name, root in _sections(pkg): 직후
        sec_no = int(re.fullmatch(r"Contents/section(\d+)\.xml", name).group(1))
        prefix = "" if sec_no == 0 else f"sec{sec_no}:"
        # ... 셀 슬롯 append 시:
                            slots.append({
                                "key": f"{prefix}cell:{table_index}:{row}:{col}",
                                ...
```

기존 `p:` 키는 문서 전역 인덱스라 변경하지 않는다.

- [ ] **Step 4: 통과 확인**

Run: `python3.13 -m pytest tests/ -q`
Expected: 전체 green (107 + 3)

- [ ] **Step 5: Commit**

```bash
git add core/analyze.py tests/test_carryover4.py
git commit -m "fix: 슬롯 셀 키 섹션 접두사, 체크박스 휴리스틱(항목 머리표 제외)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 패키지 확장 — 엔트리 추가 지원 + EditContext

**Files:**
- Modify: `core/package.py` (`write_replaced(dst, replacements, additions=None)`)
- Modify: `core/edit.py` (`EditContext`, `edit_file` 확장)
- Test: `tests/test_package_add.py`

**Interfaces:**
- Consumes: 기존 `write_replaced`, `SectionEditor`
- Produces (Task 3~6이 의존):
  - `HwpxPackage.write_replaced(dst, replacements, additions=None)` — `additions: dict[str, bytes]`는 원본에 없는 새 엔트리. 로컬 레코드는 기존 엔트리 뒤에, 중앙 레코드는 기존 중앙 디렉터리 뒤에 추가. DEFLATED, flag 0x0800(UTF-8 이름), 날짜 1980-01-01. additions에 원본 기존 이름이 있으면 `PackageError`.
  - `edit.EditContext` — 속성 `pkg`, `section: SectionEditor`, `header: HeaderEditor | None`(Task 3에서 채움; 이 태스크에서는 항상 None), `additions: dict[str, bytes]`, `replacements: dict[str, bytes]`(섹션 외 추가 교체 — content.hpf 등). 메서드 `.stage_replacement(name, data)`, `.stage_addition(name, data)`.
  - `edit.edit_file(src, dst, fn, section=...)` — `fn(ctx_or_editor)`: **하위 호환**을 위해 fn의 인자는 `SectionEditor`를 유지하고, `SectionEditor`가 `.ctx` 속성으로 `EditContext`를 노출한다. 저장 시 `{section: editor.serialize(), **ctx.replacements}` + `ctx.additions`.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_package_add.py
import zipfile
import pytest
from core.package import HwpxPackage, PackageError
from core.edit import edit_file
from tests.fixture import build_minimal_hwpx


def test_write_replaced_with_additions(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    dst = tmp_path / "b.hwpx"
    pkg = HwpxPackage.open(src)
    pkg.write_replaced(dst, {}, additions={"BinData/image1.png": b"\x89PNG-fake"})
    with zipfile.ZipFile(dst) as zf:
        assert zf.testzip() is None
        assert zf.read("BinData/image1.png") == b"\x89PNG-fake"
        info = zf.getinfo("BinData/image1.png")
        assert info.flag_bits & 0x800
    with zipfile.ZipFile(src) as za, zipfile.ZipFile(dst) as zb:
        for name in za.namelist():
            assert za.read(name) == zb.read(name)
        assert zb.infolist()[0].filename == "mimetype"


def test_additions_reject_existing_name(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    with pytest.raises(PackageError):
        HwpxPackage.open(src).write_replaced(tmp_path / "x.hwpx", {},
                                            additions={"mimetype": b"x"})


def test_edit_context_stages_addition_and_replacement(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    dst = tmp_path / "b.hwpx"

    def fn(ed):
        ed.ctx.stage_addition("BinData/x.bin", b"123")
        hpf = ed.ctx.pkg.read_text("Contents/content.hpf").replace(
            "fixture", "수정됨")
        ed.ctx.stage_replacement("Contents/content.hpf", hpf.encode("utf-8"))
        return "ok"

    assert edit_file(src, dst, fn) == "ok"
    out = HwpxPackage.open(dst)
    assert out.read("BinData/x.bin") == b"123"
    assert "수정됨" in out.read_text("Contents/content.hpf")
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_package_add.py -v`
Expected: FAIL (`TypeError: additions` / `AttributeError: ctx`)

- [ ] **Step 3: write_replaced 확장 (core/package.py)**

`write_replaced` 시그니처를 `def write_replaced(self, dst, replacements, additions=None):`로 바꾸고, 기존 로컬 레코드 루프 뒤·중앙 디렉터리 쓰기 전에 추가 엔트리를 처리한다:

```python
        additions = additions or {}
        for name in additions:
            if name in names:
                raise PackageError(f"이미 존재하는 엔트리는 additions 불가: {name}")
        added_centrals = []
        for name, raw in additions.items():
            c = zlib.compressobj(9, zlib.DEFLATED, -15)
            comp = c.compress(raw) + c.flush()
            crc = zlib.crc32(raw) & 0xFFFFFFFF
            fname = name.encode("utf-8")
            offset = out.tell()
            # 로컬 헤더: sig, ver 20, flags 0x800, method 8, time 0, date 0x21(1980-01-01)
            out.write(struct.pack("<4sHHHHHIIIHH", b"PK\x03\x04", 20, 0x0800, 8,
                                  0, 0x21, crc, len(comp), len(raw), len(fname), 0))
            out.write(fname)
            out.write(comp)
            central = struct.pack("<4sHHHHHHIIIHHHHHII", b"PK\x01\x02", 20, 20,
                                  0x0800, 8, 0, 0x21, crc, len(comp), len(raw),
                                  len(fname), 0, 0, 0, 0, 0, offset) + fname
            added_centrals.append(central)

        cd_start = out.tell()
        for rec, name in centrals:
            struct.pack_into("<I", rec, 42, new_offsets[name])
            out.write(rec)
        for rec in added_centrals:
            out.write(rec)
        cd_size = out.tell() - cd_start
        total_entries = len(centrals) + len(added_centrals)
        eocd_rec = bytearray(...)  # 기존 코드 유지
        struct.pack_into("<HHII", eocd_rec, 8, total_entries, total_entries,
                         cd_size, cd_start)
        out.write(eocd_rec)
```

(EOCD의 오프셋 8/10은 "이 디스크의 엔트리 수/전체 엔트리 수" — 추가분을 반영해야 zipfile이 새 엔트리를 인식한다.)

- [ ] **Step 4: EditContext + edit_file 확장 (core/edit.py)**

```python
class EditContext:
    def __init__(self, pkg, section_editor):
        self.pkg = pkg
        self.section = section_editor
        self.header = None            # Task 3에서 HeaderEditor
        self.additions = {}
        self.replacements = {}

    def stage_replacement(self, name, data):
        self.replacements[name] = data

    def stage_addition(self, name, data):
        self.additions[name] = data


# SectionEditor.__init__에 self.ctx = None 추가

def edit_file(src, dst, fn, section="Contents/section0.xml"):
    pkg = HwpxPackage.open(src)
    editor = SectionEditor.from_package(pkg, section)
    ctx = EditContext(pkg, editor)
    editor.ctx = ctx
    result = fn(editor)
    replacements = {section: editor.serialize()}
    if ctx.header is not None and ctx.header.dirty:
        replacements["Contents/header.xml"] = ctx.header.serialize()
    replacements.update(ctx.replacements)
    pkg.write_replaced(dst, replacements, additions=ctx.additions)
    return result
```

(`ctx.header`는 Task 3에서 `HeaderEditor`가 채워질 때까지 None — 위 코드는 None 안전.)

- [ ] **Step 5: 통과 확인**

Run: `python3.13 -m pytest tests/ -q`
Expected: 전체 green

- [ ] **Step 6: Commit**

```bash
git add core/package.py core/edit.py tests/test_package_add.py
git commit -m "feat: 엔트리 추가 지원 write_replaced와 EditContext

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: core/header.py + 글자/문단 서식 (set-text-style / set-para-style)

**Files:**
- Create: `core/header.py`
- Modify: `core/edit.py` (`_target_para`, `set_text_style`, `set_para_style`, ctx.header 로딩)
- Modify: `scripts/hwpx.py`
- Test: `tests/test_style.py`

**Interfaces:**
- Consumes: `EditContext`, `edit_file`
- Produces:
  - `header.HeaderEditor(xml_bytes)` — `.from_package(pkg)`, `.dirty: bool`, `.serialize() -> bytes`
    - `.clone_char_pr(base_id, *, bold=None, italic=None, underline=None, color=None, size_pt=None) -> str` — base charPr 복제·변형·charProperties에 추가·itemCnt 보정·새 id 반환. bold/italic/underline은 `hh:bold`/`hh:italic` 요소 존재 여부, underline은 `hh:underline type="BOTTOM"|"NONE"`, color는 `textColor="#RRGGBB"`, size_pt는 `height=pt*100`.
    - `.clone_para_pr(base_id, *, align=None, line_spacing=None) -> str` — `hh:align horizontal=`(LEFT/CENTER/RIGHT/JUSTIFY), `hh:lineSpacing value=`(%). 없는 base면 `EditError`.
  - `SectionEditor._target_para(after=None, index=None) -> p` — `after` 문구 포함 본문 문단(셀 제외) 또는 문서순 `index`(음수는 끝에서). 둘 다 None이면 마지막 본문 문단. 없으면 `EditError`.
  - `SectionEditor.set_text_style(*, after=None, index=None, bold=None, italic=None, underline=None, color=None, size_pt=None)` — 대상 문단의 모든 run의 charPrIDRef를 (run별 base 복제) 새 id로 repoint. `ctx.header` 필요(없으면 `EditError`).
  - `SectionEditor.set_para_style(*, after=None, index=None, align=None, line_spacing=None)`
  - CLI: `set-text-style <src> <dst> [--after 문구 | --para N] [--bold] [--italic] [--underline] [--color RRGGBB] [--size PT]` / `set-para-style <src> <dst> [--after|--para] [--align left|center|right|justify] [--line-spacing 160]`
  - `edit_file`이 `ctx.header = HeaderEditor.from_package(pkg)`를 항상 로드(수정 없으면 dirty False → header.xml 바이트 동일)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_style.py
import xml.etree.ElementTree as ET
import zipfile
import pytest
from core.package import HwpxPackage
from core.edit import edit_file, EditError
from core.header import HeaderEditor
from core.guards import check_package
from tests.fixture import build_form_hwpx, build_minimal_hwpx

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _header_root(path):
    return ET.fromstring(HwpxPackage.open(path).read("Contents/header.xml"))


def test_clone_char_pr_adds_entry_and_fixes_itemcnt(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    he = HeaderEditor.from_package(HwpxPackage.open(src))
    new_id = he.clone_char_pr("0", bold=True, color="C00000", size_pt=16)
    assert new_id == "1"
    root = ET.fromstring(he.serialize())
    coll = root.find(f".//{{{NS_HH}}}charProperties")
    chars = coll.findall(f"{{{NS_HH}}}charPr")
    assert coll.get("itemCnt") == "2" and len(chars) == 2
    new = chars[-1]
    assert new.get("height") == "1600" and new.get("textColor") == "#C00000"
    assert new.find(f"{{{NS_HH}}}bold") is not None
    assert he.dirty


def test_set_text_style_repoints_only_target(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.set_text_style(after="안녕하세요", bold=True))
    root = ET.fromstring(HwpxPackage.open(dst).read("Contents/section0.xml"))
    refs = {}
    for p in root.iter(f"{{{NS_HP}}}p"):
        text = "".join(t.text or "" for r in p.findall(f"{{{NS_HP}}}run")
                       for t in r.findall(f"{{{NS_HP}}}t"))
        for r in p.findall(f"{{{NS_HP}}}run"):
            refs.setdefault(text, set()).add(r.get("charPrIDRef"))
    assert refs["안녕하세요"] == {"1"}          # 새 charPr
    assert refs["감사합니다"] == {"0"}          # 비대상 불변
    assert check_package(dst)["ok"]
    hroot = _header_root(dst)
    assert hroot.find(f".//{{{NS_HH}}}charProperties").get("itemCnt") == "2"


def test_set_para_style_align_and_spacing(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.set_para_style(
        after="안녕하세요", align="center", line_spacing=180))
    hroot = _header_root(dst)
    paras = hroot.find(f".//{{{NS_HH}}}paraProperties")
    assert paras.get("itemCnt") == "2"
    new = paras.findall(f"{{{NS_HH}}}paraPr")[-1]
    assert new.find(f"{{{NS_HH}}}align").get("horizontal") == "CENTER"
    ls = new.find(f".//{{{NS_HH}}}lineSpacing")
    assert ls is not None and ls.get("value") == "180"
    assert check_package(dst)["ok"]


def test_header_untouched_when_no_style_edit(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.replace_text({"성명": "이름"}))
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(dst) as b:
        assert a.read("Contents/header.xml") == b.read("Contents/header.xml")


def test_target_para_index_and_missing(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.set_text_style(index=-1, italic=True))
    assert check_package(dst)["ok"]
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx",
                  lambda ed: ed.set_text_style(after="없는문구", bold=True))
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_style.py -v`
Expected: FAIL (`ModuleNotFoundError: core.header`)

- [ ] **Step 3: core/header.py 구현**

```python
# core/header.py
"""header.xml 스타일 관리 — charPr/paraPr 복제·변형, itemCnt 보정."""
import copy
import xml.etree.ElementTree as ET

from core.edit import EditError, NS, _XML_DECL

NS_HH = NS["hh"]
NS_HC = NS["hc"]


def _h(tag):
    return f"{{{NS_HH}}}{tag}"


class HeaderEditor:
    def __init__(self, xml_bytes):
        self.root = ET.fromstring(xml_bytes)
        self.dirty = False

    @classmethod
    def from_package(cls, pkg):
        return cls(pkg.read("Contents/header.xml"))

    def _collection(self, coll, child):
        el = self.root.find(f".//{_h(coll)}")
        if el is None:
            raise EditError(f"header.xml에 {coll} 없음")
        return el, el.findall(_h(child))

    def _next_id(self, items):
        return str(max((int(c.get("id")) for c in items if c.get("id", "").isdigit()),
                       default=-1) + 1)

    def _find(self, items, base_id):
        for c in items:
            if c.get("id") == str(base_id):
                return c
        raise EditError(f"스타일 id 없음: {base_id}")

    def clone_char_pr(self, base_id, *, bold=None, italic=None, underline=None,
                      color=None, size_pt=None):
        coll, items = self._collection("charProperties", "charPr")
        new = copy.deepcopy(self._find(items, base_id))
        new.set("id", self._next_id(items))
        for flag, tag in ((bold, "bold"), (italic, "italic")):
            if flag is None:
                continue
            existing = new.find(_h(tag))
            if flag and existing is None:
                anchor = new.find(_h("offset"))
                idx = list(new).index(anchor) + 1 if anchor is not None else len(new)
                new.insert(idx, ET.Element(_h(tag)))
            elif not flag and existing is not None:
                new.remove(existing)
        if underline is not None:
            ul = new.find(_h("underline"))
            if ul is None:
                ul = ET.SubElement(new, _h("underline"),
                                   {"shape": "SOLID", "color": "#000000"})
            ul.set("type", "BOTTOM" if underline else "NONE")
        if color is not None:
            new.set("textColor", "#" + color.lstrip("#").upper())
        if size_pt is not None:
            new.set("height", str(int(round(float(size_pt) * 100))))
        coll.append(new)
        coll.set("itemCnt", str(len(coll.findall(_h("charPr")))))
        self.dirty = True
        return new.get("id")

    _ALIGN = {"left": "LEFT", "center": "CENTER", "right": "RIGHT",
              "justify": "JUSTIFY"}

    def clone_para_pr(self, base_id, *, align=None, line_spacing=None):
        coll, items = self._collection("paraProperties", "paraPr")
        new = copy.deepcopy(self._find(items, base_id))
        new.set("id", self._next_id(items))
        if align is not None:
            key = align.lower()
            if key not in self._ALIGN:
                raise EditError(f"정렬 값 오류: {align}")
            al = new.find(_h("align"))
            if al is None:
                al = ET.SubElement(new, _h("align"), {"vertical": "BASELINE"})
            al.set("horizontal", self._ALIGN[key])
        if line_spacing is not None:
            found = list(new.iter(_h("lineSpacing")))
            if not found:
                found = [ET.SubElement(new, _h("lineSpacing"),
                                       {"unit": "HWPUNIT"})]
            for ls in found:
                ls.set("type", "PERCENT")
                ls.set("value", str(int(line_spacing)))
        coll.append(new)
        coll.set("itemCnt", str(len(coll.findall(_h("paraPr")))))
        self.dirty = True
        return new.get("id")

    def serialize(self):
        return (_XML_DECL + ET.tostring(self.root, encoding="unicode")).encode("utf-8")
```

주의: `core/header.py`가 `core.edit`를 import하고 `core.edit.edit_file`이 `HeaderEditor`를 쓰면 순환 import가 된다. 해결: `edit_file` 안에서 지역 import(`from core.header import HeaderEditor`)를 사용한다 — 이 경우에 한해 지역 import 허용(주석으로 이유 명시).

- [ ] **Step 4: SectionEditor 확장 (core/edit.py)**

```python
    # ---- 대상 문단 선택 ----
    def _body_paras(self):
        parents = {c: par for par in self.root.iter() for c in par}
        out = []
        for p in self._paras():
            node, in_cell = p, False
            while node is not None:
                node = parents.get(node)
                if node is not None and node.tag == _q("subList"):
                    in_cell = True
                    break
            if not in_cell:
                out.append(p)
        return out

    def _target_para(self, after=None, index=None):
        body = self._body_paras()
        if not body:
            raise EditError("본문 문단 없음")
        if after is not None:
            for p in body:
                if after in self._para_text(p):
                    return p
            raise EditError(f"본문에서 기준 문구를 찾지 못함: {after}")
        if index is None:
            index = -1
        try:
            return body[index]
        except IndexError:
            raise EditError(f"문단 인덱스 범위 밖: {index}")

    def _require_header(self):
        if self.ctx is None or self.ctx.header is None:
            raise EditError("헤더 편집기 없음 — edit_file 경유 필요")
        return self.ctx.header

    # ---- 서식 ----
    def set_text_style(self, *, after=None, index=None, bold=None, italic=None,
                       underline=None, color=None, size_pt=None):
        he = self._require_header()
        p = self._target_para(after, index)
        cache = {}
        for run in p.findall(_q("run")):
            base = run.get("charPrIDRef", "0")
            if base not in cache:
                cache[base] = he.clone_char_pr(base, bold=bold, italic=italic,
                                               underline=underline, color=color,
                                               size_pt=size_pt)
            run.set("charPrIDRef", cache[base])
        self._mark(p)

    def set_para_style(self, *, after=None, index=None, align=None,
                       line_spacing=None):
        he = self._require_header()
        p = self._target_para(after, index)
        new_id = he.clone_para_pr(p.get("paraPrIDRef", "0"), align=align,
                                  line_spacing=line_spacing)
        p.set("paraPrIDRef", new_id)
        self._mark(p)
```

`edit_file`에서 `ctx.header` 로드:

```python
def edit_file(src, dst, fn, section="Contents/section0.xml"):
    from core.header import HeaderEditor  # 순환 import 회피 (header→edit 의존)
    pkg = HwpxPackage.open(src)
    editor = SectionEditor.from_package(pkg, section)
    ctx = EditContext(pkg, editor)
    ctx.header = HeaderEditor.from_package(pkg)
    editor.ctx = ctx
    ...
```

- [ ] **Step 5: CLI (scripts/hwpx.py)**

```python
def _target_kwargs(args):
    return {"after": args.after, "index": args.para}


def cmd_set_text_style(args):
    kw = dict(bold=True if args.bold else None, italic=True if args.italic else None,
              underline=True if args.underline else None,
              color=args.color, size_pt=args.size)
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.set_text_style(**_target_kwargs(args), **kw))
    return _finish_edited(args.dst, {"set_text_style": kw})


def cmd_set_para_style(args):
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.set_para_style(**_target_kwargs(args),
                                                    align=args.align,
                                                    line_spacing=args.line_spacing))
    return _finish_edited(args.dst, {"set_para_style": {"align": args.align,
                                                        "line_spacing": args.line_spacing}})

# build_parser():
    def _add_target(parser):
        parser.add_argument("--after", help="기준 문구를 포함한 본문 문단")
        parser.add_argument("--para", type=int, help="본문 문단 인덱스 (음수=끝에서)")

    ts = sub.add_parser("set-text-style", help="글자 서식 (대상 문단 전체 run)")
    ts.add_argument("src"); ts.add_argument("dst")
    _add_target(ts)
    ts.add_argument("--bold", action="store_true")
    ts.add_argument("--italic", action="store_true")
    ts.add_argument("--underline", action="store_true")
    ts.add_argument("--color", help="RRGGBB")
    ts.add_argument("--size", type=float, help="pt")
    ts.set_defaults(func=cmd_set_text_style)

    ps = sub.add_parser("set-para-style", help="문단 서식")
    ps.add_argument("src"); ps.add_argument("dst")
    _add_target(ps)
    ps.add_argument("--align", choices=["left", "center", "right", "justify"])
    ps.add_argument("--line-spacing", type=int, help="%%")
    ps.set_defaults(func=cmd_set_para_style)
```

(`ts.add_argument("src"); ts.add_argument("dst")`는 구현 시 두 줄로 나눈다.)

- [ ] **Step 6: 통과 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add core/header.py core/edit.py scripts/hwpx.py tests/test_style.py
git commit -m "feat: 헤더 스타일 편집기와 글자/문단 서식 커맨드

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 페이지 설정·다단·쪽 나누기·머리말/꼬리말/쪽번호

**Files:**
- Modify: `core/edit.py`
- Modify: `scripts/hwpx.py`
- Modify: `docs/hancom-verification.md` (머리말/꼬리말 검증 항목 추가)
- Test: `tests/test_page.py`

**Interfaces:**
- Consumes: `SectionEditor`, `_target_para`
- Produces:
  - `.set_page(*, orientation=None, size=None, margins_mm=None)` — 첫 문단 secPr의 `hp:pagePr`: orientation `portrait|landscape` → `landscape="WIDELY"|"NARROWLY"`(가로면 width/height 교환); size `a4|a3|b5|letter` → width/height HWPUNIT (A4 59528×84186, A3 84186×119055, B5 51023×72283, Letter 61199×79370); margins_mm dict `{left,right,top,bottom,header,footer}` mm→HWPUNIT(×283.5 반올림).
  - `.set_columns(count, gap_mm=None)` — 첫 문단 `hp:ctrl/hp:colPr` `colCount`, gap → `spaceColumns`(secPr 속성)… 실제 OWPML은 colPr에 `sameGap`/`hp:colSz`가 있으나 v1은 `colCount`와 secPr `spaceColumns`만 설정.
  - `.set_page_break(after, on=True)` — 기준 문단의 `pageBreak="1"|"0"`.
  - `.set_header_footer(kind, text, *, align="left")` — kind `header|footer`. 첫 문단 첫 run에 secPr·colPr ctrl 뒤 `hp:ctrl` 봉투로 삽입: `<hp:ctrl><hp:header id="" applyPageType="BOTH"><hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0"><hp:p id=".." paraPrIDRef=".." styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>text</hp:t></hp:run></hp:p></hp:subList></hp:header></hp:ctrl>`. 같은 kind가 이미 있으면 텍스트만 갱신(중복 방지). align은 header 있으면 `clone_para_pr(0, align=)`으로 문단 paraPr 지정.
  - `.remove_header_footer(kind)`
  - `.set_page_number(*, where="footer", align="center")` — 해당 머리말/꼬리말(없으면 생성)의 문단에 `<hp:run charPrIDRef="0"><hp:autoNum num="1" numType="PAGE"><hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar="" supscript="0"/></hp:autoNum></hp:run>` 추가(이미 있으면 갱신 없음).
  - CLI: `set-page <src> <dst> [--orientation portrait|landscape] [--size a4|a3|b5|letter] [--margin-mm N] ...` (`--margin-mm`은 상하좌우 일괄), `set-columns <src> <dst> --count N [--gap-mm N]`, `page-break <src> <dst> --after 문구 [--off]`, `set-header <src> <dst> --text T [--align]`, `set-footer ...`, `remove-header`, `remove-footer`, `set-pagenum <src> <dst> [--where header|footer] [--align]`
- 한컴 검증 항목: 머리말/꼬리말/쪽번호는 실물 샘플 미확인 구조 — `docs/hancom-verification.md`에 검증 항목 추가.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_page.py
import xml.etree.ElementTree as ET
import pytest
from core.package import HwpxPackage
from core.edit import edit_file, EditError
from core.guards import check_package
from tests.fixture import build_form_hwpx

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _sec_root(path):
    return ET.fromstring(HwpxPackage.open(path).read("Contents/section0.xml"))


def _first_run(root):
    return root.find(f"{{{NS_HP}}}p/{{{NS_HP}}}run")


def test_set_page_landscape_a3_margins(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.set_page(
        orientation="landscape", size="a3",
        margins_mm={"left": 16, "right": 16, "top": 20, "bottom": 20}))
    pp = _first_run(_sec_root(dst)).find(f".//{{{NS_HP}}}pagePr")
    assert pp.get("landscape") == "NARROWLY"
    assert (pp.get("width"), pp.get("height")) == ("119055", "84186")
    m = pp.find(f"{{{NS_HP}}}margin")
    assert m.get("left") == "4536" and m.get("top") == "5670"
    assert check_package(dst)["ok"]


def test_set_columns_and_page_break(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: (ed.set_columns(2, gap_mm=8),
                                    ed.set_page_break("감사합니다")))
    root = _sec_root(dst)
    col = _first_run(root).find(f".//{{{NS_HP}}}colPr")
    assert col.get("colCount") == "2"
    assert _first_run(root).find(f"{{{NS_HP}}}secPr").get("spaceColumns") == "2268"
    target = [p for p in root.iter(f"{{{NS_HP}}}p")
              if "감사합니다" in "".join(t.text or "" for r in p.findall(f"{{{NS_HP}}}run")
                                     for t in r.findall(f"{{{NS_HP}}}t"))][0]
    assert target.get("pageBreak") == "1"
    assert check_package(dst)["ok"]


def test_header_footer_insert_update_remove(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    edit_file(src, d1, lambda ed: ed.set_header_footer("header", "대외비", align="center"))
    root = _sec_root(d1)
    headers = list(root.iter(f"{{{NS_HP}}}header"))
    assert len(headers) == 1
    assert "대외비" in "".join(t.text or "" for t in headers[0].iter(f"{{{NS_HP}}}t"))
    assert check_package(d1)["ok"]

    d2 = tmp_path / "2.hwpx"
    edit_file(d1, d2, lambda ed: ed.set_header_footer("header", "일급비밀"))
    root2 = _sec_root(d2)
    headers2 = list(root2.iter(f"{{{NS_HP}}}header"))
    assert len(headers2) == 1                     # 중복 생성 없음
    txt = "".join(t.text or "" for t in headers2[0].iter(f"{{{NS_HP}}}t"))
    assert "일급비밀" in txt and "대외비" not in txt

    d3 = tmp_path / "3.hwpx"
    edit_file(d2, d3, lambda ed: ed.remove_header_footer("header"))
    assert not list(_sec_root(d3).iter(f"{{{NS_HP}}}header"))


def test_page_number_in_footer(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.set_page_number(where="footer", align="center"))
    root = _sec_root(dst)
    footers = list(root.iter(f"{{{NS_HP}}}footer"))
    assert len(footers) == 1
    auto = footers[0].find(f".//{{{NS_HP}}}autoNum")
    assert auto is not None and auto.get("numType") == "PAGE"
    assert check_package(dst)["ok"]


def test_invalid_page_args(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx", lambda ed: ed.set_page(size="a9"))
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "y.hwpx",
                  lambda ed: ed.set_header_footer("sidebar", "x"))
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_page.py -v`
Expected: FAIL (`AttributeError: set_page`)

- [ ] **Step 3: 구현 (core/edit.py의 SectionEditor에 추가)**

```python
_PAGE_SIZES = {"a4": (59528, 84186), "a3": (84186, 119055),
               "b5": (51023, 72283), "letter": (61199, 79370)}


def _mm(v):
    return str(int(round(float(v) * 283.5)))


class SectionEditor:
    # ... 기존 ...

    def _first_run(self):
        p = self.root.find(_q("p"))
        run = p.find(_q("run")) if p is not None else None
        if run is None or run.find(_q("secPr")) is None:
            raise EditError("첫 문단 첫 run에 secPr 없음")
        return p, run

    def set_page(self, *, orientation=None, size=None, margins_mm=None):
        p, run = self._first_run()
        pagepr = run.find(_q("secPr")).find(_q("pagePr"))
        if pagepr is None:
            raise EditError("pagePr 없음")
        if size is not None:
            if size.lower() not in _PAGE_SIZES:
                raise EditError(f"지원하지 않는 용지: {size}")
            w, h = _PAGE_SIZES[size.lower()]
            pagepr.set("width", str(w)); pagepr.set("height", str(h))
        if orientation is not None:
            w, h = int(pagepr.get("width")), int(pagepr.get("height"))
            if orientation == "landscape":
                pagepr.set("landscape", "NARROWLY")
                if w < h:
                    pagepr.set("width", str(h)); pagepr.set("height", str(w))
            elif orientation == "portrait":
                pagepr.set("landscape", "WIDELY")
                if w > h:
                    pagepr.set("width", str(h)); pagepr.set("height", str(w))
            else:
                raise EditError(f"orientation 값 오류: {orientation}")
        if margins_mm:
            m = pagepr.find(_q("margin"))
            if m is None:
                raise EditError("margin 없음")
            for k, v in margins_mm.items():
                if k not in ("left", "right", "top", "bottom", "header",
                             "footer", "gutter"):
                    raise EditError(f"여백 키 오류: {k}")
                m.set(k, _mm(v))
        self._mark(p)

    def set_columns(self, count, gap_mm=None):
        p, run = self._first_run()
        col = run.find(f"{_q('ctrl')}/{_q('colPr')}")
        if col is None:
            raise EditError("colPr 없음")
        if int(count) < 1:
            raise EditError("단 수는 1 이상")
        col.set("colCount", str(int(count)))
        if gap_mm is not None:
            run.find(_q("secPr")).set("spaceColumns", _mm(gap_mm))
        self._mark(p)

    def set_page_break(self, after, on=True):
        p = self._target_para(after=after)
        p.set("pageBreak", "1" if on else "0")
        self._mark(p)

    _HF_KINDS = ("header", "footer")

    def _find_hf(self, kind):
        return list(self.root.iter(_q(kind)))

    def _hf_para(self, hf):
        return hf.find(f"{_q('subList')}/{_q('p')}")

    def set_header_footer(self, kind, text, *, align=None):
        if kind not in self._HF_KINDS:
            raise EditError(f"kind는 header|footer: {kind}")
        existing = self._find_hf(kind)
        p0, run = self._first_run()
        if existing:
            hp = self._hf_para(existing[0])
            ts = self._direct_ts(hp)
            if not ts:
                ET.SubElement(hp.find(_q("run")), _q("t"))
                ts = self._direct_ts(hp)
            ts[0].text = text
            for t in ts[1:]:
                t.text = ""
            target_p = hp
        else:
            ctrl = ET.Element(_q("ctrl"))
            hf = ET.SubElement(ctrl, _q(kind), {"id": "", "applyPageType": "BOTH"})
            sub = ET.SubElement(hf, _q("subList"), {
                "id": "", "textDirection": "HORIZONTAL", "lineWrap": "BREAK",
                "vertAlign": "TOP" if kind == "header" else "BOTTOM",
                "linkListIDRef": "0", "linkListNextIDRef": "0",
                "textWidth": "0", "textHeight": "0", "hasTextRef": "0",
                "hasNumRef": "0"})
            hp = ET.SubElement(sub, _q("p"), {
                "id": str(self._max_id() + 1), "paraPrIDRef": "0",
                "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0",
                "merged": "0"})
            r = ET.SubElement(hp, _q("run"), {"charPrIDRef": "0"})
            t = ET.SubElement(r, _q("t"))
            t.text = text
            # secPr, colPr ctrl 뒤에 삽입
            idx = max(i for i, c in enumerate(list(run))
                      if c.tag in (_q("secPr"), _q("ctrl"))) + 1
            run.insert(idx, ctrl)
            target_p = hp
        if align is not None:
            he = self._require_header()
            target_p.set("paraPrIDRef",
                         he.clone_para_pr(target_p.get("paraPrIDRef", "0"),
                                          align=align))
        self._mark(p0)

    def remove_header_footer(self, kind):
        if kind not in self._HF_KINDS:
            raise EditError(f"kind는 header|footer: {kind}")
        p0, run = self._first_run()
        removed = 0
        for ctrl in list(run.findall(_q("ctrl"))):
            if ctrl.find(_q(kind)) is not None:
                run.remove(ctrl)
                removed += 1
        if not removed:
            raise EditError(f"{kind} 없음")
        self._mark(p0)

    def set_page_number(self, *, where="footer", align="center"):
        if where not in self._HF_KINDS:
            raise EditError(f"where는 header|footer: {where}")
        if not self._find_hf(where):
            self.set_header_footer(where, "", align=align)
        hf = self._find_hf(where)[0]
        hp = self._hf_para(hf)
        if hp.find(f".//{_q('autoNum')}") is not None:
            return
        r = ET.SubElement(hp, _q("run"), {"charPrIDRef": "0"})
        auto = ET.SubElement(r, _q("autoNum"), {"num": "1", "numType": "PAGE"})
        ET.SubElement(auto, _q("autoNumFormat"), {
            "type": "DIGIT", "userChar": "", "prefixChar": "",
            "suffixChar": "", "supscript": "0"})
        self._mark(self._first_run()[0])
```

- [ ] **Step 4: CLI (scripts/hwpx.py)**

```python
def cmd_set_page(args):
    margins = None
    if args.margin_mm is not None:
        margins = {k: args.margin_mm for k in ("left", "right", "top", "bottom")}
    edit_mod.edit_file(args.src, args.dst, lambda ed: ed.set_page(
        orientation=args.orientation, size=args.size, margins_mm=margins))
    return _finish_edited(args.dst, {"set_page": vars(args)})


def cmd_set_columns(args):
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.set_columns(args.count, gap_mm=args.gap_mm))
    return _finish_edited(args.dst, {"columns": args.count})


def cmd_page_break(args):
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.set_page_break(args.after, on=not args.off))
    return _finish_edited(args.dst, {"page_break": args.after, "on": not args.off})


def _cmd_hf(kind):
    def run(args):
        edit_mod.edit_file(args.src, args.dst,
                           lambda ed: ed.set_header_footer(kind, args.text,
                                                           align=args.align))
        return _finish_edited(args.dst, {kind: args.text})
    return run


def _cmd_remove_hf(kind):
    def run(args):
        edit_mod.edit_file(args.src, args.dst,
                           lambda ed: ed.remove_header_footer(kind))
        return _finish_edited(args.dst, {"removed": kind})
    return run


def cmd_set_pagenum(args):
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.set_page_number(where=args.where,
                                                     align=args.align))
    return _finish_edited(args.dst, {"pagenum": args.where})

# build_parser():
    pg = sub.add_parser("set-page", help="용지/방향/여백")
    pg.add_argument("src"); pg.add_argument("dst")
    pg.add_argument("--orientation", choices=["portrait", "landscape"])
    pg.add_argument("--size", choices=["a4", "a3", "b5", "letter"])
    pg.add_argument("--margin-mm", type=float, help="상하좌우 일괄")
    pg.set_defaults(func=cmd_set_page)

    cl = sub.add_parser("set-columns", help="다단")
    cl.add_argument("src"); cl.add_argument("dst")
    cl.add_argument("--count", type=int, required=True)
    cl.add_argument("--gap-mm", type=float)
    cl.set_defaults(func=cmd_set_columns)

    pb = sub.add_parser("page-break", help="쪽 나누기 토글")
    pb.add_argument("src"); pb.add_argument("dst")
    pb.add_argument("--after", required=True)
    pb.add_argument("--off", action="store_true")
    pb.set_defaults(func=cmd_page_break)

    for kind in ("header", "footer"):
        s = sub.add_parser(f"set-{kind}", help=f"{kind} 설정/갱신")
        s.add_argument("src"); s.add_argument("dst")
        s.add_argument("--text", required=True)
        s.add_argument("--align", choices=["left", "center", "right"])
        s.set_defaults(func=_cmd_hf(kind))
        rm = sub.add_parser(f"remove-{kind}", help=f"{kind} 제거")
        rm.add_argument("src"); rm.add_argument("dst")
        rm.set_defaults(func=_cmd_remove_hf(kind))

    pn = sub.add_parser("set-pagenum", help="자동 쪽번호")
    pn.add_argument("src"); pn.add_argument("dst")
    pn.add_argument("--where", choices=["header", "footer"], default="footer")
    pn.add_argument("--align", choices=["left", "center", "right"], default="center")
    pn.set_defaults(func=cmd_set_pagenum)
```

- [ ] **Step 5: 한컴 검증 항목 추가 (docs/hancom-verification.md)**

`## 검증 절차` 뒤에 섹션 추가:

```markdown
## Phase 4 추가 검증 항목 (구조 미확인 — 우선 확인 필요)

머리말·꼬리말·쪽번호는 실물 샘플 없이 표준 구조로 작성했다. 아래를 한 번 확인한다.

    python3 scripts/hwpx.py set-header 샘플.hwpx h.hwpx --text "대외비" --align center
    python3 scripts/hwpx.py set-pagenum h.hwpx hp.hwpx --where footer

- [ ] h.hwpx: 머리말 "대외비"가 각 쪽 상단 가운데에 보이는가
- [ ] hp.hwpx: 꼬리말에 쪽번호가 보이는가
- [ ] set-page --orientation landscape 산출물이 가로로 열리는가
- [ ] set-text-style --bold --color C00000 산출물의 대상 문단만 붉은 굵은 글씨인가

실패 시: 한컴에서 머리말을 넣고 저장한 .hwpx를 unpack해 `hp:header` 구조를
비교하고 `SectionEditor.set_header_footer`를 보정한다.
```

- [ ] **Step 6: 통과 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add core/edit.py scripts/hwpx.py docs/hancom-verification.md tests/test_page.py
git commit -m "feat: 페이지 설정·다단·쪽나누기·머리말/꼬리말/쪽번호

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 이미지 — insert / list / resize / replace / delete

**Files:**
- Create: `core/images.py`
- Modify: `core/edit.py` (`insert_image`, `list_images`, `resize_image`, `replace_image`, `delete_image`)
- Modify: `scripts/hwpx.py`
- Test: `tests/test_images.py`

**Interfaces:**
- Consumes: `EditContext.stage_addition/stage_replacement`, `_target_para`, `HwpxPackage`
- Produces:
  - `images.image_size(data: bytes) -> tuple[int, int, str]` — (px_w, px_h, ext) PNG/JPEG만; 그 외 `EditError`
  - `images.next_bin_id(pkg) -> tuple[str, str]` — content.hpf manifest의 기존 `image<N>` id를 보고 `("image<N+1>", "BinData/image<N+1>")` (확장자 제외 경로 프리픽스)
  - `images.register_in_hpf(hpf_text, item_id, href, ext) -> str` — `<opf:item id=".." href=".." media-type="image/png|jpeg" isEmbeded="1"/>`를 `</opf:manifest>` 앞에 삽입
  - `images.pic_xml(pic_id, bin_id, w_hwp, h_hwp, px_w, px_h) -> str` — 실제 한컴 문서에서 확인한 `hp:pic` 구조(offset/orgSz/curSz/flip/rotationInfo/renderingInfo/imgRect/imgClip/inMargin/imgDim/hc:img/effects/sz/pos/outMargin), treatAsChar="1"
  - `SectionEditor.insert_image(path, *, after=None, index=None, width_mm=None, height_mm=None)` — 크기 미지정 시 96dpi 기준(px×25.4/96 mm), 한쪽만 지정 시 비율 유지. 기준 문단 뒤에 그림 문단 삽입. BinData 추가 + content.hpf 갱신은 ctx에 stage.
  - `SectionEditor.list_images() -> list[dict]` — `[{"index", "bin_id", "width_mm", "height_mm"}]` (문서 순 hp:pic)
  - `SectionEditor.resize_image(index, *, width_mm=None, height_mm=None)` — 한쪽만 지정 시 비율 유지; curSz·sz·imgRect 갱신
  - `SectionEditor.replace_image(index, path)` — 새 BinData 추가·hc:img binaryItemIDRef 교체(기존 BinData는 유지 — 다른 참조 가능성), orgSz/imgClip/imgDim은 새 픽셀 크기로, 표시 크기 유지
  - `SectionEditor.delete_image(index)` — 그림 문단 제거 (그림 run만 있는 문단이면 문단 자체, 아니면 pic 요소만)
  - CLI: `insert-image <src> <dst> --image f.png [--after|--para] [--width-mm] [--height-mm]`, `list-images <file>`(JSON), `resize-image <src> <dst> --index N [--width-mm] [--height-mm]`, `replace-image <src> <dst> --index N --image f.png`, `delete-image <src> <dst> --index N`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_images.py
import struct
import zlib
import zipfile
import pytest
from core.package import HwpxPackage
from core.edit import edit_file, EditError
from core.guards import check_package
from core.images import image_size
from tests.fixture import build_form_hwpx


def _png(w, h):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_image_size_png_and_reject_unknown():
    assert image_size(_png(40, 20)) == (40, 20, "png")
    with pytest.raises(EditError):
        image_size(b"not an image")


def test_insert_list_resize_replace_delete(tmp_path):
    img = tmp_path / "a.png"; img.write_bytes(_png(96, 48))
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    edit_file(src, d1, lambda ed: ed.insert_image(str(img), after="안녕하세요",
                                                  width_mm=50))
    with zipfile.ZipFile(d1) as zf:
        names = zf.namelist()
        assert "BinData/image1.png" in names
        assert zf.testzip() is None
        hpf = zf.read("Contents/content.hpf").decode("utf-8")
        assert 'id="image1"' in hpf and "image/png" in hpf
    assert check_package(d1)["ok"]

    def lst(path):
        out = {}
        edit_file(path, tmp_path / "tmp.hwpx", lambda ed: out.setdefault("v", ed.list_images()))
        return out["v"]
    imgs = lst(d1)
    assert len(imgs) == 1 and imgs[0]["bin_id"] == "image1"
    assert imgs[0]["width_mm"] == 50 and imgs[0]["height_mm"] == 25   # 비율 유지

    d2 = tmp_path / "2.hwpx"
    edit_file(d1, d2, lambda ed: ed.resize_image(0, width_mm=30))
    assert lst(d2)[0]["height_mm"] == 15

    img2 = tmp_path / "b.png"; img2.write_bytes(_png(10, 10))
    d3 = tmp_path / "3.hwpx"
    edit_file(d2, d3, lambda ed: ed.replace_image(0, str(img2)))
    with zipfile.ZipFile(d3) as zf:
        assert "BinData/image2.png" in zf.namelist()
    assert lst(d3)[0]["bin_id"] == "image2"
    assert lst(d3)[0]["width_mm"] == 30                        # 표시 크기 유지

    d4 = tmp_path / "4.hwpx"
    edit_file(d3, d4, lambda ed: ed.delete_image(0))
    assert lst(d4) == []
    assert check_package(d4)["ok"]


def test_insert_image_index_out_of_range(tmp_path):
    img = tmp_path / "a.png"; img.write_bytes(_png(4, 4))
    src = build_form_hwpx(tmp_path / "f.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx", lambda ed: ed.resize_image(3, width_mm=1))
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_images.py -v`
Expected: FAIL (`ModuleNotFoundError: core.images`)

- [ ] **Step 3: core/images.py 구현**

```python
# core/images.py
"""이미지 바이너리 판독·hpf 등록·hp:pic XML 생성 (stdlib)."""
import re
import struct

from core.edit import EditError

MM_PER_INCH = 25.4
HWP_PER_MM = 283.5


def image_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h, "png"
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h, "jpg"
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
        raise EditError("JPEG SOF 마커를 찾지 못함")
    raise EditError("지원하지 않는 이미지 형식 (PNG/JPEG만)")


def next_bin_id(pkg):
    hpf = pkg.read_text("Contents/content.hpf")
    nums = [int(n) for n in re.findall(r'id="image(\d+)"', hpf)]
    for name in pkg.names():
        m = re.fullmatch(r"BinData/image(\d+)\.\w+", name)
        if m:
            nums.append(int(m.group(1)))
    n = max(nums, default=0) + 1
    return f"image{n}", f"BinData/image{n}"


def register_in_hpf(hpf_text, item_id, href, ext):
    mime = "image/png" if ext == "png" else "image/jpeg"
    item = (f'<opf:item id="{item_id}" href="{href}" media-type="{mime}" '
            'isEmbeded="1"/>')
    if "</opf:manifest>" not in hpf_text:
        raise EditError("content.hpf에 manifest 없음")
    return hpf_text.replace("</opf:manifest>", item + "</opf:manifest>", 1)


def mm_to_hwp(mm):
    return int(round(float(mm) * HWP_PER_MM))


def hwp_to_mm(v):
    return round(int(v) / HWP_PER_MM, 1)


def px_to_hwp(px):
    return int(round(px / 96 * MM_PER_INCH * HWP_PER_MM))


def pic_xml(pic_id, bin_id, w, h, px_w, px_h):
    org_w, org_h = px_to_hwp(px_w), px_to_hwp(px_h)
    return (
        f'<hp:pic xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
        f'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
        f'id="{pic_id}" zOrder="0" numberingType="PICTURE" '
        'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        'dropcapstyle="None" href="" groupLevel="0" instid="0" reverse="0">'
        '<hp:offset x="0" y="0"/>'
        f'<hp:orgSz width="{org_w}" height="{org_h}"/>'
        f'<hp:curSz width="{w}" height="{h}"/>'
        '<hp:flip horizontal="0" vertical="0"/>'
        '<hp:rotationInfo angle="0" centerX="0" centerY="0" rotateimage="0"/>'
        '<hp:renderingInfo>'
        '<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '</hp:renderingInfo>'
        f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/>'
        f'<hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
        f'<hp:imgClip left="0" right="{org_w}" top="0" bottom="{org_h}"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        f'<hp:imgDim dimwidth="{org_w}" dimheight="{org_h}"/>'
        f'<hc:img binaryItemIDRef="{bin_id}" bright="0" contrast="0" '
        'effect="REAL_PIC" alpha="0"/>'
        '<hp:effects></hp:effects>'
        f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" '
        'heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
        'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" '
        'vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        '</hp:pic>')
```

- [ ] **Step 4: SectionEditor 이미지 메서드 (core/edit.py)**

```python
    # ---- 이미지 ----
    def _pics(self):
        return list(self.root.iter(_q("pic")))

    def _get_pic(self, index):
        pics = self._pics()
        if not 0 <= index < len(pics):
            raise EditError(f"그림 없음: index {index} (그림 {len(pics)}개)")
        return pics[index]

    def _fit(self, px_w, px_h, width_mm, height_mm, keep_w=None, keep_h=None):
        from core.images import mm_to_hwp, px_to_hwp
        if width_mm is None and height_mm is None:
            if keep_w is not None:
                return keep_w, keep_h
            return px_to_hwp(px_w), px_to_hwp(px_h)
        ratio = px_h / px_w if px_w else 1
        if width_mm is not None and height_mm is not None:
            return mm_to_hwp(width_mm), mm_to_hwp(height_mm)
        if width_mm is not None:
            w = mm_to_hwp(width_mm)
            return w, int(round(w * ratio))
        h = mm_to_hwp(height_mm)
        return int(round(h / ratio)), h

    def insert_image(self, path, *, after=None, index=None, width_mm=None,
                     height_mm=None):
        from core import images
        if self.ctx is None:
            raise EditError("edit_file 경유 필요")
        data = Path(path).read_bytes()
        px_w, px_h, ext = images.image_size(data)
        bin_id, prefix = images.next_bin_id(self.ctx.pkg)
        entry = f"{prefix}.{ext}"
        self.ctx.stage_addition(entry, data)
        hpf = self.ctx.replacements.get("Contents/content.hpf")
        hpf = hpf.decode("utf-8") if hpf else self.ctx.pkg.read_text("Contents/content.hpf")
        self.ctx.stage_replacement("Contents/content.hpf",
                                   images.register_in_hpf(hpf, bin_id, entry, ext).encode("utf-8"))
        w, h = self._fit(px_w, px_h, width_mm, height_mm)
        anchor = self._target_para(after, index)
        parents = {c: par for par in self.root.iter() for c in par}
        parent = parents[anchor]
        pid = self._max_id() + 1
        pic_el = ET.fromstring(images.pic_xml(str(pid + 1), bin_id, w, h, px_w, px_h))
        p = ET.Element(_q("p"), {"id": str(pid), "paraPrIDRef": anchor.get("paraPrIDRef", "0"),
                                 "styleIDRef": "0", "pageBreak": "0",
                                 "columnBreak": "0", "merged": "0"})
        run = ET.SubElement(p, _q("run"), {"charPrIDRef": "0"})
        run.append(pic_el)
        parent.insert(list(parent).index(anchor) + 1, p)
        self._mark(p)

    def list_images(self):
        from core.images import hwp_to_mm
        out = []
        for i, pic in enumerate(self._pics()):
            img = pic.find(f"{{{NS['hc']}}}img")
            sz = pic.find(_q("sz"))
            out.append({"index": i,
                        "bin_id": img.get("binaryItemIDRef") if img is not None else None,
                        "width_mm": hwp_to_mm(sz.get("width")) if sz is not None else None,
                        "height_mm": hwp_to_mm(sz.get("height")) if sz is not None else None})
        return out

    def _apply_pic_size(self, pic, w, h):
        for tag in ("curSz", "sz"):
            el = pic.find(_q(tag))
            if el is not None:
                el.set("width", str(w)); el.set("height", str(h))
        rect = pic.find(_q("imgRect"))
        if rect is not None:
            pts = {"pt0": (0, 0), "pt1": (w, 0), "pt2": (w, h), "pt3": (0, h)}
            for name, (x, y) in pts.items():
                pt = rect.find(f"{{{NS['hc']}}}{name}")
                if pt is not None:
                    pt.set("x", str(x)); pt.set("y", str(y))

    def resize_image(self, index, *, width_mm=None, height_mm=None):
        pic = self._get_pic(index)
        org = pic.find(_q("orgSz"))
        sz = pic.find(_q("sz"))
        px_w, px_h = int(org.get("width")), int(org.get("height"))
        w, h = self._fit(px_w, px_h, width_mm, height_mm,
                         keep_w=int(sz.get("width")), keep_h=int(sz.get("height")))
        self._apply_pic_size(pic, w, h)
        parents = {c: par for par in self.root.iter() for c in par}
        self._mark(self._owner_para(pic, parents))

    def _owner_para(self, el, parents):
        node = el
        while node is not None and node.tag != _q("p"):
            node = parents.get(node)
        if node is None:
            raise EditError("그림의 소속 문단을 찾을 수 없음")
        return node

    def replace_image(self, index, path):
        from core import images
        pic = self._get_pic(index)
        data = Path(path).read_bytes()
        px_w, px_h, ext = images.image_size(data)
        bin_id, prefix = images.next_bin_id(self.ctx.pkg)
        # 같은 편집 세션에서 이미 stage된 추가분도 번호에 반영
        while any(n.startswith(prefix + ".") for n in self.ctx.additions):
            n = int(bin_id[5:]) + 1
            bin_id, prefix = f"image{n}", f"BinData/image{n}"
        entry = f"{prefix}.{ext}"
        self.ctx.stage_addition(entry, data)
        hpf = self.ctx.replacements.get("Contents/content.hpf")
        hpf = hpf.decode("utf-8") if hpf else self.ctx.pkg.read_text("Contents/content.hpf")
        self.ctx.stage_replacement("Contents/content.hpf",
                                   images.register_in_hpf(hpf, bin_id, entry, ext).encode("utf-8"))
        img = pic.find(f"{{{NS['hc']}}}img")
        img.set("binaryItemIDRef", bin_id)
        ow, oh = images.px_to_hwp(px_w), images.px_to_hwp(px_h)
        for tag, attrs in (("orgSz", ("width", "height")), ("imgDim", ("dimwidth", "dimheight"))):
            el = pic.find(_q(tag))
            if el is not None:
                el.set(attrs[0], str(ow)); el.set(attrs[1], str(oh))
        clip = pic.find(_q("imgClip"))
        if clip is not None:
            clip.set("right", str(ow)); clip.set("bottom", str(oh))
        parents = {c: par for par in self.root.iter() for c in par}
        self._mark(self._owner_para(pic, parents))

    def delete_image(self, index):
        pic = self._get_pic(index)
        parents = {c: par for par in self.root.iter() for c in par}
        run = parents[pic]
        p = self._owner_para(pic, parents)
        run.remove(pic)
        if not list(run):
            p.remove(run)
        if not p.findall(_q("run")):
            gp = parents[p]
            gp.remove(p)
        else:
            self._mark(p)
```

`insert_image`/`replace_image` 공통으로 아래 헬퍼를 두고, 두 메서드의 `bin_id, prefix = images.next_bin_id(...)` + while 보정 부분을 `bin_id, prefix = self._fresh_bin_id()`로 교체한다 (`next_bin_id`는 이미 stage된 additions를 보지 못하므로):

```python
    def _fresh_bin_id(self):
        from core import images
        bin_id, prefix = images.next_bin_id(self.ctx.pkg)
        while any(n.startswith(prefix + ".") for n in self.ctx.additions):
            n = int(bin_id[len("image"):]) + 1
            bin_id, prefix = f"image{n}", f"BinData/image{n}"
        return bin_id, prefix
```

`Path`는 `core/edit.py` 상단에 `from pathlib import Path` 추가.

- [ ] **Step 5: CLI (scripts/hwpx.py)**

```python
def cmd_insert_image(args):
    edit_mod.edit_file(args.src, args.dst, lambda ed: ed.insert_image(
        args.image, after=args.after, index=args.para,
        width_mm=args.width_mm, height_mm=args.height_mm))
    return _finish_edited(args.dst, {"inserted": args.image})


def cmd_list_images(args):
    pkg = HwpxPackage.open(args.file)
    ed = edit_mod.SectionEditor.from_package(pkg)
    print(json.dumps({"images": ed.list_images()}, ensure_ascii=False, indent=2))
    return 0


def cmd_resize_image(args):
    edit_mod.edit_file(args.src, args.dst, lambda ed: ed.resize_image(
        args.index, width_mm=args.width_mm, height_mm=args.height_mm))
    return _finish_edited(args.dst, {"resized": args.index})


def cmd_replace_image(args):
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.replace_image(args.index, args.image))
    return _finish_edited(args.dst, {"replaced": args.index})


def cmd_delete_image(args):
    edit_mod.edit_file(args.src, args.dst, lambda ed: ed.delete_image(args.index))
    return _finish_edited(args.dst, {"deleted": args.index})

# build_parser():
    ii = sub.add_parser("insert-image", help="이미지 삽입 (PNG/JPEG)")
    ii.add_argument("src"); ii.add_argument("dst")
    ii.add_argument("--image", required=True)
    _add_target(ii)
    ii.add_argument("--width-mm", type=float); ii.add_argument("--height-mm", type=float)
    ii.set_defaults(func=cmd_insert_image)

    li = sub.add_parser("list-images", help="그림 목록")
    li.add_argument("file")
    li.set_defaults(func=cmd_list_images)

    ri = sub.add_parser("resize-image", help="그림 크기 변경")
    ri.add_argument("src"); ri.add_argument("dst")
    ri.add_argument("--index", type=int, required=True)
    ri.add_argument("--width-mm", type=float); ri.add_argument("--height-mm", type=float)
    ri.set_defaults(func=cmd_resize_image)

    rp = sub.add_parser("replace-image", help="그림 교체")
    rp.add_argument("src"); rp.add_argument("dst")
    rp.add_argument("--index", type=int, required=True)
    rp.add_argument("--image", required=True)
    rp.set_defaults(func=cmd_replace_image)

    di = sub.add_parser("delete-image", help="그림 삭제")
    di.add_argument("src"); di.add_argument("dst")
    di.add_argument("--index", type=int, required=True)
    di.set_defaults(func=cmd_delete_image)
```

- [ ] **Step 6: 통과 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add core/images.py core/edit.py scripts/hwpx.py tests/test_images.py
git commit -m "feat: 이미지 삽입/목록/크기변경/교체/삭제

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: 표 고급 — merge-cells / add-col

**Files:**
- Modify: `core/edit.py`
- Modify: `scripts/hwpx.py`
- Test: `tests/test_table_adv.py`

**Interfaces:**
- Consumes: `_get_table`, `_reject_spans`, `_find_cell`, `_set_cell_content`
- Produces:
  - `.merge_cells(table_index, row, col, row2, col2)` — 사각 범위 병합: 앵커 셀 cellSpan을 (col2-col+1, row2-row+1)로, 범위 내 다른 셀 제거, 앵커 cellSz width/height는 병합 셀 크기 합. 기존 span 있는 표·범위 밖·역순은 `EditError`. 제거되는 셀의 텍스트는 앵커 텍스트 뒤에 공백으로 이어 붙임(데이터 손실 방지).
  - `.add_col(table_index, cells, *, at=None)` — 각 행의 마지막(또는 `at` 위치) 셀을 복제해 새 열 삽입, colAddr 재계산, colCnt/표 폭(hp:sz width += 새 열 폭) 갱신, cells 길이는 행 수와 같아야 함, 병합 표 거부.
  - CLI: `merge-cells <src> <dst> --table N --row R --col C --row2 R2 --col2 C2`, `add-col <src> <dst> --table N --cells cells.json [--at K]`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_table_adv.py
import xml.etree.ElementTree as ET
import pytest
from core.package import HwpxPackage
from core.edit import edit_file, EditError
from core.guards import check_package
from core.analyze import analyze_document, extract_text
from tests.fixture import build_form_hwpx

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _tbl(path):
    root = ET.fromstring(HwpxPackage.open(path).read("Contents/section0.xml"))
    return next(root.iter(f"{{{NS_HP}}}tbl"))


def test_merge_cells_row(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.merge_cells(0, 0, 0, 0, 1))
    tbl = _tbl(dst)
    tcs = list(tbl.iter(f"{{{NS_HP}}}tc"))
    assert len(tcs) == 3                              # 4 → 3
    anchor = tcs[0]
    assert anchor.find(f"{{{NS_HP}}}cellSpan").get("colSpan") == "2"
    assert anchor.find(f"{{{NS_HP}}}cellSz").get("width") == "42520"
    assert tbl.get("rowCnt") == "2" and tbl.get("colCnt") == "2"
    assert check_package(dst)["ok"]


def test_merge_rejects_bad_range_and_existing_span(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "a.hwpx", lambda ed: ed.merge_cells(0, 1, 1, 0, 0))
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "b.hwpx", lambda ed: ed.merge_cells(0, 0, 0, 5, 5))
    merged = tmp_path / "m.hwpx"
    edit_file(src, merged, lambda ed: ed.merge_cells(0, 0, 0, 0, 1))
    with pytest.raises(EditError):
        edit_file(merged, tmp_path / "c.hwpx", lambda ed: ed.merge_cells(0, 1, 0, 1, 1))


def test_add_col_end_and_at(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    edit_file(src, d1, lambda ed: ed.add_col(0, ["비고1", "비고2"]))
    doc = analyze_document(d1)
    assert doc["sections"][0]["tables"][0]["cols"] == 3
    tbl = _tbl(d1)
    assert tbl.get("colCnt") == "3"
    assert int(tbl.find(f"{{{NS_HP}}}sz").get("width")) > 42520
    text = extract_text(d1)
    assert "비고1" in text and "비고2" in text
    assert check_package(d1)["ok"]

    d2 = tmp_path / "2.hwpx"
    edit_file(src, d2, lambda ed: ed.add_col(0, ["번호", "번호"], at=0))
    rows = [l for l in extract_text(d2).splitlines() if "번호" in l]
    assert rows and rows[0].startswith("번호")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx", lambda ed: ed.add_col(0, ["하나"]))
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_table_adv.py -v`
Expected: FAIL (`AttributeError: merge_cells`)

- [ ] **Step 3: 구현 (SectionEditor에 추가)**

```python
    def _cell_grid(self, tbl):
        grid = {}
        for tr in tbl.findall(_q("tr")):
            for tc in tr.findall(_q("tc")):
                addr = tc.find(_q("cellAddr"))
                grid[(int(addr.get("rowAddr")), int(addr.get("colAddr")))] = (tr, tc)
        return grid

    def merge_cells(self, table_index, row, col, row2, col2):
        tbl = self._get_table(table_index)
        self._reject_spans(tbl)
        if row2 < row or col2 < col:
            raise EditError("범위는 (row,col) ≤ (row2,col2)")
        grid = self._cell_grid(tbl)
        cells = []
        for r in range(row, row2 + 1):
            for c in range(col, col2 + 1):
                if (r, c) not in grid:
                    raise EditError(f"셀 없음: ({r},{c})")
                cells.append(grid[(r, c)])
        _, anchor = grid[(row, col)]
        width = sum(int(grid[(row, c)][1].find(_q("cellSz")).get("width"))
                    for c in range(col, col2 + 1))
        height = sum(int(grid[(r, col)][1].find(_q("cellSz")).get("height"))
                     for r in range(row, row2 + 1))
        extra_text = []
        for tr, tc in cells:
            if tc is anchor:
                continue
            sub = tc.find(_q("subList"))
            if sub is not None:
                for p in sub.findall(_q("p")):
                    t = self._para_text(p)
                    if t:
                        extra_text.append(t)
            tr.remove(tc)
        if extra_text:
            first_p = anchor.find(f"{_q('subList')}/{_q('p')}")
            base = self._para_text(first_p)
            self._set_cell_content(anchor, " ".join([base] + extra_text).strip())
        span = anchor.find(_q("cellSpan"))
        span.set("colSpan", str(col2 - col + 1)); span.set("rowSpan", str(row2 - row + 1))
        sz = anchor.find(_q("cellSz"))
        sz.set("width", str(width)); sz.set("height", str(height))
        self._mark(anchor.find(f"{_q('subList')}/{_q('p')}"))

    def add_col(self, table_index, cells, *, at=None):
        tbl = self._get_table(table_index)
        self._reject_spans(tbl)
        trs = tbl.findall(_q("tr"))
        if len(cells) != len(trs):
            raise EditError(f"행 수 불일치: 값 {len(cells)}개, 표 {len(trs)}행")
        n_cols = int(tbl.get("colCnt"))
        pos = n_cols if at is None else int(at)
        if not 0 <= pos <= n_cols:
            raise EditError(f"열 위치 범위 밖: {at}")
        next_id = self._max_id() + 1
        added_width = 0
        for tr, value in zip(trs, cells):
            tcs = tr.findall(_q("tc"))
            template = tcs[-1] if pos >= len(tcs) else tcs[pos]
            new_tc = copy.deepcopy(template)
            for p in new_tc.find(_q("subList")).findall(_q("p")):
                p.set("id", str(next_id)); next_id += 1
                for seg in p.findall(_q("linesegarray")):
                    p.remove(seg)
            self._set_cell_content(new_tc, value)
            insert_at = list(tr).index(tcs[pos]) if pos < len(tcs) else list(tr).index(tcs[-1]) + 1
            tr.insert(insert_at, new_tc)
            for tc in tr.findall(_q("tc")):
                addr = tc.find(_q("cellAddr"))
                c = int(addr.get("colAddr"))
                if tc is new_tc:
                    addr.set("colAddr", str(pos))
                elif c >= pos:
                    addr.set("colAddr", str(c + 1))
            added_width = int(new_tc.find(_q("cellSz")).get("width"))
        tbl.set("colCnt", str(n_cols + 1))
        tblsz = tbl.find(_q("sz"))
        if tblsz is not None:
            tblsz.set("width", str(int(tblsz.get("width", "0")) + added_width))
```

주의: `add_col`의 colAddr 재계산 루프에서 새 셀도 `c >= pos` 조건에 걸리므로 `tc is new_tc` 분기를 먼저 둔다(위 코드처럼).

- [ ] **Step 4: CLI (scripts/hwpx.py)**

```python
def cmd_merge_cells(args):
    edit_mod.edit_file(args.src, args.dst, lambda ed: ed.merge_cells(
        args.table, args.row, args.col, args.row2, args.col2))
    return _finish_edited(args.dst, {"merged": [args.row, args.col, args.row2, args.col2]})


def cmd_add_col(args):
    cells = json.loads(_read_text_utf8(args.cells))
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.add_col(args.table, cells, at=args.at))
    return _finish_edited(args.dst, {"added_col": cells})

# build_parser():
    mc = sub.add_parser("merge-cells", help="사각 범위 셀 병합")
    mc.add_argument("src"); mc.add_argument("dst")
    for k in ("table", "row", "col", "row2", "col2"):
        mc.add_argument(f"--{k}", type=int, required=True)
    mc.set_defaults(func=cmd_merge_cells)

    ac = sub.add_parser("add-col", help="표 열 추가")
    ac.add_argument("src"); ac.add_argument("dst")
    ac.add_argument("--table", type=int, required=True)
    ac.add_argument("--cells", required=True, help='["행0값","행1값",...] JSON 파일')
    ac.add_argument("--at", type=int)
    ac.set_defaults(func=cmd_add_col)
```

- [ ] **Step 5: 통과 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add core/edit.py scripts/hwpx.py tests/test_table_adv.py
git commit -m "feat: 셀 병합과 열 추가

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: 문서 갱신 (SKILL.md / README / references)

**Files:**
- Modify: `SKILL.md`, `README.md`
- Modify: `references/owpml-format.md` (이미지·머리말 구조 노트 추가)

- [ ] **Step 1: SKILL.md 갱신**

워크플로우 트리에 분기 추가:

```
     ├─ "글자/문단 서식 바꿔줘" → set-text-style / set-para-style
     ├─ "머리말/꼬리말/쪽번호" → set-header / set-footer / set-pagenum
     ├─ "가로/용지/여백/다단/쪽나누기" → set-page / set-columns / page-break
     ├─ "이미지 넣어줘/바꿔줘" → insert-image / list-images / replace-image / resize-image / delete-image
     ├─ "셀 병합/열 추가" → merge-cells / add-col
```

커맨드 블록에 각 커맨드 1줄 예시 추가(Task 3~6의 CLI 시그니처 그대로). 필수 규칙 추가:

```markdown
10. 서식 커맨드는 대상 문단(--after 문구 | --para N)만 바꾼다. header.xml에
    새 스타일이 추가되고 다른 문단은 영향 없다. 스타일을 안 건드린 편집은
    header.xml이 바이트 동일하게 유지된다.
11. 이미지는 PNG/JPEG만. 크기 미지정 시 96dpi 환산, 한쪽만 주면 비율 유지.
    replace-image는 기존 BinData를 남기고 새 항목을 추가한다.
12. merge-cells/add-col도 병합 셀이 이미 있는 표에서는 거부된다. 머리말·꼬리말·
    쪽번호 구조는 한컴 실물 검증이 아직 없으므로(docs/hancom-verification.md)
    첫 사용 시 결과를 한컴에서 확인하도록 안내한다.
```

- [ ] **Step 2: README 사용법에 서식/이미지 커맨드 요약 3줄 추가**

```markdown
    python3 scripts/hwpx.py set-text-style 원본.hwpx 결과.hwpx --after "제목" --bold --size 16
    python3 scripts/hwpx.py insert-image 원본.hwpx 결과.hwpx --image 그림.png --after "그림 위치" --width-mm 80
    python3 scripts/hwpx.py set-header 원본.hwpx 결과.hwpx --text "대외비" --align center
```

- [ ] **Step 3: references/owpml-format.md에 절 추가**

```markdown
## 개체 구조 노트 (Phase 4)

- 그림: `hp:p > hp:run > hp:pic` (offset/orgSz/curSz/flip/rotationInfo/renderingInfo/
  imgRect/imgClip/inMargin/imgDim/hc:img@binaryItemIDRef/effects/sz/pos/outMargin).
  바이너리는 `BinData/imageN.ext`, content.hpf manifest에 `opf:item id="imageN"
  isEmbeded="1"`로 등록. (2026-08-15 한컴 실물에서 확인)
- 머리말/꼬리말: 첫 문단 첫 run, secPr·colPr ctrl 뒤 `hp:ctrl > hp:header|hp:footer
  @applyPageType > hp:subList > hp:p`. 쪽번호는 그 문단의 run에 `hp:autoNum
  @numType="PAGE"`. (표준 구조 — 실물 검증 대기)
- 스타일 추가: header.xml의 charPr/paraPr를 복제·변형해 끝에 추가하고 itemCnt 갱신.
  기존 id는 절대 재사용하지 않는다.
```

- [ ] **Step 4: 전체 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add SKILL.md README.md references/owpml-format.md
git commit -m "docs: Phase 4 서식·개체 워크플로우

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 4 이후

- **사용자 한컴 검증**: docs/hancom-verification.md의 Phase 4 항목(머리말/쪽번호/가로/서식/이미지) 1회 수행. 머리말 구조 실패 시 한컴 저장본으로 보정.
- **Phase 4b(연기)**: 각주·미주, 하이퍼링크·책갈피, 도형·글상자 — 한컴 샘플 확보 후.
- **Phase 5**: from-hwp(rhwp), 공문서 lint, 파생 템플릿.
