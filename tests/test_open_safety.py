"""check/validate의 한컴 열기 안전 구조 규칙 + id 재번호 + 임시 파일 승격 + 추출 범위."""
import os
import zipfile

import pytest

from core.analyze import extract_text
from core.edit import edit_file
from core.guards import validate_package, check_package
from core.package import HwpxPackage
from tests.fixture import (build_from_section, build_minimal_hwpx, _cell, _table,
                           BODY_PARA, HEADER_XML, CONTENT_HPF, SECTION_HEAD)

P = ('<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" '
     'merged="0">{body}</hp:p>')
TBL_HEAD = ('<hp:tbl id="{tid}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
            'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
            'rowCnt="{rows}" colCnt="{cols}" cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
            '<hp:sz width="42520" widthRelTo="ABSOLUTE" height="2400" heightRelTo="ABSOLUTE" protect="0"/>'
            '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
            'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
            'vertOffset="0" horzOffset="0"/>'
            '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
            '<hp:inMargin left="0" right="0" top="0" bottom="0"/>')


def _errs(path, prefix):
    r = validate_package(path)
    return [e for e in r["errors"] if e.startswith(prefix)]


def _warns(path, prefix):
    r = validate_package(path)
    return [w for w in r["warnings"] if w.startswith(prefix)]


def test_fixture_and_templates_pass_structural_rules(tmp_path):
    p = build_minimal_hwpx(tmp_path / "m.hwpx", with_table=True)
    r = validate_package(p)
    assert r["ok"] and r["warnings"] == [], r


def test_tab_character_in_t_is_error_but_tab_element_is_fine(tmp_path):
    bad = build_from_section(tmp_path / "bad.hwpx",
                             P.format(pid=5, body='<hp:run charPrIDRef="0"><hp:t>a\tb</hp:t></hp:run>'))
    assert _errs(bad, "text-control-char")
    good = build_from_section(tmp_path / "good.hwpx",
                              P.format(pid=5, body='<hp:run charPrIDRef="0"><hp:t>a<hp:tab/>b</hp:t></hp:run>'))
    assert not _errs(good, "text-control-char")
    tail = build_from_section(tmp_path / "tail.hwpx",
                              P.format(pid=5, body='<hp:run charPrIDRef="0"><hp:t>a<hp:tab/>b\tc</hp:t></hp:run>'))
    assert _errs(tail, "text-control-char")


def test_secpr_without_pagepr_or_margin_is_error(tmp_path):
    p = build_minimal_hwpx(tmp_path / "m.hwpx")
    pkg = HwpxPackage.open(p)
    xml = pkg.read_text("Contents/section0.xml")
    no_margin = xml.replace('<hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" '
                            'top="5668" bottom="4252"/>', "")
    assert no_margin != xml
    pkg.write_replaced(tmp_path / "nm.hwpx", {"Contents/section0.xml": no_margin.encode()})
    assert _errs(tmp_path / "nm.hwpx", "secpr-incomplete")
    start = xml.index("<hp:pagePr")
    end = xml.index("</hp:pagePr>") + len("</hp:pagePr>")
    pkg.write_replaced(tmp_path / "np.hwpx", {"Contents/section0.xml": (xml[:start] + xml[end:]).encode()})
    assert _errs(tmp_path / "np.hwpx", "secpr-incomplete")


