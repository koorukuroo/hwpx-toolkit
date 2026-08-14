"""생성 파이프라인(markdown → section → 템플릿 조립)과 Phase 1 unpack/pack 간
상호운용 회귀 테스트. build_from_template로 만든 문서를 unpack 후 재조립하면
바이트가 보존되어야 하고, 내용을 수정해 재조립하면 유효한 문서로 검증되며
수정 내용이 반영되어야 한다."""
from core.guards import validate_package
from core.markdown import render_to_section
from core.package import HwpxPackage, pack_dir
from core.template import build_from_template

SAMPLE = """# 상호운용 검증 문서

개요 문단입니다.

| 항목 | 예산 |
| --- | --- |
| 인건비 | 100 |
| 운영비 | 50 |
"""


def _build_doc(tmp_path):
    section_xml = render_to_section(SAMPLE)
    doc = tmp_path / "doc.hwpx"
    build_from_template(doc, section_xml=section_xml, title="상호운용 문서")
    r = validate_package(doc)
    assert r["ok"], r["errors"]
    return doc


def test_generated_doc_roundtrips_byte_identical(tmp_path):
    doc = _build_doc(tmp_path)
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(doc).extract_to(outdir)

    same = tmp_path / "same.hwpx"
    pack_dir(outdir, same, source=doc)
    assert same.read_bytes() == doc.read_bytes()


def test_generated_doc_edit_then_pack_validates_with_new_text(tmp_path):
    doc = _build_doc(tmp_path)
    outdir = tmp_path / "unpacked"
    HwpxPackage.open(doc).extract_to(outdir)

    sec = outdir / "Contents" / "section0.xml"
    sec.write_text(
        sec.read_text(encoding="utf-8").replace("개요 문단입니다", "수정된 개요입니다"),
        encoding="utf-8",
    )

    edited = tmp_path / "edited.hwpx"
    pack_dir(outdir, edited, source=doc)

    r = validate_package(edited)
    assert r["ok"], r["errors"]
    assert "수정된 개요입니다" in HwpxPackage.open(edited).read_text("Contents/section0.xml")
