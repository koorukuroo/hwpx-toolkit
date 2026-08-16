import xml.etree.ElementTree as ET
import zipfile
import pytest
from core.package import HwpxPackage
from core.edit import edit_file, EditError
from core.header import HeaderEditor
from core.guards import check_package
from core.template import TEMPLATES_DIR
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


def _base_template_header_bytes():
    return (TEMPLATES_DIR / "base" / "Contents" / "header.xml").read_bytes()


def _charpr_tags(he, char_id):
    root = ET.fromstring(he.serialize())
    coll = root.find(f".//{{{NS_HH}}}charProperties")
    new = next(c for c in coll.findall(f"{{{NS_HH}}}charPr") if c.get("id") == char_id)
    return [child.tag.split("}")[-1] for child in new]


def test_clone_char_pr_italic_bold_order_matches_schema():
    # 실제 한컴 문서(한컴 실물 문서)의 charPr 순서는 offset, italic, bold,
    # underline, strikeout, outline, shadow — bold/italic을 함께 추가할 때
    # 반복마다 offset을 다시 찾으면 순서가 bold, italic으로 뒤집히는 회귀를
    # 방지한다.
    he = HeaderEditor(_base_template_header_bytes())
    new_id = he.clone_char_pr("0", bold=True, italic=True)
    tags = _charpr_tags(he, new_id)
    assert tags.index("offset") < tags.index("italic") < tags.index("bold") \
        < tags.index("underline")


def test_clone_char_pr_italic_lands_before_existing_bold():
    # charPr 1은 base에 이미 bold가 있다. italic만 추가로 요청하면(bold는
    # None이라 건드리지 않음) 새 italic은 기존 bold "앞"(offset 바로 뒤)에
    # 와야 한다 — 러닝 인덱스 방식은 미지정 플래그의 위치 이동을 놓쳐
    # italic이 bold "뒤"에 삽입되는 회귀가 있었다.
    he = HeaderEditor(_base_template_header_bytes())
    new_id = he.clone_char_pr("1", italic=True)
    tags = _charpr_tags(he, new_id)
    assert tags.index("offset") < tags.index("italic") < tags.index("bold") \
        < tags.index("underline")


def test_clone_char_pr_italic_lands_before_bold_from_prior_clone():
    # 먼저 bold만 추가한 복제본을 만든 뒤, 그 결과를 base로 다시
    # italic만 추가하면 italic은 새로 생긴 bold "앞"(offset 바로 뒤)에
    # 와야 한다.
    he = HeaderEditor(_base_template_header_bytes())
    bold_only_id = he.clone_char_pr("0", bold=True)
    both_id = he.clone_char_pr(bold_only_id, italic=True)
    tags = _charpr_tags(he, both_id)
    assert tags.index("offset") < tags.index("italic") < tags.index("bold") \
        < tags.index("underline")


def test_set_text_style_requires_at_least_one_style_kw(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx",
                  lambda ed: ed.set_text_style(after="안녕하세요"))


def test_set_para_style_requires_at_least_one_style_kw(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx",
                  lambda ed: ed.set_para_style(after="안녕하세요"))