def test_table_structure_rules(tmp_path):
    cell = _cell(0, 0, "x", 11)
    # rowCnt가 실제 tr 수와 다름
    body = P.format(pid=10, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=12, rows=2, cols=1)
                    + f"<hp:tr>{cell}</hp:tr></hp:tbl></hp:run>")
    assert _errs(build_from_section(tmp_path / "a.hwpx", body), "table-structure")
    # tbl에 sz 없음
    body = P.format(pid=10, body='<hp:run charPrIDRef="0">'
                    + TBL_HEAD.format(tid=12, rows=1, cols=1).replace(
                        '<hp:sz width="42520" widthRelTo="ABSOLUTE" height="2400" heightRelTo="ABSOLUTE" protect="0"/>', "")
                    + f"<hp:tr>{cell}</hp:tr></hp:tbl></hp:run>")
    assert any("sz 없음" in e for e in _errs(build_from_section(tmp_path / "b.hwpx", body), "table-structure"))
    # 셀에 cellAddr 없음 / 폭 0
    bad_cell = cell.replace('<hp:cellAddr colAddr="0" rowAddr="0"/>', "")
    body = P.format(pid=10, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=12, rows=1, cols=1)
                    + f"<hp:tr>{bad_cell}</hp:tr></hp:tbl></hp:run>")
    assert _errs(build_from_section(tmp_path / "c.hwpx", body), "table-structure")
    zero = cell.replace('<hp:cellSz width="21260" height="2400"/>', '<hp:cellSz width="0" height="2400"/>')
    body = P.format(pid=10, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=12, rows=1, cols=1)
                    + f"<hp:tr>{zero}</hp:tr></hp:tbl></hp:run>")
    assert _errs(build_from_section(tmp_path / "d.hwpx", body), "cell-geometry-invalid")
    # 높이 0은 한컴 실물(자동 높이)에 있으므로 허용
    h0 = cell.replace('<hp:cellSz width="21260" height="2400"/>', '<hp:cellSz width="21260" height="0"/>')
    body = P.format(pid=10, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=12, rows=1, cols=1)
                    + f"<hp:tr>{h0}</hp:tr></hp:tbl></hp:run>")
    assert not _errs(build_from_section(tmp_path / "e.hwpx", body), "cell-geometry-invalid")
    # subList에 문단 없음
    empty_sub = cell[:cell.index("<hp:p ")] + "</hp:subList>" + cell[cell.index("<hp:cellAddr"):]
    body = P.format(pid=10, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=12, rows=1, cols=1)
                    + f"<hp:tr>{empty_sub}</hp:tr></hp:tbl></hp:run>")
    assert _errs(build_from_section(tmp_path / "f.hwpx", body), "sublist-empty")


def test_stale_lineseg_detected_only_when_past_text(tmp_path):
    seg = ('<hp:linesegarray><hp:lineseg textpos="{pos}" vertpos="0" vertsize="1000" textheight="1000" '
           'baseline="850" spacing="600" horzpos="0" horzsize="42520" flags="{flags}"/></hp:linesegarray>')
    body = P.format(pid=10, body='<hp:run charPrIDRef="0"><hp:t>가나다</hp:t></hp:run>' + seg.format(pos=9, flags="393216"))
    assert _errs(build_from_section(tmp_path / "s.hwpx", body), "lineseg-stale")
    body = P.format(pid=10, body='<hp:run charPrIDRef="0"><hp:t>가나다</hp:t></hp:run>' + seg.format(pos=3, flags="393216"))
    assert not _errs(build_from_section(tmp_path / "ok.hwpx", body), "lineseg-stale")
    # 빈 둘째 조각(flags에 EMPTY 비트)은 글자 수+1 위치가 정상
    body = P.format(pid=10, body='<hp:run charPrIDRef="0"><hp:t>가나다</hp:t></hp:run>' + seg.format(pos=4, flags=str(0x40000)))
    assert not _errs(build_from_section(tmp_path / "e.hwpx", body), "lineseg-stale")
    # 탭 요소는 8칸으로 센다
    body = P.format(pid=10, body='<hp:run charPrIDRef="0"><hp:t>가<hp:tab/>나</hp:t></hp:run>' + seg.format(pos=9, flags="393216"))
    assert not _errs(build_from_section(tmp_path / "t.hwpx", body), "lineseg-stale")
    missing = ('<hp:linesegarray><hp:lineseg vertpos="0" vertsize="1000" textheight="1000" '
               'baseline="850" spacing="600" horzpos="0" horzsize="42520" flags="0"/></hp:linesegarray>')
    body = P.format(pid=10, body='<hp:run charPrIDRef="0"><hp:t>가</hp:t></hp:run>' + missing)
    assert _errs(build_from_section(tmp_path / "m.hwpx", body), "lineseg-missing-textpos")


def test_field_ctrl_and_header_rules(tmp_path):
    body = P.format(pid=10, body='<hp:run charPrIDRef="0"><hp:ctrl/></hp:run>')
    assert _errs(build_from_section(tmp_path / "c.hwpx", body), "ctrl-empty")
    body = P.format(pid=10, body=(
        '<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldBegin id="5" type="CLICK_HERE" name="" editable="1" '
        'dirty="0" zorder="0" fieldid="627207531"/></hp:ctrl></hp:run>'
        '<hp:run charPrIDRef="0"><hp:t>값</hp:t></hp:run>'
        '<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldEnd beginIDRef="99" fieldid="627207531"/></hp:ctrl></hp:run>'))
    assert _errs(build_from_section(tmp_path / "f.hwpx", body), "field-unpaired")
    body = P.format(pid=10, body=(
        '<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldBegin id="5" type="ClickHere" fieldid="x"/></hp:ctrl></hp:run>'
        '<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldEnd beginIDRef="5"/></hp:ctrl></hp:run>'))
    assert _errs(build_from_section(tmp_path / "g.hwpx", body), "field-structure")
    body = P.format(pid=10, body='<hp:run charPrIDRef="0"><hp:ctrl><hp:header id="0" applyPageType="BOTH"/></hp:ctrl></hp:run>')
    assert _errs(build_from_section(tmp_path / "h.hwpx", body), "hf-structure")


