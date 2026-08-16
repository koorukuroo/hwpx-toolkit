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
    assert chars.get("itemCnt") == "7"
    c6 = root.find(f".//{{{NS_HH}}}charPr[@id='6']")
    assert c6.get("textColor") == "#FFFFFF"
    bf5 = root.find(f".//{{{NS_HH}}}borderFill[@id='5']")
    assert b"1F3864" in ET.tostring(bf5)


def test_report_markdown_uses_section_bar(tmp_path):
    md = "# 보고서\n\n## 1. 개요\n\n본문\n\n- 항목\n"
    xml = render_to_section(md, template="report")
    out = build_from_template(tmp_path / "r.hwpx", template="report", section_xml=xml,
                              title="보고서")
    assert check_package(out)["ok"]
    doc = analyze_document(out)
    assert doc["sections"][0]["tables"] == [{"index": 0, "rows": 1, "cols": 1}]  # 섹션 바
    text = extract_text(out)
    assert "1. 개요" in text and "• 항목" in text
    assert 'charPrIDRef="5"' in xml          # H1 = report 제목 스타일


def test_base_rendering_unchanged(tmp_path):
    md = "# 제목\n\n## 소제목\n\n본문"
    xml = render_to_section(md, template="base")
    assert 'charPrIDRef="1"' in xml and 'paraPrIDRef="2"' in xml
    assert "<hp:tbl" not in xml
