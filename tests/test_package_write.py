import zipfile

import pytest

from core.package import HwpxPackage, PackageError, UnsupportedZipError
from tests.fixture import MIMETYPE, build_minimal_hwpx


def test_noop_rewrite_is_byte_identical(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    dst = tmp_path / "dst.hwpx"
    HwpxPackage.open(src).write_replaced(dst, {})
    assert dst.read_bytes() == src.read_bytes()


def test_replace_one_entry_preserves_others(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    dst = tmp_path / "dst.hwpx"
    pkg = HwpxPackage.open(src)
    new_xml = pkg.read_text("Contents/section0.xml").replace("안녕하세요", "반갑습니다")
    pkg.write_replaced(dst, {"Contents/section0.xml": new_xml.encode("utf-8")})

    out = HwpxPackage.open(dst)
    assert "반갑습니다" in out.read_text("Contents/section0.xml")
    # 교체 대상 외 엔트리는 압축 바이트까지 동일
    with zipfile.ZipFile(src) as za, zipfile.ZipFile(dst) as zb:
        for name in za.namelist():
            if name == "Contents/section0.xml":
                continue
            ia, ib = za.getinfo(name), zb.getinfo(name)
            assert (ia.CRC, ia.compress_size, ia.file_size, ia.flag_bits,
                    ia.compress_type, ia.date_time) == \
                   (ib.CRC, ib.compress_size, ib.file_size, ib.flag_bits,
                    ib.compress_type, ib.date_time)
    # 결과는 여전히 유효한 ZIP + mimetype 첫 엔트리
    with zipfile.ZipFile(dst) as zf:
        assert zf.testzip() is None
        assert zf.infolist()[0].filename == "mimetype"


def test_replace_unknown_name_raises(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    with pytest.raises(PackageError):
        HwpxPackage.open(src).write_replaced(tmp_path / "x.hwpx", {"없음.xml": b""})


def test_write_replaced_rejects_non_deflate_entry(tmp_path):
    pytest.importorskip("bz2")
    src = tmp_path / "bz2.hwpx"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE.encode("utf-8"),
                    compress_type=zipfile.ZIP_STORED)
        zf.writestr(zipfile.ZipInfo("settings.xml"), b"<a/>",
                    compress_type=zipfile.ZIP_BZIP2)

    pkg = HwpxPackage.open(src)
    with pytest.raises(UnsupportedZipError):
        pkg.write_replaced(tmp_path / "out.hwpx", {"settings.xml": b"<b/>"})


def test_replace_early_entry_shifts_offsets_of_trailing_entries(tmp_path):
    """version.xml(2번째 엔트리)을 다른 길이로 교체해도 뒤따르는 엔트리의
    중앙 디렉터리 오프셋이 올바르게 패치되는지 확인 (회귀 테스트)."""
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    dst = tmp_path / "dst.hwpx"
    pkg = HwpxPackage.open(src)
    assert pkg.names()[1] == "version.xml"

    new_version = pkg.read_text("version.xml").replace(
        'appVersion="0.1"', 'appVersion="0.1-a-much-longer-value-than-before"')
    pkg.write_replaced(dst, {"version.xml": new_version.encode("utf-8")})

    with zipfile.ZipFile(dst) as zf:
        assert zf.testzip() is None
        assert zf.read("version.xml").decode("utf-8") == new_version

        with zipfile.ZipFile(src) as za:
            for name in ("Contents/section0.xml", "Contents/header.xml"):
                assert zf.read(name) == za.read(name)
                ia, ib = za.getinfo(name), zf.getinfo(name)
                assert (ia.CRC, ia.compress_size, ia.file_size) == \
                       (ib.CRC, ib.compress_size, ib.file_size)
