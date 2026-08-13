import pytest
from core.package import HwpxPackage, PackageError
from tests.fixture import build_minimal_hwpx


def test_open_and_list_names_in_local_order(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx")
    pkg = HwpxPackage.open(p)
    assert pkg.names()[0] == "mimetype"
    assert "Contents/section0.xml" in pkg.names()


def test_read_bytes_and_text(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx")
    pkg = HwpxPackage.open(p)
    assert pkg.read("mimetype") == b"application/hwp+zip"
    assert "안녕하세요" in pkg.read_text("Contents/section0.xml")


def test_read_missing_entry_raises(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx")
    pkg = HwpxPackage.open(p)
    with pytest.raises(PackageError):
        pkg.read("없는파일.xml")


def test_open_non_zip_raises(tmp_path):
    bad = tmp_path / "bad.hwpx"
    bad.write_bytes(b"not a zip")
    with pytest.raises(PackageError):
        HwpxPackage.open(bad)
