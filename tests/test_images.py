import struct
import zlib
import zipfile
import pytest
from core.package import HwpxPackage
from core.edit import edit_file, EditError
from core.guards import check_package
from core.images import image_size
from tests.fixture import build_form_hwpx


def _png(w, h):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_image_size_png_and_reject_unknown():
    assert image_size(_png(40, 20)) == (40, 20, "png")
    with pytest.raises(EditError):
        image_size(b"not an image")


def test_insert_list_resize_replace_delete(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(_png(96, 48))
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    edit_file(src, d1, lambda ed: ed.insert_image(str(img), after="안녕하세요",
                                                  width_mm=50))
    with zipfile.ZipFile(d1) as zf:
        names = zf.namelist()
        assert "BinData/image1.png" in names
        assert zf.testzip() is None
        hpf = zf.read("Contents/content.hpf").decode("utf-8")
        assert 'id="image1"' in hpf and "image/png" in hpf
    assert check_package(d1)["ok"]

    def lst(path):
        out = {}
        edit_file(path, tmp_path / "tmp.hwpx", lambda ed: out.setdefault("v", ed.list_images()))
        return out["v"]
    imgs = lst(d1)
    assert len(imgs) == 1 and imgs[0]["bin_id"] == "image1"
    assert imgs[0]["width_mm"] == 50 and imgs[0]["height_mm"] == 25   # 비율 유지

    d2 = tmp_path / "2.hwpx"
    edit_file(d1, d2, lambda ed: ed.resize_image(0, width_mm=30))
    assert lst(d2)[0]["height_mm"] == 15

    img2 = tmp_path / "b.png"
    img2.write_bytes(_png(10, 10))
    d3 = tmp_path / "3.hwpx"
    edit_file(d2, d3, lambda ed: ed.replace_image(0, str(img2)))
    with zipfile.ZipFile(d3) as zf:
        assert "BinData/image2.png" in zf.namelist()
    assert lst(d3)[0]["bin_id"] == "image2"
    assert lst(d3)[0]["width_mm"] == 30                        # 표시 크기 유지

    d4 = tmp_path / "4.hwpx"
    edit_file(d3, d4, lambda ed: ed.delete_image(0))
    assert lst(d4) == []
    assert check_package(d4)["ok"]


def test_insert_image_index_out_of_range(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(_png(4, 4))
    src = build_form_hwpx(tmp_path / "f.hwpx")
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "x.hwpx", lambda ed: ed.resize_image(3, width_mm=1))