def test_shape_rules(tmp_path):
    pic = ('<hp:pic id="30" zOrder="0" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
           'lock="0" dropcapstyle="None" href="" groupLevel="0" instid="31" reverse="0">'
           '<hp:offset x="0" y="0"/><hp:orgSz width="1" height="1"/><hp:curSz width="1" height="1"/>'
           '<hp:sz width="1" widthRelTo="ABSOLUTE" height="1" heightRelTo="ABSOLUTE" protect="0"/>'
           '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
           'vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
           '</hp:pic>')
    body = P.format(pid=10, body=f'<hp:run charPrIDRef="0">{pic}</hp:run>')
    errs = _errs(build_from_section(tmp_path / "p.hwpx", body), "shape-structure")
    assert any("renderingInfo" in e for e in errs) and any("hc:img" in e for e in errs)


def test_package_level_rules(tmp_path):
    p = build_minimal_hwpx(tmp_path / "m.hwpx")
    pkg = HwpxPackage.open(p)
    hpf = pkg.read_text("Contents/content.hpf").replace(
        '</opf:manifest>', '<opf:item id="image1" href="BinData/image1.png" media-type="image/png"/></opf:manifest>')
    pkg.write_replaced(tmp_path / "h.hwpx", {"Contents/content.hpf": hpf.encode()})
    assert _errs(tmp_path / "h.hwpx", "manifest-href-missing")
    header = pkg.read_text("Contents/header.xml").replace('secCnt="1"', 'secCnt="2"')
    pkg.write_replaced(tmp_path / "s.hwpx", {"Contents/header.xml": header.encode()})
    assert _errs(tmp_path / "s.hwpx", "seccnt-mismatch")
    ver = pkg.read_text("version.xml").replace('tagetApplication="WORDPROCESSOR" ', "")
    pkg.write_replaced(tmp_path / "v.hwpx", {"version.xml": ver.encode()})
    assert _errs(tmp_path / "v.hwpx", "version-structure")


def test_style_and_tabpr_refs_and_charpr_sentinel(tmp_path):
    body = (P.format(pid=10, body='<hp:run charPrIDRef="4294967295"><hp:t>x</hp:t></hp:run>')
            .replace('styleIDRef="0"', 'styleIDRef="7"'))
    errs = _errs(build_from_section(tmp_path / "s.hwpx", body), "dangling-ref")
    assert any("styleIDRef" in e for e in errs) and not any("charPrIDRef" in e for e in errs)


def test_duplicate_paragraph_ids_warn_except_hancom_shared_ids(tmp_path):
    body = (P.format(pid=10, body='<hp:run charPrIDRef="0"><hp:t>a</hp:t></hp:run>')
            + P.format(pid=10, body='<hp:run charPrIDRef="0"><hp:t>b</hp:t></hp:run>'))
    assert _warns(build_from_section(tmp_path / "d.hwpx", body), "duplicate-id")
    body = (P.format(pid=2147483648, body='<hp:run charPrIDRef="0"><hp:t>a</hp:t></hp:run>')
            + P.format(pid=2147483648, body='<hp:run charPrIDRef="0"><hp:t>b</hp:t></hp:run>'))
    assert not _warns(build_from_section(tmp_path / "ok.hwpx", body), "duplicate-id")


# ---------------------------------------------------------------- id 재번호

