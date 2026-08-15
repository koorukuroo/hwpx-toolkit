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


def test_add_para_after_ignores_cell_only_match(tmp_path):
    # "성명"은 표 셀 안에만 존재 — 본문 문단에는 없으므로 EditError.
    # 셀 subList 안에 조용히 삽입되는 회귀를 막는다.
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "x.hwpx"
    with pytest.raises(EditError):
        edit_file(src, dst, lambda ed: ed.add_para_after("성명", "새 문단"))
    assert not dst.exists()
