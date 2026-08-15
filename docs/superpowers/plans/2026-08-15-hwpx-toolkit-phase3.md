# hwpx-toolkit Phase 3 (편집) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 HWPX를 원본 보존 방식으로 편집하는 엔진(문구 교체·양식 채우기·표/문단 조작)과 전달 전 검증 게이트(check/guard)를 완성한다.

**Architecture:** `core/edit.py`의 `SectionEditor`가 section XML을 ET로 파싱(네임스페이스 접두사 등록으로 hp:/hs: 보존)해 편집하고, 변경된 섹션 엔트리만 Phase 1의 `write_replaced`로 교체한다 — 비수정 엔트리는 바이트 동일. 텍스트 교체는 run 분할에 대응(문단의 hp:t 텍스트를 이어붙여 매칭), 수정 문단의 `hp:linesegarray`(한컴 줄배치 캐시)는 직렬화 시 제거한다. 양식 채우기는 `analyze.fill_targets`(라벨-값 셀/체크박스/괄호 빈칸 감지) + `core/fill.py`(라벨 정규화 매칭 적용)로 구성. `guards.check_package`(사고 패턴 감지)와 `guards.guard_against_reference`(비섹션 엔트리 바이트 동일·내용 규칙·글자수 증가)가 게이트다.

**Tech Stack:** Python 3.9+ stdlib (xml.etree + copy + re + zipfile). pytest.

**Spec:** `docs/superpowers/specs/2026-08-13-hwpx-toolkit-design.md`

## Global Constraints

- 의존성: 코어와 CLI는 Python 3.9+ 표준 라이브러리만 (스펙 §9).
- 클린룸: 외부 코드·XML 복사 금지 (스펙 §2).
- 바이트 보존: 편집 시 변경된 섹션 엔트리 외 모든 엔트리는 바이트 동일 (스펙 §5) — `write_replaced` 경유 필수.
- 모든 편집 산출물은 전달 전 `check` 통과 필수; 편집 CLI는 check를 자동 실행하고 실패 시 exit 2 (스펙 §7).
- 수정된 문단의 `hp:linesegarray`는 제거, 비수정 문단의 것은 보존 (스펙 §5 edit.py).
- `hp:t`의 자식 컨트롤(hp:fwSpace 등)은 절대 삭제하지 않는다 — 텍스트 편집은 `.text`만 조작.
- rowSpan/colSpan 병합이 있는 표의 구조 편집(행 추가/삭제)은 `EditError`로 거부 (스펙 §5).
- CLI 실패 시 JSON `{"ok": false, ...}` + exit 2 (기존 계약; EditError는 PackageError의 서브클래스라 기존 래퍼가 처리).
- 테스트: `python3.13 -m pytest tests/ -q` (plain python3에 pytest 없음; venv 금지). 현재 68개 green 유지.
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- 네임스페이스: hs/hp/hh/hc = `http://www.hancom.co.kr/hwpml/2011/{section,paragraph,head,core}`.

## v1 편집 한계 (문서화 대상, 결함 아님)

- 텍스트 매칭은 `hp:t`의 직접 `.text`만 대상 (자식 컨트롤 뒤 tail 텍스트는 매칭 불가 — 남기되 건드리지 않음).
- ET 재직렬화로 편집된 섹션 XML의 표기(자기닫힘 태그 공백 등)는 원본과 다를 수 있음 — 구조·값은 동일, 다른 엔트리는 바이트 동일.
- checkbox/괄호 채우기는 리터럴 치환 기반 — 동일 리터럴이 여러 곳이면 모두 바뀜.

---

### Task 1: Phase 2 이월 정리 (BadZipFile·dotfile 필터·섹션 헬퍼)

**Files:**
- Modify: `core/package.py`
- Modify: `core/analyze.py` (`_sections`가 새 헬퍼 사용)
- Modify: `core/guards.py` (섹션 목록이 새 헬퍼 사용)
- Test: `tests/test_carryover.py`

**Interfaces:**
- Consumes: 기존 `HwpxPackage`, `pack_dir`
- Produces:
  - `package.section_names(names: list[str]) -> list[str]` — `Contents/section<N>.xml`만 숫자순 정렬로 반환. analyze/guards 공용.
  - `HwpxPackage.open`이 손상 central directory(`zipfile.BadZipFile`)에서 `PackageError`를 던짐.
  - `pack_dir`가 두 분기(source 유/무) 모두에서 dot-컴포넌트 파일을 무시.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_carryover.py
import struct
import zipfile
import pytest
from core.package import HwpxPackage, PackageError, pack_dir, section_names
from tests.fixture import build_minimal_hwpx


def test_corrupt_central_directory_raises_package_error(tmp_path):
    # EOCD는 유효(=is_zipfile 통과)하지만 CD offset이 쓰레기를 가리키는 파일
    eocd = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 1, 1, 10, 0, 0)
    bad = tmp_path / "bad.hwpx"
    bad.write_bytes(b"GARBAGE!" * 8 + eocd)
    with pytest.raises(PackageError):
        HwpxPackage.open(bad)


