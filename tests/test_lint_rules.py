from core.lint import lint_text


def _rules(text):
    return {f["rule"] for f in lint_text(text)["findings"]}


def _find(text, rule):
    return next(f for f in lint_text(text)["findings"] if f["rule"] == rule)


def test_date_padding():
    assert "date-padding" in _rules("접수 2026. 01. 05. 마감")
    assert _find("접수 2026. 01. 05. 마감", "date-padding")["suggest"] == "2026. 1. 5."
    assert "date-padding" not in _rules("접수 2026. 1. 5. 마감")


def test_year_2digit():
    assert "year-2digit" in _rules("26. 8. 16. 개최")
    assert "year-2digit" not in _rules("2026. 8. 16. 개최")
    assert "year-2digit" not in _rules("14:30 개최")


def test_amount_abbrev():
    assert "amount-abbrev" in _rules("예산 1,500천원 지원")
    assert "amount-abbrev" in _rules("총 30억원 규모")
    assert "amount-abbrev" not in _rules("금1,500,000원(금일백오십만원)")


def test_attach_colon():
    assert "attach-colon" in _rules("붙임: 사업계획서 1부.  끝.")
    assert "attach-colon" in _rules("붙임 : 사업계획서 1부.  끝.")
    assert "attach-colon" not in _rules("붙임  사업계획서 1부.  끝.")


def test_range_redundant():
    assert "range-redundant" in _rules("2026. 8. 1.~2026. 8. 16.까지 접수")
    assert "range-redundant" not in _rules("2026. 8. 1.~2026. 8. 16. 접수")
    assert "range-redundant" not in _rules("2026. 8. 16.까지 접수")


def test_range_redundant_not_mere_cooccurrence():
    assert "range-redundant" not in _rules(
        "지원등급은 A~C 등급으로 나뉘며, 신청은 3월 말까지 받는다.")
    assert "range-redundant" in _rules("2026. 8. 1.~2026. 8. 16.까지 접수")
    assert "range-redundant" not in _rules("8. 1.~8. 16. 접수")


def test_range_redundant_not_mere_cooccurrence_no_comma():
    # 쉼표가 없어도 물결표와 '까지' 사이에 문장(한글 음절이 여러 개인 프로즈)이
    # 이어지면 오탐이 되어서는 안 된다 — 거리(창 길이)가 아니라 사이 구간의
    # 한글 밀도로 판단한다.
    assert "range-redundant" not in _rules(
        "지원등급은 A~C 등급으로 나뉘며 신청은 3월 말까지 받는다.")


def test_range_redundant_real_document_date_time_range():
    # 실물 문서에서 검증된 진짜 중복 표기: 물결표와 '까지' 사이가
    # 날짜/시간(한글 음절 1개 이하)이면 창이 20자에 가깝게 넓어도 잡아야 한다.
    assert "range-redundant" in _rules(
        "□ 접수기간 : 2023.4.17.(월)~2023.5.2.(화) 18:00까지")


def test_foreign_order():
    assert "foreign-order" in _rules("AI(인공지능) 기반 서비스")
    assert _find("AI(인공지능) 기반", "foreign-order")["suggest"] == "인공지능(AI)"
    assert "foreign-order" not in _rules("인공지능(AI) 기반 서비스")
    assert "foreign-order" not in _rules("http://a.kr/AI(x) 참고")


def test_existing_rules_unaffected():
    assert "date-format" in _rules("회의는 2026.8.16 개최")
    assert "colon-spacing" in _rules("성명 : 홍길동")
    assert "end-mark" in _rules("본문입니다")
