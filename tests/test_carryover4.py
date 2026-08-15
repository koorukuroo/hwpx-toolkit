import zipfile
from core.analyze import extract_slots, fill_targets
from core.package import HwpxPackage
from tests.fixture import build_minimal_hwpx, build_form_hwpx


def _two_section_with_tables(tmp_path):
    src = build_minimal_hwpx(tmp_path / "a.hwpx", with_table=True)
    pkg = HwpxPackage.open(src)
    sec0 = pkg.read("Contents/section0.xml")
    out = tmp_path / "two.hwpx"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            zout.writestr(info, zin.read(info.filename))
        zout.writestr("Contents/section1.xml",
                      sec0.decode("utf-8").replace("셀00", "둘째섹션셀"))
    return out


def test_slot_cell_keys_unique_across_sections(tmp_path):
    p = _two_section_with_tables(tmp_path)
    slots = extract_slots(p)["slots"]
    keys = [s["key"] for s in slots]
    assert len(keys) == len(set(keys))
    assert "cell:0:0:0" in keys
    assert "sec1:cell:0:0:0" in keys
    sec1 = next(s for s in slots if s["key"] == "sec1:cell:0:0:0")
    assert sec1["text"] == "둘째섹션셀"


def test_checkbox_heuristic_excludes_bullet_markers(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx", body_texts=[
        "□ 사업목적",          # 공문 항목 머리표 → 제외
        "□동의 □비동의",       # 체크박스 → 2개
        "☐확인",               # 대체 기호 → 1개
    ])
    boxes = [t for t in fill_targets(p)["targets"] if t["kind"] == "checkbox"]
    literals = {t["literal"] for t in boxes}
    assert literals == {"□동의", "□비동의", "☐확인"}


def test_form_fixture_still_detects_checkboxes(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    boxes = {t["literal"] for t in fill_targets(p)["targets"]
             if t["kind"] == "checkbox"}
    assert boxes == {"□동의", "□비동의"}
