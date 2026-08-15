import struct
import zipfile
import pytest
from core.package import HwpxPackage, PackageError, pack_dir, section_names
from tests.fixture import build_minimal_hwpx


def test_corrupt_central_directory_raises_package_error(tmp_path):
    # EOCD는 유효(=is_zipfile 통과)하지만 CD offset이 쓰레기를 가리키는 파일
    eocd = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 1, 1, 10, 0, 0)
    bad = tmp_path / "bad.hwpx"
    bad.write_bytes(b"GARBAGE!" * 8 + eocd)
    with pytest.raises(PackageError):
        HwpxPackage.open(bad)


def test_pack_dir_ignores_dotfiles_without_source(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(src).extract_to(outdir)
    (outdir / ".DS_Store").write_bytes(b"junk")
    (outdir / "Contents" / ".hidden").write_bytes(b"junk")
    out = tmp_path / "fresh.hwpx"
    pack_dir(outdir, out)
    with zipfile.ZipFile(out) as zf:
        assert all(".DS_Store" not in n and ".hidden" not in n
                   for n in zf.namelist())


def test_pack_dir_ignores_dotfiles_with_source(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(src).extract_to(outdir)
    (outdir / ".DS_Store").write_bytes(b"junk")
    out = tmp_path / "same.hwpx"
    pack_dir(outdir, out, source=src)   # 예전엔 '원본에 없는 파일' PackageError
    assert out.read_bytes() == src.read_bytes()


def test_section_names_numeric_order():
    names = ["Contents/section10.xml", "Contents/section2.xml",
             "Contents/section0.xml", "Contents/header.xml", "mimetype"]
    assert section_names(names) == ["Contents/section0.xml",
                                    "Contents/section2.xml",
                                    "Contents/section10.xml"]
