import struct
import zlib
import zipfile
import pytest
from core.errors import PackageError, EditError, UnsupportedZipError
from core.package import HwpxPackage
from core.edit import edit_file
from core.images import image_size
from core.guards import check_package
from tests.fixture import build_form_hwpx, build_minimal_hwpx


def test_errors_module_is_single_source():
    import core.package, core.edit
    assert core.package.PackageError is PackageError
    assert core.edit.EditError is EditError
    assert issubclass(EditError, PackageError)
    assert issubclass(UnsupportedZipError, PackageError)


def _png(w, h):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _jpeg_with_padding(w, h):
    # SOI, APP0(짧게), 패딩 FF FF, SOF0, EOI
    app0 = b"\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00"
    sof0 = b"\xff\xc0" + struct.pack(">H", 11) + b"\x08" + struct.pack(">HH", h, w) + b"\x01\x01\x11\x00"
    return b"\xff\xd8" + app0 + b"\xff\xff" + sof0 + b"\xff\xd9"


def test_jpeg_padding_and_truncated_png():
    assert image_size(_jpeg_with_padding(30, 20)) == (30, 20, "jpg")
    with pytest.raises(EditError):
        image_size(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4)


def test_delete_image_in_cell_keeps_paragraph(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(_png(8, 8))
    src = build_form_hwpx(tmp_path / "f.hwpx")
    d1 = tmp_path / "1.hwpx"
    # 셀 (0,0,1)에 그림을 넣기 위해 셀 문단을 앵커로 삽입할 수 없으므로(본문 전용)
    # 편집기 내부 API로 셀 subList에 그림 문단을 직접 구성한다
    def put_pic_in_cell(ed):
        import xml.etree.ElementTree as ET
        from core import images
        _, tc = ed._find_cell(0, 0, 1)
        sub = tc.find(ed_q("subList"))
        p = sub.findall(ed_q("p"))[0]
        run = p.find(ed_q("run"))
        bin_id = ed._stage_new_image(img.read_bytes(), "png")
        pic = ET.fromstring(images.pic_xml(str(ed._max_id() + 1), bin_id, 1000, 1000, 8, 8))
        for t in run.findall(ed_q("t")):
            run.remove(t)
        run.append(pic)
        ed._mark(p)
    from core.edit import _q as ed_q
    edit_file(src, d1, put_pic_in_cell)
    d2 = tmp_path / "2.hwpx"
    edit_file(d1, d2, lambda ed: ed.delete_image(0))
    import xml.etree.ElementTree as ET
    root = ET.fromstring(HwpxPackage.open(d2).read("Contents/section0.xml"))
    NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
    subs = list(root.iter(f"{{{NS}}}subList"))
    assert all(s.find(f"{{{NS}}}p") is not None for s in subs)   # 빈 subList 없음
    assert check_package(d2)["ok"]


def test_check_detects_broken_image_ref(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx")
    pkg = HwpxPackage.open(src)
    sec = pkg.read_text("Contents/section0.xml").replace(
        "</hs:sec>",
        '<hp:p id="1000009999" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
        '<hp:pic id="1" zOrder="0" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" '
        'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" '
        'instid="0" reverse="0" xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core">'
        '<hc:img binaryItemIDRef="ghost" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
        '</hp:pic></hp:run></hp:p></hs:sec>')
    bad = tmp_path / "bad.hwpx"
    pkg.write_replaced(bad, {"Contents/section0.xml": sec.encode("utf-8")})
    r = check_package(bad)
    assert r["signals"]["image_ref_broken"] is True
    assert any(e.startswith("image-ref-broken: ghost") for e in r["errors"])
