import zipfile
from core.capacity import estimate_chars, cell_report, for_cell, OVER_MARGIN, text_width_em
from core.analyze import fill_targets
from core.guards import check_package
from core.edit import edit_file
from tests.fixture import (
    build_form_hwpx, build_minimal_hwpx, SECTION_HEAD, _table,
    MIMETYPE, VERSION_XML, SETTINGS_XML, CONTAINER_XML, MANIFEST_XML,
    CONTENT_HPF, HEADER_XML,
)
from tests.test_fill import _NESTED_OUTER_TABLE, _pack_section0

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
    assert first["used"] == 2.0                  # "성명" — 한글 2자 = 2.0em
    assert first["used_chars"] == 2
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
    assert target["used"] == 60.0 and target["over"] is True  # 한글 60자 = 60.0em
    assert target["used_chars"] == 60

    r = check_package(dst)
    assert r["ok"] is True                       # 경고이지 오류가 아님
    overflow_msgs = [w for w in r["warnings"] if w.startswith("cell-overflow-risk")]
    assert overflow_msgs
    # used가 em 단위 실수이므로 "자"를 그대로 붙이면 "25.5자" 같은 말이 안 되는
    # 표현이 된다 — 단위를 정직하게 "em"으로 쓰고, 사람이 읽는 실제 글자 수는
    # 별도로 "문자 N자"로 덧붙여야 한다.
    msg = next(m for m in overflow_msgs if m.startswith("cell-overflow-risk: 표"))
    assert "em <" in msg and "em (" in msg
    assert "문자 60자" in msg


def test_no_false_overflow_on_clean_fixtures(tmp_path):
    for p in (build_form_hwpx(tmp_path / "f.hwpx"),
              build_minimal_hwpx(tmp_path / "m.hwpx", with_table=True)):
        r = check_package(p)
        assert not [w for w in r["warnings"] if w.startswith("cell-overflow-risk")]


def test_margin_constant_is_lenient():
    assert OVER_MARGIN >= 1.1


def test_estimate_chars_zero_when_geometry_unknown():
    # 가용 폭/높이가 0 이하(여백이 셀 크기를 넘어서는 등 기하가 불명확한
    # 경우)면 "추정 불가"를 뜻하는 0을 반환해야 한다. 예전 로직은
    # max(1, ...)로 음수를 1로 눌러 놓아 "1자는 들어간다"는 거짓 확신을 줬다.
    assert estimate_chars(0, 0, M141, 1000, 160) == 0
    assert estimate_chars(100, 100, M141, 1000, 160) == 0    # 여백이 셀보다 큼


_NO_CELLSZ_TABLE = (
    '<hp:p id="4000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
    '<hp:tbl id="4000000002" zOrder="0" numberingType="TABLE" '
    'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
    'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
    'rowCnt="1" colCnt="1" cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
    '<hp:sz width="21260" widthRelTo="ABSOLUTE" height="2400" '
    'heightRelTo="ABSOLUTE" protect="0"/>'
    '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
    'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
    'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
    'vertOffset="0" horzOffset="0"/>'
    '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
    '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
    '<hp:tr><hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
    'dirty="0" borderFillIDRef="1">'
    '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
    'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
    'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
    '<hp:p id="4000000003" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
    '<hp:t>내용</hp:t></hp:run></hp:p>'
    '</hp:subList>'
    '<hp:cellAddr colAddr="0" rowAddr="0"/>'
    '<hp:cellSpan colSpan="1" rowSpan="1"/>'
    '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
    '</hp:tc></hp:tr></hp:tbl></hp:run></hp:p>'
)


def test_cell_report_no_cellsz_reports_zero_capacity(tmp_path):
    # cellSz가 없는 셀(예: 일부 실물 문서의 병합/특수 셀)은 폭·높이를
    # 알 수 없으므로 capacity 0, over False로 보고해야 한다(경고 오탐 방지).
    section0 = SECTION_HEAD + _NO_CELLSZ_TABLE + "</hs:sec>"
    path = _pack_section0(tmp_path / "no_cellsz.hwpx", section0)
    cells = cell_report(path)["cells"]
    assert len(cells) == 1
    assert cells[0]["capacity"] == 0
    assert cells[0]["over"] is False


