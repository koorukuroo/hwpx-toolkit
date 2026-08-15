import zipfile
from core.guards import validate_package
from core.analyze import extract_text
from tests.fixture import build_form_hwpx


def test_form_fixture_valid_and_contents(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    assert validate_package(p)["ok"]
    text = extract_text(p)
    for expected in ("성명", "연락처", "□동의 □비동의", "일반(  )통", "안녕하세요"):
        assert expected in text


def test_form_fixture_has_linesegarray_and_split_runs(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    with zipfile.ZipFile(p) as zf:
        xml = zf.read("Contents/section0.xml").decode("utf-8")
    assert xml.count("<hp:linesegarray>") == 2
    assert "<hp:t>안녕</hp:t>" in xml and "<hp:t>하세요</hp:t>" in xml
