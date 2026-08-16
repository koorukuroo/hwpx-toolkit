from core.capacity import estimate_chars, cell_report, for_cell, OVER_MARGIN
from core.analyze import fill_targets
from core.guards import check_package
from core.edit import edit_file
from tests.fixture import build_form_hwpx, build_minimal_hwpx

M141 = {"left": 141, "right": 141, "top": 141, "bottom": 141}


def test_estimate_basic_geometry():
    # 폭 21260, 높이 2400, 여백 141 사방, 10pt(1000), 줄간격 160%
    # 가용폭 20978 // 1000 = 20자/줄, 가용높이 2118 // 1600 = 1줄 → 20
    assert estimate_chars(21260, 2400, M141, 1000, 160) == 20


def test_estimate_multiline_and_guards():
    # 높이를 3배로 → 줄 수 증가
    assert estimate_chars(21260, 7200, M141, 1000, 160) == 20 * 4
    # 아주 좁아도 최소 1자 1줄
    assert estimate_chars(300, 300, M141, 1000, 160) == 1
    # 폰트 크기 불명 → 추정 불가
    assert estimate_chars(21260, 2400, M141, 0, 160) == 0


def test_cell_report_on_form_fixture(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    cells = cell_report(p)["cells"]
    assert len(cells) == 4                       # 2×2 표
    first = next(c for c in cells if (c["row"], c["col"]) == (0, 0))
    assert first["capacity"] == 20
    assert first["used"] == 2                    # "성명"
    assert first["over"] is False
    assert first["table"] == 0


def test_for_cell_lookup(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    assert for_cell(p, 0, 0, 1) == 20
    assert for_cell(p, 5, 0, 0) is None


def test_fill_targets_carry_capacity(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    labels = [t for t in fill_targets(p)["targets"] if t["kind"] == "label-cell"]
    assert labels and all(t["capacity"] == 20 for t in labels)


def test_overflow_detected_and_reported_as_warning(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "over.hwpx"
    long_text = "가" * 60                        # 추정 20자 셀에 60자
    edit_file(src, dst, lambda ed: ed.set_cell_text(0, 0, 1, long_text))

    cells = cell_report(dst)["cells"]
    target = next(c for c in cells if (c["row"], c["col"]) == (0, 1))
    assert target["used"] == 60 and target["over"] is True

    r = check_package(dst)
    assert r["ok"] is True                       # 경고이지 오류가 아님
    assert any(w.startswith("cell-overflow-risk") for w in r["warnings"])


def test_no_false_overflow_on_clean_fixtures(tmp_path):
    for p in (build_form_hwpx(tmp_path / "f.hwpx"),
              build_minimal_hwpx(tmp_path / "m.hwpx", with_table=True)):
        r = check_package(p)
        assert not [w for w in r["warnings"] if w.startswith("cell-overflow-risk")]


def test_margin_constant_is_lenient():
    assert OVER_MARGIN >= 1.1
