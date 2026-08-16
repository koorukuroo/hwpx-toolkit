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
    # hp:pagePr@landscape는 건드리지 않는다 — 회전은 폭/높이 스왑만으로 표현한다
    # (실제 방향은 landscape 속성과 폭>높이 여부의 XOR, 한컴 실물 검증 2026-08-17).
    assert pp.get("landscape") == "WIDELY"
    assert (pp.get("width"), pp.get("height")) == ("119055", "84186")
    m = pp.find(f"{{{NS_HP}}}margin")
    assert m.get("left") == "4536" and m.get("top") == "5670"
    assert check_package(dst)["ok"]


def _narrowly_variant(tmp_path):
    """landscape="WIDELY" -> "NARROWLY"로 바꾼, 이미 가로로 렌더링되는 문서
    (표의 NARROWLY/portrait-dims 행)."""
    src = build_form_hwpx(tmp_path / "f.hwpx")
    pkg = HwpxPackage.open(src)
    sec = pkg.read_text("Contents/section0.xml").replace(
        'landscape="WIDELY"', 'landscape="NARROWLY"')
    variant = tmp_path / "narrowly.hwpx"
    pkg.write_replaced(variant, {"Contents/section0.xml": sec.encode("utf-8")})
    return variant


def test_set_page_landscape_from_portrait_swaps_dims_keeps_attr(tmp_path):
    # 기준 픽스처: landscape="WIDELY", 59528x84186 (portrait dims) => 세로로 렌더링.
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.set_page(orientation="landscape"))
    pp = _first_run(_sec_root(dst)).find(f".//{{{NS_HP}}}pagePr")
    assert pp.get("landscape") == "WIDELY"
    assert (pp.get("width"), pp.get("height")) == ("84186", "59528")
    assert check_package(dst)["ok"]


def test_set_page_landscape_is_idempotent(tmp_path):
    # 두 번 연속 landscape를 적용해도 다시 세로로 뒤집히면 안 된다
    # (이번 버그: 회전을 이중 적용).
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    edit_file(src, d1, lambda ed: ed.set_page(orientation="landscape"))
    d2 = tmp_path / "2.hwpx"
    edit_file(d1, d2, lambda ed: ed.set_page(orientation="landscape"))
    pp = _first_run(_sec_root(d2)).find(f".//{{{NS_HP}}}pagePr")
    assert pp.get("landscape") == "WIDELY"
    assert (pp.get("width"), pp.get("height")) == ("84186", "59528")
    assert check_package(d2)["ok"]


def test_set_page_landscape_noop_when_already_landscape(tmp_path):
    # landscape="NARROWLY" + portrait dims는 표 상 이미 가로 렌더링 상태이므로
    # set_page(orientation="landscape")는 아무것도 바꾸지 않아야 한다.
    variant = _narrowly_variant(tmp_path)
    dst = tmp_path / "o.hwpx"
    edit_file(variant, dst, lambda ed: ed.set_page(orientation="landscape"))
    pp = _first_run(_sec_root(dst)).find(f".//{{{NS_HP}}}pagePr")
    assert pp.get("landscape") == "NARROWLY"
    assert (pp.get("width"), pp.get("height")) == ("59528", "84186")
    assert check_package(dst)["ok"]


def test_set_page_portrait_on_narrowly_swaps_dims_keeps_attr(tmp_path):
    # 같은 NARROWLY 문서에 portrait을 요청하면 스왑된 치수
    # (84186x59528, attr는 그대로)가 실제로 세로로 렌더링되는 조합이다.
    variant = _narrowly_variant(tmp_path)
    dst = tmp_path / "o.hwpx"
    edit_file(variant, dst, lambda ed: ed.set_page(orientation="portrait"))
    pp = _first_run(_sec_root(dst)).find(f".//{{{NS_HP}}}pagePr")
    assert pp.get("landscape") == "NARROWLY"
    assert (pp.get("width"), pp.get("height")) == ("84186", "59528")
    assert check_package(dst)["ok"]


def test_set_page_portrait_on_plain_portrait_is_noop(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.set_page(orientation="portrait"))
    pp = _first_run(_sec_root(dst)).find(f".//{{{NS_HP}}}pagePr")
    assert pp.get("landscape") == "WIDELY"
    assert (pp.get("width"), pp.get("height")) == ("59528", "84186")
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
    assert headers[0].get("id") == "0"        # 한컴 실물: id="" 아닌 id="0"
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


