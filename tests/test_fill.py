import json
import zipfile
import pytest
from core.analyze import fill_targets, extract_text
from core.edit import edit_file
from core.fill import fill_file
from core.guards import validate_package
from tests.fixture import (
    build_form_hwpx, build_minimal_hwpx,
    MIMETYPE, VERSION_XML, SETTINGS_XML, CONTAINER_XML, MANIFEST_XML,
    CONTENT_HPF, HEADER_XML, SECTION_HEAD, _table,
)


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


def test_fill_exact_match_priority_over_containment(tmp_path):
    # "동의" 는 "비동의" 의 부분 문자열이므로, 문서에서 □비동의가 □동의보다
    # 먼저 나오면 컨테인먼트만으로는 잘못된 타겟(비동의)에 매칭될 수 있다.
    # 정확 일치 우선 매칭이 이를 막아야 한다.
    src = build_form_hwpx(tmp_path / "form.hwpx")
    swapped = tmp_path / "swapped.hwpx"
    edit_file(src, swapped,
             lambda ed: ed.replace_text({"□동의 □비동의": "□비동의 □동의"}))
    dst = tmp_path / "out.hwpx"
    report = fill_file(swapped, dst, values={"동의": True})
    assert report["unmatched"] == []
    text = extract_text(dst)
    assert "☑동의" in text
    assert "□비동의" in text


