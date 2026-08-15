import json
import pytest
from core.package import HwpxPackage
from core.guards import check_package, guard_against_reference
from core.edit import edit_file
from tests.fixture import build_form_hwpx, build_minimal_hwpx


def test_check_passes_clean_document(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    r = check_package(p)
    assert r["ok"], r["errors"]
    assert r["signals"] == {"char_border_bug": False,
                            "vertical_misconvert": False}


def test_check_detects_char_border_bug(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    bad = tmp_path / "bad.hwpx"
    pkg = HwpxPackage.open(src)
    header = pkg.read_text("Contents/header.xml")
    # 유일한 charPr(id 0)가 실선 borderFill을 참조하도록 조작
    header = header.replace(
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>',
        '<hh:leftBorder type="SOLID" width="0.1 mm" color="#000000"/>')
    pkg.write_replaced(bad, {"Contents/header.xml": header.encode("utf-8")})
    r = check_package(bad)
    assert r["signals"]["char_border_bug"] is True
    assert not r["ok"]
    assert any(e.startswith("char-border-bug") for e in r["errors"])


def test_check_detects_vertical_misconvert(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    bad = tmp_path / "bad.hwpx"
    pkg = HwpxPackage.open(src)
    sec = pkg.read_text("Contents/section0.xml").replace(
        'textDirection="HORIZONTAL"', 'textDirection="VERTICAL"')
    pkg.write_replaced(bad, {"Contents/section0.xml": sec.encode("utf-8")})
    r = check_package(bad)
    assert r["signals"]["vertical_misconvert"] is True
    assert not r["ok"]


def test_guard_clean_edit_passes(tmp_path):
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    out = tmp_path / "out.hwpx"
    edit_file(ref, out, lambda ed: ed.replace_text({"안녕하세요": "반갑습니다"}))
    r = guard_against_reference(out, ref, rules={"require": ["반갑습니다"],
                                                 "forbid": ["안녕하세요"]})
    assert r["ok"], r["errors"]


def test_guard_detects_non_section_change_and_rules(tmp_path):
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    bad = tmp_path / "bad.hwpx"
    pkg = HwpxPackage.open(ref)
    header = pkg.read_text("Contents/header.xml").replace('height="1000"',
                                                          'height="1100"', 1)
    pkg.write_replaced(bad, {"Contents/header.xml": header.encode("utf-8")})
    r = guard_against_reference(bad, ref)
    assert any(e.startswith("entry-changed: Contents/header.xml")
               for e in r["errors"])

    out2 = tmp_path / "out2.hwpx"
    edit_file(ref, out2, lambda ed: ed.replace_text({}))
    r2 = guard_against_reference(out2, ref, rules={"forbid": ["안녕하세요"],
                                                   "require": ["없는문구"]})
    assert any(e.startswith("forbid-found") for e in r2["errors"])
    assert any(e.startswith("require-missing") for e in r2["errors"])


def test_guard_growth(tmp_path):
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    out = tmp_path / "out.hwpx"
    edit_file(ref, out, lambda ed: ed.replace_text(
        {"안녕하세요": "안녕하세요" * 30}))
    r = guard_against_reference(out, ref, max_growth=1.5)
    assert not r["ok"]
    assert any(e.startswith("growth-exceeded") for e in r["errors"])
    r2 = guard_against_reference(out, ref)
    assert any(w.startswith("growth-warning") for w in r2["warnings"])


def test_cli_check_and_guard(tmp_path, capsys):
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    ref = build_form_hwpx(tmp_path / "ref.hwpx")
    rc = hwpx_cli.main(["check", str(ref)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True

    out = tmp_path / "out.hwpx"
    edit_file(ref, out, lambda ed: ed.replace_text({"성명": "이름"}))
    rc = hwpx_cli.main(["guard", str(out), "--reference", str(ref)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
