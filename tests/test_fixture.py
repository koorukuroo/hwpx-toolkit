import zipfile
from pathlib import Path
from tests.fixture import build_minimal_hwpx


def test_fixture_is_valid_zip_with_mimetype_first(tmp_path):
    p = build_minimal_hwpx(tmp_path / "min.hwpx")
    assert zipfile.is_zipfile(p)
    with zipfile.ZipFile(p) as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/hwp+zip"
        names = zf.namelist()
        for required in ("version.xml", "Contents/header.xml",
                         "Contents/content.hpf", "Contents/section0.xml"):
            assert required in names


def test_fixture_with_table_contains_tbl(tmp_path):
    p = build_minimal_hwpx(tmp_path / "tbl.hwpx", with_table=True)
    with zipfile.ZipFile(p) as zf:
        xml = zf.read("Contents/section0.xml").decode("utf-8")
    assert "<hp:tbl" in xml and 'rowCnt="2"' in xml
