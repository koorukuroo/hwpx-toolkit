import zipfile

import pytest

from core.package import HwpxPackage, PackageError, pack_dir
from tests.fixture import build_minimal_hwpx


def test_unpack_writes_all_entries(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    names = HwpxPackage.open(src).extract_to(outdir)
    assert (outdir / "mimetype").read_bytes() == b"application/hwp+zip"
    assert (outdir / "Contents" / "section0.xml").exists()
    assert "Contents/header.xml" in names


def test_pack_with_source_is_byte_preserving(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(src).extract_to(outdir)
    # 수정 없이 재패킹 → 바이트 동일
    out1 = tmp_path / "same.hwpx"
    pack_dir(outdir, out1, source=src)
    assert out1.read_bytes() == src.read_bytes()
    # section0만 수정 → 해당 엔트리만 변경
    sec = outdir / "Contents" / "section0.xml"
    sec.write_text(sec.read_text(encoding="utf-8").replace("안녕하세요", "수정됨"),
                   encoding="utf-8")
    out2 = tmp_path / "edited.hwpx"
    pack_dir(outdir, out2, source=src)
    assert "수정됨" in HwpxPackage.open(out2).read_text("Contents/section0.xml")


def test_pack_without_source_keeps_mimetype_first(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(src).extract_to(outdir)
    out = tmp_path / "fresh.hwpx"
    pack_dir(outdir, out)
    with zipfile.ZipFile(out) as zf:
        assert zf.infolist()[0].filename == "mimetype"
        assert zf.infolist()[0].compress_type == zipfile.ZIP_STORED


def test_extract_to_rejects_parent_traversal_entry(tmp_path):
    evil = tmp_path / "evil.hwpx"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("../evil.txt", "pwned")
    outdir = tmp_path / "unpacked"
    outdir.mkdir()
    with pytest.raises(PackageError):
        HwpxPackage.open(evil).extract_to(outdir)
    assert not (tmp_path / "evil.txt").exists()


def test_extract_to_rejects_absolute_entry(tmp_path):
    evil = tmp_path / "evil_abs.hwpx"
    marker = tmp_path / "outside_marker.txt"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr(str(marker), "pwned")
    outdir = tmp_path / "unpacked_abs"
    outdir.mkdir()
    with pytest.raises(PackageError):
        HwpxPackage.open(evil).extract_to(outdir)
    assert not marker.exists()


def test_extract_to_skips_explicit_directory_entries(tmp_path):
    src = tmp_path / "with_dirs.hwpx"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/", "")  # 명시적 디렉터리 엔트리
        zf.writestr("Contents/section0.xml", "<hs:sec/>")
    outdir = tmp_path / "unpacked_dirs"
    names = HwpxPackage.open(src).extract_to(outdir)
    assert "Contents/" in names  # 목록에는 남아 있어도
    assert (outdir / "Contents" / "section0.xml").read_text(encoding="utf-8") == "<hs:sec/>"
    assert not (outdir / "Contents").is_file()