def test_pack_dir_ignores_dotfiles_without_source(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(src).extract_to(outdir)
    (outdir / ".DS_Store").write_bytes(b"junk")
    (outdir / "Contents" / ".hidden").write_bytes(b"junk")
    out = tmp_path / "fresh.hwpx"
    pack_dir(outdir, out)
    with zipfile.ZipFile(out) as zf:
        assert all(".DS_Store" not in n and ".hidden" not in n
                   for n in zf.namelist())


def test_pack_dir_ignores_dotfiles_with_source(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(src).extract_to(outdir)
    (outdir / ".DS_Store").write_bytes(b"junk")
    out = tmp_path / "same.hwpx"
    pack_dir(outdir, out, source=src)   # 예전엔 '원본에 없는 파일' PackageError
    assert out.read_bytes() == src.read_bytes()


def test_section_names_numeric_order():
    names = ["Contents/section10.xml", "Contents/section2.xml",
             "Contents/section0.xml", "Contents/header.xml", "mimetype"]
    assert section_names(names) == ["Contents/section0.xml",
                                    "Contents/section2.xml",
                                    "Contents/section10.xml"]
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_carryover.py -v`
Expected: FAIL (`ImportError: section_names` 등)

- [ ] **Step 3: 구현**

`core/package.py` 수정 3건:

(a) 파일 상단에 `import re`를 추가하고 헬퍼를 추가:

```python
def section_names(names):
    """Contents/section<N>.xml 엔트리를 숫자순으로 반환."""
    cands = []
    for n in names:
        m = re.fullmatch(r"Contents/section(\d+)\.xml", n)
        if m:
            cands.append((int(m.group(1)), n))
    return [n for _, n in sorted(cands)]
```

(b) `HwpxPackage.open`의 `zipfile.ZipFile(io.BytesIO(data))` 호출을 감싼다:

```python
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise PackageError(f"ZIP 손상: {path}: {e}") from e
```

(c) `pack_dir`의 files 수집을 dot-컴포넌트 필터로 교체 (양 분기 공용인 수집 지점 한 곳만 고친다):

```python
    files = {}
    for f in dirpath.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(dirpath)
        if any(part.startswith(".") for part in rel.parts):
            continue
        files[str(rel).replace("\\", "/")] = f
```

`core/analyze.py`의 `_sections`를 헬퍼 사용으로 교체:

```python
from core.package import HwpxPackage, section_names

def _sections(pkg):
    return [(n, ET.fromstring(pkg.read(n))) for n in section_names(pkg.names())]
```

`core/guards.py`의 섹션 목록(`sorted(n for n in names if re.fullmatch(...))` 부분)을 교체:

```python
from core.package import HwpxPackage, PackageError, section_names
# ...
    sections = section_names(names)
    if not sections:
        errors.append("required-missing: Contents/section*.xml")
```

- [ ] **Step 4: 통과 확인**

Run: `python3.13 -m pytest tests/ -q`
Expected: 전체 green (68 + 4 = 72)

- [ ] **Step 5: Commit**

```bash
git add core/package.py core/analyze.py core/guards.py tests/test_carryover.py
git commit -m "fix: BadZipFile 래핑, pack_dir dotfile 필터, 섹션 정렬 헬퍼 통일

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 양식 픽스처 확장

**Files:**
- Modify: `tests/fixture.py`
- Test: `tests/test_fixture_form.py`

**Interfaces:**
- Consumes: 기존 fixture 상수(SECTION_HEAD, BODY_PARA, _cell)
- Produces: `build_form_hwpx(path) -> Path` — 이후 태스크의 편집/채우기 테스트가 쓰는 양식 문서:
  - 표 0: 2×2 라벨-값 (`성명`/빈칸, `연락처`/빈칸)
  - 문단: `□동의 □비동의` (체크박스)
  - 문단: `제출 부수: 일반(  )통` (괄호 빈칸)
  - run 분할 문단 2개: `안녕`+`하세요`, `감사`+`합니다` — 각각 `hp:linesegarray` 포함
  - 기존 `_table`은 `rows` 파라미터를 받도록 일반화하되 기본값은 기존과 동일(기존 테스트 불변)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_fixture_form.py
import zipfile
from core.guards import validate_package
from core.analyze import extract_text
from tests.fixture import build_form_hwpx


def test_form_fixture_valid_and_contents(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    assert validate_package(p)["ok"]
    text = extract_text(p)
    for expected in ("성명", "연락처", "□동의 □비동의", "일반(  )통", "안녕하세요"):
        assert expected in text


def test_form_fixture_has_linesegarray_and_split_runs(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    with zipfile.ZipFile(p) as zf:
        xml = zf.read("Contents/section0.xml").decode("utf-8")
    assert xml.count("<hp:linesegarray>") == 2
    assert "<hp:t>안녕</hp:t>" in xml and "<hp:t>하세요</hp:t>" in xml
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_fixture_form.py -v`
Expected: FAIL (`ImportError: build_form_hwpx`)

- [ ] **Step 3: 구현 (tests/fixture.py 수정)**

`_table()`을 일반화 (기본 동작 불변):

```python
def _table(rows=None):
    if rows is None:
        rows = [["셀00", "셀01"], ["셀10", "셀11"]]
    tr_parts = []
    pid = 1000000200
    for r, row in enumerate(rows):
        cells = "".join(_cell(r, c, row[c], pid + r * len(row) + c)
                        for c in range(len(row)))
        tr_parts.append(f"<hp:tr>{cells}</hp:tr>")
    n_rows, n_cols = len(rows), len(rows[0])
    return (
        '<hp:p id="1000000100" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
        '<hp:tbl id="1000000101" zOrder="0" numberingType="TABLE" '
        'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
        f'rowCnt="{n_rows}" colCnt="{n_cols}" cellSpacing="0" '
        'borderFillIDRef="1" noAdjust="0">'
        f'<hp:sz width="42520" widthRelTo="ABSOLUTE" height="{2400 * n_rows}" '
        'heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
        'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
        'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
        'vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        + "".join(tr_parts) +
        '</hp:tbl></hp:run></hp:p>')
```

(기존 `_table()`의 셀 pid 배정 `pid + r * 2 + c`는 2열 가정이었다 — `r * len(row) + c`로 일반화. 기본 rows에서는 결과가 동일하다.)

run 분할 + linesegarray 문단 상수와 양식 빌더 추가:

```python
SPLIT_PARA = (
    '<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0">'
    '<hp:run charPrIDRef="0"><hp:t>{a}</hp:t></hp:run>'
    '<hp:run charPrIDRef="0"><hp:t>{b}</hp:t></hp:run>'
    '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1000" '
    'textheight="1000" baseline="850" spacing="600" horzpos="0" '
    'horzsize="42520" flags="393216"/></hp:linesegarray>'
    '</hp:p>')


def build_form_hwpx(path):
    """편집/채우기 테스트용 양식: 라벨-값 표, 체크박스, 괄호 빈칸, run 분할 문단."""
    path = Path(path)
    parts = [SECTION_HEAD]
    parts.append(_table(rows=[["성명", ""], ["연락처", ""]]))
    parts.append(BODY_PARA.format(pid=1000000301, text="□동의 □비동의"))
    parts.append(BODY_PARA.format(pid=1000000302, text="제출 부수: 일반(  )통"))
    parts.append(SPLIT_PARA.format(pid=1000000303, a="안녕", b="하세요"))
    parts.append(SPLIT_PARA.format(pid=1000000304, a="감사", b="합니다"))
    parts.append("</hs:sec>")
    section0 = "".join(parts)

    entries = [
        ("mimetype", MIMETYPE),
        ("version.xml", VERSION_XML),
        ("settings.xml", SETTINGS_XML),
        ("META-INF/container.xml", CONTAINER_XML),
        ("META-INF/manifest.xml", MANIFEST_XML),
        ("Contents/content.hpf", CONTENT_HPF),
        ("Contents/header.xml", HEADER_XML),
        ("Contents/section0.xml", section0),
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in entries:
            ctype = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            zf.writestr(zipfile.ZipInfo(name), text.encode("utf-8"),
                        compress_type=ctype)
    return path
```

- [ ] **Step 4: 통과 확인**

Run: `python3.13 -m pytest tests/test_fixture_form.py tests/ -q`
Expected: 전체 green (기존 테스트 불변 확인 포함)

- [ ] **Step 5: Commit**

```bash
git add tests/fixture.py tests/test_fixture_form.py
git commit -m "test: 양식 픽스처 (라벨-값 표/체크박스/괄호 빈칸/run 분할)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: core/edit.py — SectionEditor + replace + CLI replace

**Files:**
- Create: `core/edit.py`
- Modify: `scripts/hwpx.py` (replace 서브커맨드, `_finish_edited` 헬퍼)
- Test: `tests/test_edit_replace.py`

**Interfaces:**
- Consumes: `HwpxPackage`, `write_replaced`, `build_form_hwpx`, `guards.check_package`는 Task 6에서 완성되므로 이 태스크의 CLI는 우선 `guards.validate_package`를 게이트로 사용 (Task 6이 check로 교체)
- Produces (Task 4·5가 의존):
  - `edit.EditError(PackageError)`
  - `edit.SectionEditor` —
    - `SectionEditor.from_package(pkg, name="Contents/section0.xml") -> SectionEditor`
    - `.replace_text(mapping: dict[str, str]) -> dict` — `{"replaced": {old: count}, "not_found": [old...]}` — run 분할 대응, charPrIDRef 보존(텍스트만 조작), 수정 문단 mark
    - `.serialize() -> bytes` — 수정 문단의 linesegarray 제거 + XML 선언 포함 UTF-8
  - `edit.edit_file(src, dst, fn, section="Contents/section0.xml")` — pkg 열기→editor 생성→`fn(editor)` 실행→`write_replaced`로 저장, `fn`의 반환값 반환
  - CLI: `hwpx.py replace <src> <dst> --map map.json` — 결과 JSON(report+gate) 출력, gate 실패 또는 not_found 존재 시 exit 2
  - `scripts/hwpx.py`의 `_finish_edited(dst, report) -> int` — validate(추후 check) 실행 후 `{"ok", "output", "report", "gate"}` JSON 출력

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_edit_replace.py
import json
import zipfile
import pytest
from core.package import HwpxPackage
from core.edit import SectionEditor, edit_file, EditError
from core.guards import validate_package
from core.analyze import extract_text
from tests.fixture import build_form_hwpx, build_minimal_hwpx


def test_replace_across_split_runs(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    report = edit_file(src, dst,
                       lambda ed: ed.replace_text({"안녕하세요": "반갑습니다"}))
    assert report["replaced"]["안녕하세요"] == 1
    assert report["not_found"] == []
    text = extract_text(dst)
    assert "반갑습니다" in text and "안녕하세요" not in text
    assert validate_package(dst)["ok"]


def test_replace_preserves_untouched_entries_bytes(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.replace_text({"성명": "이름"}))
    with zipfile.ZipFile(src) as za, zipfile.ZipFile(dst) as zb:
        for name in za.namelist():
            if name == "Contents/section0.xml":
                continue
            assert za.read(name) == zb.read(name), name


def test_modified_para_linesegarray_removed_others_kept(tmp_path):
    import xml.etree.ElementTree as ET
    NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.replace_text({"안녕하세요": "수정됨"}))
    root = ET.fromstring(HwpxPackage.open(dst).read("Contents/section0.xml"))
    kept = removed_ok = False
    for p in root.iter(f"{{{NS_HP}}}p"):
        text = "".join(t.text or "" for run in p.findall(f"{{{NS_HP}}}run")
                       for t in run.findall(f"{{{NS_HP}}}t"))
        seg = p.find(f"{{{NS_HP}}}linesegarray")
        if "수정됨" in text:
            removed_ok = seg is None            # 수정 문단: 캐시 제거
        if "감사합니다" in text:
            kept = seg is not None              # 비수정 문단: 캐시 보존
    assert removed_ok and kept


def test_replace_not_found_reported(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    report = edit_file(src, dst, lambda ed: ed.replace_text({"없는문구": "x"}))
    assert report["not_found"] == ["없는문구"]


def test_replace_multiple_occurrences_and_self_containing(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx",
                             body_texts=["가나다 가나다", "가나다"])
    dst = tmp_path / "out.hwpx"
    report = edit_file(src, dst,
                       lambda ed: ed.replace_text({"가나다": "가나다라"}))
    assert report["replaced"]["가나다"] == 3
    assert extract_text(dst).count("가나다라") == 3


def test_cli_replace(tmp_path, capsys):
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    mp = tmp_path / "map.json"
    mp.write_text(json.dumps({"연락처": "전화번호"}), encoding="utf-8")
    rc = hwpx_cli.main(["replace", str(src), str(dst), "--map", str(mp)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    assert payload["report"]["replaced"]["연락처"] == 1
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_edit_replace.py -v`
Expected: FAIL (`ModuleNotFoundError: core.edit`)

- [ ] **Step 3: core/edit.py 구현**

```python
# core/edit.py
"""원본 보존 섹션 편집 엔진 — ET 기반, 변경 섹션만 write_replaced로 교체."""
import copy
import re
import xml.etree.ElementTree as ET

from core.package import HwpxPackage, PackageError

NS = {
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
}
for _prefix, _uri in NS.items():
    ET.register_namespace(_prefix, _uri)

_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def _q(tag):
    return f"{{{NS['hp']}}}{tag}"


class EditError(PackageError):
    pass


class SectionEditor:
    def __init__(self, xml_bytes, name="Contents/section0.xml"):
        self.name = name
        self.root = ET.fromstring(xml_bytes)
        self._modified = []          # 수정된 hp:p 요소들 (linesegarray 제거 대상)

    @classmethod
    def from_package(cls, pkg, name="Contents/section0.xml"):
        return cls(pkg.read(name), name)

    # ---- 공용 헬퍼 ----
    def _paras(self):
        return list(self.root.iter(_q("p")))

    def _direct_ts(self, p):
        return [t for run in p.findall(_q("run")) for t in run.findall(_q("t"))]

    def _para_text(self, p):
        return "".join(t.text or "" for t in self._direct_ts(p))

    def _max_id(self):
        best = 0
        for el in self.root.iter():
            v = el.get("id")
            if v and v.isdigit():
                best = max(best, int(v))
        return best

    def _mark(self, p):
        if p not in self._modified:
            self._modified.append(p)

    # ---- 문구 교체 (run 분할 대응) ----
    def replace_text(self, mapping):
        report = {"replaced": {}, "not_found": []}
        for old, new in mapping.items():
            total = 0
            for p in self._paras():
                ts = self._direct_ts(p)
                if not ts:
                    continue
                concat0 = "".join(t.text or "" for t in ts)
                starts = [m.start() for m in re.finditer(re.escape(old), concat0)]
                if not starts:
                    continue
                # 오른쪽 매치부터 처리하면 왼쪽 오프셋이 보존된다
                for i in reversed(starts):
                    j = i + len(old)
                    texts = [t.text or "" for t in ts]
                    pos = 0
                    first_done = False
                    for t, txt in zip(ts, texts):
                        s, e = pos, pos + len(txt)
                        pos = e
                        if e <= i or s >= j:
                            continue
                        head = txt[:i - s] if s < i else ""
                        tail = txt[j - s:] if e > j else ""
                        if not first_done:
                            t.text = head + new + tail
                            first_done = True
                        else:
                            t.text = tail
                    total += 1
                self._mark(p)
            report["replaced"][old] = total
            if total == 0:
                report["not_found"].append(old)
        return report

    # ---- 직렬화 ----
    def serialize(self):
        for p in self._modified:
            for seg in p.findall(_q("linesegarray")):
                p.remove(seg)
        body = ET.tostring(self.root, encoding="unicode")
        return (_XML_DECL + body).encode("utf-8")


def edit_file(src, dst, fn, section="Contents/section0.xml"):
    pkg = HwpxPackage.open(src)
    editor = SectionEditor.from_package(pkg, section)
    result = fn(editor)
    pkg.write_replaced(dst, {section: editor.serialize()})
    return result
```

- [ ] **Step 4: CLI 구현 (scripts/hwpx.py 수정)**

```python
# 상단 import에 추가:
from core import edit as edit_mod


def _finish_edited(dst, report):
    gate = guards.validate_package(dst)   # Task 6에서 check_package로 교체
    ok = gate["ok"] and not report.get("not_found")
    payload = {"ok": ok, "output": str(dst), "report": report, "gate": gate}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 2


def cmd_replace(args):
    mapping = json.loads(_read_text_utf8(args.map))
    report = edit_mod.edit_file(args.src, args.dst,
                                lambda ed: ed.replace_text(mapping))
    return _finish_edited(args.dst, report)

# build_parser() 안:
    r = sub.add_parser("replace", help="문구 교체 (run 분할 대응)")
    r.add_argument("src")
    r.add_argument("dst")
    r.add_argument("--map", required=True, help='{"옛 문구": "새 문구"} JSON 파일')
    r.set_defaults(func=cmd_replace)
```

- [ ] **Step 5: 통과 확인**

Run: `python3.13 -m pytest tests/test_edit_replace.py tests/ -q`
Expected: 전체 green

- [ ] **Step 6: Commit**

```bash
git add core/edit.py scripts/hwpx.py tests/test_edit_replace.py
git commit -m "feat: 편집 엔진과 replace (run 분할 대응, linesegarray 관리)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 구조 편집 — set-cell / add-row / del-row / add-para

**Files:**
- Modify: `core/edit.py`
- Modify: `scripts/hwpx.py`
- Test: `tests/test_edit_struct.py`

**Interfaces:**
- Consumes: Task 3의 `SectionEditor`, `edit_file`, `_finish_edited`
- Produces (Task 5가 `set_cell_text`에 의존):
  - `.set_cell_text(table_index: int, row: int, col: int, text: str) -> None` — 표는 문서 순서, row/col은 cellAddr 기준. 첫 문단 첫 run의 hp:t에 텍스트(없으면 생성), 그 외 hp:t는 비움(자식 보존). 대상 없으면 `EditError`
  - `.add_row(table_index, cells: list[str]) -> None` — 마지막 행 복제(스타일 보존), cellAddr/rowCnt/문단 id/표 높이 갱신, 열 수 불일치·병합 표는 `EditError`
  - `.del_row(table_index, row) -> None` — 행 제거, 후속 rowAddr/rowCnt/높이 갱신, 병합 표 거부
  - `.add_para_after(anchor_text: str, text: str) -> None` — 기준 문단 복제 삽입(스타일 상속), 기준 문단에 secPr/표/그림 있으면 거부
  - CLI: `set-cell <src> <dst> --table N --row R --col C --text T` / `add-row <src> <dst> --table N --cells cells.json` / `del-row <src> <dst> --table N --row R` / `add-para <src> <dst> --after 문구 --text 내용`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_edit_struct.py
import json
import pytest
import xml.etree.ElementTree as ET
from core.package import HwpxPackage
from core.edit import edit_file, EditError
from core.guards import validate_package
from core.analyze import extract_text, analyze_document
from tests.fixture import build_form_hwpx

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def test_set_cell_text(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.set_cell_text(0, 0, 1, "홍길동"))
    assert "홍길동" in extract_text(dst)
    assert validate_package(dst)["ok"]


def test_set_cell_missing_raises(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx",
                  lambda ed: ed.set_cell_text(0, 9, 9, "x"))
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "y.hwpx",
                  lambda ed: ed.set_cell_text(5, 0, 0, "x"))


def test_add_row_updates_structure(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.add_row(0, ["이메일", "a@b.kr"]))
    doc = analyze_document(dst)
    assert doc["sections"][0]["tables"][0] == {"index": 0, "rows": 3, "cols": 2}
    text = extract_text(dst)
    assert "이메일" in text and "a@b.kr" in text
    assert validate_package(dst)["ok"]
    # 문단 id 고유성
    root = ET.fromstring(HwpxPackage.open(dst).read("Contents/section0.xml"))
    ids = [p.get("id") for p in root.iter(f"{{{NS_HP}}}p")]
    assert len(ids) == len(set(ids))


def test_add_row_wrong_cols_raises(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx", lambda ed: ed.add_row(0, ["하나"]))


def test_del_row_updates_addresses(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.del_row(0, 0))
    doc = analyze_document(dst)
    assert doc["sections"][0]["tables"][0]["rows"] == 1
    text = extract_text(dst)
    assert "성명" not in text and "연락처" in text
    # 남은 행의 rowAddr가 0으로 당겨졌는지
    root = ET.fromstring(HwpxPackage.open(dst).read("Contents/section0.xml"))
    addrs = {a.get("rowAddr") for a in root.iter(f"{{{NS_HP}}}cellAddr")}
    assert addrs == {"0"}


def test_merged_table_rejected(tmp_path):
    import zipfile
    src = build_form_hwpx(tmp_path / "form.hwpx")
    # colSpan=2로 조작한 사본
    bad = tmp_path / "merged.hwpx"
    pkg = HwpxPackage.open(src)
    xml = pkg.read_text("Contents/section0.xml").replace(
        '<hp:cellSpan colSpan="1" rowSpan="1"/>',
        '<hp:cellSpan colSpan="2" rowSpan="1"/>', 1)
    pkg.write_replaced(bad, {"Contents/section0.xml": xml.encode("utf-8")})
    with pytest.raises(EditError):
        edit_file(bad, tmp_path / "x.hwpx", lambda ed: ed.add_row(0, ["a", "b"]))
    with pytest.raises(EditError):
        edit_file(bad, tmp_path / "y.hwpx", lambda ed: ed.del_row(0, 0))


def test_add_para_after(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst,
              lambda ed: ed.add_para_after("안녕하세요", "추가된 문단"))
    text = extract_text(dst)
    assert "추가된 문단" in text
    assert text.index("안녕하세요") < text.index("추가된 문단")
    assert validate_package(dst)["ok"]


def test_add_para_anchor_missing_or_container(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx",
                  lambda ed: ed.add_para_after("존재하지 않는 문구", "x"))
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_edit_struct.py -v`
Expected: FAIL (`AttributeError: set_cell_text`)

- [ ] **Step 3: 구현 (core/edit.py의 SectionEditor에 메서드 추가)**

```python
    # ---- 표 탐색 ----
    def _tables(self):
        return list(self.root.iter(_q("tbl")))

    def _get_table(self, table_index):
        tbls = self._tables()
        if not 0 <= table_index < len(tbls):
            raise EditError(f"표 없음: index {table_index} (표 {len(tbls)}개)")
        return tbls[table_index]

    def _reject_spans(self, tbl):
        for span in tbl.iter(_q("cellSpan")):
            if span.get("colSpan") != "1" or span.get("rowSpan") != "1":
                raise EditError("병합 셀(rowSpan/colSpan)이 있는 표는 구조 편집 불가")

    def _find_cell(self, table_index, row, col):
        tbl = self._get_table(table_index)
        for tc in tbl.iter(_q("tc")):
            addr = tc.find(_q("cellAddr"))
            if addr is not None and int(addr.get("rowAddr")) == row \
                    and int(addr.get("colAddr")) == col:
                return tbl, tc
        raise EditError(f"셀 없음: 표 {table_index} ({row},{col})")

    def _set_cell_content(self, tc, text):
        sub = tc.find(_q("subList"))
        if sub is None:
            raise EditError("셀에 subList 없음")
        paras = sub.findall(_q("p"))
        if not paras:
            raise EditError("셀에 문단 없음")
        first = paras[0]
        run = first.find(_q("run"))
        if run is None:
            raise EditError("셀 문단에 run 없음")
        t = run.find(_q("t"))
        if t is None:
            t = ET.SubElement(run, _q("t"))
        t.text = text
        for other in self._direct_ts(first):
            if other is not t:
                other.text = ""
        for extra in paras[1:]:
            for tt in self._direct_ts(extra):
                tt.text = ""
            self._mark(extra)
        self._mark(first)

    # ---- 셀/행 편집 ----
    def set_cell_text(self, table_index, row, col, text):
        _, tc = self._find_cell(table_index, row, col)
        self._set_cell_content(tc, text)

    def add_row(self, table_index, cells):
        tbl = self._get_table(table_index)
        self._reject_spans(tbl)
        trs = tbl.findall(_q("tr"))
        if not trs:
            raise EditError("행이 없는 표")
        last = trs[-1]
        n_cols = len(last.findall(_q("tc")))
        if len(cells) != n_cols:
            raise EditError(f"열 수 불일치: 값 {len(cells)}개, 표 {n_cols}열")
        new_tr = copy.deepcopy(last)
        next_id = self._max_id() + 1
        new_row = len(trs)
        row_height = 0
        for tc, value in zip(new_tr.findall(_q("tc")), cells):
            addr = tc.find(_q("cellAddr"))
            addr.set("rowAddr", str(new_row))
            sub = tc.find(_q("subList"))
            for p in sub.findall(_q("p")):
                p.set("id", str(next_id))
                next_id += 1
                for seg in p.findall(_q("linesegarray")):
                    p.remove(seg)
            self._set_cell_content(tc, value)
            sz = tc.find(_q("cellSz"))
            if sz is not None:
                row_height = max(row_height, int(sz.get("height", "0")))
        tbl.insert(list(tbl).index(last) + 1, new_tr)
        tbl.set("rowCnt", str(len(trs) + 1))
        tblsz = tbl.find(_q("sz"))
        if tblsz is not None and row_height:
            tblsz.set("height", str(int(tblsz.get("height", "0")) + row_height))

    def del_row(self, table_index, row):
        tbl = self._get_table(table_index)
        self._reject_spans(tbl)
        trs = tbl.findall(_q("tr"))
        target = None
        for tr in trs:
            tc = tr.find(_q("tc"))
            addr = tc.find(_q("cellAddr")) if tc is not None else None
            if addr is not None and int(addr.get("rowAddr")) == row:
                target = tr
                break
        if target is None:
            raise EditError(f"행 없음: {row}")
        first_tc = target.find(_q("tc"))
        cellsz = first_tc.find(_q("cellSz")) if first_tc is not None else None
        removed_h = int(cellsz.get("height", "0")) if cellsz is not None else 0
        tbl.remove(target)
        tbl.set("rowCnt", str(len(trs) - 1))
        for tr in tbl.findall(_q("tr")):
            for tc in tr.findall(_q("tc")):
                addr = tc.find(_q("cellAddr"))
                r = int(addr.get("rowAddr"))
                if r > row:
                    addr.set("rowAddr", str(r - 1))
        tblsz = tbl.find(_q("sz"))
        if tblsz is not None and removed_h:
            tblsz.set("height",
                      str(max(int(tblsz.get("height", "0")) - removed_h, 0)))

    # ---- 문단 추가 ----
    def add_para_after(self, anchor_text, text):
        anchor = None
        for p in self._paras():
            if anchor_text in self._para_text(p):
                for run in p.findall(_q("run")):
                    if (run.find(_q("secPr")) is not None
                            or run.find(_q("tbl")) is not None
                            or run.find(_q("pic")) is not None):
                        raise EditError(
                            "기준 문단에 secPr/표/그림이 있어 불가 — "
                            "일반 텍스트 문단을 기준으로 지정")
                anchor = p
                break
        if anchor is None:
            raise EditError(f"기준 문구 없음: {anchor_text}")
        parents = {c: par for par in self.root.iter() for c in par}
        parent = parents.get(anchor)
        if parent is None:
            raise EditError("기준 문단의 부모를 찾을 수 없음")
        new_p = copy.deepcopy(anchor)
        new_p.set("id", str(self._max_id() + 1))
        ts = self._direct_ts(new_p)
        ts[0].text = text
        for t in ts[1:]:
            t.text = ""
        for seg in new_p.findall(_q("linesegarray")):
            new_p.remove(seg)
        parent.insert(list(parent).index(anchor) + 1, new_p)
        self._mark(new_p)
```

- [ ] **Step 4: CLI 구현 (scripts/hwpx.py 수정)**

```python
def cmd_set_cell(args):
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.set_cell_text(args.table, args.row,
                                                   args.col, args.text))
    return _finish_edited(args.dst,
                          {"set_cell": [args.table, args.row, args.col]})


def cmd_add_row(args):
    cells = json.loads(_read_text_utf8(args.cells))
    edit_mod.edit_file(args.src, args.dst, lambda ed: ed.add_row(args.table, cells))
    return _finish_edited(args.dst, {"added_row": cells})


def cmd_del_row(args):
    edit_mod.edit_file(args.src, args.dst, lambda ed: ed.del_row(args.table, args.row))
    return _finish_edited(args.dst, {"deleted_row": args.row})


def cmd_add_para(args):
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.add_para_after(args.after, args.text))
    return _finish_edited(args.dst, {"added_after": args.after})

# build_parser() 안:
    sc = sub.add_parser("set-cell", help="표 셀 텍스트 설정")
    sc.add_argument("src"); sc.add_argument("dst")
    sc.add_argument("--table", type=int, required=True)
    sc.add_argument("--row", type=int, required=True)
    sc.add_argument("--col", type=int, required=True)
    sc.add_argument("--text", required=True)
    sc.set_defaults(func=cmd_set_cell)

    ar = sub.add_parser("add-row", help="표 행 추가 (마지막 행 복제)")
    ar.add_argument("src"); ar.add_argument("dst")
    ar.add_argument("--table", type=int, required=True)
    ar.add_argument("--cells", required=True, help='["값1","값2"] JSON 파일')
    ar.set_defaults(func=cmd_add_row)

    dr = sub.add_parser("del-row", help="표 행 삭제")
    dr.add_argument("src"); dr.add_argument("dst")
    dr.add_argument("--table", type=int, required=True)
    dr.add_argument("--row", type=int, required=True)
    dr.set_defaults(func=cmd_del_row)

    ap = sub.add_parser("add-para", help="기준 문구 뒤 문단 추가")
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--after", required=True)
    ap.add_argument("--text", required=True)
    ap.set_defaults(func=cmd_add_para)
```

- [ ] **Step 5: 통과 확인**

Run: `python3.13 -m pytest tests/test_edit_struct.py tests/ -q`
Expected: 전체 green

- [ ] **Step 6: Commit**

```bash
git add core/edit.py scripts/hwpx.py tests/test_edit_struct.py
git commit -m "feat: 구조 편집 (set-cell/add-row/del-row/add-para)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 양식 채우기 — fill_targets + core/fill.py + CLI fill

**Files:**
- Modify: `core/analyze.py` (`fill_targets`, `_norm_label` 추가)
- Create: `core/fill.py`
- Modify: `scripts/hwpx.py`
- Test: `tests/test_fill.py`

**Interfaces:**
- Consumes: `SectionEditor.set_cell_text`/`replace_text`, `edit_file`, `analyze._sections`/`_para_direct_text`
- Produces:
  - `analyze._norm_label(s: str) -> str` — 공백/콜론(반각·전각)/괄호 제거
  - `analyze.fill_targets(path) -> dict` — `{"targets": [...]}`:
    - `{"key", "kind": "label-cell", "label", "table", "row", "col"}` — 라벨(비어있지 않고 ≤10자) 셀의 오른쪽 빈 셀
    - `{"key", "kind": "checkbox", "literal"}` — `□` + 뒤따르는 단어(≤10자). literal은 원문 그대로(`□동의`)
    - `{"key", "kind": "paren", "literal", "prefix", "blank"}` — `(공백+)` 빈칸. literal=prefix+blank (prefix는 빈칸 앞 최대 10자)
    - 표를 품은 컨테이너 문단은 checkbox/paren 스캔에서 제외, 셀 내부 문단은 포함
  - `fill.fill_file(src, dst, values: dict | None = None, cells: list | None = None) -> dict` — `{"filled": [key...], "unmatched": [key...]}`:
    - values의 키를 `_norm_label`로 정규화해 타겟 key와 매칭(동일 또는 한쪽이 접두사)
    - label-cell → `set_cell_text`; checkbox → 값이 truthy면 literal의 `□`를 `☑`로 교체(replace_text); paren → literal을 `prefix + "(" + 값 + ")"`로 교체
    - cells `[{"table","row","col","value"}]` → 좌표 직접 채움
  - CLI: `fill <src> --analyze` (타겟 JSON 출력) / `fill <src> <dst> --values values.json [--cells cells.json]` — unmatched 있으면 exit 2

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_fill.py
import json
import pytest
from core.analyze import fill_targets, extract_text
from core.fill import fill_file
from core.guards import validate_package
from tests.fixture import build_form_hwpx


def test_fill_targets_detects_all_kinds(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    targets = fill_targets(p)["targets"]
    kinds = {t["kind"] for t in targets}
    assert kinds == {"label-cell", "checkbox", "paren"}
    labels = {t["key"] for t in targets if t["kind"] == "label-cell"}
    assert labels == {"성명", "연락처"}
    boxes = {t["literal"] for t in targets if t["kind"] == "checkbox"}
    assert boxes == {"□동의", "□비동의"}
    paren = next(t for t in targets if t["kind"] == "paren")
    assert paren["blank"] == "(  )"
    assert paren["literal"].endswith("(  )")


def test_fill_by_labels_and_checkbox_and_paren(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "filled.hwpx"
    report = fill_file(src, dst, values={
        "성  명": "홍길동",          # 정규화 매칭 확인 (공백 삽입)
        "연락처": "010-1234-5678",
        "동의": True,
        "일반": "3",
    })
    assert report["unmatched"] == []
    text = extract_text(dst)
    assert "홍길동" in text and "010-1234-5678" in text
    assert "☑동의" in text and "□비동의" in text     # 비동의는 그대로
    assert "일반(3)통" in text
    assert validate_package(dst)["ok"]


def test_fill_unmatched_reported(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    report = fill_file(src, dst, values={"없는라벨": "x"})
    assert report["unmatched"] == ["없는라벨"]


def test_fill_by_cells_coordinates(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    report = fill_file(src, dst,
                       cells=[{"table": 0, "row": 1, "col": 1,
                               "value": "curator@x.kr"}])
    assert report["filled"] == ["cell:0:1:1"]
    assert "curator@x.kr" in extract_text(dst)


def test_cli_fill_analyze_and_apply(tmp_path, capsys):
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    src = build_form_hwpx(tmp_path / "form.hwpx")

    rc = hwpx_cli.main(["fill", str(src), "--analyze"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and len(payload["targets"]) >= 4

    values = tmp_path / "values.json"
    values.write_text(json.dumps({"성명": "김철수"}), encoding="utf-8")
    dst = tmp_path / "out.hwpx"
    rc = hwpx_cli.main(["fill", str(src), str(dst), "--values", str(values)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    assert "김철수" in extract_text(dst)
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_fill.py -v`
Expected: FAIL (`ImportError: fill_targets`)

- [ ] **Step 3: analyze.fill_targets 구현 (core/analyze.py에 추가)**

```python
# core/analyze.py에 추가
_CHECKBOX_RE = re.compile(r"□\s*(\S{1,10})")
_PAREN_RE = re.compile(r"\(\s+\)")


def _norm_label(s):
    return re.sub(r"[\s:：()（）]", "", s)


def fill_targets(path):
    pkg = HwpxPackage.open(path)
    targets = []
    table_index = 0
    for name, root in _sections(pkg):
        for p in root.findall(_q("p")):
            tbls = [tbl for run in p.findall(_q("run"))
                    for tbl in run.findall(_q("tbl"))]
            if tbls:
                for tbl in tbls:
                    grid = {}
                    for tc in tbl.iter(_q("tc")):
                        addr = tc.find(_q("cellAddr"))
                        r = int(addr.get("rowAddr"))
                        c = int(addr.get("colAddr"))
                        sub = tc.find(_q("subList"))
                        cell_text = ""
                        if sub is not None:
                            cell_text = " ".join(
                                _para_direct_text(cp)
                                for cp in sub.findall(_q("p"))).strip()
                        grid[(r, c)] = cell_text
                    for (r, c), cell_text in sorted(grid.items()):
                        if (cell_text and len(cell_text) <= 10
                                and grid.get((r, c + 1)) == ""):
                            targets.append({
                                "key": _norm_label(cell_text),
                                "kind": "label-cell", "label": cell_text,
                                "table": table_index, "row": r, "col": c + 1})
                    table_index += 1
                continue
            text = _para_direct_text(p)
            for m in _CHECKBOX_RE.finditer(text):
                targets.append({"key": _norm_label(m.group(1)),
                                "kind": "checkbox", "literal": m.group(0)})
            for m in _PAREN_RE.finditer(text):
                prefix = text[max(0, m.start() - 10):m.start()]
                targets.append({"key": _norm_label(prefix),
                                "kind": "paren", "prefix": prefix,
                                "blank": m.group(0),
                                "literal": prefix + m.group(0)})
    return {"targets": targets}
```

주의: paren의 key는 prefix 정규화 결과라 `제출부수일반` 같은 합성 키가 된다. 매칭이 접두사 규칙(한쪽이 다른 쪽의 접두사)이므로 사용자가 `일반`으로 주면… 접두사가 아니라 **포함**이다. 매칭 규칙에 "한쪽이 다른 쪽을 포함(in)"을 사용한다 — Step 4의 `_match` 참조.

- [ ] **Step 4: core/fill.py 구현**

```python
# core/fill.py
"""양식 채우기 — fill_targets 결과에 값을 매핑해 적용."""
from core import analyze
from core.edit import edit_file


def _match(norm_key, target_key):
    if not norm_key or not target_key:
        return False
    return norm_key == target_key or norm_key in target_key \
        or target_key in norm_key


def fill_file(src, dst, values=None, cells=None):
    values = values or {}
    cells = cells or []
    targets = analyze.fill_targets(src)["targets"]

    plan = []          # (설명 키, 적용 함수 목록용 데이터)
    unmatched = []
    for key, val in values.items():
        nk = analyze._norm_label(key)
        tgt = next((t for t in targets if _match(nk, t["key"])), None)
        if tgt is None:
            unmatched.append(key)
        else:
            plan.append((key, tgt, val))

    def apply(ed):
        filled = []
        for key, tgt, val in plan:
            if tgt["kind"] == "label-cell":
                ed.set_cell_text(tgt["table"], tgt["row"], tgt["col"], str(val))
            elif tgt["kind"] == "checkbox":
                if val:
                    ed.replace_text(
                        {tgt["literal"]: tgt["literal"].replace("□", "☑", 1)})
            elif tgt["kind"] == "paren":
                ed.replace_text(
                    {tgt["literal"]: tgt["prefix"] + "(" + str(val) + ")"})
            filled.append(key)
        for spec in cells:
            ed.set_cell_text(spec["table"], spec["row"], spec["col"],
                             str(spec["value"]))
            filled.append(f"cell:{spec['table']}:{spec['row']}:{spec['col']}")
        return filled

    filled = edit_file(src, dst, apply)
    return {"filled": filled, "unmatched": unmatched}
```

- [ ] **Step 5: CLI 구현 (scripts/hwpx.py 수정)**

```python
from core import fill as fill_mod


def cmd_fill(args):
    if args.analyze:
        result = analyze.fill_targets(args.src)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not args.dst:
        raise PackageError("채우기에는 <dst> 인자가 필요합니다")
    values = json.loads(_read_text_utf8(args.values)) if args.values else None
    cells = json.loads(_read_text_utf8(args.cells)) if args.cells else None
    if not values and not cells:
        raise PackageError("--values 또는 --cells 중 하나는 필요합니다")
    report = fill_mod.fill_file(args.src, args.dst, values=values, cells=cells)
    gate = guards.validate_package(args.dst)   # Task 6에서 check로 교체
    ok = gate["ok"] and not report["unmatched"]
    print(json.dumps({"ok": ok, "output": args.dst, "report": report,
                      "gate": gate}, ensure_ascii=False, indent=2))
    return 0 if ok else 2

# build_parser() 안:
    f = sub.add_parser("fill", help="양식 필드 채우기")
    f.add_argument("src")
    f.add_argument("dst", nargs="?")
    f.add_argument("--analyze", action="store_true", help="채울 타겟만 출력")
    f.add_argument("--values", help='{"라벨": "값"} JSON 파일')
    f.add_argument("--cells", help='[{"table","row","col","value"}] JSON 파일')
    f.set_defaults(func=cmd_fill)
```

- [ ] **Step 6: 통과 확인**

Run: `python3.13 -m pytest tests/test_fill.py tests/ -q`
Expected: 전체 green

- [ ] **Step 7: Commit**

```bash
git add core/analyze.py core/fill.py scripts/hwpx.py tests/test_fill.py
git commit -m "feat: 양식 채우기 (fill_targets + fill)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: check/guard 게이트 + CLI + SKILL.md 편집 워크플로우

**Files:**
- Modify: `core/guards.py` (`check_package`, `guard_against_reference` 추가)
- Modify: `scripts/hwpx.py` (check/guard 서브커맨드, `_finish_edited`/`cmd_fill`의 게이트를 check로 교체)
- Modify: `SKILL.md`, `README.md`
- Test: `tests/test_check_guard.py`

**Interfaces:**
- Consumes: `validate_package`, `section_names`, `extract_text`, 편집 CLI들
- Produces:
  - `guards.check_package(path) -> dict` — `{"ok", "errors", "warnings", "signals": {"char_border_bug": bool, "vertical_misconvert": bool}}`. validate 결과에 사고 패턴 검출을 더함:
    - char-border-bug: charPr 과반이 실선 edge를 가진 borderFill을 참조 → error
    - vertical-misconvert: 셀 subList 과반(4개 이상일 때)이 textDirection VERTICAL → error
  - `guards.guard_against_reference(output, reference, *, rules=None, max_growth=None) -> dict` — `{"ok", "errors", "warnings", "growth"}`:
    - 레퍼런스의 비섹션 엔트리가 출력에서 바이트 동일해야 함 (`entry-changed`/`entry-missing`), 출력에 추가 엔트리 없어야 함 (`entry-added`)
    - rules: `{"require": [...], "forbid": [...], "forbid_regex": [...]}` — extract_text 결과에 적용
    - growth: 공백 제외 글자 수 비율. max_growth 초과 시 error, 지정 없으면 1.05 초과 시 warning
  - CLI: `check <file>` (exit 0/2), `guard <output> --reference <ref> [--rules rules.json] [--max-growth 1.1]` (exit 0/2)
  - `_finish_edited`와 `cmd_fill`의 게이트를 `guards.check_package`로 교체 (스펙 §7: 전달 전 check 필수)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_check_guard.py
import json
import pytest
from core.package import HwpxPackage
from core.guards import check_package, guard_against_reference
from core.edit import edit_file
from tests.fixture import build_form_hwpx, build_minimal_hwpx


def test_check_passes_clean_document(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    r = check_package(p)
    assert r["ok"], r["errors"]
    assert r["signals"] == {"char_border_bug": False,
                            "vertical_misconvert": False}


def test_check_detects_char_border_bug(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    bad = tmp_path / "bad.hwpx"
    pkg = HwpxPackage.open(src)
    header = pkg.read_text("Contents/header.xml")
    # 유일한 charPr(id 0)가 실선 borderFill을 참조하도록 조작
    header = header.replace(
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>',
        '<hh:leftBorder type="SOLID" width="0.1 mm" color="#000000"/>')
    pkg.write_replaced(bad, {"Contents/header.xml": header.encode("utf-8")})
    r = check_package(bad)
    assert r["signals"]["char_border_bug"] is True
    assert not r["ok"]
    assert any(e.startswith("char-border-bug") for e in r["errors"])


def test_check_detects_vertical_misconvert(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    bad = tmp_path / "bad.hwpx"
    pkg = HwpxPackage.open(src)
    sec = pkg.read_text("Contents/section0.xml").replace(
        'textDirection="HORIZONTAL"', 'textDirection="VERTICAL"')
    pkg.write_replaced(bad, {"Contents/section0.xml": sec.encode("utf-8")})
    r = check_package(bad)
    assert r["signals"]["vertical_misconvert"] is True
    assert not r["ok"]


def test_guard_clean_edit_passes(tmp_path):
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    out = tmp_path / "out.hwpx"
    edit_file(ref, out, lambda ed: ed.replace_text({"안녕하세요": "반갑습니다"}))
    r = guard_against_reference(out, ref, rules={"require": ["반갑습니다"],
                                                 "forbid": ["안녕하세요"]})
    assert r["ok"], r["errors"]


def test_guard_detects_non_section_change_and_rules(tmp_path):
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    bad = tmp_path / "bad.hwpx"
    pkg = HwpxPackage.open(ref)
    header = pkg.read_text("Contents/header.xml").replace('height="1000"',
                                                          'height="1100"', 1)
    pkg.write_replaced(bad, {"Contents/header.xml": header.encode("utf-8")})
    r = guard_against_reference(bad, ref)
    assert any(e.startswith("entry-changed: Contents/header.xml")
               for e in r["errors"])

    out2 = tmp_path / "out2.hwpx"
    edit_file(ref, out2, lambda ed: ed.replace_text({}))
    r2 = guard_against_reference(out2, ref, rules={"forbid": ["안녕하세요"],
                                                   "require": ["없는문구"]})
    assert any(e.startswith("forbid-found") for e in r2["errors"])
    assert any(e.startswith("require-missing") for e in r2["errors"])


def test_guard_growth(tmp_path):
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    out = tmp_path / "out.hwpx"
    edit_file(ref, out, lambda ed: ed.replace_text(
        {"안녕하세요": "안녕하세요" * 30}))
    r = guard_against_reference(out, ref, max_growth=1.5)
    assert not r["ok"]
    assert any(e.startswith("growth-exceeded") for e in r["errors"])
    r2 = guard_against_reference(out, ref)
    assert any(w.startswith("growth-warning") for w in r2["warnings"])


def test_cli_check_and_guard(tmp_path, capsys):
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    rc = hwpx_cli.main(["check", str(ref)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True

    out = tmp_path / "out.hwpx"
    edit_file(ref, out, lambda ed: ed.replace_text({"성명": "이름"}))
    rc = hwpx_cli.main(["guard", str(out), "--reference", str(ref)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_check_guard.py -v`
Expected: FAIL (`ImportError: check_package`)

- [ ] **Step 3: guards 구현 (core/guards.py에 추가)**

```python
# core/guards.py에 추가 (기존 import 재사용: ET, zipfile, re,
#  HwpxPackage, PackageError, section_names)


def check_package(path):
    base = validate_package(path)
    signals = {"char_border_bug": False, "vertical_misconvert": False}
    errors = list(base["errors"])
    warnings = list(base["warnings"])
    try:
        pkg = HwpxPackage.open(path)
        header = ET.fromstring(pkg.read("Contents/header.xml"))
        solid_ids = set()
        for bf in header.iter(f"{{{NS_HH}}}borderFill"):
            for edge in ("leftBorder", "rightBorder", "topBorder",
                         "bottomBorder"):
                e = bf.find(f"{{{NS_HH}}}{edge}")
                if e is not None and e.get("type") not in (None, "NONE"):
                    solid_ids.add(bf.get("id"))
                    break
        chars = list(header.iter(f"{{{NS_HH}}}charPr"))
        bordered = [c for c in chars
                    if c.get("borderFillIDRef") in solid_ids]
        if chars and len(bordered) / len(chars) > 0.5:
            signals["char_border_bug"] = True
            errors.append(
                "char-border-bug: charPr 과반이 실선 테두리 borderFill 참조 — "
                "fix 후 재검사 필요")
        vert = total = 0
        for name in section_names(pkg.names()):
            root = ET.fromstring(pkg.read(name))
            for sub in root.iter(f"{{{NS_HP}}}subList"):
                total += 1
                if sub.get("textDirection") == "VERTICAL":
                    vert += 1
        if total >= 4 and vert / total > 0.5:
            signals["vertical_misconvert"] = True
            errors.append(
                "vertical-misconvert: 셀 과반이 세로쓰기 — 오변환 여부 확인 필요")
    except (PackageError, ET.ParseError):
        pass  # 구조 오류는 validate가 이미 errors에 보고
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "signals": signals}


def guard_against_reference(output, reference, *, rules=None, max_growth=None):
    from core.analyze import extract_text
    errors, warnings = [], []
    out_pkg = HwpxPackage.open(output)
    ref_pkg = HwpxPackage.open(reference)
    sections = set(section_names(ref_pkg.names()))
    out_names = set(out_pkg.names())
    for name in ref_pkg.names():
        if name in sections:
            continue
        if name not in out_names:
            errors.append(f"entry-missing: {name}")
        elif out_pkg.read(name) != ref_pkg.read(name):
            errors.append(f"entry-changed: {name} (섹션 외 엔트리는 바이트 동일해야 함)")
    for name in out_pkg.names():
        if name not in set(ref_pkg.names()):
            errors.append(f"entry-added: {name}")

    text = extract_text(output)
    rules = rules or {}
    for kw in rules.get("require", []):
        if kw not in text:
            errors.append(f"require-missing: {kw}")
    for kw in rules.get("forbid", []):
        if kw in text:
            errors.append(f"forbid-found: {kw}")
    for pat in rules.get("forbid_regex", []):
        if re.search(pat, text):
            errors.append(f"forbid-regex-found: {pat}")

    ref_len = len(re.sub(r"\s", "", extract_text(reference)))
    out_len = len(re.sub(r"\s", "", text))
    growth = (out_len / ref_len) if ref_len else 1.0
    if max_growth is not None:
        if growth > max_growth:
            errors.append(f"growth-exceeded: {growth:.2f} > {max_growth}")
    elif growth > 1.05:
        warnings.append(
            f"growth-warning: 공백 제외 글자 수 {growth:.2f}배 — 쪽수 증가 위험")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "growth": round(growth, 3)}
```

(`NS_HP`가 guards.py에 없으면 상단에 `NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"`를 추가 — Phase 1 코드에 이미 있다.)

- [ ] **Step 4: CLI 구현 + 게이트 교체 (scripts/hwpx.py 수정)**

```python
def cmd_check(args):
    result = guards.check_package(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def cmd_guard(args):
    rules = json.loads(_read_text_utf8(args.rules)) if args.rules else None
    result = guards.guard_against_reference(
        args.output, args.reference, rules=rules, max_growth=args.max_growth)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2

# build_parser() 안:
    ck = sub.add_parser("check", help="전달 전 필수 게이트 (validate + 사고 패턴)")
    ck.add_argument("file")
    ck.set_defaults(func=cmd_check)

    g = sub.add_parser("guard", help="레퍼런스 대비 가드")
    g.add_argument("output")
    g.add_argument("--reference", required=True)
    g.add_argument("--rules", help='{"require":[],"forbid":[],"forbid_regex":[]}')
    g.add_argument("--max-growth", type=float, default=None)
    g.set_defaults(func=cmd_guard)
```

그리고 `_finish_edited`와 `cmd_fill`의 `guards.validate_package(...)` 호출을 `guards.check_package(...)`로 교체한다 (Task 3/5 주석에 예고됨).

- [ ] **Step 5: SKILL.md / README 갱신**

SKILL.md 워크플로우 트리를 아래로 교체:

```markdown
## 워크플로우 선택

    사용자 요청
     ├─ "읽어줘/내용 알려줘" → extract
     ├─ "구조 분석" → analyze / "편집할 곳" → analyze --slots
     ├─ "새 문서 만들어줘" (마크다운) → new
     ├─ "문구 바꿔줘" → replace → (자동 check)
     ├─ "양식 빈칸 채워줘" → fill --analyze → values.json 작성 → fill → (자동 check)
     ├─ "표에 행 추가/삭제, 셀 수정" → add-row / del-row / set-cell
     ├─ "문단 추가" → add-para
     ├─ "파일 정상 확인" → check (편집 후엔 guard --reference 원본 병행)
     ├─ "XML 직접 수정" → unpack → 편집 → pack --source
     └─ .hwp 파일 → 미지원 안내
```

커맨드 블록에 추가:

```markdown
    # 편집 (원본 보존: 변경 섹션 외 바이트 동일, 자동 check 게이트)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" replace 원본.hwpx 결과.hwpx --map map.json
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" fill 양식.hwpx --analyze          # 1) 타겟 확인
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" fill 양식.hwpx 결과.hwpx --values values.json  # 2) 채우기
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-cell 원본.hwpx 결과.hwpx --table 0 --row 1 --col 1 --text "값"
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" add-row 원본.hwpx 결과.hwpx --table 0 --cells cells.json
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" del-row 원본.hwpx 결과.hwpx --table 0 --row 2
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" add-para 원본.hwpx 결과.hwpx --after "기준 문구" --text "새 문단"
    # 게이트
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" check 결과.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" guard 결과.hwpx --reference 원본.hwpx --rules rules.json
```

필수 규칙에 추가:

```markdown
7. 편집 커맨드(replace/fill/set-cell/add-row/del-row/add-para)는 check를
   자동 실행한다. ok:false면 산출물을 전달하지 않는다. 레퍼런스가 있는
   작업(기관명 교체 등 전면 수정)은 guard --reference로 원문 잔재
   (forbid)·필수 키워드(require)·글자 수 증가까지 검사한 뒤 전달한다.
8. 병합 셀(rowSpan/colSpan)이 있는 표의 행 추가/삭제는 거부된다(EditError).
   이 경우 구조 한계를 사용자에게 알린다.
9. fill 워크플로우: ① `fill --analyze`로 타겟 키 확인 → ② 타겟 key에만 값을
   매핑한 values.json 작성 → ③ `fill --values` 실행 → unmatched가 비어야 완료.
```

README 사용법 블록에 편집/게이트 커맨드 요약 3줄 추가:

```markdown
    python3 scripts/hwpx.py replace 원본.hwpx 결과.hwpx --map map.json   # 문구 교체
    python3 scripts/hwpx.py fill 양식.hwpx 결과.hwpx --values values.json # 양식 채우기
    python3 scripts/hwpx.py check 결과.hwpx                               # 전달 전 게이트
```

- [ ] **Step 6: 전체 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green

```bash
git add core/guards.py scripts/hwpx.py SKILL.md README.md tests/test_check_guard.py
git commit -m "feat: check/guard 게이트와 편집 워크플로우 문서

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 3 이후

- Phase 4(개체·고급 서식): 이미지/도형/각주/머리말·꼬리말/다단/페이지 설정, merge-cells/add-col, set-text-style/set-para-style — 별도 계획.
- 한컴 실물 검증 체크포인트(docs/hancom-verification.md)는 여전히 미수행 — 편집 경로는 원본 보존이라 리스크가 낮지만, 생성(new) 경로 검증 시 편집 산출물도 함께 확인 권장.
- 이월 minor (레저 유지): ET 재직렬화 표기 차이는 한컴 파일 실측에서 재평가.
