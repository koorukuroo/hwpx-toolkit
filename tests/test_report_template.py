import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from core import owpml
from core.markdown import render_to_section
from core.template import build_from_template, TEMPLATES_DIR
from core.guards import check_package
from core.analyze import extract_text, analyze_document

ROOT = Path(__file__).resolve().parent.parent
NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def test_style_maps_exist_and_generator_idempotent():
    for t in ("base", "report"):
        m = json.loads((TEMPLATES_DIR / t / "styles.json").read_text("utf-8"))
        assert "heading" in m and "table" in m
    files = {p: p.read_bytes() for p in (TEMPLATES_DIR).rglob("*") if p.is_file()}
    subprocess.run([sys.executable, str(ROOT / "scripts/dev/gen_templates.py")], check=True)
    after = {p: p.read_bytes() for p in (TEMPLATES_DIR).rglob("*") if p.is_file()}
    assert files == after
    assert not (ROOT / "scripts/dev/gen_base_template.py").exists()


def test_report_header_has_extra_styles():
    root = ET.fromstring((TEMPLATES_DIR / "report/Contents/header.xml").read_bytes())
    chars = root.find(f".//{{{NS_HH}}}charProperties")
    assert chars.get("itemCnt") == "12"     # 공통 배치 (base와 같은 개수)
    c8 = root.find(f".//{{{NS_HH}}}charPr[@id='8']")
    assert c8.get("textColor") == "#FFFFFF"     # 포인트색 위 흰 글자 (칩 번호)
    bf5 = root.find(f".//{{{NS_HH}}}borderFill[@id='5']")
    assert b"1F3864" in ET.tostring(bf5)        # 포인트색 배경
    c1 = root.find(f".//{{{NS_HH}}}charPr[@id='1']")
    assert c1.get("height") == "2200" and c1.get("textColor") == "#1F3864"


def test_report_markdown_uses_section_chip(tmp_path):
    md = "# 보고서\n\n## 1. 개요\n\n본문\n\n- 항목\n"
    xml = render_to_section(md, template="report")
    out = build_from_template(tmp_path / "r.hwpx", template="report", section_xml=xml,
                              title="보고서")
    assert check_package(out)["ok"]
    doc = analyze_document(out)
    # 제목(아래선 1칸 표) + 번호 칩
    assert doc["sections"][0]["tables"] == [{"index": 0, "rows": 1, "cols": 1},
                                             {"index": 1, "rows": 1, "cols": 3}]
    text = extract_text(out)
    assert "Ⅰ |  | 개요" in text and "□ 항목" in text    # 1. → Ⅰ 칩, 보고서 기호 □
    assert 'charPrIDRef="1"' in xml          # H1 = 제목 스타일


def test_base_rendering_uses_rule_table_for_h2(tmp_path):
    md = "# 제목\n\n## 소제목\n\n본문"
    xml = render_to_section(md, template="base")
    assert 'charPrIDRef="1"' in xml                       # 제목 문단 (base 제목은 선 없음)
    assert 'charPrIDRef="2"><hp:t>소제목' in xml           # ## 는 셀 아래선 표
    assert xml.count("<hp:tbl") == 1 and 'borderFillIDRef="6"' in xml


def test_report_table_uses_style_map(tmp_path):
    md = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    xml = render_to_section(md, template="report")
    out = build_from_template(tmp_path / "t.hwpx", template="report", section_xml=xml,
                              title="표")
    assert check_package(out)["ok"]
    doc = analyze_document(out)
    assert doc["sections"][0]["tables"] == [{"index": 0, "rows": 2, "cols": 2}]

    # 커스텀 style_map이 실제로 렌더 결과에 반영되는지 배선 확인
    alloc = owpml.IdAllocator()
    custom_xml = owpml.table(
        [["a", "b"], ["1", "2"]], alloc,
        style_map={"table": {"header_char": "6", "header_border": "5",
                              "body_border": "3", "cell_para": "5"}})
    assert 'borderFillIDRef="5"' in custom_xml
    assert 'charPrIDRef="6"' in custom_xml
