from core.lint import lint_text, lint_file
from tests.fixture import build_minimal_hwpx


def _rules(text):
    return {f["rule"] for f in lint_text(text)["findings"]}


def test_date_rules():
    assert "date-format" in _rules("회의는 2026.8.16 개최")
    assert "date-format" in _rules("2026-08-16 제출")
    assert "date-format" in _rules("2026년 8월 16일까지")
    assert "date-format" not in _rules("2026. 8. 16. 개최")


def test_time_rules():
    assert "time-format" in _rules("오후 2시 30분 시작")
    assert "time-format" in _rules("오전 9시 개회")
    assert "time-format" not in _rules("14:30 시작")
    f = next(x for x in lint_text("오후 2시 30분")["findings"] if x["rule"] == "time-format")
    assert f["suggest"] == "14:30"


def test_amount_rule():
    assert "amount-hangul" in _rules("예산 1,500,000원 지원")
    assert "amount-hangul" not in _rules("금1,500,000원(금일백오십만원)")


def test_attachment_and_end_mark():
    ok = "붙임  1. 사업계획서 1부.\n      2. 예산서 1부.  끝."
    assert not ({"attachment-format", "end-mark"} & _rules(ok))
    assert "attachment-format" in _rules("붙임  1. 사업계획서\n  끝.")
    assert "end-mark" in _rules("본문입니다.\n붙임  1. 계획서 1부.")
    assert "end-mark" in _rules("본문입니다.끝.")       # 띄어쓰기 없음


def test_item_hierarchy_and_colon():
    assert "item-hierarchy" in _rules("1. 개요\n1) 세부")     # 가. 건너뜀
    assert "item-hierarchy" not in _rules("1. 개요\n가. 세부\n1) 상세")
    assert "colon-spacing" in _rules("성명 : 홍길동")
    assert "colon-spacing" in _rules("성명:홍길동")
    assert "colon-spacing" not in _rules("성명: 홍길동")
    assert "colon-spacing" not in _rules("14:30 시작")


def test_lint_file_hwpx(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx", body_texts=["회의 2026.8.16 개최"])
    r = lint_file(p)
    assert r["count"] >= 1 and r["findings"][0]["rule"] == "date-format"
