"""fill 인식 범위 확장 — 머리글 행 표, 미리 값이 있는 셀, 라벨: 값 문단, 누름틀, verify."""
import zipfile

from core.analyze import fill_targets, extract_text, is_label
from core.fill import fill_file
from core.guards import validate_package
from tests.fixture import build_from_section, _table, BODY_PARA, _cell
from tests.test_open_safety import P, TBL_HEAD


def test_is_label_rules():
    assert is_label("성명") and is_label("담당자 연락처") and is_label("사업 개요:")
    assert is_label("기관명(한글)") and is_label("짧은라벨")
    assert not is_label("□ 생산기술") and not is_label("2") and not is_label("2026. 1. 1.")
    assert not is_label("이 셀에는 아주 긴 설명 문장이 들어 있어서 라벨로 보기 어렵습니다 정말로요")


def test_header_row_table_targets_cell_below(tmp_path):
    src = build_from_section(tmp_path / "h.hwpx", _table(rows=[["성명", "소속"], ["", ""]]))
    targets = {t["key"]: t for t in fill_targets(src)["targets"] if t["kind"] == "label-cell"}
    assert targets["성명"]["placement"] == "below" and (targets["성명"]["row"], targets["성명"]["col"]) == (1, 0)
    assert targets["소속"]["placement"] == "below" and (targets["소속"]["row"], targets["소속"]["col"]) == (1, 1)
    dst = tmp_path / "o.hwpx"
    rep = fill_file(src, dst, values={"성명": "홍길동", "소속": "총무과"})
    assert rep["filled"] == ["성명", "소속"] and rep["verified"] == ["성명", "소속"]
    assert "홍길동 | 총무과" in extract_text(dst)


def test_prefilled_guide_text_is_overwritten(tmp_path):
    src = build_from_section(tmp_path / "p.hwpx",
                             _table(rows=[["사업명", "(사업명을 적으세요)"], ["번호", "A-1"]]))
    targets = {t["key"]: t for t in fill_targets(src)["targets"] if t["kind"] == "label-cell"}
    assert targets["사업명"]["prefilled"] == "(사업명을 적으세요)"
    assert targets["번호"]["prefilled"] == "A-1"
    dst = tmp_path / "o.hwpx"
    rep = fill_file(src, dst, values={"사업명": "AI 전환"})
    assert rep["verified"] == ["사업명"]
    text = extract_text(dst)
    assert "사업명 | AI 전환" in text and "적으세요" not in text and "A-1" in text


def test_label_next_to_label_is_not_prefilled_target(tmp_path):
    src = build_from_section(tmp_path / "l.hwpx", _table(rows=[["성명", "연락처"], ["홍", "010"]]))
    keys = [(t["key"], t.get("prefilled")) for t in fill_targets(src)["targets"] if t["kind"] == "label-cell"]
    assert ("성명", "연락처") not in keys


def test_inline_label_value_paragraph(tmp_path):
    body = (BODY_PARA.format(pid=1000000301, text="담당자: ")
            + BODY_PARA.format(pid=1000000302, text="연락처 : 02-000-0000")
            + BODY_PARA.format(pid=1000000303, text="이 문장은 설명입니다: 그러니까 길지요 아주 길어서 라벨이 아닙니다"))
    src = build_from_section(tmp_path / "i.hwpx", body)
    targets = [t for t in fill_targets(src)["targets"] if t["kind"] == "inline"]
    assert [t["label"] for t in targets] == ["담당자", "연락처"]
    dst = tmp_path / "o.hwpx"
    rep = fill_file(src, dst, values={"담당자": "김철수", "연락처": "031-111-2222"})
    assert rep["verified"] == ["담당자", "연락처"] and not rep["unmatched"]
    text = extract_text(dst)
    assert "담당자: 김철수" in text and "연락처: 031-111-2222" in text and "02-000-0000" not in text


def _field_run(fid, prompt, name=""):
    return ('<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldBegin id="%s" type="CLICK_HERE" name="%s" editable="1" '
            'dirty="0" zorder="0" fieldid="627207531"/></hp:ctrl></hp:run>'
            '<hp:run charPrIDRef="0"><hp:t>%s</hp:t></hp:run>'
            '<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldEnd beginIDRef="%s" fieldid="627207531"/></hp:ctrl></hp:run>'
            % (fid, name, prompt, fid))


def test_form_field_in_body_and_in_label_cell(tmp_path):
    para = P.format(pid=1000000401, body='<hp:run charPrIDRef="0"><hp:t>신청일: </hp:t></hp:run>' + _field_run(90, "날짜를 입력", name="신청일자"))
    cell = _cell(0, 1, "", 1000000411).replace('<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>', _field_run(91, "이름 입력"))
    tbl = P.format(pid=1000000410, body='<hp:run charPrIDRef="0">' + TBL_HEAD.format(tid=1000000412, rows=1, cols=2)
                   + "<hp:tr>" + _cell(0, 0, "성명", 1000000413) + cell + "</hp:tr></hp:tbl></hp:run>")
    src = build_from_section(tmp_path / "f.hwpx", para + tbl)
    targets = fill_targets(src)["targets"]
    field = next(t for t in targets if t["kind"] == "field")
    assert field["key"] == "신청일자" and field["value"] == "날짜를 입력"
    label = next(t for t in targets if t["kind"] == "label-cell")
    assert label["field"] is True
    dst = tmp_path / "o.hwpx"
    rep = fill_file(src, dst, values={"신청일자": "2026. 10. 15.", "성명": "홍길동"})
    assert rep["verified"] == ["신청일자", "성명"], rep
    xml = zipfile.ZipFile(dst).read("Contents/section0.xml").decode()
    assert xml.count('dirty="1"') == 2 and "날짜를 입력" not in xml and "이름 입력" not in xml
    assert validate_package(dst)["ok"]


def test_checkbox_with_space_after_box(tmp_path):
    src = build_from_section(tmp_path / "c.hwpx", BODY_PARA.format(pid=1000000301, text="□ 생산기술  □ 친환경"))
    targets = [t for t in fill_targets(src)["targets"] if t["kind"] == "checkbox"]
    assert {t["key"] for t in targets} == {"생산기술", "친환경"}
    dst = tmp_path / "o.hwpx"
    rep = fill_file(src, dst, values={"친환경": "yes", "생산기술": "no"})
    assert rep["verified"] == ["친환경"] and rep["skipped"] == ["생산기술"]
    assert "□ 생산기술  ☑ 친환경" in extract_text(dst)


def test_verify_failed_is_reported(tmp_path, monkeypatch):
    src = build_from_section(tmp_path / "v.hwpx", _table(rows=[["성명", ""]]))
    dst = tmp_path / "o.hwpx"
    from core import fill as fill_mod
    real = fill_mod.analyze.extract_text
    monkeypatch.setattr(fill_mod.analyze, "extract_text", lambda p: real(p).replace("홍길동", "???"))
    rep = fill_file(src, dst, values={"성명": "홍길동"})
    assert rep["filled"] == ["성명"] and rep["verify_failed"] == ["성명"]