def test_fill_targets_scans_checkbox_inside_table_cell(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    with_cell_checkbox = tmp_path / "cellbox.hwpx"
    edit_file(src, with_cell_checkbox,
             lambda ed: ed.set_cell_text(0, 0, 1, "□셀동의"))

    targets = fill_targets(with_cell_checkbox)["targets"]
    boxes = {t["literal"] for t in targets if t["kind"] == "checkbox"}
    assert "□셀동의" in boxes

    dst = tmp_path / "out.hwpx"
    report = fill_file(with_cell_checkbox, dst, values={"셀동의": True})
    assert report["unmatched"] == []
    assert "☑셀동의" in extract_text(dst)


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


def _pack_section0(path, section0_xml):
    """section0.xml 하나만으로 최소 HWPX 패키지를 만든다 (표 주소 지정 회귀
    테스트 등 fixture.py 헬퍼로 표현 못 하는 구조를 직접 조립할 때 사용)."""
    entries = [
        ("mimetype", MIMETYPE),
        ("version.xml", VERSION_XML),
        ("settings.xml", SETTINGS_XML),
        ("META-INF/container.xml", CONTAINER_XML),
        ("META-INF/manifest.xml", MANIFEST_XML),
        ("Contents/content.hpf", CONTENT_HPF),
        ("Contents/header.xml", HEADER_XML),
        ("Contents/section0.xml", section0_xml),
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in entries:
            ctype = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            zf.writestr(zipfile.ZipInfo(name), text.encode("utf-8"),
                        compress_type=ctype)
    return path


# 1x1 표(테이블 0) 안의 유일한 셀에, 다시 1x1 표(중첩)를 품은 문서.
# core.edit.SectionEditor._tables()가 self.root.iter()로 표를 전부 주워 담으면
# 이 중첩 표가 테이블 1로 잡혀 아래의 실제 두 번째 최상위 표(라벨-값 표)가
# 테이블 2로 밀려나며 core.analyze의 번호 체계와 어긋난다 (회귀 대상 버그).
_NESTED_OUTER_TABLE = (
    '<hp:p id="3000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
    '<hp:tbl id="3000000002" zOrder="0" numberingType="TABLE" '
    'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
    'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
    'rowCnt="1" colCnt="1" cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
    '<hp:sz width="42520" widthRelTo="ABSOLUTE" height="2400" '
    'heightRelTo="ABSOLUTE" protect="0"/>'
    '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
    'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
    'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
    'vertOffset="0" horzOffset="0"/>'
    '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
    '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
    '<hp:tr>'
    '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
    'dirty="0" borderFillIDRef="1">'
    '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
    'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
    'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
    '<hp:p id="3000000003" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
    '<hp:tbl id="3000000004" zOrder="0" numberingType="TABLE" '
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
    '<hp:tr>'
    '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
    'dirty="0" borderFillIDRef="1">'
    '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
    'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
    'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
    '<hp:p id="3000000005" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
    '<hp:t>중첩</hp:t></hp:run></hp:p>'
    '</hp:subList>'
    '<hp:cellAddr colAddr="0" rowAddr="0"/>'
    '<hp:cellSpan colSpan="1" rowSpan="1"/>'
    '<hp:cellSz width="21260" height="2400"/>'
    '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
    '</hp:tc></hp:tr></hp:tbl>'
    '</hp:run></hp:p>'
    '</hp:subList>'
    '<hp:cellAddr colAddr="0" rowAddr="0"/>'
    '<hp:cellSpan colSpan="1" rowSpan="1"/>'
    '<hp:cellSz width="42520" height="2400"/>'
    '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
    '</hp:tc></hp:tr></hp:tbl>'
    '</hp:run></hp:p>'
)


def test_fill_targets_and_edit_agree_on_table_index_with_nested_table(tmp_path):
    """표-주소 지정 계약 일치 회귀 테스트.

    outer(표0)의 유일한 셀 안에 nested(중첩) 표가 있고, 그 뒤에 진짜
    두 번째 최상위 표(라벨-값)가 온다. fill_targets는 최상위 표만 세므로
    두 번째 표를 index 1로 잡아야 하고, SectionEditor._tables()도 동일하게
    top-level 표만 순서대로 세어 index 1이 같은 표를 가리켜야 한다.
    """
    second_table = _table(rows=[["둘째표", ""]])
    section0 = SECTION_HEAD + _NESTED_OUTER_TABLE + second_table + "</hs:sec>"
    path = _pack_section0(tmp_path / "nested.hwpx", section0)

    targets = fill_targets(path)["targets"]
    label_targets = [t for t in targets if t["kind"] == "label-cell"]
    assert len(label_targets) == 1
    tgt = label_targets[0]
    assert tgt["table"] == 1
    assert tgt["key"] == "둘째표"
    assert tgt["section"] == "Contents/section0.xml"

    dst = tmp_path / "out.hwpx"
    report = fill_file(path, dst, values={"둘째표": "채움값"})
    assert report["unmatched"] == []
    text = extract_text(dst)
    assert "채움값" in text
    # 중첩 셀은 손대지 않아야 함 (extract_text는 중첩 표 텍스트를 추출하지
    # 않으므로 원본 섹션 XML에서 직접 확인한다)
    from core.package import HwpxPackage
    out_section0 = HwpxPackage.open(dst).read_text("Contents/section0.xml")
    assert "중첩" in out_section0


def test_fill_targets_ignores_nested_table_cells(tmp_path):
    """fill_targets의 grid 구성이 tbl.iter(tc)로 표를 순회하면, 중첩 표의
    셀이 바깥 셀과 같은 (rowAddr,colAddr) 주소를 갖고 있어 바깥 셀의 텍스트를
    덮어써 버릴 수 있다 (core.capacity._direct_cells에서 이미 고친 것과
    동일한 버그). 최상위 표의 직계 셀(tr→tc)만 봐야 한다."""
    second_table = _table(rows=[["둘째표", ""]])
    section0 = SECTION_HEAD + _NESTED_OUTER_TABLE + second_table + "</hs:sec>"
    path = _pack_section0(tmp_path / "nested2.hwpx", section0)

    targets = fill_targets(path)["targets"]
    # 중첩 표의 텍스트("중첩")가 라벨/체크박스/괄호 타겟 어디에도 나타나면 안 됨
    assert not any(t.get("label") == "중첩" for t in targets)
    assert not any("중첩" in t.get("literal", "") for t in targets)
    # 표 인덱스는 최상위 표(0, 1)만 가리켜야 함 — 중첩 표는 별도 인덱스를
    # 받지 않고, 중첩 셀이 클로버링을 일으켜도 표 번호 자체는 새지 않는다
    assert {t["table"] for t in targets if "table" in t} <= {0, 1}
    label_targets = [t for t in targets if t["kind"] == "label-cell"]
    assert len(label_targets) == 1 and label_targets[0]["key"] == "둘째표"


# 2열짜리 최상위 표: col0="라벨"(0,0), col1=""(0,1)이며 col1 셀 안에 중첩
# 1x1 표가 있고, 그 중첩 셀의 주소가 일부러 col0과 같은 (0,0)으로 충돌한다.
# tbl.iter(tc)로 순회하면 문서 순서상 col0→col1→(col1 내부의 중첩 tc) 순으로
# 방문되므로, 마지막에 방문되는 중첩 tc가 grid[(0,0)]을 "중첩"으로 덮어써
# 진짜 라벨 "라벨"을 지워버린다 — 최상위 셀만 보면 이 충돌이 아예 없다.
_COLLIDING_NESTED_TABLE = (
    '<hp:p id="9100000100" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
    '<hp:tbl id="9100000101" zOrder="0" numberingType="TABLE" '
    'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
    'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
    'rowCnt="1" colCnt="2" cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
    '<hp:sz width="42520" widthRelTo="ABSOLUTE" height="2400" '
    'heightRelTo="ABSOLUTE" protect="0"/>'
    '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
    'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
    'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
    'vertOffset="0" horzOffset="0"/>'
    '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
    '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
    '<hp:tr>'
    # col0: 진짜 라벨 셀, 주소 (0,0)
    '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
    'dirty="0" borderFillIDRef="1">'
    '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
    'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
    'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
    '<hp:p id="9100000102" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0">'
    '<hp:run charPrIDRef="0"><hp:t>라벨</hp:t></hp:run></hp:p>'
    '</hp:subList>'
    '<hp:cellAddr colAddr="0" rowAddr="0"/>'
    '<hp:cellSpan colSpan="1" rowSpan="1"/>'
    '<hp:cellSz width="21260" height="2400"/>'
    '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
    '</hp:tc>'
    # col1: 값 셀(직접 텍스트는 빈칸), 안에 중첩 표가 있고 그 중첩 셀 주소가
    # col0과 똑같이 (0,0)으로 충돌한다.
    '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
    'dirty="0" borderFillIDRef="1">'
    '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
    'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
    'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
    '<hp:p id="9100000103" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
    '<hp:tbl id="9100000104" zOrder="0" numberingType="TABLE" '
    'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
    'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
    'rowCnt="1" colCnt="1" cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
    '<hp:sz width="10000" widthRelTo="ABSOLUTE" height="1200" '
    'heightRelTo="ABSOLUTE" protect="0"/>'
    '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
    'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
    'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
    'vertOffset="0" horzOffset="0"/>'
    '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
    '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
    '<hp:tr>'
    '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
    'dirty="0" borderFillIDRef="1">'
    '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
    'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
    'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
    '<hp:p id="9100000105" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
    '<hp:t>중첩</hp:t></hp:run></hp:p>'
    '</hp:subList>'
    '<hp:cellAddr colAddr="0" rowAddr="0"/>'
    '<hp:cellSpan colSpan="1" rowSpan="1"/>'
    '<hp:cellSz width="10000" height="1200"/>'
    '<hp:cellMargin left="0" right="0" top="0" bottom="0"/>'
    '</hp:tc></hp:tr></hp:tbl>'
    '</hp:run></hp:p>'
    '</hp:subList>'
    '<hp:cellAddr colAddr="1" rowAddr="0"/>'
    '<hp:cellSpan colSpan="1" rowSpan="1"/>'
    '<hp:cellSz width="21260" height="2400"/>'
    '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
    '</hp:tc>'
    '</hp:tr></hp:tbl></hp:run></hp:p>'
)


def test_fill_targets_grid_not_clobbered_by_colliding_nested_address(tmp_path):
    """중첩 표의 셀 주소가 바깥 형제 셀의 주소와 우연히 같으면(둘 다 (0,0)),
    tbl.iter(tc) 순회는 grid[(0,0)]을 나중에 방문되는 중첩 셀 텍스트("중첩")로
    덮어써 진짜 라벨("라벨")을 잃어버린다. 최상위 셀(tr→tc)만 보면 이런
    충돌 자체가 일어나지 않아야 한다."""
    section0 = SECTION_HEAD + _COLLIDING_NESTED_TABLE + "</hs:sec>"
    path = _pack_section0(tmp_path / "colliding_nested.hwpx", section0)

    targets = fill_targets(path)["targets"]
    label_targets = [t for t in targets if t["kind"] == "label-cell"]
    assert len(label_targets) == 1
    assert label_targets[0]["label"] == "라벨"
    assert label_targets[0]["key"] == "라벨"
    assert not any(t.get("label") == "중첩" for t in targets)


def test_fill_multi_section_target_reported_unmatched(tmp_path):
    """멀티섹션 문서: section1 전용 타겟에 값을 채우려 하면 예외 없이
    unmatched로 보고되고 section0은 그대로 남아야 한다 (멀티섹션 편집은
    Phase 4 — v1은 section0만 지원)."""
    src = build_form_hwpx(tmp_path / "form.hwpx")
    section1_xml = (SECTION_HEAD + _table(rows=[["섹션1전용", ""]])
                     + "</hs:sec>").encode("utf-8")
    with zipfile.ZipFile(src, "r") as zf_in:
        entries = {info.filename: zf_in.read(info.filename)
                   for info in zf_in.infolist()}
    entries["Contents/section1.xml"] = section1_xml
    with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for name, data in entries.items():
            ctype = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            zf_out.writestr(zipfile.ZipInfo(name), data, compress_type=ctype)

    targets = fill_targets(src)["targets"]
    sec1_tgt = next(t for t in targets if t["key"] == "섹션1전용")
    assert sec1_tgt["section"] == "Contents/section1.xml"

    dst = tmp_path / "out.hwpx"
    report = fill_file(src, dst, values={"섹션1전용": "값"})
    assert report["unmatched"] == ["섹션1전용"]
    assert report["filled"] == []
    text = extract_text(dst)
    assert "값" not in text
    assert "성명" in text and "연락처" in text     # section0 그대로


def test_fill_report_reflects_actual_outcomes(tmp_path):
    # (1) checkbox와 paren 리터럴이 겹치는 문구 — 두 값 모두 채우려 하면
    # 먼저 적용된 checkbox 교체가 paren의 원본 리터럴을 깨뜨려 실제로는
    # 바뀌지 않는데, 예전 코드는 이를 filled로 잘못 보고했다.
    overlap_src = build_minimal_hwpx(tmp_path / "overlap.hwpx",
                                     body_texts=["신청 여부: □확인(  )"])
    targets = fill_targets(overlap_src)["targets"]
    checkbox_key = next(t["key"] for t in targets if t["kind"] == "checkbox")
    paren_key = next(t["key"] for t in targets if t["kind"] == "paren")
    assert checkbox_key != paren_key

    dst1 = tmp_path / "overlap_out.hwpx"
    report1 = fill_file(overlap_src, dst1,
                        values={checkbox_key: True, paren_key: "3"})
    assert checkbox_key in report1["filled"]
    assert paren_key in report1["unmatched"]
    assert paren_key not in report1["filled"]

    # (2) falsy 체크박스 값은 실제로 아무 편집도 하지 않으므로 filled가 아닌
    # skipped로 보고되어야 한다.
    form_src = build_form_hwpx(tmp_path / "form.hwpx")
    dst2 = tmp_path / "form_out.hwpx"
    report2 = fill_file(form_src, dst2, values={"비동의": False})
    assert "비동의" in report2["skipped"]
    assert "비동의" not in report2["filled"]
