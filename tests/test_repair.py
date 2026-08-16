import xml.etree.ElementTree as ET
import zipfile
import pytest
from core.errors import PackageError
from core.package import HwpxPackage
from core.guards import check_package
from core.repair import fix_char_borders
from tests.fixture import build_minimal_hwpx

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _make_bordered(tmp_path, name="bad.hwpx"):
    """charPr 0이 실선 borderFill을 참조하도록 조작한 문서."""
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    pkg = HwpxPackage.open(src)
    header = pkg.read_text("Contents/header.xml").replace(
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>',
        '<hh:leftBorder type="SOLID" width="0.1 mm" color="#000000"/>')
    bad = tmp_path / name
    pkg.write_replaced(bad, {"Contents/header.xml": header.encode("utf-8")})
    return bad


def test_check_detects_then_repair_fixes(tmp_path):
    bad = _make_bordered(tmp_path)
    assert check_package(bad)["signals"]["char_border_bug"] is True

    out = tmp_path / "fixed.hwpx"
    report = fix_char_borders(bad, out)
    assert report["changed"] is True
    assert report["fixed"] >= 1
    assert report["created"] is True          # 픽스처엔 무테두리 borderFill이 없음

    after = check_package(out)
    assert after["signals"]["char_border_bug"] is False
    assert after["ok"], after["errors"]


def test_repair_adds_borderless_fill_and_fixes_itemcnt(tmp_path):
    bad = _make_bordered(tmp_path)
    out = tmp_path / "fixed.hwpx"
    report = fix_char_borders(bad, out)
    root = ET.fromstring(HwpxPackage.open(out).read("Contents/header.xml"))
    coll = root.find(f".//{{{NS_HH}}}borderFills")
    fills = coll.findall(f"{{{NS_HH}}}borderFill")
    assert coll.get("itemCnt") == str(len(fills))
    new = [b for b in fills if b.get("id") == report["borderfill_id"]][0]
    for edge in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
        assert new.find(f"{{{NS_HH}}}{edge}").get("type") == "NONE"
    for cp in root.iter(f"{{{NS_HH}}}charPr"):
        assert cp.get("borderFillIDRef") == report["borderfill_id"]


def test_repair_preserves_other_entries(tmp_path):
    bad = _make_bordered(tmp_path)
    out = tmp_path / "fixed.hwpx"
    fix_char_borders(bad, out)
    with zipfile.ZipFile(bad) as a, zipfile.ZipFile(out) as b:
        for name in a.namelist():
            if name == "Contents/header.xml":
                continue
            assert a.read(name) == b.read(name), name


def test_repair_reuses_existing_borderless_fill(tmp_path):
    """실물 문서에서는 header.xml에 무테두리 borderFill이 이미 있고, charPr가
    다른(실선) borderFill을 참조하도록 망가진 경우가 많다. 이 경로는 새
    borderFill을 만들지 않고 기존 것을 재사용해야 한다 (created=False)."""
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    pkg = HwpxPackage.open(src)
    header = pkg.read_text("Contents/header.xml")

    solid_fill = (
        '<hh:borderFill id="2" threeD="0" shadow="0" centerLine="NONE" '
        'breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:leftBorder type="SOLID" width="0.1 mm" color="#000000"/>'
        '<hh:rightBorder type="SOLID" width="0.1 mm" color="#000000"/>'
        '<hh:topBorder type="SOLID" width="0.1 mm" color="#000000"/>'
        '<hh:bottomBorder type="SOLID" width="0.1 mm" color="#000000"/>'
        '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
        '</hh:borderFill>'
    )
    # id="1"(무테두리)은 그대로 두고, id="2"(실선)를 추가한 뒤 charPr가
    # id="2"를 참조하도록 망가뜨린다.
    assert header.count('<hh:borderFills itemCnt="1">') == 1
    header = header.replace('<hh:borderFills itemCnt="1">',
                            '<hh:borderFills itemCnt="2">', 1)
    header = header.replace('</hh:borderFills>', solid_fill + '</hh:borderFills>', 1)
    assert header.count('borderFillIDRef="1">') == 1
    header = header.replace('borderFillIDRef="1">', 'borderFillIDRef="2">', 1)

    bad = tmp_path / "bad.hwpx"
    pkg.write_replaced(bad, {"Contents/header.xml": header.encode("utf-8")})
    assert check_package(bad)["signals"]["char_border_bug"] is True

    out = tmp_path / "fixed.hwpx"
    report = fix_char_borders(bad, out)
    assert report["created"] is False               # 기존 무테두리 fill 재사용
    assert report["fixed"] >= 1
    assert report["borderfill_id"] == "1"            # 원래 있던 무테두리 fill의 id

    after = check_package(out)
    assert after["signals"]["char_border_bug"] is False
    assert after["ok"], after["errors"]


def test_repair_noop_on_clean_document(tmp_path):
    clean = build_minimal_hwpx(tmp_path / "clean.hwpx")
    out = tmp_path / "same.hwpx"
    report = fix_char_borders(clean, out)
    assert report["changed"] is False and report["fixed"] == 0
    assert out.read_bytes() == clean.read_bytes()      # 완전 동일 복사


def test_repair_rejects_header_without_borderfills(tmp_path):
    src = build_minimal_hwpx(tmp_path / "src.hwpx")
    pkg = HwpxPackage.open(src)
    header = pkg.read_text("Contents/header.xml")
    start = header.index("<hh:borderFills")
    end = header.index("</hh:borderFills>") + len("</hh:borderFills>")
    broken = tmp_path / "broken.hwpx"
    pkg.write_replaced(broken, {"Contents/header.xml":
                                (header[:start] + header[end:]).encode("utf-8")})
    with pytest.raises(PackageError):
        fix_char_borders(broken, tmp_path / "x.hwpx")


def test_cli_fix_borders(tmp_path, capsys):
    import json
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    bad = _make_bordered(tmp_path)
    out = tmp_path / "cli.hwpx"
    rc = hwpx_cli.main(["fix-borders", str(bad), str(out)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    assert payload["report"]["fixed"] >= 1
