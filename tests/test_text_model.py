"""hp:t 텍스트 모델 — 자식 요소 뒤 tail 텍스트를 읽고 쓰는 계약 (재현된 버그의 회귀 테스트)."""
import xml.etree.ElementTree as ET

import pytest

from core import text as tm
from core.analyze import extract_text, fill_targets
from core.edit import edit_file, EditError
from core.fill import fill_file, truthy
from tests.fixture import build_from_section, BODY_PARA, _cell

HP = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'


def _t(xml):
    return ET.fromstring(f'<hp:t {HP}>{xml}</hp:t>')


def test_t_text_includes_tails_and_maps_inline_elements():
    t = _t("1. Term of<hp:lineBreak/>Labor<hp:tab/>contract<hp:fwSpace/>end")
    assert tm.t_text(t) == "1. Term of\nLabor\tcontract　end"


def test_t_write_round_trips_inline_elements_and_strips_controls():
    t = _t("old<hp:lineBreak/>junk")
    tm.set_t_text(t, "a\tb\nc\x00d\r\ne")
    out = ET.tostring(t, encoding="unicode")
    assert "<hp:tab />b" in out and "<hp:lineBreak />c" in out
    assert "\t" not in (t.text or "") and all("\t" not in (c.tail or "") for c in t)
    assert tm.t_text(t) == "a\tb\ncd\ne"
    assert "junk" not in out and "old" not in out


def test_t_write_keeps_opaque_children_in_place():
    t = _t("가<hp:markpenBegin color=\"#FFFF00\"/>나<hp:markpenEnd/>다")
    model, opaque = tm.t_model(t)
    assert len(opaque) == 2 and tm.t_text(t) == "가나다"
    tm.t_write(t, model.replace("나", "너"), opaque)
    assert tm.t_text(t) == "가너다"
    assert [c.tag.split("}")[1] for c in t] == ["markpenBegin", "markpenEnd"]


def _linebreak_doc(tmp_path):
    cell = _cell(0, 0, "", 1000000200).replace(
        "<hp:t></hp:t>", "<hp:t>1. Term of<hp:lineBreak/>Labor<hp:lineBreak/>contract</hp:t>")
    cell2 = _cell(0, 1, "값", 1000000201)
    tbl = ('<hp:p id="1000000100" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" '
           'merged="0"><hp:run charPrIDRef="0">'
           '<hp:tbl id="1000000101" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
           'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
           'rowCnt="1" colCnt="2" cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
           '<hp:sz width="42520" widthRelTo="ABSOLUTE" height="2400" heightRelTo="ABSOLUTE" protect="0"/>'
           '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
           'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
           'vertOffset="0" horzOffset="0"/>'
           '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
           '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
           f'<hp:tr>{cell}{cell2}</hp:tr></hp:tbl></hp:run></hp:p>')
    return build_from_section(tmp_path / "lb.hwpx", tbl)


def test_replace_reaches_text_after_linebreak(tmp_path):
    src = _linebreak_doc(tmp_path)
    dst = tmp_path / "out.hwpx"
    rep = edit_file(src, dst, lambda ed: ed.replace_text({"contract": "계약", "Labor": "근로"}))
    assert rep["replaced"] == {"contract": 1, "Labor": 1} and not rep["not_found"]
    text = extract_text(dst)
    assert "1. Term of 근로 계약" in text          # text 모드: 셀 줄바꿈은 공백
    md = extract_text(dst, fmt="markdown")
    assert "1. Term of<br>근로<br>계약" in md       # markdown: <br>


def test_set_cell_leaves_no_residue_after_inline_elements(tmp_path):
    src = _linebreak_doc(tmp_path)
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.set_cell_text(0, 0, 0, "새 값"))
    import zipfile
    xml = zipfile.ZipFile(dst).read("Contents/section0.xml").decode()
    assert "Labor" not in xml and "contract" not in xml and "lineBreak" not in xml
    assert "<hp:t>새 값</hp:t>" in xml