def test_check_caps_overflow_warnings_at_20_with_summary_line(tmp_path):
    # cell-overflow-risk 경고는 20건까지만 개별 표시하고, 그 이상은
    # "외 N건 더" 요약 한 줄로 묶는다.
    rows = [[f"라벨{i}", "가" * 60] for i in range(25)]
    overflow_table = _table(rows=rows)
    section0 = SECTION_HEAD + overflow_table + "</hs:sec>"
    path = _pack_section0(tmp_path / "many_overflow.hwpx", section0)

    cells = cell_report(path)["cells"]
    over = [c for c in cells if c["over"]]
    assert len(over) == 25                     # 25개 셀 모두 넘침

    r = check_package(path)
    overflow_msgs = [w for w in r["warnings"] if w.startswith("cell-overflow-risk")]
    assert len(overflow_msgs) == 21             # 20건 개별 + 요약 1줄
    assert overflow_msgs[-1] == "cell-overflow-risk: 외 5건 더"


def test_cell_report_ignores_nested_table_cells(tmp_path):
    """중첩 표의 셀은 최상위 표의 셀로 잘못 집계되면 안 된다 (analyze._table_rows,
    edit._tables와 동일하게 최상위 표만 v1 지원 대상). _NESTED_OUTER_TABLE은
    표0의 유일한 셀 안에 다시 1x1 표를 품는다."""
    second_table = _table(rows=[["둘째표", ""]])
    section0 = SECTION_HEAD + _NESTED_OUTER_TABLE + second_table + "</hs:sec>"
    path = _pack_section0(tmp_path / "nested.hwpx", section0)

    cells = cell_report(path)["cells"]
    keys = [(c["section"], c["table"], c["row"], c["col"]) for c in cells]
    assert len(keys) == len(set(keys))            # 중복 키 없음

    # 표0은 셀이 1개(중첩 표를 품은 그 셀)뿐이어야 하고, 그 텍스트는 outer
    # 셀 자체의 직접 텍스트(빈 문자열)여야 한다 — 중첩 표의 "중첩" 텍스트가
    # 표0/(0,0)으로 새어 들어가면 안 된다.
    table0 = [c for c in cells if c["table"] == 0]
    assert len(table0) == 1
    assert table0[0]["used_chars"] == 0

    # 표1(둘째표)은 정상적으로 2셀 집계된다.
    table1 = [c for c in cells if c["table"] == 1]
    assert len(table1) == 2


def test_ascii_digits_are_half_width_not_over_but_hangul_is(tmp_path):
    """실물 문서에서 "125,000" 같은 반각 숫자/콤마 셀이 글자 수 기준으로는
    넘침처럼 보여도 실제로는 em 폭 기준이라 넘치지 않아야 한다."""
    assert text_width_em("125,000") == 3.5
    assert text_width_em("가나다") == 3.0
    assert text_width_em("1 2") == 1.0            # 공백 제외

    # capacity 20(em)인 폼 기준 셀 — 임계는 20*1.15=23em.
    src = build_form_hwpx(tmp_path / "form.hwpx")

    dst_ascii = tmp_path / "ascii.hwpx"
    edit_file(src, dst_ascii, lambda ed: ed.set_cell_text(0, 0, 1, "1" * 25))
    cells = cell_report(dst_ascii)["cells"]
    target = next(c for c in cells if (c["row"], c["col"]) == (0, 1))
    assert target["used_chars"] == 25              # 옛 로직이면 25 > 23 → 오탐
    assert target["used"] == 12.5                  # 반각 25자 = 12.5em
    assert target["over"] is False                 # em 기준으로는 넘치지 않음

    dst_hangul = tmp_path / "hangul.hwpx"
    edit_file(src, dst_hangul, lambda ed: ed.set_cell_text(0, 0, 1, "가" * 25))
    cells2 = cell_report(dst_hangul)["cells"]
    target2 = next(c for c in cells2 if (c["row"], c["col"]) == (0, 1))
    assert target2["used"] == 25.0
    assert target2["over"] is True                 # 한글 25자는 실제로 넘침


def test_numeric_cell_not_over_capacity_seven():
    """브리프 재현 예시: 추정 수용 7em 셀에 "125,000"(7자, 3.5em)은 넘치지
    않지만, 같은 셀에 한글 20자(20em)가 들어가면 넘친다."""
    capacity = 7
    used_numeric = round(text_width_em("125,000"), 1)
    assert used_numeric == 3.5
    assert not (capacity and used_numeric > capacity * OVER_MARGIN)

    used_hangul = round(text_width_em("가" * 20), 1)
    assert used_hangul == 20.0
    assert capacity and used_hangul > capacity * OVER_MARGIN
