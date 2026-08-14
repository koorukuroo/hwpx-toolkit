# hwpx-toolkit Phase 2 (생성) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OWPML 스펙 기반 자체 base 템플릿과 요소 빌더(owpml.py)를 만들고, 마크다운→HWPX 생성 CLI(`new`, `build`)를 완성한다.

**Architecture:** templates/base/는 생성기 스크립트(scripts/dev/gen_base_template.py)가 만들어 커밋하는 정적 파일이다. core/template.py가 템플릿 디렉터리를 mimetype-first ZIP으로 조립하고, core/owpml.py가 문단/표 XML 조각을 생성하며, core/markdown.py가 마크다운을 블록으로 파싱해 owpml로 렌더링한다. 한컴 호환 리스크는 (1) secPr을 템플릿 section0.xml에서 추출하는 구조(추후 한컴 저장본으로 템플릿만 교체하면 코드 무변경)와 (2) 마지막 사용자 한컴 열림 검증 체크포인트로 헤지한다.

**Tech Stack:** Python 3.9+ stdlib (zipfile, xml.etree, re, json, argparse). pytest.

**Spec:** `docs/superpowers/specs/2026-08-13-hwpx-toolkit-design.md`

## Global Constraints

- 의존성: 코어와 CLI는 Python 3.9+ 표준 라이브러리만 (스펙 §9).
- 클린룸: 외부 저장소의 코드·XML·템플릿 복사 금지. templates/base/*는 OWPML(KS X 6101) 지식 기반 자체 작성 (스펙 §2, §8).
- mimetype은 첫 ZIP 엔트리 + STORED, 내용 `application/hwp+zip` (스펙 §5).
- 모든 생성 산출물은 전달 전 `guards.validate_package` 통과 필수; CLI 실패 시 JSON `{"ok": false, ...}` + exit 2 (Phase 1 확립 계약).
- 템플릿 파일 직접 편집 금지 — 수정은 생성기(scripts/dev/gen_base_template.py)를 고쳐 재실행.
- 테스트 실행: `python3.13 -m pytest tests/ -q` (이 머신의 plain python3에는 pytest 없음; venv 생성 금지). CLI 실행은 plain python3 가능.
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- OWPML 네임스페이스: hs/hp/hh/hc = `http://www.hancom.co.kr/hwpml/2011/{section,paragraph,head,core}`.
- 기존 35개 테스트는 전 태스크에서 green 유지.

## base 템플릿 스타일 ID 맵 (Task 1이 구현, 이후 태스크와 references 문서가 참조)

| 종류 | ID | 내용 |
|------|----|------|
| font | 0 | 함초롬바탕 (본문) |
| font | 1 | 함초롬돋움 (제목/헤더) |
| borderFill | 1 | 테두리 없음 (페이지 보더용) |
| borderFill | 2 | 테두리 없음 (charPr/paraPr 참조용) |
| borderFill | 3 | SOLID 0.12mm 4면 (표 본문 셀) |
| borderFill | 4 | SOLID 0.12mm 4면 + #E6E6E6 배경 (표 헤더 셀) |
| charPr | 0 | 10pt(1000) 바탕 본문 |
| charPr | 1 | 18pt(1800) 돋움 볼드 — 문서 제목(H1) |
| charPr | 2 | 14pt(1400) 돋움 볼드 — H2 |
| charPr | 3 | 12pt(1200) 돋움 볼드 — H3 이하 |
| charPr | 4 | 10pt(1000) 돋움 볼드 — 표 헤더 |
| paraPr | 0 | JUSTIFY 160% 본문 |
| paraPr | 1 | CENTER 160%, prev/next 800 — 제목(H1) |
| paraPr | 2 | LEFT 160%, prev 600 next 200 — H2 |
| paraPr | 3 | LEFT 160%, prev 400 next 100 — H3 이하 |
| paraPr | 4 | JUSTIFY 160%, left 600 — 목록 |
| paraPr | 5 | CENTER 130% — 표 셀 |
| style | 0 | PARA "바탕글" (paraPr 0 + charPr 0) |

---

### Task 1: base 템플릿 생성기와 템플릿 파일

**Files:**
- Create: `scripts/dev/gen_base_template.py`
- Create: `templates/base/` 전체 (생성기 실행 산출물: mimetype, version.xml, settings.xml, META-INF/container.xml, META-INF/manifest.xml, Contents/content.hpf, Contents/header.xml, Contents/section0.xml)
- Test: `tests/test_base_template.py`

**Interfaces:**
- Consumes: 없음
- Produces: `templates/base/` 정적 파일들. 이후 태스크가 의존하는 사실 —
  - `Contents/section0.xml`은 secPr+colPr을 품은 첫 문단 1개와 빈 문단 1개를 가진 완결된 `<hs:sec>` 문서
  - `Contents/content.hpf`에 문자열 `<opf:title>무제</opf:title>`가 정확히 1회 등장 (Task 2가 치환)
  - 스타일 ID 맵은 위 표와 일치

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_base_template.py
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "templates" / "base"

REQUIRED = [
    "mimetype", "version.xml", "settings.xml",
    "META-INF/container.xml", "META-INF/manifest.xml",
    "Contents/content.hpf", "Contents/header.xml", "Contents/section0.xml",
]

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def test_all_template_files_exist():
    for rel in REQUIRED:
        assert (BASE / rel).is_file(), f"누락: {rel}"


def test_mimetype_content():
    assert (BASE / "mimetype").read_bytes() == b"application/hwp+zip"


def test_all_xml_files_well_formed():
    for rel in REQUIRED:
        if rel == "mimetype":
            continue
        ET.fromstring((BASE / rel).read_bytes())


def test_header_itemcnt_consistency_and_style_map():
    root = ET.fromstring((BASE / "Contents/header.xml").read_bytes())
    for coll, child, expected in [
        ("fontfaces", "fontface", 7),
        ("borderFills", "borderFill", 4),
        ("charProperties", "charPr", 5),
        ("paraProperties", "paraPr", 6),
        ("styles", "style", 1),
    ]:
        el = root.find(f".//{{{NS_HH}}}{coll}")
        children = el.findall(f"{{{NS_HH}}}{child}")
        assert int(el.get("itemCnt")) == len(children) == expected, coll
    # 제목 charPr: 18pt 볼드
    char1 = root.find(f".//{{{NS_HH}}}charPr[@id='1']")
    assert char1.get("height") == "1800"
    assert char1.find(f"{{{NS_HH}}}bold") is not None
    # 표 헤더 borderFill 4는 배경색 보유
    bf4 = root.find(f".//{{{NS_HH}}}borderFill[@id='4']")
    assert b"E6E6E6" in ET.tostring(bf4)


def test_section_skeleton_first_para_has_secpr_and_colpr():
    root = ET.fromstring((BASE / "Contents/section0.xml").read_bytes())
    first_run = root.find(f"{{{NS_HP}}}p/{{{NS_HP}}}run")
    assert first_run.find(f"{{{NS_HP}}}secPr") is not None
    ctrl = first_run.find(f"{{{NS_HP}}}ctrl")
    assert ctrl is not None and ctrl.find(f"{{{NS_HP}}}colPr") is not None
    pagepr = first_run.find(f"{{{NS_HP}}}secPr/{{{NS_HP}}}pagePr")
    assert pagepr.get("width") == "59528" and pagepr.get("height") == "84186"


def test_content_hpf_has_title_token():
    text = (BASE / "Contents/content.hpf").read_text(encoding="utf-8")
    assert text.count("<opf:title>무제</opf:title>") == 1


def test_generator_is_idempotent():
    """생성기를 다시 실행해도 커밋된 파일과 동일해야 한다."""
    import subprocess, sys
    before = {rel: (BASE / rel).read_bytes() for rel in REQUIRED}
    subprocess.run([sys.executable,
                    str(BASE.parent.parent / "scripts/dev/gen_base_template.py")],
                   check=True)
    after = {rel: (BASE / rel).read_bytes() for rel in REQUIRED}
    assert before == after
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_base_template.py -v`
Expected: FAIL (템플릿 파일 없음)

- [ ] **Step 3: 생성기 구현**

```python
# scripts/dev/gen_base_template.py
#!/usr/bin/env python3
"""templates/base/* 생성기 — OWPML(KS X 6101) 지식 기반 클린룸 작성.

템플릿을 고칠 때는 이 파일을 수정하고 재실행한다 (산출물 직접 편집 금지).
스타일 ID 맵은 docs/superpowers/plans/2026-08-15-hwpx-toolkit-phase2.md 및
references/base-template-styles.md 참조.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BASE = ROOT / "templates" / "base"

LANGS = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]


def _seven(value):
    keys = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")
    return " ".join(f'{k}="{value}"' for k in keys)


def fontfaces():
    faces = []
    for lang in LANGS:
        faces.append(
            f'<hh:fontface lang="{lang}" fontCnt="2">'
            '<hh:font id="0" face="함초롬바탕" type="TTF" isEmbedded="0"/>'
            '<hh:font id="1" face="함초롬돋움" type="TTF" isEmbedded="0"/>'
            '</hh:fontface>')
    return '<hh:fontfaces itemCnt="7">' + "".join(faces) + '</hh:fontfaces>'


def border_fill(bid, edge_type="NONE", width="0.1 mm", fill=None):
    edges = "".join(
        f'<hh:{e}Border type="{edge_type}" width="{width}" color="#000000"/>'
        for e in ("left", "right", "top", "bottom"))
    fill_xml = ""
    if fill:
        fill_xml = (f'<hc:fillBrush><hc:winBrush faceColor="#{fill}" '
                    'hatchColor="#999999" alpha="0"/></hc:fillBrush>')
    return (f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" '
            'breakCellSeparateLine="0">'
            '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
            '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
            f'{edges}'
            '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
            f'{fill_xml}</hh:borderFill>')


def char_pr(cid, height, font=0, bold=False):
    bold_xml = "<hh:bold/>" if bold else ""
    return (f'<hh:charPr id="{cid}" height="{height}" textColor="#000000" '
            'shadeColor="none" useFontSpace="0" useKerning="0" symMark="NONE" '
            'borderFillIDRef="2">'
            f'<hh:fontRef {_seven(font)}/>'
            f'<hh:ratio {_seven(100)}/>'
            f'<hh:spacing {_seven(0)}/>'
            f'<hh:relSz {_seven(100)}/>'
            f'<hh:offset {_seven(0)}/>'
            f'{bold_xml}'
            '<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
            '<hh:strikeout shape="NONE" color="#000000"/>'
            '<hh:outline type="NONE"/>'
            '<hh:shadow type="NONE" color="#B2B2B2" offsetX="10" offsetY="10"/>'
            '</hh:charPr>')


def para_pr(pid, align="JUSTIFY", spacing=160, prev=0, nxt=0, left=0):
    margin = (
        '<hh:margin>'
        '<hc:intent value="0" unit="HWPUNIT"/>'
        f'<hc:left value="{left}" unit="HWPUNIT"/>'
        '<hc:right value="0" unit="HWPUNIT"/>'
        f'<hc:prev value="{prev}" unit="HWPUNIT"/>'
        f'<hc:next value="{nxt}" unit="HWPUNIT"/>'
        '</hh:margin>'
        f'<hh:lineSpacing type="PERCENT" value="{spacing}" unit="HWPUNIT"/>')
    return (f'<hh:paraPr id="{pid}" tabPrIDRef="0" condense="0" '
            'fontLineHeight="0" snapToGrid="1" suppressLineNumbers="0" checked="0">'
            f'<hh:align horizontal="{align}" vertical="BASELINE"/>'
            '<hh:heading type="NONE" idRef="0" level="0"/>'
            '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" '
            'widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" '
            'lineWrap="BREAK"/>'
            '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
            '<hp:switch>'
            f'<hp:case hp:required-namespace='
            f'"http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">{margin}</hp:case>'
            f'<hp:default>{margin}</hp:default>'
            '</hp:switch>'
            '<hh:border borderFillIDRef="2" offsetLeft="0" offsetRight="0" '
            'offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/>'
            '</hh:paraPr>')


def header_xml():
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
        'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
        'version="1.4" secCnt="1">',
        '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>',
        '<hh:refList>',
        fontfaces(),
        '<hh:borderFills itemCnt="4">',
        border_fill(1),
        border_fill(2),
        border_fill(3, edge_type="SOLID", width="0.12 mm"),
        border_fill(4, edge_type="SOLID", width="0.12 mm", fill="E6E6E6"),
        '</hh:borderFills>',
        '<hh:charProperties itemCnt="5">',
        char_pr(0, 1000),
        char_pr(1, 1800, font=1, bold=True),
        char_pr(2, 1400, font=1, bold=True),
        char_pr(3, 1200, font=1, bold=True),
        char_pr(4, 1000, font=1, bold=True),
        '</hh:charProperties>',
        '<hh:tabProperties itemCnt="1">'
        '<hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/>'
        '</hh:tabProperties>',
        '<hh:paraProperties itemCnt="6">',
        para_pr(0),
        para_pr(1, align="CENTER", prev=800, nxt=800),
        para_pr(2, align="LEFT", prev=600, nxt=200),
        para_pr(3, align="LEFT", prev=400, nxt=100),
        para_pr(4, left=600),
        para_pr(5, align="CENTER", spacing=130),
        '</hh:paraProperties>',
        '<hh:styles itemCnt="1">'
        '<hh:style id="0" type="PARA" name="바탕글" engName="Normal" '
        'paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0" langID="1042" '
        'lockForm="0"/>'
        '</hh:styles>',
        '</hh:refList>',
        '</hh:head>',
    ]
    return "".join(parts)


def _note_pr(tag, place, line_length):
    return (f'<hp:{tag}>'
            '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" '
            'suffixChar=")" supscript="0"/>'
            f'<hp:noteLine length="{line_length}" type="SOLID" width="0.12 mm" '
            'color="#000000"/>'
            '<hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/>'
            '<hp:numbering type="CONTINUOUS" newNum="1"/>'
            f'<hp:placement place="{place}" beneathText="0"/>'
            f'</hp:{tag}>')


def section0_xml():
    page_border = "".join(
        f'<hp:pageBorderFill type="{t}" borderFillIDRef="1" textBorder="PAPER" '
        'headerInside="0" footerInside="0" fillArea="PAPER">'
        '<hp:offset left="1417" right="1417" top="1417" bottom="1417"/>'
        '</hp:pageBorderFill>'
        for t in ("BOTH", "EVEN", "ODD"))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
        '<hp:p id="1000000000" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0">'
        '<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" '
        'tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" '
        'outlineShapeIDRef="0" memoShapeIDRef="0" textVerticalWidthHead="0" '
        'masterPageCnt="0">'
        '<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>'
        '<hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>'
        '<hp:visibility hideFirstHeader="0" hideFirstFooter="0" '
        'hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL" '
        'hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>'
        '<hp:lineNumberShape restartType="0" countBy="0" distance="0" '
        'startNumber="0"/>'
        '<hp:pagePr landscape="WIDELY" width="59528" height="84186" '
        'gutterType="LEFT_ONLY">'
        '<hp:margin header="4252" footer="4252" gutter="0" left="8504" '
        'right="8504" top="5668" bottom="4252"/>'
        '</hp:pagePr>'
        + _note_pr("footNotePr", "EACH_COLUMN", "-1")
        + _note_pr("endNotePr", "END_OF_DOCUMENT", "14692344")
        + page_border +
        '</hp:secPr>'
        '<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" '
        'sameSz="1" sameGap="0"/></hp:ctrl>'
        '</hp:run>'
        '<hp:run charPrIDRef="0"><hp:t/></hp:run>'
        '</hp:p>'
        '<hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0"><hp:t/></hp:run>'
        '</hp:p>'
        '</hs:sec>')


VERSION_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
    'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="1" '
    'buildNumber="0" os="10" xmlVersion="1.4" application="hwpx-toolkit" '
    'appVersion="0.2"/>')

SETTINGS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<ha:HWPApplicationSetting '
    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app">'
    '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>'
    '</ha:HWPApplicationSetting>')

CONTAINER_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<ocf:container '
    'xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" '
    'media-type="application/hwpml-package+xml"/></ocf:rootfiles>'
    '</ocf:container>')

MANIFEST_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<odf:manifest '
    'xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">'
    '<odf:file-entry odf:full-path="mimetype" odf:media-type=""/>'
    '<odf:file-entry odf:full-path="version.xml" odf:media-type=""/>'
    '<odf:file-entry odf:full-path="Contents/header.xml" '
    'odf:media-type="application/xml"/>'
    '<odf:file-entry odf:full-path="Contents/section0.xml" '
    'odf:media-type="application/xml"/>'
    '<odf:file-entry odf:full-path="settings.xml" '
    'odf:media-type="application/xml"/>'
    '</odf:manifest>')

CONTENT_HPF = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" version="" '
    'unique-identifier="" id="">'
    '<opf:metadata><opf:title>무제</opf:title>'
    '<opf:language>ko</opf:language></opf:metadata>'
    '<opf:manifest>'
    '<opf:item id="header" href="Contents/header.xml" '
    'media-type="application/xml"/>'
    '<opf:item id="section0" href="Contents/section0.xml" '
    'media-type="application/xml"/>'
    '<opf:item id="settings" href="settings.xml" '
    'media-type="application/xml"/>'
    '</opf:manifest>'
    '<opf:spine><opf:itemref idref="header"/>'
    '<opf:itemref idref="section0"/></opf:spine>'
    '</opf:package>')


def main():
    files = {
        "mimetype": "application/hwp+zip",
        "version.xml": VERSION_XML,
        "settings.xml": SETTINGS_XML,
        "META-INF/container.xml": CONTAINER_XML,
        "META-INF/manifest.xml": MANIFEST_XML,
        "Contents/content.hpf": CONTENT_HPF,
        "Contents/header.xml": header_xml(),
        "Contents/section0.xml": section0_xml(),
    }
    for rel, text in files.items():
        path = BASE / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files to {BASE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 생성기 실행 + 통과 확인**

Run: `python3 scripts/dev/gen_base_template.py && python3.13 -m pytest tests/test_base_template.py -v`
Expected: 7 PASS

- [ ] **Step 5: .gitignore 확인**

`.gitignore`의 `*.hwpx` 규칙은 templates/에 영향 없음(템플릿은 디렉터리). templates/base/mimetype 등이 `git status`에 보이는지 확인하고 커밋에 포함.

- [ ] **Step 6: Commit**

```bash
git add scripts/dev/gen_base_template.py templates/base tests/test_base_template.py
git commit -m "feat: base 템플릿 생성기와 템플릿 파일 (OWPML 클린룸)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: core/template.py — 템플릿 조립

**Files:**
- Create: `core/template.py`
- Test: `tests/test_template.py`

**Interfaces:**
- Consumes: `templates/base/*` (Task 1), `core.guards.validate_package`
- Produces:
  - `template.TEMPLATES_DIR: Path` — 저장소의 templates/ 절대경로
  - `template.build_from_template(dst, *, template="base", section_xml=None, title=None) -> Path`
    - templates/<template>/의 모든 파일을 mimetype-first ZIP으로 조립 (mimetype STORED, 나머지 DEFLATED; 엔트리 순서: mimetype, version.xml, settings.xml, META-INF/*, Contents/*)
    - `section_xml`(str)이 주어지면 Contents/section0.xml 내용을 그것으로 교체
    - `title`이 주어지면 content.hpf의 `<opf:title>무제</opf:title>`을 xml-escape된 title로 치환
    - 존재하지 않는 템플릿이면 `PackageError`
    - 반환: dst의 Path

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_template.py
import zipfile
import pytest
from core.guards import validate_package
from core.package import PackageError
from core.template import build_from_template


def test_build_base_passes_validate(tmp_path):
    out = build_from_template(tmp_path / "doc.hwpx")
    r = validate_package(out)
    assert r["ok"], r["errors"]
    with zipfile.ZipFile(out) as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED


def test_title_is_patched_and_escaped(tmp_path):
    out = build_from_template(tmp_path / "doc.hwpx", title="계획 <2026> & 보고")
    with zipfile.ZipFile(out) as zf:
        hpf = zf.read("Contents/content.hpf").decode("utf-8")
    assert "무제" not in hpf
    assert "계획 &lt;2026&gt; &amp; 보고" in hpf


def test_section_override(tmp_path):
    from core.template import TEMPLATES_DIR
    skeleton = (TEMPLATES_DIR / "base/Contents/section0.xml").read_text("utf-8")
    custom = skeleton.replace("</hs:sec>",
        '<hp:p id="1000000002" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0"><hp:t>커스텀 본문</hp:t></hp:run></hp:p>'
        '</hs:sec>')
    out = build_from_template(tmp_path / "doc.hwpx", section_xml=custom)
    assert validate_package(out)["ok"]
    from core.analyze import extract_text
    assert "커스텀 본문" in extract_text(out)


def test_unknown_template_raises(tmp_path):
    with pytest.raises(PackageError):
        build_from_template(tmp_path / "x.hwpx", template="없는템플릿")
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_template.py -v`
Expected: FAIL (`ModuleNotFoundError: core.template`)

- [ ] **Step 3: 구현**

```python
# core/template.py
"""템플릿 디렉터리 → HWPX 조립."""
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from core.package import PackageError

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_ENTRY_ORDER = ["mimetype", "version.xml", "settings.xml"]


def _ordered_names(names):
    def key(name):
        if name in _ENTRY_ORDER:
            return (0, _ENTRY_ORDER.index(name), name)
        if name.startswith("META-INF/"):
            return (1, 0, name)
        return (2, 0, name)
    return sorted(names, key=key)


def build_from_template(dst, *, template="base", section_xml=None, title=None):
    tdir = TEMPLATES_DIR / template
    if not tdir.is_dir():
        raise PackageError(f"템플릿 없음: {template}")
    files = {}
    for f in tdir.rglob("*"):
        if f.is_file():
            files[str(f.relative_to(tdir)).replace("\\", "/")] = f.read_bytes()
    if section_xml is not None:
        files["Contents/section0.xml"] = section_xml.encode("utf-8")
    if title is not None:
        hpf = files["Contents/content.hpf"].decode("utf-8")
        files["Contents/content.hpf"] = hpf.replace(
            "<opf:title>무제</opf:title>",
            f"<opf:title>{_xml_escape(title)}</opf:title>", 1).encode("utf-8")
    dst = Path(dst)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in _ordered_names(files):
            ctype = (zipfile.ZIP_STORED if name == "mimetype"
                     else zipfile.ZIP_DEFLATED)
            zf.writestr(zipfile.ZipInfo(name), files[name], compress_type=ctype)
    return dst
```

- [ ] **Step 4: 통과 확인**

Run: `python3.13 -m pytest tests/test_template.py tests/ -q`
Expected: 전체 green (35 + 4)

- [ ] **Step 5: Commit**

```bash
git add core/template.py tests/test_template.py
git commit -m "feat: 템플릿 조립 (build_from_template)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: core/owpml.py — 요소 빌더

**Files:**
- Create: `core/owpml.py`
- Test: `tests/test_owpml.py`

**Interfaces:**
- Consumes: `template.TEMPLATES_DIR`(스켈레톤 로드), `build_from_template`(테스트에서)
- Produces (Task 4·5가 의존):
  - `owpml.IdAllocator` — `alloc = IdAllocator(start=1000000002)`; `alloc.next() -> str`
  - `owpml.xml_escape(text: str) -> str`
  - `owpml.load_skeleton(template="base") -> tuple[str, str]` — 템플릿 section0.xml에서 (첫 문단 XML 전체, `<hs:sec ...>` 여는 태그)를 추출해 반환
  - `owpml.sec_document(first_para: str, body_parts: list[str], sec_open: str) -> str` — 완결된 section0.xml 문자열
  - `owpml.text_para(text, alloc, *, char_pr="0", para_pr="0", page_break=False) -> str`
  - `owpml.empty_line(alloc) -> str`
  - `owpml.heading_para(level: int, text, alloc) -> str` — level 1→(charPr 1, paraPr 1), 2→(2,2), 3 이상→(3,3)
  - `owpml.bullet_para(text, alloc, marker="•") -> str` — paraPr 4, 텍스트 앞에 `마커 + 공백`
  - `owpml.table(rows: list[list[str]], alloc, *, header=True, total_width=42520, row_height=2400) -> str` — 컨테이너 문단 XML. 열 너비 균등 분할(나머지는 마지막 열에), 헤더 행은 borderFill 4 + charPr 4, 본문 행은 borderFill 3 + charPr 0, 셀 문단 paraPr 5. 빈 rows 또는 열 수 불일치 시 `ValueError`
- 모든 빌더 출력은 문자열이며 텍스트는 xml_escape 처리됨

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_owpml.py
import xml.etree.ElementTree as ET
import pytest
from core import owpml
from core.guards import validate_package
from core.template import build_from_template
from core.analyze import extract_text, analyze_document

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _build_doc(tmp_path, body_parts):
    first, sec_open = owpml.load_skeleton()
    xml = owpml.sec_document(first, body_parts, sec_open)
    ET.fromstring(xml)  # well-formed 확인
    return build_from_template(tmp_path / "doc.hwpx", section_xml=xml)


def test_escape_and_unique_ids(tmp_path):
    alloc = owpml.IdAllocator()
    p1 = owpml.text_para("a<b>&\"c", alloc)
    p2 = owpml.text_para("둘", alloc)
    assert "a&lt;b&gt;&amp;" in p1
    id1 = ET.fromstring(p1).get("id")
    id2 = ET.fromstring(p2).get("id")
    assert id1 != id2


def test_full_document_roundtrip(tmp_path):
    alloc = owpml.IdAllocator()
    parts = [
        owpml.heading_para(1, "문서 제목", alloc),
        owpml.text_para("첫 본문 문단", alloc),
        owpml.heading_para(2, "섹션 하나", alloc),
        owpml.bullet_para("항목 하나", alloc),
        owpml.bullet_para("항목 둘", alloc),
        owpml.empty_line(alloc),
        owpml.table([["이름", "값"], ["가", "1"], ["나", "2"]], alloc),
    ]
    out = _build_doc(tmp_path, parts)
    r = validate_package(out)
    assert r["ok"], r["errors"]
    text = extract_text(out)
    for expected in ("문서 제목", "첫 본문 문단", "• 항목 하나", "이름 | 값", "나 | 2"):
        assert expected in text
    doc = analyze_document(out)
    assert doc["sections"][0]["tables"] == [{"index": 0, "rows": 3, "cols": 2}]


def test_heading_style_mapping():
    alloc = owpml.IdAllocator()
    h1 = owpml.heading_para(1, "제목", alloc)
    h4 = owpml.heading_para(4, "소제목", alloc)
    assert 'paraPrIDRef="1"' in h1 and 'charPrIDRef="1"' in h1
    assert 'paraPrIDRef="3"' in h4 and 'charPrIDRef="3"' in h4


def test_page_break_flag():
    alloc = owpml.IdAllocator()
    p = owpml.text_para("새 쪽", alloc, page_break=True)
    assert 'pageBreak="1"' in p


def test_table_column_widths_sum_to_total():
    alloc = owpml.IdAllocator()
    t = owpml.table([["a", "b", "c"]], alloc, header=False)
    root = ET.fromstring(t)
    widths = [int(sz.get("width"))
              for sz in root.iter(f"{{{NS_HP}}}cellSz")]
    assert sum(widths) == 42520
    assert len(set(widths)) <= 2  # 균등 + 마지막 열 보정


def test_table_rejects_ragged_rows():
    alloc = owpml.IdAllocator()
    with pytest.raises(ValueError):
        owpml.table([["a", "b"], ["c"]], alloc)
    with pytest.raises(ValueError):
        owpml.table([], alloc)
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_owpml.py -v`
Expected: FAIL (`ModuleNotFoundError: core.owpml`)

- [ ] **Step 3: 구현**

```python
# core/owpml.py
"""OWPML 요소 빌더 — 문자열 기반 XML 조각 생성."""
from xml.sax.saxutils import escape as xml_escape

from core.template import TEMPLATES_DIR


class IdAllocator:
    def __init__(self, start=1000000002):
        self._next = start

    def next(self):
        value = self._next
        self._next += 1
        return str(value)


def load_skeleton(template="base"):
    xml = (TEMPLATES_DIR / template / "Contents/section0.xml").read_text("utf-8")
    open_start = xml.index("<hs:sec")
    open_end = xml.index(">", open_start) + 1
    sec_open = xml[open_start:open_end]
    p_start = xml.index("<hp:p", open_end)
    p_end = xml.index("</hp:p>", p_start) + len("</hp:p>")
    first_para = xml[p_start:p_end]
    return first_para, sec_open


def sec_document(first_para, body_parts, sec_open):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            + sec_open + first_para + "".join(body_parts) + "</hs:sec>")


def _para(pid, text, char_pr, para_pr, page_break):
    pb = "1" if page_break else "0"
    return (f'<hp:p id="{pid}" paraPrIDRef="{para_pr}" styleIDRef="0" '
            f'pageBreak="{pb}" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{char_pr}">'
            + (f"<hp:t>{text}</hp:t>" if text else "<hp:t/>")
            + "</hp:run></hp:p>")


def text_para(text, alloc, *, char_pr="0", para_pr="0", page_break=False):
    return _para(alloc.next(), xml_escape(text), char_pr, para_pr, page_break)


def empty_line(alloc):
    return _para(alloc.next(), "", "0", "0", False)


_HEADING_MAP = {1: ("1", "1"), 2: ("2", "2")}


def heading_para(level, text, alloc):
    char_pr, para_pr = _HEADING_MAP.get(level, ("3", "3"))
    return _para(alloc.next(), xml_escape(text), char_pr, para_pr, False)


def bullet_para(text, alloc, marker="•"):
    return _para(alloc.next(), f"{marker} {xml_escape(text)}", "0", "4", False)


def _cell(row, col, text, width, height, alloc, *, header_cell):
    border = "4" if header_cell else "3"
    char_pr = "4" if header_cell else "0"
    return (
        '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
        f'dirty="0" borderFillIDRef="{border}">'
        '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
        'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
        'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="{alloc.next()}" paraPrIDRef="5" styleIDRef="0" '
        'pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{char_pr}">'
        + (f"<hp:t>{xml_escape(text)}</hp:t>" if text else "<hp:t/>")
        + "</hp:run></hp:p></hp:subList>"
        f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="{height}"/>'
        '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
        '</hp:tc>')


def table(rows, alloc, *, header=True, total_width=42520, row_height=2400):
    if not rows:
        raise ValueError("빈 표는 만들 수 없음")
    cols = len(rows[0])
    if cols == 0 or any(len(r) != cols for r in rows):
        raise ValueError("모든 행의 열 수가 같아야 함")
    base = total_width // cols
    widths = [base] * cols
    widths[-1] += total_width - base * cols
    tr_parts = []
    for r, row in enumerate(rows):
        is_header = header and r == 0
        cells = "".join(
            _cell(r, c, row[c], widths[c], row_height, alloc,
                  header_cell=is_header)
            for c in range(cols))
        tr_parts.append(f"<hp:tr>{cells}</hp:tr>")
    tbl_id = alloc.next()
    height = row_height * len(rows)
    return (
        f'<hp:p id="{alloc.next()}" paraPrIDRef="0" styleIDRef="0" '
        'pageBreak="0" columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0">'
        f'<hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" '
        'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        'dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{len(rows)}" colCnt="{cols}" cellSpacing="0" '
        'borderFillIDRef="3" noAdjust="0">'
        f'<hp:sz width="{total_width}" widthRelTo="ABSOLUTE" '
        f'height="{height}" heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
        'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
        'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
        'vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="141" bottom="141"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        + "".join(tr_parts) +
        '</hp:tbl></hp:run></hp:p>')
```

- [ ] **Step 4: 통과 확인**

Run: `python3.13 -m pytest tests/test_owpml.py tests/ -q`
Expected: 전체 green

- [ ] **Step 5: Commit**

```bash
git add core/owpml.py tests/test_owpml.py
git commit -m "feat: OWPML 요소 빌더 (owpml.py)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: core/markdown.py — 마크다운 파서 + 렌더러

**Files:**
- Create: `core/markdown.py`
- Test: `tests/test_markdown.py`

**Interfaces:**
- Consumes: `owpml.*` (Task 3), `build_from_template` (테스트)
- Produces (Task 5가 의존):
  - `markdown.parse_markdown(text: str) -> list[dict]` — 블록 리스트. 블록 형태:
    - `{"type": "heading", "level": int, "text": str}`
    - `{"type": "paragraph", "text": str}`
    - `{"type": "bullet", "items": [str, ...]}`
    - `{"type": "ordered", "items": [str, ...]}`
    - `{"type": "table", "rows": [[str, ...], ...]}` (구분선 행 제외)
  - `markdown.render_to_section(md_text: str, template="base") -> str` — 완결된 section0.xml
  - `markdown.first_heading(md_text: str) -> str | None` — 첫 `#` 제목 텍스트
- 지원 문법: `#`~`######` 제목, `-`/`*` 불릿, `1.` 순서 목록(항목 텍스트 앞에 `1. ` 등 번호를 그대로 유지해 렌더), GitHub 표(구분선 행 `---` 필수), 빈 줄 구분 문단. 인라인 강조는 `**`와 백틱(`` ` ``)만 제거(v1 한계로 문서화), 그 외 텍스트는 그대로.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_markdown.py
from core.markdown import parse_markdown, render_to_section, first_heading
from core.template import build_from_template
from core.guards import validate_package
from core.analyze import extract_text, analyze_document

SAMPLE = """# 사업 계획

개요 문단입니다. **강조**와 `코드` 포함.

## 목표

- 첫 목표
- 둘째 목표

1. 단계 하나
2. 단계 둘

| 항목 | 예산 |
| --- | --- |
| 인건비 | 100 |
| 운영비 | 50 |
"""


def test_parse_blocks():
    blocks = parse_markdown(SAMPLE)
    types = [b["type"] for b in blocks]
    assert types == ["heading", "paragraph", "heading", "bullet",
                     "ordered", "table"]
    assert blocks[0] == {"type": "heading", "level": 1, "text": "사업 계획"}
    assert blocks[1]["text"] == "개요 문단입니다. 강조와 코드 포함."
    assert blocks[3]["items"] == ["첫 목표", "둘째 목표"]
    assert blocks[4]["items"] == ["1. 단계 하나", "2. 단계 둘"]
    assert blocks[5]["rows"] == [["항목", "예산"], ["인건비", "100"],
                                 ["운영비", "50"]]


def test_first_heading():
    assert first_heading(SAMPLE) == "사업 계획"
    assert first_heading("본문만") is None


def test_render_roundtrip(tmp_path):
    xml = render_to_section(SAMPLE)
    out = build_from_template(tmp_path / "doc.hwpx", section_xml=xml,
                              title=first_heading(SAMPLE))
    r = validate_package(out)
    assert r["ok"], r["errors"]
    text = extract_text(out)
    for expected in ("사업 계획", "개요 문단입니다", "• 첫 목표",
                     "1. 단계 하나", "인건비 | 100"):
        assert expected in text
    doc = analyze_document(out)
    assert doc["sections"][0]["tables"] == [{"index": 0, "rows": 3, "cols": 2}]


def test_multiline_paragraph_joined():
    blocks = parse_markdown("한 줄\n둘째 줄\n\n새 문단")
    assert blocks[0]["text"] == "한 줄 둘째 줄"
    assert blocks[1]["text"] == "새 문단"
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_markdown.py -v`
Expected: FAIL (`ModuleNotFoundError: core.markdown`)

- [ ] **Step 3: 구현**

```python
# core/markdown.py
"""마크다운 → 블록 → OWPML 섹션. 지원 문법은 SKILL.md/README에 문서화된 부분집합."""
import re

from core import owpml

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
_ORDERED_RE = re.compile(r"^(\d+)\.\s+(.*)$")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")


def _clean_inline(text):
    return text.replace("**", "").replace("`", "")


def _split_table_row(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_markdown(text):
    blocks = []
    para_lines = []

    def flush_para():
        if para_lines:
            blocks.append({"type": "paragraph",
                           "text": _clean_inline(" ".join(para_lines))})
            para_lines.clear()

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush_para()
            i += 1
            continue
        m = _HEADING_RE.match(stripped)
        if m:
            flush_para()
            blocks.append({"type": "heading", "level": len(m.group(1)),
                           "text": _clean_inline(m.group(2).strip())})
            i += 1
            continue
        if _TABLE_ROW_RE.match(stripped) and i + 1 < len(lines) \
                and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            flush_para()
            rows = [_split_table_row(stripped)]
            i += 2
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i].strip()):
                rows.append(_split_table_row(lines[i].strip()))
                i += 1
            rows = [[_clean_inline(c) for c in row] for row in rows]
            blocks.append({"type": "table", "rows": rows})
            continue
        m = _BULLET_RE.match(stripped)
        if m:
            flush_para()
            items = [_clean_inline(m.group(1).strip())]
            i += 1
            while i < len(lines):
                m2 = _BULLET_RE.match(lines[i].strip())
                if not m2:
                    break
                items.append(_clean_inline(m2.group(1).strip()))
                i += 1
            blocks.append({"type": "bullet", "items": items})
            continue
        m = _ORDERED_RE.match(stripped)
        if m:
            flush_para()
            items = [f"{m.group(1)}. {_clean_inline(m.group(2).strip())}"]
            i += 1
            while i < len(lines):
                m2 = _ORDERED_RE.match(lines[i].strip())
                if not m2:
                    break
                items.append(f"{m2.group(1)}. {_clean_inline(m2.group(2).strip())}")
                i += 1
            blocks.append({"type": "ordered", "items": items})
            continue
        para_lines.append(stripped)
        i += 1
    flush_para()
    return blocks


def first_heading(text):
    for block in parse_markdown(text):
        if block["type"] == "heading":
            return block["text"]
    return None


def render_to_section(md_text, template="base"):
    first, sec_open = owpml.load_skeleton(template)
    alloc = owpml.IdAllocator()
    parts = []
    for block in parse_markdown(md_text):
        if block["type"] == "heading":
            parts.append(owpml.heading_para(block["level"], block["text"], alloc))
        elif block["type"] == "paragraph":
            parts.append(owpml.text_para(block["text"], alloc))
        elif block["type"] == "bullet":
            for item in block["items"]:
                parts.append(owpml.bullet_para(item, alloc))
        elif block["type"] == "ordered":
            for item in block["items"]:
                parts.append(owpml.text_para(item, alloc, para_pr="4"))
        elif block["type"] == "table":
            parts.append(owpml.table(block["rows"], alloc))
    return owpml.sec_document(first, parts, sec_open)
```

- [ ] **Step 4: 통과 확인**

Run: `python3.13 -m pytest tests/test_markdown.py tests/ -q`
Expected: 전체 green

- [ ] **Step 5: Commit**

```bash
git add core/markdown.py tests/test_markdown.py
git commit -m "feat: 마크다운 파서와 OWPML 렌더러

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: CLI `new` / `build` 서브커맨드

**Files:**
- Modify: `scripts/hwpx.py`
- Test: `tests/test_cli_new.py`

**Interfaces:**
- Consumes: `markdown.render_to_section`, `markdown.first_heading`, `template.build_from_template`, `guards.validate_package`
- Produces:
  - `hwpx.py new <input.md> -o <out.hwpx> [--template base] [--title 제목]` — 마크다운→HWPX. title 미지정 시 첫 제목, 그것도 없으면 입력 파일 stem. 생성 후 validate 자동 실행: ok면 `{"ok": true, "output": ..., "validate": {...}}` exit 0, 아니면 `{"ok": false, ...}` exit 2 (산출물은 남김)
  - `hwpx.py build --section <section.xml> -o <out.hwpx> [--template base] [--title 제목]` — section0.xml 직접 지정 조립. 같은 validate 게이트
  - 기존 5개 서브커맨드 불변. `main()`의 기존 예외 래퍼가 새 커맨드에도 적용됨

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_cli_new.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import importlib
hwpx_cli = importlib.import_module("hwpx")


def test_new_from_markdown(tmp_path, capsys):
    md = tmp_path / "in.md"
    md.write_text("# 제목\n\n본문입니다.\n", encoding="utf-8")
    out = tmp_path / "out.hwpx"
    rc = hwpx_cli.main(["new", str(md), "-o", str(out)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    assert out.exists()
    from core.analyze import extract_text
    assert "본문입니다" in extract_text(out)


def test_new_title_defaults_to_first_heading(tmp_path, capsys):
    md = tmp_path / "in.md"
    md.write_text("# 보고서 제목\n\n내용\n", encoding="utf-8")
    out = tmp_path / "out.hwpx"
    hwpx_cli.main(["new", str(md), "-o", str(out)])
    capsys.readouterr()
    import zipfile
    with zipfile.ZipFile(out) as zf:
        assert "보고서 제목" in zf.read("Contents/content.hpf").decode("utf-8")


def test_build_with_section_file(tmp_path, capsys):
    from core import owpml
    first, sec_open = owpml.load_skeleton()
    alloc = owpml.IdAllocator()
    xml = owpml.sec_document(first, [owpml.text_para("빌드 본문", alloc)], sec_open)
    section = tmp_path / "sec.xml"
    section.write_text(xml, encoding="utf-8")
    out = tmp_path / "out.hwpx"
    rc = hwpx_cli.main(["build", "--section", str(section), "-o", str(out)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    from core.analyze import extract_text
    assert "빌드 본문" in extract_text(out)


def test_new_missing_input_returns_2(tmp_path, capsys):
    rc = hwpx_cli.main(["new", str(tmp_path / "없음.md"),
                        "-o", str(tmp_path / "o.hwpx")])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2 and payload["ok"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `python3.13 -m pytest tests/test_cli_new.py -v`
Expected: FAIL (unknown command 'new' — argparse가 SystemExit(2)를 던지므로, 테스트가 SystemExit로 실패하는 것도 RED로 인정)

- [ ] **Step 3: 구현 (scripts/hwpx.py에 추가)**

```python
# scripts/hwpx.py에 추가 — 상단 import에:
from core import markdown as md_mod
from core.template import build_from_template


def _finish_generated(out_path):
    result = guards.validate_package(out_path)
    payload = {"ok": result["ok"], "output": str(out_path), "validate": result}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def cmd_new(args):
    src = Path(args.input)
    if not src.is_file():
        raise PackageError(f"입력 파일 없음: {src}")
    text = src.read_text(encoding="utf-8")
    title = args.title or md_mod.first_heading(text) or src.stem
    section = md_mod.render_to_section(text, template=args.template)
    build_from_template(args.output, template=args.template,
                        section_xml=section, title=title)
    return _finish_generated(args.output)


def cmd_build(args):
    section = Path(args.section).read_text(encoding="utf-8") \
        if args.section else None
    build_from_template(args.output, template=args.template,
                        section_xml=section, title=args.title)
    return _finish_generated(args.output)

# build_parser() 안에 추가:
    n = sub.add_parser("new", help="마크다운 → HWPX 생성")
    n.add_argument("input")
    n.add_argument("-o", "--output", required=True)
    n.add_argument("--template", default="base")
    n.add_argument("--title")
    n.set_defaults(func=cmd_new)

    b = sub.add_parser("build", help="header+section 조립")
    b.add_argument("--section")
    b.add_argument("-o", "--output", required=True)
    b.add_argument("--template", default="base")
    b.add_argument("--title")
    b.set_defaults(func=cmd_build)
```

주의: `cmd_new`의 파일 부재는 `PackageError`로 던져 기존 `main()` 예외 래퍼가 JSON+exit 2로 변환하게 한다. `Path`는 이미 import되어 있는지 확인하고 없으면 추가.

- [ ] **Step 4: 통과 확인 + CLI 스모크**

Run: `python3.13 -m pytest tests/test_cli_new.py tests/ -q` → 전체 green
Run:
```bash
printf '# 스모크\n\n한 줄 본문\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n' > /private/tmp/smoke.md
python3 scripts/hwpx.py new /private/tmp/smoke.md -o /private/tmp/smoke.hwpx
python3 scripts/hwpx.py extract /private/tmp/smoke.hwpx --format markdown
```
Expected: ok:true JSON + 마크다운 표 포함 추출 출력

- [ ] **Step 5: Commit**

```bash
git add scripts/hwpx.py tests/test_cli_new.py
git commit -m "feat: new/build 생성 커맨드

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: 문서 갱신 + 한컴 검증 체크포인트

**Files:**
- Modify: `SKILL.md` (생성 워크플로우 추가)
- Create: `references/base-template-styles.md`
- Create: `docs/hancom-verification.md`
- Modify: `README.md` (new/build 사용법 추가)

**Interfaces:**
- Consumes: Task 1~5의 산출물
- Produces: Phase 2 문서 세트

- [ ] **Step 1: SKILL.md 갱신**

워크플로우 트리의 `"새 문서 만들어줘"` 분기와 커맨드 목록을 채운다. SKILL.md의 `## 워크플로우 선택` 블록을 아래로 교체:

```markdown
## 워크플로우 선택

    사용자 요청
     ├─ "읽어줘/내용 알려줘" → extract
     ├─ "구조 분석/어떤 양식인지" → analyze
     ├─ "편집할 곳 찾아줘" → analyze --slots
     ├─ "새 문서 만들어줘" (마크다운/텍스트 콘텐츠) → new ★
     ├─ "파일이 정상인지 확인" → validate
     ├─ "XML 직접 보기/고치기" → unpack → (편집) → pack --source
     └─ .hwp 파일 → 미지원 안내 (한글에서 .hwpx로 저장 요청)
```

커맨드 블록에 추가:

```markdown
    # 생성: 마크다운 → HWPX (제목/표/목록 지원; 강조 문법은 제거됨)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" new 입력.md -o 결과.hwpx [--title 제목]
    # 생성: section0.xml 직접 조립 (스타일 ID는 references/base-template-styles.md)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" build --section sec.xml -o 결과.hwpx
```

필수 규칙에 추가:

```markdown
5. new/build는 validate를 자동 실행한다. 출력 JSON의 ok가 false면 산출물을
   사용자에게 전달하지 않는다.
6. 마크다운 지원 범위: #~###### 제목, -/* 불릿, 1. 순서 목록, GitHub 표,
   빈 줄 구분 문단. **강조**와 `코드`는 마커만 제거된다. 이 밖의 문법은
   일반 텍스트로 들어간다.
```

- [ ] **Step 2: references/base-template-styles.md 작성**

플랜 상단의 "base 템플릿 스타일 ID 맵" 표를 그대로 옮기고, 아래 문구를 추가:

```markdown
# base 템플릿 스타일 ID 맵

(표: 플랜의 스타일 ID 맵과 동일 — font 0/1, borderFill 1~4, charPr 0~4,
paraPr 0~5, style 0)

- 템플릿 수정은 `scripts/dev/gen_base_template.py`를 고쳐 재실행한다.
  산출물(templates/base/*)을 직접 편집하지 않는다.
- section0.xml을 손으로 쓸 때는 위 ID만 참조한다. 정의되지 않은
  charPrIDRef/paraPrIDRef는 validate의 dangling-ref로 잡힌다.
- secPr은 템플릿 section0.xml의 첫 문단에서 통째로 가져온다
  (`owpml.load_skeleton`). 추후 한컴 저장본으로 템플릿을 교체하면
  코드 변경 없이 호환성이 좋아진다.
```

- [ ] **Step 3: docs/hancom-verification.md 작성**

```markdown
# 한컴오피스 열림 검증 체크리스트 (Phase 2 게이트)

base 템플릿은 OWPML 스펙 기반 클린룸 작성물로, 구조 검증(validate)은
통과하지만 실제 한컴오피스 열림은 아직 확인되지 않았다. 아래를 한컴이
설치된 환경에서 1회 수행한다.

## 검증 절차

1. `python3 scripts/hwpx.py new samples/verify.md -o verify.hwpx` 로 생성
   (samples/verify.md: 제목 + 본문 + 불릿 + 순서목록 + 3x2 표를 포함할 것)
2. 한컴오피스(한글)에서 verify.hwpx를 연다.
3. 확인 항목:
   - [ ] 경고/복구 대화상자 없이 열리는가
   - [ ] 제목이 18pt 굵은 돋움으로 보이는가
   - [ ] 본문이 10pt 바탕, 양쪽 정렬로 보이는가
   - [ ] 표의 테두리와 헤더 행 회색 배경이 보이는가
   - [ ] 편집(타이핑) 후 저장이 정상 동작하는가
4. 편집 후 저장한 파일을 `python3 scripts/hwpx.py validate`로 재검증한다.

## 실패 시

- 대화상자 문구/증상을 기록해 이슈로 남긴다.
- 한컴에서 빈 문서를 .hwpx로 저장한 파일을 확보하면:
  unpack으로 header.xml/section0.xml 구조를 비교하고, 차이를
  scripts/dev/gen_base_template.py에 반영하거나, 스펙 §8의 헤지대로
  한컴 저장본을 새 base 템플릿으로 채택한다 (secPr 추출 구조라
  코드 변경 불필요).
```

- [ ] **Step 4: README 사용법 갱신**

README의 "사용법 (Phase 1)" 섹션 제목을 "사용법"으로 바꾸고 new/build 두 줄을 추가:

```markdown
    python3 scripts/hwpx.py new 문서.md -o 문서.hwpx              # 마크다운 → HWPX
    python3 scripts/hwpx.py build --section sec.xml -o 문서.hwpx  # 직접 조립
```

- [ ] **Step 5: 전체 확인 + Commit**

Run: `python3.13 -m pytest tests/ -q` → 전체 green (35 + 약 19 = 약 54)

```bash
git add SKILL.md references/base-template-styles.md docs/hancom-verification.md README.md
git commit -m "docs: 생성 워크플로우와 한컴 검증 체크포인트

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 2 이후

- **사용자 체크포인트**: docs/hancom-verification.md 절차로 한컴 열림 검증. 실패 시 생성기 수정 반복 또는 한컴 저장본 템플릿 채택.
- Phase 1 이월 항목 중 `HwpxPackage.open`의 BadZipFile 래핑은 Phase 3 착수 시 처리.
- Phase 3(편집: replace/fill/표 조작 + check 게이트)는 별도 계획.
