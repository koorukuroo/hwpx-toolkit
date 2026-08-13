import zipfile
from core.guards import validate_package
from tests.fixture import build_minimal_hwpx


def test_fixture_passes(tmp_path):
    p = build_minimal_hwpx(tmp_path / "ok.hwpx")
    r = validate_package(p)
    assert r["ok"], r["errors"]


def _rebuild_without_mimetype_first(src, dst):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        infos = zin.infolist()
        for info in infos[1:] + infos[:1]:   # mimetype을 마지막으로
            zout.writestr(info, zin.read(info.filename))


def test_mimetype_not_first_fails(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    _rebuild_without_mimetype_first(src, bad)
    r = validate_package(bad)
    assert not r["ok"]
    assert any(e.startswith("mimetype-not-first") for e in r["errors"])


def _replace_entry(src, dst, name, new_bytes):
    from core.package import HwpxPackage
    HwpxPackage.open(src).write_replaced(dst, {name: new_bytes})


def test_malformed_xml_fails(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    _replace_entry(src, bad, "Contents/section0.xml", b"<hs:sec>\xea\xb9\xa8\xec\xa7\x84 XML")
    r = validate_package(bad)
    assert any(e.startswith("xml-malformed") for e in r["errors"])


def test_itemcnt_mismatch_fails(tmp_path):
    from core.package import HwpxPackage
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    header = HwpxPackage.open(src).read_text("Contents/header.xml")
    header = header.replace('charProperties itemCnt="1"', 'charProperties itemCnt="5"')
    _replace_entry(src, bad, "Contents/header.xml", header.encode("utf-8"))
    r = validate_package(bad)
    assert any(e.startswith("itemcnt-mismatch") for e in r["errors"])


def test_dangling_charpr_ref_fails(tmp_path):
    from core.package import HwpxPackage
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    sec = HwpxPackage.open(src).read_text("Contents/section0.xml")
    sec = sec.replace('charPrIDRef="0"', 'charPrIDRef="99"', 1)
    _replace_entry(src, bad, "Contents/section0.xml", sec.encode("utf-8"))
    r = validate_package(bad)
    assert any(e.startswith("dangling-ref") for e in r["errors"])


def test_missing_secpr_fails(tmp_path):
    from core.package import HwpxPackage
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    bad = tmp_path / "bad.hwpx"
    sec = HwpxPackage.open(src).read_text("Contents/section0.xml")
    start = sec.index("<hp:secPr")
    end = sec.index("</hp:secPr>") + len("</hp:secPr>")
    _replace_entry(src, bad, "Contents/section0.xml",
                   (sec[:start] + sec[end:]).encode("utf-8"))
    r = validate_package(bad)
    assert any(e.startswith("secpr-missing") for e in r["errors"])