def test_header_footer_update_marks_header_paragraph_not_p0(tmp_path):
    # set_header_footer의 UPDATE 경로는 실제로 수정한 헤더 하위 문단(hp)을
    # 마킹해야 한다 — p0(섹션 첫 문단)만 마킹하면 hp가 들고 있던 stale
    # linesegarray가 그대로 남는다.
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    edit_file(src, d1, lambda ed: ed.set_header_footer("header", "대외비"))

    def _inject_stale_lineseg(ed):
        hp = ed._hf_para(ed._find_hf("header")[0])
        ET.SubElement(hp, f"{{{NS_HP}}}linesegarray")

    d2 = tmp_path / "2.hwpx"
    edit_file(d1, d2, _inject_stale_lineseg)
    header_p2 = list(_sec_root(d2).iter(f"{{{NS_HP}}}header"))[0].find(f".//{{{NS_HP}}}p")
    assert header_p2.find(f"{{{NS_HP}}}linesegarray") is not None   # 주입 확인

    d3 = tmp_path / "3.hwpx"
    edit_file(d2, d3, lambda ed: ed.set_header_footer("header", "일급비밀"))
    header_p3 = list(_sec_root(d3).iter(f"{{{NS_HP}}}header"))[0].find(f".//{{{NS_HP}}}p")
    assert header_p3.find(f"{{{NS_HP}}}linesegarray") is None
    assert check_package(d3)["ok"]


def test_remove_header_footer_searches_whole_section(tmp_path):
    # remove_header_footer는 p0의 첫 run만 볼 게 아니라 섹션 전체에서
    # header/footer ctrl을 찾아야 한다 (set_header_footer가 root.iter로
    # 찾는 것과 대칭).
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    edit_file(src, d1, lambda ed: ed.set_header_footer("footer", "쪽 하단"))

    def _move_ctrl_to_other_para(ed):
        p0, run0 = ed._first_run()
        footer_ctrl = next(c for c in run0.findall(f"{{{NS_HP}}}ctrl")
                           if c.find(f"{{{NS_HP}}}footer") is not None)
        run0.remove(footer_ctrl)
        target = ed._target_para(after="제출 부수")
        target.find(f"{{{NS_HP}}}run").append(footer_ctrl)

    d2 = tmp_path / "2.hwpx"
    edit_file(d1, d2, _move_ctrl_to_other_para)
    root2 = _sec_root(d2)
    assert len(list(root2.iter(f"{{{NS_HP}}}footer"))) == 1
    first_run2 = root2.find(f"{{{NS_HP}}}p/{{{NS_HP}}}run")
    assert first_run2.find(f"{{{NS_HP}}}ctrl/{{{NS_HP}}}footer") is None  # 이동 확인

    d3 = tmp_path / "3.hwpx"
    edit_file(d2, d3, lambda ed: ed.remove_header_footer("footer"))
    assert not list(_sec_root(d3).iter(f"{{{NS_HP}}}footer"))
    assert check_package(d3)["ok"]


def test_page_number_in_footer(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    dst = tmp_path / "o.hwpx"
    edit_file(src, dst, lambda ed: ed.set_page_number(where="footer", align="center"))
    root = _sec_root(dst)
    footers = list(root.iter(f"{{{NS_HP}}}footer"))
    assert len(footers) == 1
    auto = footers[0].find(f".//{{{NS_HP}}}autoNum")
    assert auto is not None and auto.get("numType") == "PAGE"
    # 한컴 실물: hp:run > hp:ctrl > hp:autoNum (autoNum이 ctrl 없이 run
    # 바로 밑에 오면 잘못된 구조)
    parents = {c: p for p in root.iter() for c in p}
    ctrl = parents[auto]
    assert ctrl.tag == f"{{{NS_HP}}}ctrl"
    run = parents[ctrl]
    assert run.tag == f"{{{NS_HP}}}run"
    assert run.find(f"{{{NS_HP}}}t") is not None      # ctrl 뒤 빈 hp:t
    assert check_package(dst)["ok"]


def test_invalid_page_args(tmp_path):
    src = build_form_hwpx(tmp_path / "f.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx", lambda ed: ed.set_page(size="a9"))
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "y.hwpx",
                  lambda ed: ed.set_header_footer("sidebar", "x"))
