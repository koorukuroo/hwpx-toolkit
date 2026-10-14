"""lint 추가 규칙, guard 구조 동일성, 표 쪽 넘침 경고."""
import json

from core.edit import edit_file
from core.guards import check_package, guard_against_reference, document_structure
from core.lint import lint_text
from tests.fixture import build_form_hwpx, build_minimal_hwpx, build_from_section, _table


def _rules(text, **kw):
    return {f["rule"] for f in lint_text(text, **kw)["findings"]}


def _one(text, rule, **kw):
    return next(f for f in lint_text(text, **kw)["findings"] if f["rule"] == rule)


def test_date_end_dot():
    f = _one("회의는 2026. 1. 6 개최", "date-end-dot")
    assert f["suggest"] == "2026. 1. 6."
    assert "date-end-dot" not in _rules("회의는 2026. 1. 6. 개최")
    assert "date-end-dot" not in _rules("2026. 1. 6.(화) 14:00")


def test_time_rules_24h_and_colon_space():
    assert _one("마감 24:00", "time-24h")["suggest"] == "00:00"
    assert _one("13 : 20 시작", "time-colon-space")["suggest"] == "13:20"
    assert "time-colon-space" not in _rules("13:20 시작")
    assert _one("24시 마감", "time-format")["suggest"] == "00:00"


def test_money_geum_space():
    assert _one("계약금 금 113,560원(금십일만삼천오백육십원)", "money-geum-space")["suggest"] == "금113,560원"
    assert "money-geum-space" not in _rules("금113,560원(금십일만삼천오백육십원)")


def test_single_attachment_numbered():
    assert "attachment-single-numbered" in _rules("본문.\n\n붙임  1. 사업계획서 1부.  끝.")
    assert "attachment-single-numbered" not in _rules("붙임  1. 사업계획서 1부.\n      2. 예산서 1부.  끝.")
    assert "attachment-single-numbered" not in _rules("붙임  사업계획서 1부.  끝.")


def test_lone_sub_item():
    assert "item-lone" in _rules("1. 개요\n  가. 목적\n2. 추진\n  가. 일정\n  나. 예산")
    assert "item-lone" not in _rules("1. 개요\n  가. 목적\n  나. 범위")
    assert "item-lone" not in _rules("1. 개요")       # 최상위 하나는 허용


def test_gonmun_structure_gate():
    text = "수신  수신자 참조\n제목  안내\n1. 본문입니다.  끝.\n\n울산광역시장\n시행 총무과-123 (2026. 1. 6.)\n공개"
    assert not {r for r in _rules(text, doc_type="gonmun") if r.startswith("gonmun-")}
    missing = _rules("제목 안내\n본문.  끝.", doc_type="gonmun")
    assert {"gonmun-missing-susin", "gonmun-missing-sihaeng", "gonmun-missing-disclosure",
            "gonmun-missing-balsin"} <= missing
    assert "gonmun-missing-susin" not in _rules("제목 안내\n본문.  끝.")


def test_bogo_style():
    assert "bogo-sentence-ending" in _rules("□ 추진 배경\n ○ 본 사업은 지역 경제 활성화를 위해 추진합니다.", doc_type="bogo")
    assert "bogo-sentence-ending" not in _rules("□ 추진 배경\n ○ 지역 경제 활성화를 위한 사업 추진", doc_type="bogo")
    assert "bogo-sentence-ending" not in _rules("본 사업은 지역 경제 활성화를 위해 추진합니다.")


def test_guard_reports_structure_changes_as_warning_then_error(tmp_path):
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    out = tmp_path / "out.hwpx"
    edit_file(ref, out, lambda ed: ed.add_row(0, ["추가", "값"]))
    r = guard_against_reference(out, ref)
    assert r["ok"] and any(w.startswith("structure-tables") for w in r["warnings"])
    assert r["structure"][0]["tables"] == [["3", "2"]]
    r2 = guard_against_reference(out, ref, strict_structure=True)
    assert not r2["ok"] and any(e.startswith("structure-tables") for e in r2["errors"])
    same = tmp_path / "same.hwpx"
    edit_file(ref, same, lambda ed: ed.replace_text({"안녕하세요": "반갑습니다"}))
    r3 = guard_against_reference(same, ref, strict_structure=True)
    assert r3["ok"] and not any(w.startswith("structure-") for w in r3["warnings"])


def test_guard_flags_lost_pictures_and_paragraphs(tmp_path):
    ref = build_minimal_hwpx(tmp_path / "ref.hwpx")
    out = tmp_path / "out.hwpx"
    edit_file(ref, out, lambda ed: ed.add_para_after("안녕하세요", "추가 문단"))
    r = guard_against_reference(out, ref)
    assert any(w.startswith("structure-paragraphs") for w in r["warnings"])


def test_table_taller_than_page_warning(tmp_path):
    rows = [["r", "v"]] * 40                        # 40행 × 2400 = 96000 > A4 본문 높이
    nosplit = _table(rows=rows).replace('pageBreak="CELL"', 'pageBreak="NONE"')
    src = build_from_section(tmp_path / "t.hwpx", nosplit)
    r = check_package(src)
    assert any(w.startswith("table-taller-than-page") for w in r["warnings"]), r["warnings"]
    # 한컴 실물처럼 pageBreak="CELL"(기본)이면 여러 쪽에 걸쳐 나뉘므로 경고 없음
    cell = build_from_section(tmp_path / "c.hwpx", _table(rows=rows))
    assert not any(w.startswith("table-taller-than-page") for w in check_package(cell)["warnings"])
    # 행 단위 나눔(TABLE)은 한 행이 본문보다 클 때만
    tall_row = _table(rows=[["r", "v"]]).replace('pageBreak="CELL"', 'pageBreak="TABLE"') \
        .replace('height="2400"', 'height="80000"')
    tr = build_from_section(tmp_path / "r.hwpx", tall_row)
    assert any(w.startswith("table-taller-than-page") for w in check_package(tr)["warnings"])


def test_cli_guard_strict_and_lint_doc_type(tmp_path, capsys):
    from scripts import hwpx as cli
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    out = tmp_path / "out.hwpx"
    edit_file(ref, out, lambda ed: ed.add_row(0, ["추가", "값"]))
    code = cli.main(["guard", str(out), "--reference", str(ref), "--strict-structure"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2 and not payload["ok"]
    t = tmp_path / "g.txt"
    t.write_text("제목 안내\n본문.  끝.", encoding="utf-8")
    code = cli.main(["lint", str(t), "--doc-type", "gonmun"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0 and any(f["rule"] == "gonmun-missing-susin" for f in payload["findings"])