def test_add_row_renumbers_cloned_object_ids(tmp_path):
    from core.images import pic_xml
    pic = pic_xml("500", "image1", 100, 100, 10, 10, instid="501").replace(
        ' xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core"', "")
    cell = _cell(0, 0, "x", 11).replace("</hp:run></hp:p>", f"</hp:run><hp:run charPrIDRef=\"0\">{pic}</hp:run></hp:p>")
    body = P.format(pid=10, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=12, rows=1, cols=1)
                    + f"<hp:tr>{cell}</hp:tr></hp:tbl></hp:run>")
    hpf = CONTENT_HPF.replace('</opf:manifest>', '<opf:item id="image1" href="BinData/image1.png" '
                              'media-type="image/png" isEmbeded="1"/></opf:manifest>')
    src = build_from_section(tmp_path / "r.hwpx", body, extra_entries={"BinData/image1.png": b"\x89PNG"})
    # content.hpf를 바꿔 끼운다
    pkg = HwpxPackage.open(src)
    pkg.write_replaced(tmp_path / "r2.hwpx", {"Contents/content.hpf": hpf.encode()})
    dst = tmp_path / "o.hwpx"
    edit_file(tmp_path / "r2.hwpx", dst, lambda ed: ed.add_row(0, ["y"]))
    xml = zipfile.ZipFile(dst).read("Contents/section0.xml").decode()
    import re
    ids = re.findall(r'<hp:pic [^>]*\bid="(\d+)"[^>]*\binstid="(\d+)"', xml)
    assert len(ids) == 2 and len({i for i, _ in ids}) == 2 and len({j for _, j in ids}) == 2
    assert not _warns(dst, "duplicate-id")


def test_renumber_keeps_field_pairs_consistent(tmp_path):
    field = ('<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldBegin id="77" type="CLICK_HERE" name="" editable="1" '
             'dirty="0" zorder="0" fieldid="627207531"/></hp:ctrl></hp:run>'
             '<hp:run charPrIDRef="0"><hp:t>안내문</hp:t></hp:run>'
             '<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldEnd beginIDRef="77" fieldid="627207531"/></hp:ctrl></hp:run>')
    cell = _cell(0, 0, "", 11).replace('<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>', field)
    body = P.format(pid=10, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=12, rows=1, cols=1)
                    + f"<hp:tr>{cell}</hp:tr></hp:tbl></hp:run>")
    src = build_from_section(tmp_path / "f.hwpx", body)
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.add_row(0, ["값"]))
    xml = zipfile.ZipFile(dst).read("Contents/section0.xml").decode()
    import re
    begins = re.findall(r'fieldBegin id="(\d+)"', xml)
    ends = re.findall(r'beginIDRef="(\d+)"', xml)
    assert len(set(begins)) == 2 and sorted(begins) == sorted(ends)
    assert not _errs(dst, "field-unpaired")
    # 누름틀 채우기: 값이 들어가고 dirty="1"
    assert xml.count('dirty="1"') == 1 and "값" in xml


# ---------------------------------------------------------------- CLI 승격/거부

def test_cli_rejects_output_that_fails_check(tmp_path, capsys):
    import json
    from scripts import hwpx as cli
    bad = build_from_section(tmp_path / "bad.hwpx",
                             P.format(pid=5, body='<hp:run charPrIDRef="0"><hp:t>a\tb</hp:t></hp:run>')
                             + P.format(pid=6, body='<hp:run charPrIDRef="0"><hp:t>안녕</hp:t></hp:run>'))
    dst = tmp_path / "out.hwpx"
    m = tmp_path / "m.json"
    m.write_text('{"안녕": "반가워"}', encoding="utf-8")
    code = cli.main(["replace", str(bad), str(dst), "--map", str(m)])
    out = json.loads(capsys.readouterr().out)
    assert code == 2 and not out["ok"] and out["output"] is None
    assert not dst.exists() and (tmp_path / "out.rejected.hwpx").exists()
    assert not any(n.startswith(".out") for n in os.listdir(tmp_path))


