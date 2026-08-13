# hwpx-toolkit Phase 1 (기반) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** HWPX 패키지의 바이트 보존 읽기/쓰기, 구조 검증, 텍스트 추출, 구조/슬롯 분석을 제공하는 스킬의 기반 계층을 완성한다.

**Architecture:** 순수 stdlib 코어 모듈(core/package.py, core/guards.py, core/analyze.py) 위에 단일 CLI(scripts/hwpx.py)의 서브커맨드를 얹는다. 테스트 픽스처는 자체 빌더(tests/fixture.py)로 생성하며 외부 파일을 복사하지 않는다.

**Tech Stack:** Python 3.9+ stdlib만 (zipfile, zlib, struct, xml.etree.ElementTree, json, argparse, pathlib). 테스트는 pytest.

**Spec:** `docs/superpowers/specs/2026-08-13-hwpx-toolkit-design.md`

## Global Constraints

- 의존성: 코어와 CLI는 Python 3.9+ 표준 라이브러리만 사용한다 (스펙 §9).
- 클린룸: 외부 저장소의 코드·XML·픽스처를 복사하지 않는다 (스펙 §2).
- 바이트 보존: 편집 시 변경 대상 ZIP 엔트리 외에는 로컬 헤더·압축 바이트·플래그가 바이트 동일해야 한다 (스펙 §5 package.py).
- mimetype은 항상 첫 ZIP 엔트리 + STORED, 내용은 `application/hwp+zip` (스펙 §5).
- OWPML 네임스페이스: hs=`http://www.hancom.co.kr/hwpml/2011/section`, hp=`.../2011/paragraph`, hh=`.../2011/head`, hc=`.../2011/core`.
- LICENSE 저작권 표기: `Copyright (c) 2026 Kyunghoon` (사용자 확정값; 변경 요청 시 LICENSE 1행만 수정).
- 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 추가.
- 모든 CLI 서브커맨드는 기계 소비용 JSON을 stdout으로 출력한다 (extract 텍스트 출력 제외). 실패 시 exit code 2.

---

### Task 1: 저장소 스캐폴딩

**Files:**
- Create: `LICENSE`
- Create: `README.md`
- Create: `.gitignore`
- Create: `core/__init__.py` (빈 파일)
- Create: `tests/__init__.py` (빈 파일)

**Interfaces:**
- Consumes: 없음
- Produces: 저장소 뼈대. 이후 모든 태스크가 `core/`, `tests/` 패키지를 사용.

- [ ] **Step 1: LICENSE 작성**

```text
MIT License

Copyright (c) 2026 Kyunghoon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: README.md 작성**

```markdown
# hwpx-toolkit

한글(Hancom Office) HWPX 문서를 생성·읽기·편집·검증하는 MIT 라이선스 Claude 스킬.

- 순수 Python stdlib 코어 (pip install 불필요)
- 원본 바이트 보존 편집 (변경 엔트리 외 바이트 동일)
- 전달 전 필수 검증 게이트

## 사용법 (Phase 1)

    python3 scripts/hwpx.py extract 문서.hwpx            # 텍스트 추출
    python3 scripts/hwpx.py extract 문서.hwpx --format markdown
    python3 scripts/hwpx.py analyze 문서.hwpx            # 구조/슬롯 JSON
    python3 scripts/hwpx.py validate 문서.hwpx           # 구조 검증
    python3 scripts/hwpx.py unpack 문서.hwpx ./out/      # ZIP 해체
    python3 scripts/hwpx.py pack ./out/ 결과.hwpx --source 문서.hwpx

## 개발

    python3 -m pytest tests/ -v

## 라이선스

