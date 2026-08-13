"""텍스트 추출 테스트."""
from core.analyze import extract_text
from tests.fixture import build_minimal_hwpx


def test_extract_plain_text(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx",
                           body_texts=["첫 문단", "둘째 문단"])
    out = extract_text(p)
    assert "첫 문단" in out and "둘째 문단" in out
    assert out.index("첫 문단") < out.index("둘째 문단")


def test_extract_includes_table_cells(tmp_path):
    p = build_minimal_hwpx(tmp_path / "t.hwpx", with_table=True)
    out = extract_text(p)
    assert "셀00" in out and "셀11" in out


def test_extract_markdown_table(tmp_path):
    p = build_minimal_hwpx(tmp_path / "t.hwpx", with_table=True)
    md = extract_text(p, fmt="markdown")
    assert "| 셀00 | 셀01 |" in md
    assert "| --- | --- |" in md
