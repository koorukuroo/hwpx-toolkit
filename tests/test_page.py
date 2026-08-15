import xml.etree.ElementTree as ET
import pytest
from core.package import HwpxPackage
from core.edit import edit_file, EditError
from core.guards import check_package
from tests.fixture import build_form_hwpx

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _sec_root(path):
    return ET.fromstring(HwpxPackage.open(path).read("Contents/section0.xml"))


def _first_run(root):
    return root.find(f"{{{NS_HP}}}p/{{{NS_HP}}}run")


def test_set_page_landscape_a3_margins(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.set_page(
        orientation="landscape", size="a3",
        margins_mm={"left": 16, "right": 16, "top": 20, "bottom": 20}))
    pp = _first_run(_sec_root(dst)).find(f".//{{{NS_HP}}}pagePr")
    assert pp.get("landscape") == "NARROWLY"
    assert (pp.get("width"), pp.get("height")) == ("119055", "84186")
    m = pp.find(f"{{{NS_HP}}}margin")
    assert m.get("left") == "4536" and m.get("top") == "5670"
    assert check_package(dst)["ok"]


def test_set_columns_and_page_break(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: (ed.set_columns(2, gap_mm=8),
                                    ed.set_page_break("감사합니다")))
    root = _sec_root(dst)
    col = _first_run(root).find(f".//{{{NS_HP}}}colPr")
    assert col.get("colCount") == "2"
    assert _first_run(root).find(f"{{{NS_HP}}}secPr").get("spaceColumns") == "2268"
    target = [p for p in root.iter(f"{{{NS_HP}}}p")
              if "감사합니다" in "".join(t.text or "" for r in p.findall(f"{{{NS_HP}}}run")
                                     for t in r.findall(f"{{{NS_HP}}}t"))][0]
    assert target.get("pageBreak") == "1"
    assert check_package(dst)["ok"]


def test_header_footer_insert_update_remove(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    edit_file(src, d1, lambda ed: ed.set_header_footer("header", "대외비", align="center"))
    root = _sec_root(d1)
    headers = list(root.iter(f"{{{NS_HP}}}header"))
    assert len(headers) == 1
    assert "대외비" in "".join(t.text or "" for t in headers[0].iter(f"{{{NS_HP}}}t"))
    assert check_package(d1)["ok"]

    d2 = tmp_path / "2.hwpx"
    edit_file(d1, d2, lambda ed: ed.set_header_footer("header", "일급비밀"))
    root2 = _sec_root(d2)
    headers2 = list(root2.iter(f"{{{NS_HP}}}header"))
    assert len(headers2) == 1                     # 중복 생성 없음
    txt = "".join(t.text or "" for t in headers2[0].iter(f"{{{NS_HP}}}t"))
    assert "일급비밀" in txt and "대외비" not in txt

    d3 = tmp_path / "3.hwpx"
    edit_file(d2, d3, lambda ed: ed.remove_header_footer("header"))
    assert not list(_sec_root(d3).iter(f"{{{NS_HP}}}header"))


def test_page_number_in_footer(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.set_page_number(where="footer", align="center"))
    root = _sec_root(dst)
    footers = list(root.iter(f"{{{NS_HP}}}footer"))
    assert len(footers) == 1
    auto = footers[0].find(f".//{{{NS_HP}}}autoNum")
    assert auto is not None and auto.get("numType") == "PAGE"
    assert check_package(dst)["ok"]


def test_invalid_page_args(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx", lambda ed: ed.set_page(size="a9"))
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "y.hwpx",
                  lambda ed: ed.set_header_footer("sidebar", "x"))
