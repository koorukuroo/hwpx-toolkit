import zipfile
from core.package import HwpxPackage
from tests.fixture import build_minimal_hwpx


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
    import pytest
    from core.package import PackageError
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    with pytest.raises(PackageError):
        HwpxPackage.open(src).write_replaced(tmp_path / "x.hwpx", {"없음.xml": b""})
