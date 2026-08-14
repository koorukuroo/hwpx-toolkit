import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "templates" / "base"

REQUIRED = [
    "mimetype", "version.xml", "settings.xml",
    "META-INF/container.xml", "META-INF/manifest.xml",
    "Contents/content.hpf", "Contents/header.xml", "Contents/section0.xml",
]

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def test_all_template_files_exist():
    for rel in REQUIRED:
        assert (BASE / rel).is_file(), f"누락: {rel}"


def test_mimetype_content():
    assert (BASE / "mimetype").read_bytes() == b"application/hwp+zip"


def test_all_xml_files_well_formed():
    for rel in REQUIRED:
        if rel == "mimetype":
            continue
        ET.fromstring((BASE / rel).read_bytes())


def test_header_itemcnt_consistency_and_style_map():
    root = ET.fromstring((BASE / "Contents/header.xml").read_bytes())
    for coll, child, expected in [
        ("fontfaces", "fontface", 7),
        ("borderFills", "borderFill", 4),
        ("charProperties", "charPr", 5),
        ("paraProperties", "paraPr", 6),
        ("styles", "style", 1),
    ]:
        el = root.find(f".//{{{NS_HH}}}{coll}")
        children = el.findall(f"{{{NS_HH}}}{child}")
        assert int(el.get("itemCnt")) == len(children) == expected, coll
    # 제목 charPr: 18pt 볼드
    char1 = root.find(f".//{{{NS_HH}}}charPr[@id='1']")
    assert char1.get("height") == "1800"
    assert char1.find(f"{{{NS_HH}}}bold") is not None
    # 표 헤더 borderFill 4는 배경색 보유
    bf4 = root.find(f".//{{{NS_HH}}}borderFill[@id='4']")
    assert b"E6E6E6" in ET.tostring(bf4)


def test_section_skeleton_first_para_has_secpr_and_colpr():
    root = ET.fromstring((BASE / "Contents/section0.xml").read_bytes())
    first_run = root.find(f"{{{NS_HP}}}p/{{{NS_HP}}}run")
    assert first_run.find(f"{{{NS_HP}}}secPr") is not None
    ctrl = first_run.find(f"{{{NS_HP}}}ctrl")
    assert ctrl is not None and ctrl.find(f"{{{NS_HP}}}colPr") is not None
    pagepr = first_run.find(f"{{{NS_HP}}}secPr/{{{NS_HP}}}pagePr")
    assert pagepr.get("width") == "59528" and pagepr.get("height") == "84186"


def test_content_hpf_has_title_token():
    text = (BASE / "Contents/content.hpf").read_text(encoding="utf-8")
    assert text.count("<opf:title>무제</opf:title>") == 1


def test_generator_is_idempotent():
    """생성기를 다시 실행해도 커밋된 파일과 동일해야 한다."""
    import subprocess, sys
    before = {rel: (BASE / rel).read_bytes() for rel in REQUIRED}
    subprocess.run([sys.executable,
                    str(BASE.parent.parent / "scripts/dev/gen_base_template.py")],
                   check=True)
    after = {rel: (BASE / rel).read_bytes() for rel in REQUIRED}
    assert before == after
