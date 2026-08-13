import zipfile

from core.analyze import analyze_document, extract_slots
from tests.fixture import build_minimal_hwpx


def test_analyze_reports_page_and_tables(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx", with_table=True)
    r = analyze_document(p)
    assert r["page"]["width"] == 59528
    assert r["page"]["margins"]["left"] == 8504
    assert r["styles"]["charPrCount"] == 1
    sec = r["sections"][0]
    assert sec["tables"] == [{"index": 0, "rows": 2, "cols": 2}]


def test_slots_paragraphs_and_cells(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx",
                           body_texts=["본문 하나"], with_table=True)
    slots = extract_slots(p)["slots"]
    keys = [s["key"] for s in slots]
    assert "p:1" in keys                 # p:0은 secPr 문단(텍스트 없음)이라 제외됨
    assert "cell:0:0:0" in keys and "cell:0:1:1" in keys
    cell = next(s for s in slots if s["key"] == "cell:0:1:1")
    assert cell["text"] == "셀11"
    # 표를 품은 컨테이너 문단은 p: 슬롯에 없어야 함
    para_texts = [s["text"] for s in slots if s["type"] == "paragraph"]
    assert all("셀" not in t for t in para_texts)


def test_slots_p_index_is_document_global_across_sections(tmp_path):
    """p: 인덱스는 섹션마다 리셋되지 않고 문서 전체에서 이어져야 함 (회귀 테스트)."""
    base_path = tmp_path / "multi.hwpx"
    build_minimal_hwpx(base_path, body_texts=["본문 하나"], with_table=True)

    # section0.xml과 같은 구조(secPr 문단 + 본문 문단)를 가진 두 번째 섹션을
    # 별도로 만들어 section1.xml로 끼워 넣는다 (fixture.py의 section0.xml
    # 생성 로직을 재사용, 텍스트만 다르게).
    other_path = tmp_path / "other.hwpx"
    build_minimal_hwpx(other_path, body_texts=["섹션1 문단"], with_table=False)
    with zipfile.ZipFile(other_path, "r") as zf_other:
        section1_xml = zf_other.read("Contents/section0.xml")

    with zipfile.ZipFile(base_path, "r") as zf_in:
        entries = {info.filename: zf_in.read(info.filename) for info in zf_in.infolist()}
    entries["Contents/section1.xml"] = section1_xml
    with zipfile.ZipFile(base_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for name, data in entries.items():
            ctype = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            zf_out.writestr(zipfile.ZipInfo(name), data, compress_type=ctype)

    slots = extract_slots(base_path)["slots"]
    keys = [s["key"] for s in slots]

    # (a) 모든 슬롯 키는 섹션 경계를 넘어 고유해야 함
    assert len(keys) == len(set(keys))

    # (b) section1의 문단 인덱스는 section0의 문단 수(3: secPr + 본문 + 표 컨테이너)
    # 다음부터 이어져야 하며 p:0/p:1로 리셋되면 안 됨
    sec1_slot = next(s for s in slots if s["text"] == "섹션1 문단")
    assert sec1_slot["key"] == "p:4"
    assert sec1_slot["section"] == "Contents/section1.xml"
