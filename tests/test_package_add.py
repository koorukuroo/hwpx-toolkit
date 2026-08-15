import zipfile
import pytest
from core.package import HwpxPackage, PackageError
from core.edit import edit_file
from tests.fixture import build_minimal_hwpx


def test_write_replaced_with_additions(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    dst = tmp_path / "b.hwpx"
    pkg = HwpxPackage.open(src)
    pkg.write_replaced(dst, {}, additions={"BinData/image1.png": b"\x89PNG-fake"})
    with zipfile.ZipFile(dst) as zf:
        assert zf.testzip() is None
        assert zf.read("BinData/image1.png") == b"\x89PNG-fake"
        info = zf.getinfo("BinData/image1.png")
        assert info.flag_bits & 0x800
    with zipfile.ZipFile(src) as za, zipfile.ZipFile(dst) as zb:
        for name in za.namelist():
            assert za.read(name) == zb.read(name)
        assert zb.infolist()[0].filename == "mimetype"


def test_additions_reject_existing_name(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    with pytest.raises(PackageError):
        HwpxPackage.open(src).write_replaced(tmp_path / "x.hwpx", {},
                                            additions={"mimetype": b"x"})


def test_edit_context_stages_addition_and_replacement(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    dst = tmp_path / "b.hwpx"

    def fn(ed):
        ed.ctx.stage_addition("BinData/x.bin", b"123")
        hpf = ed.ctx.pkg.read_text("Contents/content.hpf").replace(
            "fixture", "수정됨")
        ed.ctx.stage_replacement("Contents/content.hpf", hpf.encode("utf-8"))
        return "ok"

    assert edit_file(src, dst, fn) == "ok"
    out = HwpxPackage.open(dst)
    assert out.read("BinData/x.bin") == b"123"
    assert "수정됨" in out.read_text("Contents/content.hpf")
