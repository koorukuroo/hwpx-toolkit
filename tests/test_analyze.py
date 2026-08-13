from core.analyze import analyze_document, extract_slots
from tests.fixture import build_minimal_hwpx


def test_analyze_reports_page_and_tables(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx", with_table=True)
    r = analyze_document(p)
    assert r["page"]["width"] == 59528
    assert r["page"]["margins"]["left"] == 8504
    assert r["styles"]["charPrCount"] == 1
    sec = r["sections"][0]
    assert sec["tables"] == [{"index": 0, "rows": 2, "cols": 2}]


def test_slots_paragraphs_and_cells(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx",
                           body_texts=["본문 하나"], with_table=True)
    slots = extract_slots(p)["slots"]
    keys = [s["key"] for s in slots]
    assert "p:1" in keys                 # p:0은 secPr 문단(텍스트 없음)이라 제외됨
    assert "cell:0:0:0" in keys and "cell:0:1:1" in keys
    cell = next(s for s in slots if s["key"] == "cell:0:1:1")
    assert cell["text"] == "셀11"
    # 표를 품은 컨테이너 문단은 p: 슬롯에 없어야 함
    para_texts = [s["text"] for s in slots if s["type"] == "paragraph"]
    assert all("셀" not in t for t in para_texts)
