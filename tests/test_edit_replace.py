import json
import zipfile
import pytest
from core.package import HwpxPackage
from core.edit import SectionEditor, edit_file, EditError
from core.guards import validate_package
from core.analyze import extract_text
from tests.fixture import build_form_hwpx, build_minimal_hwpx


def test_replace_across_split_runs(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    report = edit_file(src, dst,
                       lambda ed: ed.replace_text({"안녕하세요": "반갑습니다"}))
    assert report["replaced"]["안녕하세요"] == 1
    assert report["not_found"] == []
    text = extract_text(dst)
    assert "반갑습니다" in text and "안녕하세요" not in text
    assert validate_package(dst)["ok"]


def test_replace_preserves_untouched_entries_bytes(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.replace_text({"성명": "이름"}))
    with zipfile.ZipFile(src) as za, zipfile.ZipFile(dst) as zb:
        for name in za.namelist():
            if name == "Contents/section0.xml":
                continue
            assert za.read(name) == zb.read(name), name


def test_modified_para_linesegarray_removed_others_kept(tmp_path):
    import xml.etree.ElementTree as ET
    NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    edit_file(src, dst, lambda ed: ed.replace_text({"안녕하세요": "수정됨"}))
    root = ET.fromstring(HwpxPackage.open(dst).read("Contents/section0.xml"))
    kept = removed_ok = False
    for p in root.iter(f"{{{NS_HP}}}p"):
        text = "".join(t.text or "" for run in p.findall(f"{{{NS_HP}}}run")
                       for t in run.findall(f"{{{NS_HP}}}t"))
        seg = p.find(f"{{{NS_HP}}}linesegarray")
        if "수정됨" in text:
            removed_ok = seg is None            # 수정 문단: 캐시 제거
        if "감사합니다" in text:
            kept = seg is not None              # 비수정 문단: 캐시 보존
    assert removed_ok and kept


def test_replace_not_found_reported(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    report = edit_file(src, dst, lambda ed: ed.replace_text({"없는문구": "x"}))
    assert report["not_found"] == ["없는문구"]


def test_replace_empty_old_raises(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx", lambda ed: ed.replace_text({"": "x"}))


def test_replace_multiple_occurrences_and_self_containing(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx",
                             body_texts=["가나다 가나다", "가나다"])
    dst = tmp_path / "out.hwpx"
    report = edit_file(src, dst,
                       lambda ed: ed.replace_text({"가나다": "가나다라"}))
    assert report["replaced"]["가나다"] == 3
    assert extract_text(dst).count("가나다라") == 3


def test_cli_replace(tmp_path, capsys):
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    mp = tmp_path / "map.json"
    mp.write_text(json.dumps({"연락처": "전화번호"}), encoding="utf-8")
    rc = hwpx_cli.main(["replace", str(src), str(dst), "--map", str(mp)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    assert payload["report"]["replaced"]["연락처"] == 1
