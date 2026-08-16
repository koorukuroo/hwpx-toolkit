import json
from core.guards import guard_against_reference
from core.edit import edit_file
from tests.fixture import build_minimal_hwpx


def _doc(tmp_path, name, texts):
    return build_minimal_hwpx(tmp_path / name, body_texts=texts)


def test_default_placeholders_detected(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["기관명 자리"])
    out = _doc(tmp_path, "out.hwpx", ["기관명 ○○○○ 확인", "담당 {{name}}", "TODO 확인"])
    r = guard_against_reference(out, ref)
    found = " ".join(e for e in r["errors"] if e.startswith("placeholder-found"))
    assert "○" in found and "{{name}}" in found and "TODO" in found
    assert r["ok"] is False


def test_default_placeholders_can_be_disabled(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["기관명 자리"])
    out = _doc(tmp_path, "out.hwpx", ["담당 {{name}}"])
    r = guard_against_reference(out, ref, no_default_placeholders=True)
    assert not [e for e in r["errors"] if e.startswith("placeholder-found")]


def test_extra_placeholder_regex(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["본문"])
    out = _doc(tmp_path, "out.hwpx", ["금액 XXX원"])
    r = guard_against_reference(out, ref, rules={"placeholder_regex": [r"X{3,}"]})
    assert any(e.startswith("placeholder-found") for e in r["errors"])


def test_require_regex(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["본문"])
    out = _doc(tmp_path, "out.hwpx", ["2026. 8. 16. 시행"])
    ok = guard_against_reference(out, ref,
                                 rules={"require_regex": [r"\d{4}\. \d{1,2}\. \d{1,2}\."]})
    assert not [e for e in ok["errors"] if e.startswith("require-regex-missing")]
    bad = guard_against_reference(out, ref, rules={"require_regex": [r"별지 제\d+호"]})
    assert any(e.startswith("require-regex-missing") for e in bad["errors"])


def test_unchanged_ratio_flags_lazy_rewrite(tmp_path):
    long_a = "이것은 충분히 긴 첫 번째 문장입니다"
    long_b = "이것은 충분히 긴 두 번째 문장입니다"
    long_c = "이것은 충분히 긴 세 번째 문장입니다"
    ref = _doc(tmp_path, "ref.hwpx", [long_a, long_b, long_c])
    lazy = tmp_path / "lazy.hwpx"
    edit_file(ref, lazy, lambda ed: ed.replace_text({long_a: "완전히 새로 쓴 첫 문장입니다"}))

    r = guard_against_reference(lazy, ref, max_unchanged_ratio=0.35)
    assert r["unchanged_ratio"] > 0.35
    assert any(e.startswith("unchanged-too-high") for e in r["errors"])

    lenient = guard_against_reference(lazy, ref, max_unchanged_ratio=0.9)
    assert not [e for e in lenient["errors"] if e.startswith("unchanged-too-high")]


def test_unchanged_ratio_absent_when_not_requested(tmp_path):
    ref = _doc(tmp_path, "ref.hwpx", ["본문"])
    r = guard_against_reference(ref, ref)
    assert r["unchanged_ratio"] is None


def test_placeholder_inherited_from_reference_is_warning_not_error(tmp_path):
    # 레퍼런스에도 있는 익명화 표기(홍○○)는 그대로 옮겨졌을 뿐 새로 만든 게
    # 아니므로 오류가 아니라 경고여야 한다.
    ref = _doc(tmp_path, "ref.hwpx", ["담당자 홍○○ (○○부 소속)"])
    out = _doc(tmp_path, "out.hwpx", ["담당자 홍○○ (○○부 소속) 확인함"])
    r = guard_against_reference(out, ref)
    assert r["ok"] is True, r["errors"]
    assert not [e for e in r["errors"] if e.startswith("placeholder-found")]
    assert any(w.startswith("placeholder-inherited") for w in r["warnings"])


def test_placeholder_still_errors_when_reference_is_clean(tmp_path):
    # 레퍼런스에 없던 placeholder를 출력이 새로 만들면 여전히 오류.
    ref = _doc(tmp_path, "ref.hwpx", ["기관명 자리"])
    out = _doc(tmp_path, "out.hwpx", ["담당 {{name}}"])
    r = guard_against_reference(out, ref)
    assert any(e.startswith("placeholder-found") for e in r["errors"])
    assert r["ok"] is False


def test_placeholder_errors_when_output_has_more_than_reference(tmp_path):
    # 레퍼런스에 ○○가 1건 있어도, 출력이 2건으로 늘리면 오류.
    ref = _doc(tmp_path, "ref.hwpx", ["담당자 홍○○"])
    out = _doc(tmp_path, "out.hwpx", ["담당자 홍○○ 및 부담당자 김○○"])
    r = guard_against_reference(out, ref)
    assert any(e.startswith("placeholder-found") for e in r["errors"])
    assert r["ok"] is False


def test_cli_guard_new_flags(tmp_path, capsys):
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    ref = _doc(tmp_path, "ref.hwpx", ["담당 {{name}}"])
    rc = hwpx_cli.main(["guard", str(ref), "--reference", str(ref),
                        "--no-default-placeholders"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