MIT — [LICENSE](LICENSE) 참조. 설계 배경은 docs/superpowers/specs/ 참조.
```

- [ ] **Step 3: .gitignore 작성**

```text
__pycache__/
*.pyc
.pytest_cache/
build/
*.hwpx
!tests/fixtures/**
```

- [ ] **Step 4: 빈 패키지 파일 생성**

`core/__init__.py`, `tests/__init__.py`를 빈 내용으로 생성.

- [ ] **Step 5: pytest 동작 확인**

Run: `cd <저장소 루트> && python3 -m pytest tests/ -v`
Expected: "no tests ran" (에러 없이 종료)

- [ ] **Step 6: Commit**

```bash
git add LICENSE README.md .gitignore core/__init__.py tests/__init__.py
git commit -m "chore: 저장소 스캐폴딩 (MIT LICENSE, README)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 테스트 픽스처 빌더

**Files:**
- Create: `tests/fixture.py`
- Test: `tests/test_fixture.py`

**Interfaces:**
- Consumes: 없음
- Produces: `build_minimal_hwpx(path: Path, *, body_texts: list[str] | None = None, with_table: bool = False) -> Path` — 이후 모든 테스트가 사용. 반환값은 생성된 파일 경로.

이 픽스처는 "우리 validator 기준으로 유효"한 최소 HWPX이다. 한컴 열림 보장은 Phase 2의 base 템플릿에서 다룬다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_fixture.py
import zipfile
from pathlib import Path
from tests.fixture import build_minimal_hwpx


def test_fixture_is_valid_zip_with_mimetype_first(tmp_path):
    p = build_minimal_hwpx(tmp_path / "min.hwpx")
    assert zipfile.is_zipfile(p)
    with zipfile.ZipFile(p) as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/hwp+zip"
        names = zf.namelist()
        for required in ("version.xml", "Contents/header.xml",
                         "Contents/content.hpf", "Contents/section0.xml"):
            assert required in names


def test_fixture_with_table_contains_tbl(tmp_path):
    p = build_minimal_hwpx(tmp_path / "tbl.hwpx", with_table=True)
    with zipfile.ZipFile(p) as zf:
        xml = zf.read("Contents/section0.xml").decode("utf-8")
    assert "<hp:tbl" in xml and 'rowCnt="2"' in xml
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_fixture.py -v`
Expected: FAIL (`ModuleNotFoundError: tests.fixture`)

- [ ] **Step 3: 픽스처 빌더 구현**

```python
# tests/fixture.py
"""테스트용 최소 HWPX 패키지 빌더 (자체 작성 XML, 외부 파일 미복사)."""
import zipfile
from pathlib import Path

MIMETYPE = "application/hwp+zip"

VERSION_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
    'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="1" '
    'buildNumber="0" os="10" xmlVersion="1.4" application="hwpx-toolkit" appVersion="0.1"/>'
)

SETTINGS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"/>'
)

CONTAINER_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" '
    'media-type="application/hwpml-package+xml"/></ocf:rootfiles></ocf:container>'
)

MANIFEST_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'
)

CONTENT_HPF = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" version="" '
    'unique-identifier="" id="">'
    '<opf:metadata><opf:title>fixture</opf:title></opf:metadata>'
    '<opf:manifest>'
    '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
    '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
    '</opf:manifest>'
    '<opf:spine><opf:itemref idref="header"/><opf:itemref idref="section0"/></opf:spine>'
    '</opf:package>'
)

HEADER_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
    'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" version="1.4" secCnt="1">'
    '<hh:refList>'
    '<hh:fontfaces itemCnt="1">'
    '<hh:fontface lang="HANGUL" fontCnt="1">'
    '<hh:font id="0" face="함초롬바탕" type="TTF" isEmbedded="0"/>'
    '</hh:fontface></hh:fontfaces>'
    '<hh:borderFills itemCnt="1">'
    '<hh:borderFill id="1" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
    '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
    '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
    '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
    '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
    '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
    '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
    '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
    '</hh:borderFill></hh:borderFills>'
    '<hh:charProperties itemCnt="1">'
    '<hh:charPr id="0" height="1000" textColor="#000000" shadeColor="none" '
    'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="1">'
    '<hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
    '</hh:charPr></hh:charProperties>'
    '<hh:paraProperties itemCnt="1">'
    '<hh:paraPr id="0" tabPrIDRef="0" condense="0" fontLineHeight="0" '
    'snapToGrid="1" suppressLineNumbers="0" checked="0">'
    '<hh:align horizontal="JUSTIFY" vertical="BASELINE"/>'
    '</hh:paraPr></hh:paraProperties>'
    '</hh:refList></hh:head>'
)

SECTION_HEAD = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
    '<hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0">'
    '<hp:run charPrIDRef="0">'
    '<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000">'
    '<hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">'
    '<hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" '
    'top="5668" bottom="4252"/>'
    '</hp:pagePr></hp:secPr>'
    '<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" '
    'sameSz="1" sameGap="0"/></hp:ctrl>'
    '</hp:run></hp:p>'
)

BODY_PARA = (
    '<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0">'
    '<hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run></hp:p>'
)


def _cell(row, col, text, pid):
    return (
        '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
        'dirty="0" borderFillIDRef="1">'
        '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
        'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
        'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run></hp:p>'
        '</hp:subList>'
        f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:cellSz width="21260" height="2400"/>'
        '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
        '</hp:tc>'
    )


def _table():
    rows = []
    pid = 1000000200
    for r in range(2):
        cells = "".join(_cell(r, c, f"셀{r}{c}", pid + r * 2 + c) for c in range(2))
        rows.append(f"<hp:tr>{cells}</hp:tr>")
    return (
        '<hp:p id="1000000100" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
        '<hp:tbl id="1000000101" zOrder="0" numberingType="TABLE" '
        'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" rowCnt="2" '
        'colCnt="2" cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
        '<hp:sz width="42520" widthRelTo="ABSOLUTE" height="4800" '
        'heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
        'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
        'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
        'vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        + "".join(rows) +
        '</hp:tbl></hp:run></hp:p>'
    )


def build_minimal_hwpx(path, *, body_texts=None, with_table=False):
    path = Path(path)
    if body_texts is None:
        body_texts = ["안녕하세요", "두 번째 문단"]
    parts = [SECTION_HEAD]
    pid = 1000000002
    for t in body_texts:
        parts.append(BODY_PARA.format(pid=pid, text=t))
        pid += 1
    if with_table:
        parts.append(_table())
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
            zf.writestr(zipfile.ZipInfo(name), text.encode("utf-8"), compress_type=ctype)
    return path
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_fixture.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fixture.py tests/test_fixture.py
git commit -m "test: 최소 HWPX 픽스처 빌더 추가

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: core/package.py — 읽기 API

**Files:**
- Create: `core/package.py`
- Test: `tests/test_package_read.py`

**Interfaces:**
- Consumes: `tests.fixture.build_minimal_hwpx`
- Produces: `HwpxPackage` 클래스 —
  - `HwpxPackage.open(path: str | Path) -> HwpxPackage`
  - `.names() -> list[str]` (로컬 레코드 순서)
  - `.read(name: str) -> bytes`
  - `.read_text(name: str) -> str` (UTF-8 디코드)
  - `.path: Path` 속성
  - 예외 `PackageError(Exception)`, `UnsupportedZipError(PackageError)`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_package_read.py
import pytest
from core.package import HwpxPackage, PackageError
from tests.fixture import build_minimal_hwpx


def test_open_and_list_names_in_local_order(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx")
    pkg = HwpxPackage.open(p)
    assert pkg.names()[0] == "mimetype"
    assert "Contents/section0.xml" in pkg.names()


def test_read_bytes_and_text(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx")
    pkg = HwpxPackage.open(p)
    assert pkg.read("mimetype") == b"application/hwp+zip"
    assert "안녕하세요" in pkg.read_text("Contents/section0.xml")


def test_read_missing_entry_raises(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx")
    pkg = HwpxPackage.open(p)
    with pytest.raises(PackageError):
        pkg.read("없는파일.xml")


def test_open_non_zip_raises(tmp_path):
    bad = tmp_path / "bad.hwpx"
    bad.write_bytes(b"not a zip")
    with pytest.raises(PackageError):
        HwpxPackage.open(bad)
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_package_read.py -v`
Expected: FAIL (`ModuleNotFoundError: core.package`)

- [ ] **Step 3: 읽기 API 구현**

```python
# core/package.py
"""HWPX ZIP 패키지 IO — 읽기 + 바이트 보존 쓰기 (순수 stdlib)."""
import io
import struct
import zipfile
import zlib
from pathlib import Path


class PackageError(Exception):
    pass


class UnsupportedZipError(PackageError):
    pass


class HwpxPackage:
    def __init__(self, path, data, zf):
        self.path = Path(path)
        self._data = data          # 원본 파일 전체 바이트
        self._zf = zf              # zipfile.ZipFile(BytesIO)
        self._infos = sorted(zf.infolist(), key=lambda i: i.header_offset)

    @classmethod
    def open(cls, path):
        path = Path(path)
        try:
            data = path.read_bytes()
        except OSError as e:
            raise PackageError(f"파일을 읽을 수 없음: {path}: {e}") from e
        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise PackageError(f"ZIP 형식이 아님: {path}")
        zf = zipfile.ZipFile(io.BytesIO(data))
        return cls(path, data, zf)

    def names(self):
        return [i.filename for i in self._infos]

    def read(self, name):
        try:
            return self._zf.read(name)
        except KeyError as e:
            raise PackageError(f"엔트리 없음: {name}") from e

    def read_text(self, name):
        return self.read(name).decode("utf-8")
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_package_read.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add core/package.py tests/test_package_read.py
git commit -m "feat: HwpxPackage 읽기 API

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: core/package.py — 바이트 보존 쓰기

**Files:**
- Modify: `core/package.py` (Task 3의 클래스에 메서드 추가)
- Test: `tests/test_package_write.py`

**Interfaces:**
- Consumes: Task 3의 `HwpxPackage`
- Produces: `HwpxPackage.write_replaced(dst: str | Path, replacements: dict[str, bytes]) -> None`
  - 교체 대상 외 모든 엔트리는 로컬 헤더+압축 바이트가 원본과 바이트 동일
  - replacements에 없는 이름이 원본에 없으면 `PackageError`
  - flag bit 3(data descriptor) 또는 ZIP64 감지 시 `UnsupportedZipError`

핵심 설계: 원본 파일 바이트에서 (1) 각 엔트리의 로컬 레코드(로컬 헤더+압축 데이터)를 슬라이스로 확보, (2) 중앙 디렉터리 레코드도 원시 바이트로 확보한다. 쓸 때는 무변경 엔트리의 로컬 레코드를 그대로 이어 붙이고, 교체 엔트리는 원본 로컬 헤더의 crc/csize/usize 필드(오프셋 14/18/22)만 패치해 재사용한다. 중앙 레코드는 원시 바이트에서 offset 필드(42)와 교체 엔트리의 crc/사이즈(16/20/24)만 패치한다. EOCD는 cd size(12)/offset(16)만 패치한다. 이렇게 하면 무변경 시 출력이 원본과 완전 동일하다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_package_write.py
import zipfile
from core.package import HwpxPackage
from tests.fixture import build_minimal_hwpx


def test_noop_rewrite_is_byte_identical(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    dst = tmp_path / "dst.hwpx"
    HwpxPackage.open(src).write_replaced(dst, {})
    assert dst.read_bytes() == src.read_bytes()


def test_replace_one_entry_preserves_others(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    dst = tmp_path / "dst.hwpx"
    pkg = HwpxPackage.open(src)
    new_xml = pkg.read_text("Contents/section0.xml").replace("안녕하세요", "반갑습니다")
    pkg.write_replaced(dst, {"Contents/section0.xml": new_xml.encode("utf-8")})

    out = HwpxPackage.open(dst)
    assert "반갑습니다" in out.read_text("Contents/section0.xml")
    # 교체 대상 외 엔트리는 압축 바이트까지 동일
    with zipfile.ZipFile(src) as za, zipfile.ZipFile(dst) as zb:
        for name in za.namelist():
            if name == "Contents/section0.xml":
                continue
            ia, ib = za.getinfo(name), zb.getinfo(name)
            assert (ia.CRC, ia.compress_size, ia.file_size, ia.flag_bits,
                    ia.compress_type, ia.date_time) == \
                   (ib.CRC, ib.compress_size, ib.file_size, ib.flag_bits,
                    ib.compress_type, ib.date_time)
    # 결과는 여전히 유효한 ZIP + mimetype 첫 엔트리
    with zipfile.ZipFile(dst) as zf:
        assert zf.testzip() is None
        assert zf.infolist()[0].filename == "mimetype"


def test_replace_unknown_name_raises(tmp_path):
    import pytest
    from core.package import PackageError
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    with pytest.raises(PackageError):
        HwpxPackage.open(src).write_replaced(tmp_path / "x.hwpx", {"없음.xml": b""})
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_package_write.py -v`
Expected: FAIL (`AttributeError: write_replaced`)

- [ ] **Step 3: 바이트 보존 쓰기 구현 (core/package.py에 추가)**

```python
# core/package.py에 추가 (클래스 밖 헬퍼 + 메서드)

_EOCD_SIG = b"PK\x05\x06"
_CENTRAL_SIG = b"PK\x01\x02"


def _find_eocd(data):
    idx = data.rfind(_EOCD_SIG)
    if idx < 0:
        raise PackageError("EOCD 레코드 없음")
    return idx


def _central_records(data):
    """중앙 디렉터리를 (원시 바이트, 파일명) 리스트로 반환."""
    eocd = _find_eocd(data)
    cd_size, cd_off = struct.unpack("<II", data[eocd + 12:eocd + 20])
    if cd_off == 0xFFFFFFFF:
        raise UnsupportedZipError("ZIP64 미지원")
    records, pos, end = [], cd_off, cd_off + cd_size
    while pos < end:
        if data[pos:pos + 4] != _CENTRAL_SIG:
            raise PackageError("중앙 디렉터리 손상")
        fn_len, ex_len, cm_len = struct.unpack("<HHH", data[pos + 28:pos + 34])
        rec_len = 46 + fn_len + ex_len + cm_len
        name = data[pos + 46:pos + 46 + fn_len].decode("utf-8")
        records.append((bytearray(data[pos:pos + rec_len]), name))
        pos += rec_len
    return records, eocd


def _local_record_span(data, info):
    """엔트리의 (로컬 헤더 시작, 데이터 시작, 레코드 끝) 오프셋."""
    off = info.header_offset
    if info.flag_bits & 0x08:
        raise UnsupportedZipError(f"data descriptor 사용 엔트리 미지원: {info.filename}")
    fn_len, ex_len = struct.unpack("<HH", data[off + 26:off + 30])
    data_start = off + 30 + fn_len + ex_len
    return off, data_start, data_start + info.compress_size


class HwpxPackage:
    # ... Task 3의 기존 메서드 유지 ...

    def write_replaced(self, dst, replacements):
        names = set(self.names())
        for name in replacements:
            if name not in names:
                raise PackageError(f"원본에 없는 엔트리 교체 불가: {name}")
        data = self._data
        centrals, eocd = _central_records(data)
        central_by_name = {n: rec for rec, n in centrals}

        out = io.BytesIO()
        new_offsets = {}
        for info in self._infos:
            name = info.filename
            start, data_start, end = _local_record_span(data, info)
            new_offsets[name] = out.tell()
            if name in replacements:
                raw = replacements[name]
                crc = zlib.crc32(raw) & 0xFFFFFFFF
                if info.compress_type == zipfile.ZIP_STORED:
                    comp = raw
                else:
                    c = zlib.compressobj(9, zlib.DEFLATED, -15)
                    comp = c.compress(raw) + c.flush()
                header = bytearray(data[start:data_start])
                struct.pack_into("<III", header, 14, crc, len(comp), len(raw))
                out.write(header)
                out.write(comp)
                central = central_by_name[name]
                struct.pack_into("<III", central, 16, crc, len(comp), len(raw))
            else:
                out.write(data[start:end])

        cd_start = out.tell()
        for rec, name in centrals:
            struct.pack_into("<I", rec, 42, new_offsets[name])
            out.write(rec)
        cd_size = out.tell() - cd_start
        eocd_rec = bytearray(data[eocd:eocd + 22] + data[eocd + 22:eocd + 22 +
                             struct.unpack("<H", data[eocd + 20:eocd + 22])[0]])
        struct.pack_into("<II", eocd_rec, 12, cd_size, cd_start)
        out.write(eocd_rec)
        Path(dst).write_bytes(out.getvalue())
```

주의: `_central_records`가 반환한 레코드 순서와 `self._infos`(로컬 순서)는 다를 수 있으므로 중앙 디렉터리는 반드시 **원본 중앙 디렉터리 순서**로 쓴다 (위 코드처럼 `centrals` 순회).

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_package_write.py tests/test_package_read.py -v`
Expected: 7 PASS (no-op 바이트 동일 테스트 포함)

- [ ] **Step 5: Commit**

```bash
git add core/package.py tests/test_package_write.py
git commit -m "feat: 바이트 보존 엔트리 교체 쓰기 (write_replaced)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: core/guards.py validate + CLI 뼈대

**Files:**
- Create: `core/guards.py`
- Create: `scripts/hwpx.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `HwpxPackage` (Task 3)
- Produces:
  - `guards.validate_package(path) -> dict` — `{"ok": bool, "errors": [str], "warnings": [str]}`. 에러 문자열은 `코드: 상세` 형식 (코드 목록은 아래).
  - CLI: `python3 scripts/hwpx.py validate <file>` — JSON 출력, ok면 exit 0, 아니면 exit 2.
  - CLI 뼈대: argparse 서브파서 구조. 이후 태스크가 서브커맨드를 추가.

에러 코드: `zip-invalid`, `required-missing`, `mimetype-not-first`, `mimetype-not-stored`, `mimetype-bad-content`, `xml-malformed`, `itemcnt-mismatch`, `dangling-ref`, `secpr-missing`.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_validate.py
import zipfile
from core.guards import validate_package
from tests.fixture import build_minimal_hwpx


def test_fixture_passes(tmp_path):
    p = build_minimal_hwpx(tmp_path / "ok.hwpx")
    r = validate_package(p)
    assert r["ok"], r["errors"]


def _rebuild_without_mimetype_first(src, dst):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        infos = zin.infolist()
        for info in infos[1:] + infos[:1]:   # mimetype을 마지막으로
            zout.writestr(info, zin.read(info.filename))


def test_mimetype_not_first_fails(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    _rebuild_without_mimetype_first(src, bad)
    r = validate_package(bad)
    assert not r["ok"]
    assert any(e.startswith("mimetype-not-first") for e in r["errors"])


def _replace_entry(src, dst, name, new_bytes):
    from core.package import HwpxPackage
    HwpxPackage.open(src).write_replaced(dst, {name: new_bytes})


def test_malformed_xml_fails(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    _replace_entry(src, bad, "Contents/section0.xml", b"<hs:sec>깨진 XML")
    r = validate_package(bad)
    assert any(e.startswith("xml-malformed") for e in r["errors"])


def test_itemcnt_mismatch_fails(tmp_path):
    from core.package import HwpxPackage
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    header = HwpxPackage.open(src).read_text("Contents/header.xml")
    header = header.replace('charProperties itemCnt="1"', 'charProperties itemCnt="5"')
    _replace_entry(src, bad, "Contents/header.xml", header.encode("utf-8"))
    r = validate_package(bad)
    assert any(e.startswith("itemcnt-mismatch") for e in r["errors"])


def test_dangling_charpr_ref_fails(tmp_path):
    from core.package import HwpxPackage
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    sec = HwpxPackage.open(src).read_text("Contents/section0.xml")
    sec = sec.replace('charPrIDRef="0"', 'charPrIDRef="99"', 1)
    _replace_entry(src, bad, "Contents/section0.xml", sec.encode("utf-8"))
    r = validate_package(bad)
    assert any(e.startswith("dangling-ref") for e in r["errors"])


def test_missing_secpr_fails(tmp_path):
    from core.package import HwpxPackage
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    sec = HwpxPackage.open(src).read_text("Contents/section0.xml")
    start = sec.index("<hp:secPr")
    end = sec.index("</hp:secPr>") + len("</hp:secPr>")
    _replace_entry(src, bad, "Contents/section0.xml",
                   (sec[:start] + sec[end:]).encode("utf-8"))
    r = validate_package(bad)
    assert any(e.startswith("secpr-missing") for e in r["errors"])
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_validate.py -v`
Expected: FAIL (`ModuleNotFoundError: core.guards`)

- [ ] **Step 3: validate 구현**

```python
# core/guards.py
"""검증 게이트 — Phase 1: 구조 검증(validate)."""
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from core.package import HwpxPackage, PackageError

REQUIRED_ENTRIES = ("mimetype", "version.xml", "Contents/header.xml",
                    "Contents/content.hpf")
MIMETYPE_VALUE = b"application/hwp+zip"

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

# header.xml의 (컬렉션 태그, 자식 태그, 섹션에서 참조하는 속성명)
_ID_GROUPS = [
    ("charProperties", "charPr", "charPrIDRef"),
    ("paraProperties", "paraPr", "paraPrIDRef"),
    ("borderFills", "borderFill", "borderFillIDRef"),
]


def validate_package(path):
    errors, warnings = [], []
    try:
        pkg = HwpxPackage.open(path)
    except PackageError as e:
        return {"ok": False, "errors": [f"zip-invalid: {e}"], "warnings": []}

    names = pkg.names()
    for req in REQUIRED_ENTRIES:
        if req not in names:
            errors.append(f"required-missing: {req}")
    sections = sorted(n for n in names
                      if re.fullmatch(r"Contents/section\d+\.xml", n))
    if not sections:
        errors.append("required-missing: Contents/section*.xml")

    if "mimetype" in names:
        if names[0] != "mimetype":
            errors.append("mimetype-not-first: mimetype이 첫 엔트리가 아님")
        with zipfile.ZipFile(pkg.path) as zf:
            info = zf.getinfo("mimetype")
            if info.compress_type != zipfile.ZIP_STORED:
                errors.append("mimetype-not-stored: STORED가 아님")
        if pkg.read("mimetype") != MIMETYPE_VALUE:
            errors.append("mimetype-bad-content: application/hwp+zip 아님")

    trees = {}
    for name in names:
        if not (name.endswith(".xml") or name.endswith(".hpf")):
            continue
        try:
            trees[name] = ET.fromstring(pkg.read(name))
        except ET.ParseError as e:
            errors.append(f"xml-malformed: {name}: {e}")

    header = trees.get("Contents/header.xml")
    defined = {}
    if header is not None:
        for coll, child, _ in _ID_GROUPS:
            coll_el = header.find(f".//{{{NS_HH}}}{coll}")
            if coll_el is None:
                defined[child] = set()
                continue
            children = coll_el.findall(f"{{{NS_HH}}}{child}")
            declared = coll_el.get("itemCnt")
            if declared is not None and int(declared) != len(children):
                errors.append(
                    f"itemcnt-mismatch: {coll} itemCnt={declared}, 실제={len(children)}")
            defined[child] = {c.get("id") for c in children}

    for sec_name in sections:
        tree = trees.get(sec_name)
        if tree is None:
            continue
        for coll, child, attr in _ID_GROUPS:
            used = set(re.findall(rf'{attr}="(\d+)"', pkg.read_text(sec_name)))
            missing = used - defined.get(child, set())
            if header is not None and missing:
                errors.append(
                    f"dangling-ref: {sec_name} {attr} 미정의 id {sorted(missing)}")
        first_p = tree.find(f"{{{NS_HP}}}p")
        if first_p is not None:
            first_run = first_p.find(f"{{{NS_HP}}}run")
            has_secpr = (first_run is not None and
                         first_run.find(f"{{{NS_HP}}}secPr") is not None)
            if not has_secpr:
                errors.append(f"secpr-missing: {sec_name} 첫 문단 첫 런에 secPr 없음")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
```

- [ ] **Step 4: CLI 뼈대 + validate 서브커맨드 구현**

```python
# scripts/hwpx.py
#!/usr/bin/env python3
"""hwpx-toolkit 단일 CLI. 사용: python3 scripts/hwpx.py <command> ..."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import guards  # noqa: E402


def cmd_validate(args):
    result = guards.validate_package(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def build_parser():
    p = argparse.ArgumentParser(prog="hwpx")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="HWPX 구조 검증")
    v.add_argument("file")
    v.set_defaults(func=cmd_validate)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 통과 확인**

Run: `python3 -m pytest tests/test_validate.py -v` → 6 PASS
Run: `python3 scripts/hwpx.py validate <(echo)` 대신 실제 픽스처로:
`python3 -c "from tests.fixture import build_minimal_hwpx; build_minimal_hwpx('/tmp/f.hwpx')" && python3 scripts/hwpx.py validate /tmp/f.hwpx; echo "exit=$?"`
Expected: `"ok": true`, exit=0

- [ ] **Step 6: Commit**

```bash
git add core/guards.py scripts/hwpx.py tests/test_validate.py
git commit -m "feat: validate 게이트와 CLI 뼈대

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: core/analyze.py — 텍스트 추출 + CLI extract

**Files:**
- Create: `core/analyze.py`
- Modify: `scripts/hwpx.py` (extract 서브커맨드 추가)
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: `HwpxPackage`
- Produces:
  - `analyze.extract_text(path, fmt="text") -> str` — fmt는 `"text"` 또는 `"markdown"`. 문단은 줄 단위, 표는 text 모드에서 `셀1 | 셀2` 행, markdown 모드에서 GitHub 표(첫 행을 헤더로).
  - CLI: `hwpx.py extract <file> [--format text|markdown]` — stdout에 텍스트 출력.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_extract.py
from core.analyze import extract_text
from tests.fixture import build_minimal_hwpx


def test_extract_plain_text(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx",
                           body_texts=["첫 문단", "둘째 문단"])
    out = extract_text(p)
    assert "첫 문단" in out and "둘째 문단" in out
    assert out.index("첫 문단") < out.index("둘째 문단")


def test_extract_includes_table_cells(tmp_path):
    p = build_minimal_hwpx(tmp_path / "t.hwpx", with_table=True)
    out = extract_text(p)
    assert "셀00" in out and "셀11" in out


def test_extract_markdown_table(tmp_path):
    p = build_minimal_hwpx(tmp_path / "t.hwpx", with_table=True)
    md = extract_text(p, fmt="markdown")
    assert "| 셀00 | 셀01 |" in md
    assert "| --- | --- |" in md
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_extract.py -v`
Expected: FAIL (`ModuleNotFoundError: core.analyze`)

- [ ] **Step 3: extract_text 구현**

```python
# core/analyze.py
"""문서 분석 — 텍스트 추출, 구조 리포트, 편집 슬롯."""
import re
import xml.etree.ElementTree as ET

from core.package import HwpxPackage

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _q(tag):
    return f"{{{NS_HP}}}{tag}"


def _para_direct_text(p_el):
    """문단의 직접 런 텍스트 (표/개체 내부 제외)."""
    parts = []
    for run in p_el.findall(_q("run")):
        for t in run.findall(_q("t")):
            parts.append("".join(t.itertext()))
    return "".join(parts)


def _table_rows(tbl_el):
    rows = []
    for tr in tbl_el.findall(_q("tr")):
        row = []
        for tc in tr.findall(_q("tc")):
            texts = []
            sublist = tc.find(_q("subList"))
            if sublist is not None:
                for p in sublist.findall(_q("p")):
                    texts.append(_para_direct_text(p))
            row.append(" ".join(t for t in texts if t))
        rows.append(row)
    return rows


def _sections(pkg):
    names = sorted(n for n in pkg.names()
                   if re.fullmatch(r"Contents/section\d+\.xml", n))
    return [(n, ET.fromstring(pkg.read(n))) for n in names]


def extract_text(path, fmt="text"):
    pkg = HwpxPackage.open(path)
    lines = []
    for _, root in _sections(pkg):
        for p in root.findall(_q("p")):
            tbls = [tbl for run in p.findall(_q("run"))
                    for tbl in run.findall(_q("tbl"))]
            if tbls:
                for tbl in tbls:
                    rows = _table_rows(tbl)
                    if not rows:
                        continue
                    if fmt == "markdown":
                        lines.append("| " + " | ".join(rows[0]) + " |")
                        lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
                        for row in rows[1:]:
                            lines.append("| " + " | ".join(row) + " |")
                    else:
                        for row in rows:
                            lines.append(" | ".join(row))
                continue
            text = _para_direct_text(p)
            if text:
                lines.append(text)
    return "\n".join(lines)
```

- [ ] **Step 4: CLI에 extract 추가 (scripts/hwpx.py 수정)**

`build_parser()`에 추가:

```python
from core import analyze  # 파일 상단 import에 추가


def cmd_extract(args):
    print(analyze.extract_text(args.file, fmt=args.format))
    return 0

# build_parser() 안:
    e = sub.add_parser("extract", help="텍스트 추출")
    e.add_argument("file")
    e.add_argument("--format", choices=["text", "markdown"], default="text")
    e.set_defaults(func=cmd_extract)
```

- [ ] **Step 5: 통과 확인**

Run: `python3 -m pytest tests/test_extract.py -v` → 3 PASS
Run: `python3 -c "from tests.fixture import build_minimal_hwpx; build_minimal_hwpx('/tmp/f.hwpx', with_table=True)" && python3 scripts/hwpx.py extract /tmp/f.hwpx --format markdown`
Expected: 문단 텍스트와 마크다운 표 출력

- [ ] **Step 6: Commit**

```bash
git add core/analyze.py scripts/hwpx.py tests/test_extract.py
git commit -m "feat: 텍스트 추출 (extract, 표/마크다운 지원)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: core/analyze.py — 구조 리포트 + 슬롯 + CLI analyze

**Files:**
- Modify: `core/analyze.py`
- Modify: `scripts/hwpx.py` (analyze 서브커맨드 추가)
- Test: `tests/test_analyze.py`

**Interfaces:**
- Consumes: Task 6의 `_sections`, `_para_direct_text`, `_table_rows`
- Produces:
  - `analyze.analyze_document(path) -> dict`:
    ```json
    {"page": {"width": 59528, "height": 84186,
              "margins": {"left":8504,"right":8504,"top":5668,"bottom":4252,
                          "header":4252,"footer":4252,"gutter":0}},
     "styles": {"charPrCount": 1, "paraPrCount": 1, "borderFillCount": 1},
     "sections": [{"name": "Contents/section0.xml", "paragraphCount": 3,
                   "tables": [{"index":0,"rows":2,"cols":2}]}]}
    ```
  - `analyze.extract_slots(path) -> dict`:
    ```json
    {"slots": [
      {"key": "p:1", "type": "paragraph", "section": "Contents/section0.xml",
       "text": "안녕하세요"},
      {"key": "cell:0:0:0", "type": "cell", "table": 0, "row": 0, "col": 0,
       "text": "셀00"}]}
    ```
    슬롯 규칙: `p:<문서순 문단 인덱스>`는 직접 텍스트가 있고 표/그림을 품지 않은 문단만. `cell:<표번호>:<row>:<col>`은 모든 셀. 표 번호는 문서 전체 순서.
  - CLI: `hwpx.py analyze <file> [--slots]` — JSON 출력. `--slots`면 슬롯만, 아니면 구조 리포트.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_analyze.py
from core.analyze import analyze_document, extract_slots
from tests.fixture import build_minimal_hwpx


def test_analyze_reports_page_and_tables(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx", with_table=True)
    r = analyze_document(p)
    assert r["page"]["width"] == 59528
    assert r["page"]["margins"]["left"] == 8504
    assert r["styles"]["charPrCount"] == 1
    sec = r["sections"][0]
    assert sec["tables"] == [{"index": 0, "rows": 2, "cols": 2}]


def test_slots_paragraphs_and_cells(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx",
                           body_texts=["본문 하나"], with_table=True)
    slots = extract_slots(p)["slots"]
    keys = [s["key"] for s in slots]
    assert "p:1" in keys                 # p:0은 secPr 문단(텍스트 없음)이라 제외됨
    assert "cell:0:0:0" in keys and "cell:0:1:1" in keys
    cell = next(s for s in slots if s["key"] == "cell:0:1:1")
    assert cell["text"] == "셀11"
    # 표를 품은 컨테이너 문단은 p: 슬롯에 없어야 함
    para_texts = [s["text"] for s in slots if s["type"] == "paragraph"]
    assert all("셀" not in t for t in para_texts)
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_analyze.py -v`
Expected: FAIL (`ImportError: analyze_document`)

- [ ] **Step 3: 구현 (core/analyze.py에 추가)**

```python
# core/analyze.py에 추가

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def analyze_document(path):
    pkg = HwpxPackage.open(path)
    result = {"page": None, "styles": {}, "sections": []}

    header = ET.fromstring(pkg.read("Contents/header.xml"))
    for coll, key in (("charProperties", "charPrCount"),
                      ("paraProperties", "paraPrCount"),
                      ("borderFills", "borderFillCount")):
        el = header.find(f".//{{{NS_HH}}}{coll}")
        result["styles"][key] = len(list(el)) if el is not None else 0

    table_index = 0
    for name, root in _sections(pkg):
        sec_info = {"name": name, "paragraphCount": 0, "tables": []}
        for p in root.findall(_q("p")):
            sec_info["paragraphCount"] += 1
            for run in p.findall(_q("run")):
                secpr = run.find(_q("secPr"))
                if secpr is not None and result["page"] is None:
                    pagepr = secpr.find(_q("pagePr"))
                    if pagepr is not None:
                        margin = pagepr.find(_q("margin"))
                        result["page"] = {
                            "width": int(pagepr.get("width")),
                            "height": int(pagepr.get("height")),
                            "margins": {k: int(margin.get(k)) for k in
                                        ("left", "right", "top", "bottom",
                                         "header", "footer", "gutter")}
                            if margin is not None else {},
                        }
                for tbl in run.findall(_q("tbl")):
                    sec_info["tables"].append({
                        "index": table_index,
                        "rows": int(tbl.get("rowCnt")),
                        "cols": int(tbl.get("colCnt")),
                    })
                    table_index += 1
        result["sections"].append(sec_info)
    return result


def extract_slots(path):
    pkg = HwpxPackage.open(path)
    slots = []
    table_index = 0
    for name, root in _sections(pkg):
        for p_idx, p in enumerate(root.findall(_q("p"))):
            tbls = [tbl for run in p.findall(_q("run"))
                    for tbl in run.findall(_q("tbl"))]
            if tbls:
                for tbl in tbls:
                    for tr in tbl.findall(_q("tr")):
                        for tc in tr.findall(_q("tc")):
                            addr = tc.find(_q("cellAddr"))
                            row = int(addr.get("rowAddr"))
                            col = int(addr.get("colAddr"))
                            texts = []
                            sublist = tc.find(_q("subList"))
                            if sublist is not None:
                                for cp in sublist.findall(_q("p")):
                                    texts.append(_para_direct_text(cp))
                            slots.append({
                                "key": f"cell:{table_index}:{row}:{col}",
                                "type": "cell", "table": table_index,
                                "row": row, "col": col,
                                "text": " ".join(t for t in texts if t),
                            })
                    table_index += 1
                continue
            text = _para_direct_text(p)
            if text:
                slots.append({"key": f"p:{p_idx}", "type": "paragraph",
                              "section": name, "text": text})
    return {"slots": slots}
```

- [ ] **Step 4: CLI에 analyze 추가 (scripts/hwpx.py 수정)**

```python
def cmd_analyze(args):
    if args.slots:
        result = analyze.extract_slots(args.file)
    else:
        result = analyze.analyze_document(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

# build_parser() 안:
    a = sub.add_parser("analyze", help="구조/슬롯 분석")
    a.add_argument("file")
    a.add_argument("--slots", action="store_true", help="편집 슬롯만 출력")
    a.set_defaults(func=cmd_analyze)
```

- [ ] **Step 5: 통과 확인**

Run: `python3 -m pytest tests/test_analyze.py -v` → 2 PASS
Run: `python3 scripts/hwpx.py analyze /tmp/f.hwpx --slots`
Expected: 슬롯 JSON 출력

- [ ] **Step 6: Commit**

```bash
git add core/analyze.py scripts/hwpx.py tests/test_analyze.py
git commit -m "feat: 구조 리포트와 편집 슬롯 분석 (analyze)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: unpack / pack CLI

**Files:**
- Modify: `core/package.py` (`extract_to`, `pack_dir` 추가)
- Modify: `scripts/hwpx.py` (unpack/pack 서브커맨드 추가)
- Test: `tests/test_unpack_pack.py`

**Interfaces:**
- Consumes: `HwpxPackage`, `write_replaced`
- Produces:
  - `HwpxPackage.extract_to(dirpath: str | Path) -> list[str]` — 엔트리를 디렉터리에 풀고 엔트리명 리스트 반환.
  - `package.pack_dir(dirpath, dst, source=None) -> None` (모듈 함수) — source가 주어지면 디렉터리 내 파일 중 source와 바이트가 다른 것만 `write_replaced`로 교체(바이트 보존). source가 없으면 mimetype 첫 엔트리+STORED 규칙으로 새 ZIP 작성. 디렉터리에 source에 없는 파일이 있으면 `PackageError`.
  - CLI: `hwpx.py unpack <file> <dir>` / `hwpx.py pack <dir> <out> [--source original.hwpx]` — 결과 JSON `{"ok": true, "entries": N}` 출력.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_unpack_pack.py
from core.package import HwpxPackage, pack_dir
from tests.fixture import build_minimal_hwpx


def test_unpack_writes_all_entries(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    names = HwpxPackage.open(src).extract_to(outdir)
    assert (outdir / "mimetype").read_bytes() == b"application/hwp+zip"
    assert (outdir / "Contents" / "section0.xml").exists()
    assert "Contents/header.xml" in names


def test_pack_with_source_is_byte_preserving(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(src).extract_to(outdir)
    # 수정 없이 재패킹 → 바이트 동일
    out1 = tmp_path / "same.hwpx"
    pack_dir(outdir, out1, source=src)
    assert out1.read_bytes() == src.read_bytes()
    # section0만 수정 → 해당 엔트리만 변경
    sec = outdir / "Contents" / "section0.xml"
    sec.write_text(sec.read_text(encoding="utf-8").replace("안녕하세요", "수정됨"),
                   encoding="utf-8")
    out2 = tmp_path / "edited.hwpx"
    pack_dir(outdir, out2, source=src)
    assert "수정됨" in HwpxPackage.open(out2).read_text("Contents/section0.xml")


def test_pack_without_source_keeps_mimetype_first(tmp_path):
    import zipfile
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(src).extract_to(outdir)
    out = tmp_path / "fresh.hwpx"
    pack_dir(outdir, out)
    with zipfile.ZipFile(out) as zf:
        assert zf.infolist()[0].filename == "mimetype"
        assert zf.infolist()[0].compress_type == zipfile.ZIP_STORED
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_unpack_pack.py -v`
Expected: FAIL (`ImportError: pack_dir`)

- [ ] **Step 3: 구현 (core/package.py에 추가)**

```python
# core/package.py에 추가

class HwpxPackage:
    # ... 기존 메서드 유지 ...

    def extract_to(self, dirpath):
        dirpath = Path(dirpath)
        for name in self.names():
            target = dirpath / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.read(name))
        return self.names()


def pack_dir(dirpath, dst, source=None):
    dirpath = Path(dirpath)
    files = {str(f.relative_to(dirpath)).replace("\\", "/"): f
             for f in dirpath.rglob("*") if f.is_file()}
    if source is not None:
        pkg = HwpxPackage.open(source)
        src_names = set(pkg.names())
        extra = set(files) - src_names
        if extra:
            raise PackageError(f"원본에 없는 파일 (엔트리 추가는 Phase 3+): {sorted(extra)}")
        replacements = {}
        for name, f in files.items():
            data = f.read_bytes()
            if data != pkg.read(name):
                replacements[name] = data
        pkg.write_replaced(dst, replacements)
    else:
        names = sorted(files)
        if "mimetype" in files:
            names.remove("mimetype")
            names.insert(0, "mimetype")
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in names:
                ctype = (zipfile.ZIP_STORED if name == "mimetype"
                         else zipfile.ZIP_DEFLATED)
                zf.writestr(zipfile.ZipInfo(name), files[name].read_bytes(),
                            compress_type=ctype)
```

- [ ] **Step 4: CLI에 unpack/pack 추가 (scripts/hwpx.py 수정)**

```python
from core.package import HwpxPackage, pack_dir  # 상단 import에 추가


def cmd_unpack(args):
    names = HwpxPackage.open(args.file).extract_to(args.dir)
    print(json.dumps({"ok": True, "entries": len(names)}, ensure_ascii=False))
    return 0


def cmd_pack(args):
    pack_dir(args.dir, args.out, source=args.source)
    print(json.dumps({"ok": True}, ensure_ascii=False))
    return 0

# build_parser() 안:
    u = sub.add_parser("unpack", help="HWPX를 디렉터리로 해체")
    u.add_argument("file")
    u.add_argument("dir")
    u.set_defaults(func=cmd_unpack)

    k = sub.add_parser("pack", help="디렉터리를 HWPX로 패킹")
    k.add_argument("dir")
    k.add_argument("out")
    k.add_argument("--source", help="바이트 보존 기준이 될 원본 HWPX")
    k.set_defaults(func=cmd_pack)
```

- [ ] **Step 5: 통과 확인**

Run: `python3 -m pytest tests/test_unpack_pack.py -v` → 3 PASS

- [ ] **Step 6: Commit**

```bash
git add core/package.py scripts/hwpx.py tests/test_unpack_pack.py
git commit -m "feat: unpack/pack (바이트 보존 재패킹)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: SKILL.md v0 + 전체 검증

**Files:**
- Create: `SKILL.md`
- Create: `references/owpml-format.md`
- Modify: `README.md` (필요 시 사용법 갱신)

**Interfaces:**
- Consumes: Task 5~8의 CLI 서브커맨드
- Produces: LLM 진입점 SKILL.md (Phase 1 워크플로우), 포맷 레퍼런스 초판

- [ ] **Step 1: SKILL.md 작성**

```markdown
---
name: hwpx-toolkit
description: "한글(HWPX) 문서 읽기·분석·검증 스킬 (Phase 1). .hwpx 파일, 한글 문서,
  Hancom, OWPML 관련 요청 시 사용. 생성·편집 기능은 이후 Phase에서 추가된다.
  .hwp 바이너리는 지원하지 않는다."
allowed-tools: Bash(python3 *), Read, Write, Glob, Grep
---

# hwpx-toolkit

HWPX는 한컴오피스 한글의 개방형 문서 포맷(OWPML, KS X 6101)이다.
ZIP 패키지 + XML 파트 구조. 모든 커맨드는 순수 Python stdlib로 동작한다 (pip 불필요).

## 워크플로우 선택

    사용자 요청
     ├─ "읽어줘/내용 알려줘" → extract
     ├─ "구조 분석/어떤 양식인지" → analyze
     ├─ "편집할 곳 찾아줘" → analyze --slots
     ├─ "파일이 정상인지 확인" → validate
     ├─ "XML 직접 보기/고치기" → unpack → (편집) → pack --source
     └─ .hwp 파일 → 미지원 안내 (한글에서 .hwpx로 저장 요청)

## 커맨드

    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" extract 문서.hwpx [--format markdown]
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" analyze 문서.hwpx [--slots]
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" validate 문서.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" unpack 문서.hwpx ./작업디렉토리/
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" pack ./작업디렉토리/ 결과.hwpx --source 문서.hwpx

## 필수 규칙

1. **pack은 반드시 --source와 함께** 사용해 원본 바이트를 보존한다.
   --source 없는 pack은 새 문서 조립 전용(Phase 2 이후)이다.
2. **모든 산출물은 전달 전 validate를 통과**해야 한다. exit 0이 아니면
   사용자에게 완료를 보고하지 않는다.
3. XML 편집 시 네임스페이스 접두사(hp:, hs:, hh:, hc:)를 유지하고,
   `<hp:t>` 내부 자식 태그(hp:fwSpace 등)를 삭제하지 않는다.
4. .hwp(구형 바이너리)는 읽기·편집·변환 모두 미지원. 한글에서
   "다른 이름으로 저장 → HWPX"를 안내한다.

## 포맷 상세

references/owpml-format.md 참조 (단위: 1pt=100 HWPUNIT, A4 폭 59528, 본문폭 42520).
```

- [ ] **Step 2: references/owpml-format.md 작성**

```markdown
# OWPML(HWPX) 포맷 노트

자체 조사·KS X 6101 표준 기반 정리. 외부 문서를 복사하지 않는다.

## 패키지 구조

| 엔트리 | 역할 |
|--------|------|
| mimetype | `application/hwp+zip`, 첫 엔트리, STORED |
| version.xml | 포맷 버전 |
| settings.xml | 앱 설정 |
| META-INF/container.xml | 루트 파일(content.hpf) 지시 |
| Contents/content.hpf | 파트 목록(manifest/spine) |
| Contents/header.xml | 스타일 정의 (fontfaces/borderFills/charProperties/paraProperties) |
| Contents/section0.xml | 본문 (섹션당 1파일) |
| BinData/* | 이미지 등 바이너리 |

## 네임스페이스

| 접두사 | URI |
|--------|-----|
| hs | http://www.hancom.co.kr/hwpml/2011/section |
| hp | http://www.hancom.co.kr/hwpml/2011/paragraph |
| hh | http://www.hancom.co.kr/hwpml/2011/head |
| hc | http://www.hancom.co.kr/hwpml/2011/core |

## 단위 (HWPUNIT)

| 값 | HWPUNIT |
|----|---------|
| 1pt | 100 |
| 1mm | 283.5 |
| A4 폭 210mm | 59528 |
| A4 높이 297mm | 84186 |
| 기본 좌우여백 30mm | 8504 |
| A4 본문폭 | 42520 |

## 필수 불변식

1. section 첫 문단의 첫 run에 `hp:secPr` + `hp:ctrl/hp:colPr` 필수.
2. header.xml 각 컬렉션의 itemCnt = 실제 자식 수.
3. section의 charPrIDRef/paraPrIDRef/borderFillIDRef는 header에 정의된 id만 참조.
4. 문단 id는 문서 내 고유 정수.
5. 표: cellAddr(rowAddr/colAddr)와 rowCnt/colCnt 정합, 열 너비 합 = 표 폭.
6. `hp:t`는 mixed content — 텍스트와 hp:fwSpace/hp:lineBreak 등이 섞일 수 있으므로
   pretty-print 금지, 자식 태그 삭제 금지.
7. `hp:linesegarray`는 한컴의 줄 배치 캐시 — 텍스트 수정 시 해당 문단 것을 제거해야
   손상 경고를 피한다 (Phase 3 edit에서 구현).
```

- [ ] **Step 3: 전체 테스트 + CLI 스모크 확인**

Run: `python3 -m pytest tests/ -v`
Expected: 전체 PASS (약 20개)

Run:
```bash
python3 -c "from tests.fixture import build_minimal_hwpx; build_minimal_hwpx('/tmp/smoke.hwpx', with_table=True)"
python3 scripts/hwpx.py validate /tmp/smoke.hwpx
python3 scripts/hwpx.py extract /tmp/smoke.hwpx --format markdown
python3 scripts/hwpx.py analyze /tmp/smoke.hwpx --slots
```
Expected: validate ok:true, 텍스트/표/슬롯 정상 출력

- [ ] **Step 4: Commit**

```bash
git add SKILL.md references/owpml-format.md README.md
git commit -m "docs: SKILL.md v0와 OWPML 포맷 레퍼런스

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 1 이후

- Phase 2(생성: base 템플릿 + owpml 빌더 + new/build)는 별도 계획으로 작성한다.
  Phase 2 시작 시 한컴오피스 열림 검증(사용자 협조)이 필요하다.
- 실제 한컴 저장 HWPX로 `write_replaced` 바이트 보존을 검증하는 것은 사용자가
  샘플 .hwpx를 제공하는 즉시 수동 스모크 테스트로 수행한다 (픽스처는 합성 파일이므로).
```
