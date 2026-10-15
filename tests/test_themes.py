"""테마 템플릿 — base/gonmun/report/modern 이 같은 스타일 ID 배치를 쓰고, 렌더러가
테마 값(기호·번호 서식·칩·표 선·열 폭·내어쓰기)을 반영하는지."""
import json
import re
import xml.etree.ElementTree as ET

import pytest

from core import owpml
from core.analyze import analyze_document, extract_text
from core.guards import check_package
from core.markdown import render_document, render_to_section
from core.template import TEMPLATES_DIR, build_from_template

THEMES = ("base", "gonmun", "report", "modern")
NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

SAMPLE = """---
title: 계획서
subtitle: 부제목 줄
author: 작성자
date: 2026. 10. 15.
---
# 계획서

## 개요

- 상위 항목
  - 하위 항목
    - 셋째 항목

1. 첫째
   1. 첫째의 첫째
      1. 깊은 항목

## 2. 세부 계획

| 시간 | 내용 | 비고 |
| --- | --- | --- |
| 14:00 | 아주 긴 설명이 들어가는 셀입니다. 두 줄 이상으로 넘어가도록 충분히 깁니다. | |
| 15:00 | 짧은 값 | 실습 |

![그림 설명](없음.png)
"""


@pytest.mark.parametrize("theme", THEMES)
def test_theme_header_layout_is_uniform(theme):
    root = ET.fromstring((TEMPLATES_DIR / theme / "Contents/header.xml").read_bytes())
    counts = {coll: len(root.find(f".//{{{NS_HH}}}{coll}"))
              for coll in ("borderFills", "charProperties", "paraProperties")}
    assert counts == {"borderFills": 11, "charProperties": 12, "paraProperties": 13}
    styles = json.loads((TEMPLATES_DIR / theme / "styles.json").read_text("utf-8"))
    assert styles["theme"] == theme
    assert styles["heading"]["1"] == ["1", "1"] and styles["bold_char"] == "5"
    assert styles["table"]["cell_char"] == "7" and styles["caption"] == ["9", "11"]
    assert len(styles["bullets"]) >= 3 and len(styles["ordered"]) >= 3
    # 목록 1단계는 내어쓰기 (intent < 0, left > 0)
    list1 = root.find(f".//{{{NS_HH}}}paraPr[@id='4']")
    margin = list1.find(f".//{{{NS_HP}}}default/{{{NS_HH}}}margin")
    NS_HC = "http://www.hancom.co.kr/hwpml/2011/core"
    intent = int(margin.find(f"{{{NS_HC}}}intent").get("value"))
    left = int(margin.find(f"{{{NS_HC}}}left").get("value"))
    assert intent < 0 and left == -intent


@pytest.mark.parametrize("theme", THEMES)
def test_every_theme_renders_sample_and_passes_check(theme, tmp_path):
    section, assets, manifest = render_document(SAMPLE, template=theme, base_dir=tmp_path)
    out = build_from_template(tmp_path / f"{theme}.hwpx", template=theme,
                              section_xml=section, title="계획서")
    r = check_package(out)
    assert r["ok"], r["errors"]
    assert r["warnings"] == [], r["warnings"]      # 생성 표는 넘침 경고 없이 높이를 맞춘다
    text = extract_text(out)
    assert "부제목 줄" in text and "작성자 · 2026. 10. 15." in text
    assert "[그림 누락: 없음.png]" in text


def test_theme_bullets_and_ordered_formats():
    text = extract_text_of("- 상위\n  - 하위\n    - 셋째\n\n1. 하나\n   1. 하나의 하나\n      1. 깊은\n",
                           "report")
    assert "□ 상위" in text and "○ 하위" in text and "- 셋째" in text
    assert "1. 하나" in text and "가. 하나의 하나" in text and "1) 깊은" in text
    text = extract_text_of("- 상위\n\n1. 하나\n   2. 둘\n", "modern")
    assert "• 상위" in text and "1. 하나" in text and "2) 둘" in text


def extract_text_of(md, theme):
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        out = build_from_template(Path(d) / "x.hwpx", template=theme,
                                  section_xml=render_to_section(md, template=theme))
        return extract_text(out)


def test_report_section_chip_numbering_and_explicit_numbers(tmp_path):
    md = "# 제목\n\n## 개요\n\n## 3. 추진 계획\n\n## Ⅴ 기대효과\n\n## 제7장 부록\n"
    xml = render_to_section(md, template="report")
    out = build_from_template(tmp_path / "c.hwpx", template="report", section_xml=xml)
    assert check_package(out)["ok"]
    text = extract_text(out)
    assert "Ⅰ |  | 개요" in text          # 번호 없으면 순번
    assert "Ⅲ |  | 추진 계획" in text     # 3. → Ⅲ
    assert "Ⅴ |  | 기대효과" in text      # 로마 숫자는 그대로
    assert "Ⅶ |  | 부록" in text          # 제7장 → Ⅶ
    tables = analyze_document(out)["sections"][0]["tables"]
    assert [t["cols"] for t in tables] == [1, 3, 3, 3, 3]      # 제목 선 표 + 칩 4개
    # 번호 칸: 포인트색 배경(5) + 흰 글자(8); 제목 칸: 아래 굵은 선(8)
    assert 'borderFillIDRef="5"' in xml and 'charPrIDRef="8"' in xml
    assert 'borderFillIDRef="8"' in xml


