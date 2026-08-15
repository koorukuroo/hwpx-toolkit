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
