"""온라인 조사 반영분 — 구조 순서 경고, 공문서 띄어쓰기 lint, 링크·각주·머리말·쪽번호 생성,
패키지 한도, 쪽 미리보기(render)."""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from core import owpml
from core.analyze import extract_text
from core.guards import check_package, validate_package
from core.lint import lint_text
from core.markdown import document_decorations, footnote_definitions, parse_markdown, render_document
from core.package import HwpxPackage, PackageError
from core.template import build_from_template
from tests.fixture import build_from_section, build_minimal_hwpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import importlib  # noqa: E402
cli = importlib.import_module("hwpx")

P = ('<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
     '{body}</hp:p>')


def _rules(text):
    return {f["rule"] for f in lint_text(text)["findings"]}


# ---------------------------------------------------------------- lint
def test_lint_tilde_weekday_law_quotes():
    r = lint_text('일시: 2023. 11. 11. (토) / 기간: 4. 23. ~ 6. 15. / "초중등교육법"에 따라')
    rules = {f["rule"]: f for f in r["findings"]}
    assert rules["weekday-paren-space"]["suggest"] == "11.(토)"
    assert "tilde-spacing" in rules and "~" in rules["tilde-spacing"]["suggest"]
    assert rules["law-title-quotes"]["suggest"] == "「초중등교육법」"
    assert "tilde-spacing" not in _rules("기간: 4. 23.~6. 15.")


def test_lint_common_spacing_fixes():
    text = "참석자 50여명, 20명 당 1명, 그 동안 두가지 안을 제 4차 회의에서 검토, 50%이상 참여, 3일내 제출, 귀 교에서 10. 25.(금) 까지"
    sugg = [f["suggest"] for f in lint_text(text)["findings"] if f["rule"] == "spacing-common"]
    for expected in ("50여 명", "20명당", "그동안", "두 가지", "제4차", "50% 이상", "3일 내", "귀교", "(금)까지"):
        assert expected in sugg, expected
    assert "spacing-common" not in _rules("제4차 회의, 귀교, 50% 이상, 그동안")


# ---------------------------------------------------------------- guards
def test_lineseg_not_last_and_field_span_are_warnings(tmp_path):
    body = (P.format(pid="10", body='<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1000" '
                     'textheight="1000" baseline="850" spacing="600" horzpos="0" horzsize="42520" '
                     'flags="393216"/></hp:linesegarray><hp:run charPrIDRef="0"><hp:t>a</hp:t></hp:run>')
            + P.format(pid="11", body='<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldBegin id="77" type="CLICK_HERE" '
                       'name="" editable="1" dirty="0" zorder="-1" fieldid="1"/></hp:ctrl><hp:t>x</hp:t></hp:run>')
            + P.format(pid="12", body='<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldEnd beginIDRef="77" fieldid="1"/>'
                       '</hp:ctrl><hp:t/></hp:run>'))
    out = build_from_section(tmp_path / "w.hwpx", body)
    r = validate_package(out)
    assert r["ok"], r["errors"]
    joined = "\n".join(r["warnings"])
    assert "lineseg-not-last" in joined and "field-spans-paragraphs" in joined


def test_secpr_ctrl_order_warning(tmp_path):
    out = build_minimal_hwpx(tmp_path / "o.hwpx")
    pkg = HwpxPackage.open(out)
    sec = pkg.read_text("Contents/section0.xml")
    hf = ('<hp:ctrl><hp:header id="0" applyPageType="BOTH"><hp:subList id="" textDirection="HORIZONTAL" '
          'lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" '
          'textHeight="0" hasTextRef="0" hasNumRef="0"><hp:p id="900" paraPrIDRef="0" styleIDRef="0" '
          'pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>h</hp:t></hp:run>'
          '</hp:p></hp:subList></hp:header></hp:ctrl>')
    assert "</hp:secPr><hp:ctrl><hp:colPr" in sec
    bad = sec.replace("</hp:secPr><hp:ctrl><hp:colPr", "</hp:secPr>" + hf + "<hp:ctrl><hp:colPr", 1)
    pkg.write_replaced(tmp_path / "bad.hwpx", {"Contents/section0.xml": bad.encode("utf-8")})
    r = validate_package(tmp_path / "bad.hwpx")
    assert any(w.startswith("secpr-ctrl-order") for w in r["warnings"])
    good = sec.replace("<hp:ctrl><hp:colPr", "<hp:ctrl><hp:colPr", 1)
    assert not any(w.startswith("secpr-ctrl-order") for w in validate_package(out)["warnings"])


# ---------------------------------------------------------------- generation
MD = """---
title: 계획
author: 작성자
header: 머리말 문구
footer: 꼬리말 문구
page_number: footer-right
---
# 계획

본문은 [국립국어원](https://www.korean.go.kr/a?b=1;c)에서 확인한다[^1]. 둘째[^two] 참조.

| 구분 | 내용 |
| --- | --- |
| 링크 | [한컴](https://www.hancom.com) 참조 |

[^1]: 첫째 각주.
[^two]: 둘째 각주 본문.
"""


def test_footnote_definitions_parsed_and_removed():
    assert footnote_definitions(MD) == {"1": "첫째 각주.", "two": "둘째 각주 본문."}
    assert all(b["type"] != "paragraph" or "[^1]:" not in b["text"] for b in parse_markdown(MD))


