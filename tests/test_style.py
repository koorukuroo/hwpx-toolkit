import xml.etree.ElementTree as ET
import zipfile
import pytest
from core.package import HwpxPackage
from core.edit import edit_file, EditError
from core.header import HeaderEditor
from core.guards import check_package
from tests.fixture import build_form_hwpx, build_minimal_hwpx

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _header_root(path):
    return ET.fromstring(HwpxPackage.open(path).read("Contents/header.xml"))


def test_clone_char_pr_adds_entry_and_fixes_itemcnt(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    he = HeaderEditor.from_package(HwpxPackage.open(src))
    new_id = he.clone_char_pr("0", bold=True, color="C00000", size_pt=16)
    assert new_id == "1"
    root = ET.fromstring(he.serialize())
    coll = root.find(f".//{{{NS_HH}}}charProperties")
    chars = coll.findall(f"{{{NS_HH}}}charPr")
    assert coll.get("itemCnt") == "2" and len(chars) == 2
    new = chars[-1]
    assert new.get("height") == "1600" and new.get("textColor") == "#C00000"
    assert new.find(f"{{{NS_HH}}}bold") is not None
    assert he.dirty


def test_set_text_style_repoints_only_target(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.set_text_style(after="안녕하세요", bold=True))
    root = ET.fromstring(HwpxPackage.open(dst).read("Contents/section0.xml"))
    refs = {}
    for p in root.iter(f"{{{NS_HP}}}p"):
        text = "".join(t.text or "" for r in p.findall(f"{{{NS_HP}}}run")
                       for t in r.findall(f"{{{NS_HP}}}t"))
        for r in p.findall(f"{{{NS_HP}}}run"):
            refs.setdefault(text, set()).add(r.get("charPrIDRef"))
    assert refs["안녕하세요"] == {"1"}          # 새 charPr
    assert refs["감사합니다"] == {"0"}          # 비대상 불변
    assert check_package(dst)["ok"]
    hroot = _header_root(dst)
    assert hroot.find(f".//{{{NS_HH}}}charProperties").get("itemCnt") == "2"


def test_set_para_style_align_and_spacing(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.set_para_style(
        after="안녕하세요", align="center", line_spacing=180))
    hroot = _header_root(dst)
    paras = hroot.find(f".//{{{NS_HH}}}paraProperties")
    assert paras.get("itemCnt") == "2"
    new = paras.findall(f"{{{NS_HH}}}paraPr")[-1]
    assert new.find(f"{{{NS_HH}}}align").get("horizontal") == "CENTER"
    ls = new.find(f".//{{{NS_HH}}}lineSpacing")
    assert ls is not None and ls.get("value") == "180"
    assert check_package(dst)["ok"]


def test_header_untouched_when_no_style_edit(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.replace_text({"성명": "이름"}))
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(dst) as b:
        assert a.read("Contents/header.xml") == b.read("Contents/header.xml")


def test_target_para_index_and_missing(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.set_text_style(index=-1, italic=True))
    assert check_package(dst)["ok"]
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx",
                  lambda ed: ed.set_text_style(after="없는문구", bold=True))
