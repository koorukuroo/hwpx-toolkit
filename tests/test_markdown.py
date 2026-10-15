from core.markdown import parse_markdown, render_to_section, first_heading
from core.template import build_from_template
from core.guards import validate_package
from core.analyze import extract_text, analyze_document

SAMPLE = """# 사업 계획

개요 문단입니다. **강조**와 `코드` 포함.

## 목표

- 첫 목표
- 둘째 목표

1. 단계 하나
2. 단계 둘

| 항목 | 예산 |
| --- | --- |
| 인건비 | 100 |
| 운영비 | 50 |
"""


def test_parse_blocks():
    blocks = parse_markdown(SAMPLE)
    types = [b["type"] for b in blocks]
    assert types == ["heading", "paragraph", "heading", "bullet",
                     "ordered", "table"]
    assert blocks[0] == {"type": "heading", "level": 1, "text": "사업 계획"}
    assert blocks[1]["text"] == "개요 문단입니다. **강조**와 `코드` 포함."   # 인라인 마커는 렌더 시 run으로
    assert blocks[3]["items"] == ["첫 목표", "둘째 목표"]
    assert blocks[4]["items"] == ["1. 단계 하나", "2. 단계 둘"]
    assert blocks[5]["rows"] == [["항목", "예산"], ["인건비", "100"],
                                 ["운영비", "50"]]


def test_first_heading():
    assert first_heading(SAMPLE) == "사업 계획"
    assert first_heading("본문만") is None


def test_render_roundtrip(tmp_path):
    xml = render_to_section(SAMPLE)
    out = build_from_template(tmp_path / "doc.hwpx", section_xml=xml,
                              title=first_heading(SAMPLE))
    r = validate_package(out)
    assert r["ok"], r["errors"]
    text = extract_text(out)
    for expected in ("사업 계획", "개요 문단입니다", "• 첫 목표",
                     "1. 단계 하나", "인건비 | 100"):
        assert expected in text
    doc = analyze_document(out)
    # base 테마의 ## 는 아래선 1칸 표, 그 뒤 마크다운 표
    assert doc["sections"][0]["tables"] == [{"index": 0, "rows": 1, "cols": 1},
                                             {"index": 1, "rows": 3, "cols": 2}]


def test_multiline_paragraph_joined():
    blocks = parse_markdown("한 줄\n둘째 줄\n\n새 문단")
    assert blocks[0]["text"] == "한 줄 둘째 줄"
    assert blocks[1]["text"] == "새 문단"


def test_table_short_row_padded(tmp_path):
    md = """| 항목 | 예산 |
| --- | --- |
| 인건비 | 100 |
| 운영비 |
"""
    blocks = parse_markdown(md)
    assert blocks[0]["rows"] == [["항목", "예산"], ["인건비", "100"],
                                 ["운영비", ""]]
    xml = render_to_section(md)
    out = build_from_template(tmp_path / "short.hwpx", section_xml=xml)
    r = validate_package(out)
    assert r["ok"], r["errors"]


def test_table_long_row_truncated(tmp_path):
    md = """| 항목 | 예산 |
| --- | --- |
| 인건비 | 100 | 초과 |
| 운영비 | 50 |
"""
    blocks = parse_markdown(md)
    assert blocks[0]["rows"] == [["항목", "예산"], ["인건비", "100"],
                                 ["운영비", "50"]]
    xml = render_to_section(md)
    out = build_from_template(tmp_path / "long.hwpx", section_xml=xml)
    r = validate_package(out)
    assert r["ok"], r["errors"]