def test_set_cell_writes_tab_and_newline_as_elements(tmp_path):
    src = _linebreak_doc(tmp_path)
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.set_cell_text(0, 0, 1, "a\tb\nc"))
    import zipfile
    xml = zipfile.ZipFile(dst).read("Contents/section0.xml").decode()
    assert "<hp:t>a<hp:tab />b<hp:lineBreak />c</hp:t>" in xml
    assert "\t" not in xml


def test_set_cell_drops_extra_plain_paragraphs_but_keeps_nested_objects(tmp_path):
    inner_tbl = ('<hp:tbl id="7" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
                 'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
                 'rowCnt="1" colCnt="1" cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
                 '<hp:sz width="1000" widthRelTo="ABSOLUTE" height="1000" heightRelTo="ABSOLUTE" protect="0"/>'
                 '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
                 'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
                 'vertOffset="0" horzOffset="0"/>'
                 '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
                 '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
                 '<hp:tr>' + _cell(0, 0, "중첩", 9) + '</hp:tr></hp:tbl>')
    cell = _cell(0, 0, "첫째", 1000000200).replace(
        "</hp:p></hp:subList>",
        '</hp:p><hp:p id="1000000210" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" '
        'merged="0"><hp:run charPrIDRef="0"><hp:t>둘째</hp:t></hp:run></hp:p>'
        '<hp:p id="1000000211" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" '
        f'merged="0"><hp:run charPrIDRef="0">{inner_tbl}</hp:run></hp:p></hp:subList>')
    tbl = ('<hp:p id="1000000100" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" '
           'merged="0"><hp:run charPrIDRef="0">'
           '<hp:tbl id="1000000101" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
           'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
           'rowCnt="1" colCnt="1" cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
           '<hp:sz width="42520" widthRelTo="ABSOLUTE" height="2400" heightRelTo="ABSOLUTE" protect="0"/>'
           '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
           'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
           'vertOffset="0" horzOffset="0"/>'
           '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
           '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
           f'<hp:tr>{cell}</hp:tr></hp:tbl></hp:run></hp:p>')
    src = build_from_section(tmp_path / "n.hwpx", tbl)
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.set_cell_text(0, 0, 0, "값"))
    import zipfile
    xml = zipfile.ZipFile(dst).read("Contents/section0.xml").decode()
    assert "둘째" not in xml and 'id="1000000210"' not in xml
    assert "중첩" in xml and 'id="1000000211"' in xml
    assert "값" in extract_text(dst) and "중첩" in extract_text(dst)


def test_dominant_run_carries_new_paragraph_text(tmp_path):
    para = ('<hp:p id="1000000050" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" '
            'merged="0"><hp:run charPrIDRef="0"><hp:t>※ </hp:t></hp:run>'
            '<hp:run charPrIDRef="0"><hp:t>본문이 길게 들어 있는 런입니다</hp:t></hp:run></hp:p>')
    src = build_from_section(tmp_path / "d.hwpx", para)
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.add_para_after("본문이", "새 문단"))
    import zipfile
    xml = zipfile.ZipFile(dst).read("Contents/section0.xml").decode()
    assert '<hp:run charPrIDRef="0"><hp:t /></hp:run><hp:run charPrIDRef="0"><hp:t>새 문단</hp:t>' in xml


def test_truthy_rejects_false_like_strings():
    assert truthy(True) and truthy("☑") and truthy("yes") and truthy("예")
    for v in (False, 0, "", "false", "False", "0", "no", "□", "아니오"):
        assert not truthy(v), v


def test_fill_skips_string_false_checkbox(tmp_path):
    from tests.fixture import build_form_hwpx
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    rep = fill_file(src, dst, values={"동의": "false"})
    assert rep["skipped"] == ["동의"] and not rep["filled"]
    assert "☑" not in extract_text(dst)
