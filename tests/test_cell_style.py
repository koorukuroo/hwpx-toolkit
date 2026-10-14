import json
import xml.etree.ElementTree as ET

from core.edit import edit_file, EditError
from core.guards import check_package
from core.package import HwpxPackage
from tests.fixture import build_minimal_hwpx

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HC = "http://www.hancom.co.kr/hwpml/2011/core"


def test_set_cell_style_adds_borderfill_and_repoints_cells(tmp_path):
    src = build_minimal_hwpx(tmp_path / "m.hwpx", with_table=True)
    dst = tmp_path / "o.hwpx"
    n = edit_file(src, dst, lambda ed: ed.set_cell_style(0, 0, 0, bg="E6E6E6", border="solid",
                                                         row2=0, col2=1))
    assert n == 2
    assert check_package(dst)["ok"]
    pkg = HwpxPackage.open(dst)
    header = ET.fromstring(pkg.read("Contents/header.xml"))
    fills = header.findall(f".//{{{NS_HH}}}borderFill")
    assert len(fills) == 2 and header.find(f".//{{{NS_HH}}}borderFills").get("itemCnt") == "2"
    new = fills[-1]
    assert new.find(f"{{{NS_HC}}}fillBrush/{{{NS_HC}}}winBrush").get("faceColor") == "#E6E6E6"
    assert all(new.find(f"{{{NS_HH}}}{e}").get("type") == "SOLID"
               for e in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"))
    sec = pkg.read_text("Contents/section0.xml")
    assert sec.count(f'borderFillIDRef="{new.get("id")}"') == 2


def test_set_cell_style_requires_option_and_existing_cell(tmp_path):
    src = build_minimal_hwpx(tmp_path / "m.hwpx", with_table=True)
    import pytest
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "a.hwpx", lambda ed: ed.set_cell_style(0, 0, 0))
    with pytest.raises(EditError):
        edit_file(src, tmp_path / "b.hwpx", lambda ed: ed.set_cell_style(0, 9, 9, bg="FF0000"))


def test_cli_set_cell_style(tmp_path, capsys):
    from scripts import hwpx as cli
    src = build_minimal_hwpx(tmp_path / "m.hwpx", with_table=True)
    dst = tmp_path / "o.hwpx"
    code = cli.main(["set-cell-style", str(src), str(dst), "--table", "0", "--row", "1", "--col", "0",
                     "--bg", "none", "--border", "none"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0 and payload["ok"] and payload["report"]["styled_cells"] == 1
