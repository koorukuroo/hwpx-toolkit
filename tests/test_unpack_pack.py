from core.package import HwpxPackage, pack_dir
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
    import zipfile
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(src).extract_to(outdir)
    out = tmp_path / "fresh.hwpx"
    pack_dir(outdir, out)
    with zipfile.ZipFile(out) as zf:
        assert zf.infolist()[0].filename == "mimetype"
        assert zf.infolist()[0].compress_type == zipfile.ZIP_STORED
