import os
import shutil
import zipfile
import pytest
from pathlib import Path
from core.errors import PackageError
from core import convert

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "labor_template.hwp"


def _section0(path):
    with zipfile.ZipFile(path) as zf:
        return zf.read("Contents/section0.xml").decode("utf-8")


# ---------------------------------------------------------------- 동봉 파일

def test_vendor_files_and_notice_present():
    for rel in ("vendor/rhwp/rhwp.js", "vendor/rhwp/rhwp_bg.wasm",
                "vendor/rhwp/LICENSE", "scripts/rhwp_convert.mjs",
                "vendor/pyhwpx_hwp5/__init__.py", "vendor/pyhwpx_hwp5/_etree.py",
                "vendor/pyhwpx_hwp5/LICENSE", "vendor/pyhwpx_hwp5/NOTICE",
                "THIRD_PARTY_NOTICES.md", "tests/fixtures/labor_template.hwp"):
        assert (ROOT / rel).is_file(), rel
    assert "MIT" in (ROOT / "vendor/rhwp/LICENSE").read_text(encoding="utf-8")
    assert "Apache" in (ROOT / "vendor/pyhwpx_hwp5/LICENSE").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "@rhwp/core" in notices and "python-hwpx" in notices


def test_vendored_engine_has_no_lxml_dependency():
    import re
    for py in (ROOT / "vendor" / "pyhwpx_hwp5").glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+lxml\b", text, re.M), py.name


# ---------------------------------------------------------------- 입력 검증

def test_rejects_non_hwp_and_missing(tmp_path):
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(tmp_path / "없음.hwp", tmp_path / "o.hwpx")
    bad = tmp_path / "x.txt"
    bad.write_text("x")
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(bad, tmp_path / "o.hwpx")


def test_rejects_same_input_and_output(tmp_path):
    f = tmp_path / "a.hwp"
    f.write_bytes(FIXTURE.read_bytes())
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(f, f)
    assert f.read_bytes() == FIXTURE.read_bytes()


def test_rejects_unknown_engine(tmp_path):
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(FIXTURE, tmp_path / "o.hwpx", engine="hancom")


# ---------------------------------------------------------------- python 엔진

def test_python_engine_converts_fixture_and_passes_check(tmp_path):
    out = tmp_path / "conv.hwpx"
    r = convert.hwp_to_hwpx(FIXTURE, out, engine="python")
    assert r["engine"] == "python"
    assert r["ok"] and r["check"]["ok"], r["check"]["errors"]
    assert r["report"] == {"unconverted": {}, "dropped": {}, "notes": {}}
    from core.analyze import extract_text
    assert "Term of" in extract_text(out)


def test_python_engine_preserves_page_geometry_and_cell_linebreaks(tmp_path):
    out = tmp_path / "conv.hwpx"
    convert.hwp_to_hwpx(FIXTURE, out, engine="python")
    xml = _section0(out)
    assert 'width="59528" height="84188"' in xml
    assert ('<hp:margin header="0" footer="0" gutter="0" left="5385" right="5385" '
            'top="5669" bottom="2834"/>') in xml
    # 셀 안 줄바꿈은 hp:lineBreak 요소로 남고 텍스트가 붙지 않는다
    assert "1. Term of<hp:lineBreak/>Labor<hp:lineBreak/>contract" in xml
    assert "Term ofLabor" not in xml
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert names[0] == "mimetype"
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        header = zf.read("Contents/header.xml").decode("utf-8")
        assert 'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar"' in xml
        assert header.count("<hh:charPr ") == 89 and header.count("<hh:paraPr ") == 90


def test_python_engine_output_is_editable_with_byte_preserving_replace(tmp_path):
    from core import edit as edit_mod
    out = tmp_path / "conv.hwpx"
    convert.hwp_to_hwpx(FIXTURE, out, engine="python")
    edited = tmp_path / "edit.hwpx"
    report = edit_mod.edit_file(out, edited, lambda ed: ed.replace_text({"Labor": "근로"}))
    # 셀 안 <hp:lineBreak/> 뒤의 "Labor"(tail 텍스트)까지 3건 모두 교체된다
    assert report["replaced"] == {"Labor": 3}, report
    xml = _section0(edited)
    assert "근로" in xml and "Labor" not in xml
    assert "1. Term of<hp:lineBreak />근로<hp:lineBreak />contract" in xml
    # 바이트 보존: 섹션·헤더 외 엔트리는 그대로
    with zipfile.ZipFile(out) as a, zipfile.ZipFile(edited) as b:
        for name in a.namelist():
            if name not in ("Contents/section0.xml", "Preview/PrvText.txt"):
                assert a.read(name) == b.read(name), name


def test_python_engine_rejects_garbage_without_fallback(tmp_path):
    f = tmp_path / "garbage.hwp"
    f.write_bytes(b"not a real hwp file at all" * 10)
    with pytest.raises(PackageError) as ei:
        convert.hwp_to_hwpx(f, tmp_path / "o.hwpx", engine="python")
    assert "python" in str(ei.value)


def test_auto_rejects_garbage_even_when_rhwp_could_run(tmp_path):
    f = tmp_path / "garbage.hwp"
    f.write_bytes(b"not a real hwp file at all" * 10)
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(f, tmp_path / "o.hwpx")


# ---------------------------------------------------------------- 폴백 정책

class _FakeHwp5Error(Exception):
    def __init__(self, code, message="boom"):
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = None


