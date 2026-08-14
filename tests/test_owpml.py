import xml.etree.ElementTree as ET
import pytest
from core import owpml
from core.guards import validate_package
from core.template import build_from_template
from core.analyze import extract_text, analyze_document

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _build_doc(tmp_path, body_parts):
    first, sec_open = owpml.load_skeleton()
    xml = owpml.sec_document(first, body_parts, sec_open)
    ET.fromstring(xml)  # well-formed 확인
    return build_from_template(tmp_path / "doc.hwpx", section_xml=xml)


def test_escape_and_unique_ids(tmp_path):
    alloc = owpml.IdAllocator()
    p1 = owpml.text_para("a<b>&\"c", alloc)
    p2 = owpml.text_para("둘", alloc)
    assert "a&lt;b&gt;&amp;" in p1
    id1 = ET.fromstring(p1).get("id")
    id2 = ET.fromstring(p2).get("id")
    assert id1 != id2


def test_full_document_roundtrip(tmp_path):
    alloc = owpml.IdAllocator()
    parts = [
        owpml.heading_para(1, "문서 제목", alloc),
        owpml.text_para("첫 본문 문단", alloc),
        owpml.heading_para(2, "섹션 하나", alloc),
        owpml.bullet_para("항목 하나", alloc),
        owpml.bullet_para("항목 둘", alloc),
        owpml.empty_line(alloc),
        owpml.table([["이름", "값"], ["가", "1"], ["나", "2"]], alloc),
    ]
    out = _build_doc(tmp_path, parts)
    r = validate_package(out)
    assert r["ok"], r["errors"]
    text = extract_text(out)
    for expected in ("문서 제목", "첫 본문 문단", "• 항목 하나", "이름 | 값", "나 | 2"):
        assert expected in text
    doc = analyze_document(out)
    assert doc["sections"][0]["tables"] == [{"index": 0, "rows": 3, "cols": 2}]


def test_heading_style_mapping():
    alloc = owpml.IdAllocator()
    h1 = owpml.heading_para(1, "제목", alloc)
    h4 = owpml.heading_para(4, "소제목", alloc)
    assert 'paraPrIDRef="1"' in h1 and 'charPrIDRef="1"' in h1
    assert 'paraPrIDRef="3"' in h4 and 'charPrIDRef="3"' in h4


def test_page_break_flag():
    alloc = owpml.IdAllocator()
    p = owpml.text_para("새 쪽", alloc, page_break=True)
    assert 'pageBreak="1"' in p


def test_table_column_widths_sum_to_total():
    alloc = owpml.IdAllocator()
    t = owpml.table([["a", "b", "c"]], alloc, header=False)
    root = ET.fromstring(t)
    widths = [int(sz.get("width"))
              for sz in root.iter(f"{{{NS_HP}}}cellSz")]
    assert sum(widths) == 42520
    assert len(set(widths)) <= 2  # 균등 + 마지막 열 보정


def test_table_rejects_ragged_rows():
    alloc = owpml.IdAllocator()
    with pytest.raises(ValueError):
        owpml.table([["a", "b"], ["c"]], alloc)
    with pytest.raises(ValueError):
        owpml.table([], alloc)