def test_cli_promotes_passing_output(tmp_path, capsys):
    import json
    from scripts import hwpx as cli
    src = build_minimal_hwpx(tmp_path / "m.hwpx")
    dst = tmp_path / "out.hwpx"
    m = tmp_path / "m.json"
    m.write_text('{"안녕하세요": "반갑습니다"}', encoding="utf-8")
    code = cli.main(["replace", str(src), str(dst), "--map", str(m)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] and dst.exists()
    assert not any(n.endswith(".pending") for n in os.listdir(tmp_path))


def test_atomic_write_leaves_no_temp(tmp_path):
    src = build_minimal_hwpx(tmp_path / "m.hwpx")
    pkg = HwpxPackage.open(src)
    pkg.write_replaced(tmp_path / "m.hwpx", {})   # 제자리 쓰기도 안전
    assert HwpxPackage.open(tmp_path / "m.hwpx").names()
    assert not any(n.endswith(".tmp") for n in os.listdir(tmp_path))


# ---------------------------------------------------------------- 추출 범위

def test_extract_covers_nested_table_textbox_header_and_footnote(tmp_path):
    inner = (TBL_HEAD.format(tid=40, rows=1, cols=2) + "<hp:tr>" + _cell(0, 0, "중첩A", 41)
             + _cell(0, 1, "중첩B", 42) + "</hp:tr></hp:tbl>")
    cell = _cell(0, 0, "바깥", 11).replace("</hp:run></hp:p>", f'</hp:run><hp:run charPrIDRef="0">{inner}</hp:run></hp:p>')
    outer = P.format(pid=10, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=12, rows=1, cols=1)
                     + f"<hp:tr>{cell}</hp:tr></hp:tbl></hp:run>")
    rect = ('<hp:rect id="50" zOrder="0" numberingType="NONE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
            'lock="0" dropcapstyle="None" href="" groupLevel="0" instid="51" ratio="0">'
            '<hp:offset x="0" y="0"/><hp:orgSz width="1" height="1"/><hp:curSz width="1" height="1"/>'
            '<hp:flip horizontal="0" vertical="0"/><hp:rotationInfo angle="0" centerX="0" centerY="0" rotateimage="1"/>'
            '<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            '<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            '<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
            '<hp:drawText lastWidth="1" name="" editable="0"><hp:textMargin left="0" right="0" top="0" bottom="0"/>'
            '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" '
            'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            + P.format(pid=52, body='<hp:run charPrIDRef="0"><hp:t>글상자 내용</hp:t></hp:run>')
            + '</hp:subList></hp:drawText>'
            '<hc:pt0 x="0" y="0"/><hc:pt1 x="1" y="0"/><hc:pt2 x="1" y="1"/><hc:pt3 x="0" y="1"/></hp:rect>')
    header = ('<hp:ctrl><hp:header id="0" applyPageType="BOTH"><hp:subList id="" textDirection="HORIZONTAL" '
              'lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" '
              'hasTextRef="0" hasNumRef="0">' + P.format(pid=60, body='<hp:run charPrIDRef="0"><hp:t>머리말 텍스트</hp:t></hp:run>')
              + '</hp:subList></hp:header></hp:ctrl>')
    foot = ('<hp:ctrl><hp:footNote number="1"><hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
            'vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" '
            'hasNumRef="0">' + P.format(pid=70, body='<hp:run charPrIDRef="0"><hp:t>각주 내용</hp:t></hp:run>')
            + '</hp:subList></hp:footNote></hp:ctrl>')
    body = (outer
            + P.format(pid=20, body=f'<hp:run charPrIDRef="0">{header}</hp:run><hp:run charPrIDRef="0"><hp:t>본문</hp:t></hp:run>')
            + P.format(pid=21, body=f'<hp:run charPrIDRef="0"><hp:t>문장</hp:t></hp:run><hp:run charPrIDRef="0">{foot}</hp:run>')
            + P.format(pid=22, body=f'<hp:run charPrIDRef="0">{rect}</hp:run>'))
    src = build_from_section(tmp_path / "y.hwpx", body)
    text = extract_text(tmp_path / "y.hwpx")
    assert "바깥 중첩A | 중첩B" in text
    assert "[머리말] 머리말 텍스트" in text and "본문" in text
    assert "[각주] 각주 내용" in text
    assert "글상자 내용" in text
    assert validate_package(tmp_path / "y.hwpx")["ok"], validate_package(tmp_path / "y.hwpx")["errors"]


def test_extract_pads_merged_cells_to_grid(tmp_path):
    a = _cell(0, 0, "병합", 11).replace('<hp:cellSpan colSpan="1" rowSpan="1"/>', '<hp:cellSpan colSpan="2" rowSpan="1"/>')
    b = _cell(1, 0, "왼", 12)
    c = _cell(1, 1, "오", 13)
    body = P.format(pid=10, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=12, rows=2, cols=2)
                    + f"<hp:tr>{a}</hp:tr><hp:tr>{b}{c}</hp:tr></hp:tbl></hp:run>")
    src = build_from_section(tmp_path / "m.hwpx", body)
    md = extract_text(src, fmt="markdown").splitlines()
    assert md[0] == "| 병합 |  |" and md[2] == "| 왼 | 오 |"
    assert extract_text(src).splitlines()[0] == "병합 | "