def test_protected_document_never_falls_back(tmp_path, monkeypatch):
    def boom(src, dst):
        raise _FakeHwp5Error("hwp5-password", "The HWP document is password-protected.")
    monkeypatch.setattr(convert, "_convert_python", boom)
    monkeypatch.setattr(convert, "node_available", lambda: "/usr/bin/node")
    called = []
    monkeypatch.setattr(convert, "_convert_rhwp", lambda *a, **k: called.append(a))
    with pytest.raises(PackageError) as ei:
        convert.hwp_to_hwpx(FIXTURE, tmp_path / "o.hwpx")
    assert "password" in str(ei.value) and "[hwp5-password]" in str(ei.value)
    assert not called


def test_python_failure_without_node_reports_python_error(tmp_path, monkeypatch):
    def boom(src, dst):
        raise _FakeHwp5Error("hwp5-damaged")
    monkeypatch.setattr(convert, "_convert_python", boom)
    monkeypatch.setattr(convert, "node_available", lambda: None)
    with pytest.raises(PackageError) as ei:
        convert.hwp_to_hwpx(FIXTURE, tmp_path / "o.hwpx")
    assert "python 엔진" in str(ei.value)


def test_python_failure_falls_back_to_rhwp_and_records_reason(tmp_path, monkeypatch):
    def boom(src, dst):
        raise _FakeHwp5Error("hwp5-damaged", "records broken")
    monkeypatch.setattr(convert, "_convert_python", boom)
    monkeypatch.setattr(convert, "node_available", lambda: "/usr/bin/node")

    def fake_rhwp(src, dst, timeout):
        # 실제 rhwp 대신 python 엔진으로 산출물을 만들어 check 단계까지 흐르게 한다
        monkeypatch.undo()
        convert._convert_python(Path(src), Path(dst))
        return {"engine": "rhwp", "report": {"page_geometry_restored": True, "known_losses": []}}
    monkeypatch.setattr(convert, "_convert_rhwp", fake_rhwp)
    r = convert.hwp_to_hwpx(FIXTURE, tmp_path / "o.hwpx")
    assert r["engine"] == "rhwp" and r["ok"]
    assert "records broken" in r["fallback_reason"]


def test_rhwp_engine_requires_node(tmp_path, monkeypatch):
    monkeypatch.setattr(convert, "node_available", lambda: None)
    with pytest.raises(PackageError) as ei:
        convert.hwp_to_hwpx(FIXTURE, tmp_path / "o.hwpx", engine="rhwp")
    assert "Node" in str(ei.value)


# ---------------------------------------------------------------- rhwp 후처리

def test_patch_page_geometry_rewrites_size_and_margins():
    xml = (b'<hs:sec><hp:secPr><hp:pagePr landscape="WIDELY" width="59528" height="84186" '
           b'gutterType="LEFT_ONLY"><hp:margin header="4252" footer="4252" gutter="0" '
           b'left="8504" right="8504" top="5668" bottom="4252"/></hp:pagePr></hp:secPr></hs:sec>')
    page_def = {"width": 59528, "height": 84188, "marginLeft": 5385, "marginRight": 5385,
                "marginTop": 5669, "marginBottom": 2834, "marginHeader": 0, "marginFooter": 0,
                "marginGutter": 0}
    out = convert._patch_page_geometry(xml, page_def)
    assert b'width="59528" height="84188"' in out
    assert (b'<hp:margin header="0" footer="0" gutter="0" left="5385" right="5385" '
            b'top="5669" bottom="2834"/>') in out
    # pagePr이 없으면 그대로
    assert convert._patch_page_geometry(b"<hs:sec/>", page_def) == b"<hs:sec/>"


def test_mark_embedded_images_adds_flag_once():
    hpf = (b'<opf:item id="image1" href="BinData/image1.png" media-type="image/png"/>'
           b'<opf:item id="image2" href="BinData/image2.jpg" media-type="image/jpeg" isEmbeded="1"/>'
           b'<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>')
    out = convert._mark_embedded_images(hpf)
    assert out.count(b'isEmbeded="1"') == 2
    assert b'media-type="image/png" isEmbeded="1"/>' in out
    assert b'href="Contents/header.xml" media-type="application/xml"/>' in out


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_rhwp_engine_restores_source_page_geometry(tmp_path):
    out = tmp_path / "conv.hwpx"
    r = convert.hwp_to_hwpx(FIXTURE, out, engine="rhwp")
    assert r["engine"] == "rhwp" and r["ok"], r.get("check")
    assert r["report"]["page_geometry_restored"] is True
    xml = _section0(out)
    assert 'width="59528" height="84188"' in xml
    assert 'left="5385" right="5385" top="5669" bottom="2834"' in xml
    with zipfile.ZipFile(out) as zf:
        assert zf.namelist()[0] == "mimetype"
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_rhwp_engine_failure_on_garbage_input(tmp_path):
    f = tmp_path / "garbage.hwp"
    f.write_bytes(b"not a real hwp file at all" * 10)
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(f, tmp_path / "o.hwpx", engine="rhwp")


# ---------------------------------------------------------------- 실물 코퍼스 (선택)

@pytest.mark.skipif(not os.environ.get("HWPX_TEST_HWP"), reason="HWPX_TEST_HWP 샘플 없음")
def test_real_conversion_passes_check(tmp_path):
    from core.analyze import extract_text
    out = tmp_path / "conv.hwpx"
    r = convert.hwp_to_hwpx(os.environ["HWPX_TEST_HWP"], out)
    assert r["check"]["ok"], r["check"]["errors"]
    assert extract_text(out).strip()