def test_hyperlink_and_footnote_structure(tmp_path):
    section, _, _ = render_document(MD, template="report", base_dir=tmp_path)
    assert section.count('type="HYPERLINK"') == 2 and section.count("<hp:fieldEnd") == 2
    assert 'Command">https\\:' in section and "\\;c;1;0;0;" in section   # 한컴식 이스케이프
    assert '<hp:run charPrIDRef="11"><hp:t>국립국어원</hp:t></hp:run>' in section
    # 필드 시작은 앞 글자 run 끝에, 필드 끝은 뒤 글자 run 앞에 (한컴 저장 형태)
    assert "<hp:t>본문은 </hp:t><hp:ctrl><hp:fieldBegin" in section
    assert "</hp:fieldEnd></hp:ctrl><hp:t>에서 확인한다</hp:t>" in section.replace("/></hp:ctrl>", "></hp:fieldEnd></hp:ctrl>")
    assert section.count("<hp:footNote ") == 2
    assert '<hp:footNote number="1"' in section and '<hp:footNote number="2"' in section
    assert 'numType="FOOTNOTE"' in section and "[^" not in section
    out = build_from_template(tmp_path / "f.hwpx", template="report", section_xml=section)
    r = check_package(out)
    assert r["ok"] and r["warnings"] == [], r
    text = extract_text(out)
    assert "[각주]  첫째 각주." in text and "본문은 국립국어원에서 확인한다. 둘째 참조." in text


def test_document_decorations_from_front_matter_and_theme():
    d = document_decorations(MD, "base")
    assert d == {"header": "머리말 문구", "footer": "꼬리말 문구", "page_number": ("footer", "right")}
    assert document_decorations("# x", "report")["page_number"] == ("footer", "center")   # 테마 기본값
    assert document_decorations("---\npage_number: none\n---\n# x", "report")["page_number"] is None
    assert document_decorations("# x", "base")["page_number"] is None
    with pytest.raises(ValueError):
        document_decorations("---\npage_number: 위쪽\n---\n# x", "base")


def test_cli_new_applies_header_footer_page_number_and_metadata(tmp_path, capsys):
    md = tmp_path / "d.md"
    md.write_text(MD, encoding="utf-8")
    out = tmp_path / "d.hwpx"
    assert cli.main(["new", str(md), "-o", str(out), "--theme", "gonmun"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    r = check_package(out)
    assert r["ok"] and r["warnings"] == [], r
    text = extract_text(out)
    assert "[머리말] 머리말 문구" in text and "[꼬리말] 꼬리말 문구" in text
    with zipfile.ZipFile(out) as zf:
        sec = zf.read("Contents/section0.xml").decode("utf-8")
        hpf = zf.read("Contents/content.hpf").decode("utf-8")
    assert 'numType="PAGE"' in sec                       # 쪽번호 (꼬리말 안 autoNum)
    assert '<opf:meta name="creator" content="text">작성자</opf:meta>' in hpf
    assert 'name="CreatedDate"' in hpf and 'name="ModifiedDate"' in hpf


def test_header_row_cells_are_marked_for_repeat():
    alloc = owpml.IdAllocator()
    xml = owpml.table([["a", "b"], ["1", "2"]], alloc, style_map=owpml.load_style_map("base"))
    assert xml.count('header="1"') == 2 and xml.count('header="0"') == 2
    chip = owpml.section_chip("Ⅰ", "개요", alloc, owpml.load_style_map("report"))
    assert 'header="1"' not in chip


# ---------------------------------------------------------------- package limits
def test_package_rejects_too_many_entries(tmp_path, monkeypatch):
    from core import package as pkg_mod
    monkeypatch.setattr(pkg_mod, "MAX_ENTRIES", 3)
    src = build_minimal_hwpx(tmp_path / "m.hwpx")
    with pytest.raises(PackageError):
        HwpxPackage.open(src)


def test_package_rejects_oversized_total(tmp_path, monkeypatch):
    from core import package as pkg_mod
    monkeypatch.setattr(pkg_mod, "MAX_TOTAL_BYTES", 10)
    src = build_minimal_hwpx(tmp_path / "m.hwpx")
    with pytest.raises(PackageError):
        HwpxPackage.open(src)


# ---------------------------------------------------------------- render
def _node_ok():
    node = shutil.which("node")
    if not node:
        return False
    try:
        major = int(subprocess.run([node, "--version"], capture_output=True, text=True,
                                   timeout=10).stdout.strip().lstrip("v").split(".")[0])
    except (ValueError, subprocess.SubprocessError, OSError):
        return False
    return major >= 18


@pytest.mark.skipif(not _node_ok(), reason="Node.js 18+ 없음 — render는 rhwp(WASM) 필요")
def test_render_pages_svg(tmp_path):
    from core.render import render_pages
    section, _, _ = render_document("# 제목\n\n본문 문단\n\n| a | b |\n|---|---|\n| 1 | 2 |\n",
                                    template="report", base_dir=tmp_path)
    out = build_from_template(tmp_path / "r.hwpx", template="report", section_xml=section)
    result = render_pages(out, tmp_path / "pages", fmt="svg", pages="1")
    assert result["pages"] >= 1 and len(result["files"]) == 1
    svg = Path(result["files"][0]).read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "</svg>" in svg and len(svg) > 2000


def test_render_rejects_bad_format(tmp_path):
    from core.render import render_pages
    with pytest.raises(PackageError):
        render_pages(build_minimal_hwpx(tmp_path / "m.hwpx"), tmp_path / "o", fmt="pdf")