def test_gonmun_has_no_chip_and_plain_headings():
    xml = render_to_section("# 제목\n\n## 1. 개요\n", template="gonmun")
    assert "<hp:tbl" not in xml and 'paraPrIDRef="2"' in xml


def test_rule_headings_are_single_cell_tables_without_paragraph_borders():
    import xml.etree.ElementTree as ET
    for theme, level, bf in (("base", 2, "6"), ("modern", 1, "7"), ("report", 1, "7")):
        root = ET.fromstring((TEMPLATES_DIR / theme / "Contents/header.xml").read_bytes())
        for pid in ("1", "2"):
            border = root.find(f".//{{{NS_HH}}}paraPr[@id='{pid}']/{{{NS_HH}}}border")
            assert border.get("borderFillIDRef") == "2"        # 문단 테두리 없음
        md = "# 제목\n\n## 소제목\n" if level == 2 else "# 제목\n"
        xml = render_to_section(md, template=theme)
        assert f'borderFillIDRef="{bf}"' in xml and 'cellMargin left="0" right="0"' in xml


def test_table_column_widths_follow_content_and_outer_rules():
    alloc = owpml.IdAllocator()
    style = owpml.load_style_map("report")
    rows = [["구분", "내용", "비고"],
            ["가", "열 폭은 가장 긴 셀의 글자 폭에 비례해서 배분되고, 한 줄에 다 들어가지 않는 "
                   "긴 글은 행 높이를 줄 수만큼 늘린다", ""],
            ["나", "짧다", "실습"]]
    xml = owpml.table(rows, alloc, style_map=style)
    root = ET.fromstring(xml)
    trs = root.findall(f".//{{{NS_HP}}}tr")
    widths = [int(sz.get("width")) for sz in trs[0].iter(f"{{{NS_HP}}}cellSz")]
    assert sum(widths) == 42520 and widths[1] > widths[0] and widths[1] > widths[2]
    assert min(widths) >= 3400
    # 첫 행 위 굵은 선(9), 마지막 행 아래 굵은 선(10), 중간 행은 보통 선(3)
    fills = [[tc.get("borderFillIDRef") for tc in tr.findall(f"{{{NS_HP}}}tc")] for tr in trs]
    assert set(fills[0]) == {"9"} and set(fills[1]) == {"3"} and set(fills[2]) == {"10"}
    # 짧은 값만 있는 열은 가운데(5), 긴 글이 있는 열은 왼쪽(10) 정렬
    paras = [[p.get("paraPrIDRef") for p in tr.iter(f"{{{NS_HP}}}p")] for tr in trs]
    assert paras[1] == ["5", "10", "5"]
    # 긴 셀이 있는 행은 더 높다
    heights = [int(tr.find(f"{{{NS_HP}}}tc/{{{NS_HP}}}cellSz").get("height")) for tr in trs]
    assert heights[1] > heights[2]
    # 셀 여백은 한컴 기본값
    assert '<hp:cellMargin left="510" right="510" top="141" bottom="141"/>' in xml


def test_single_row_header_table_uses_both_thick_rules():
    alloc = owpml.IdAllocator()
    xml = owpml.table([["a", "b"]], alloc, style_map=owpml.load_style_map("gonmun"))
    assert xml.count('borderFillIDRef="11"') == 2


def test_modern_tables_have_no_outer_emphasis():
    alloc = owpml.IdAllocator()
    xml = owpml.table([["a", "b"], ["1", "2"]], alloc, style_map=owpml.load_style_map("modern"))
    assert 'borderFillIDRef="9"' not in xml and 'borderFillIDRef="10"' not in xml


def test_tables_carry_inner_margins_and_glyph_breaking():
    import xml.etree.ElementTree as ET
    alloc = owpml.IdAllocator()
    xml = owpml.table([["a"]], alloc, style_map=owpml.load_style_map("base"))
    assert '<hp:inMargin left="510" right="510" top="141" bottom="141"/>' in xml   # hasMargin=0 → 표 여백 사용
    root = ET.fromstring((TEMPLATES_DIR / "base" / "Contents/header.xml").read_bytes())
    for bs in root.iter(f"{{{NS_HH}}}breakSetting"):
        assert bs.get("breakNonLatinWord") == "BREAK_WORD"


def test_cli_accepts_theme_alias(tmp_path, capsys):
    from scripts import hwpx as cli
    md = tmp_path / "d.md"
    md.write_text("# 제목\n\n## 개요\n\n본문\n", encoding="utf-8")
    out = tmp_path / "d.hwpx"
    assert cli.main(["new", str(md), "-o", str(out), "--theme", "modern"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    with open(out, "rb") as f:
        assert b"256EF4" in __import__("zipfile").ZipFile(f).read("Contents/header.xml")


def test_unknown_theme_is_rejected(tmp_path, capsys):
    from scripts import hwpx as cli
    md = tmp_path / "d.md"
    md.write_text("# 제목\n", encoding="utf-8")
    rc = cli.main(["new", str(md), "-o", str(tmp_path / "d.hwpx"), "--theme", "없음"])
    assert rc == 2 and not json.loads(capsys.readouterr().out)["ok"]


def test_image_alt_uses_caption_style(tmp_path):
    import struct, zlib
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 4 for _ in range(2))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 2, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    (tmp_path / "p.png").write_bytes(png)
    section, _, _ = render_document("![그림 1 설명](p.png)", base_dir=tmp_path)
    assert re.search(r'paraPrIDRef="11"[^>]*><hp:run charPrIDRef="9"><hp:t>그림 1 설명', section)
