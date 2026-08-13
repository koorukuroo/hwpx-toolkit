"""텍스트 추출 테스트."""
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from core.analyze import extract_text
from tests.fixture import build_minimal_hwpx, SECTION_HEAD


def test_extract_plain_text(tmp_path):
    p = build_minimal_hwpx(tmp_path / "a.hwpx",
                           body_texts=["첫 문단", "둘째 문단"])
    out = extract_text(p)
    assert "첫 문단" in out and "둘째 문단" in out
    assert out.index("첫 문단") < out.index("둘째 문단")


def test_extract_includes_table_cells(tmp_path):
    p = build_minimal_hwpx(tmp_path / "t.hwpx", with_table=True)
    out = extract_text(p)
    assert "셀00" in out and "셀11" in out


def test_extract_markdown_table(tmp_path):
    p = build_minimal_hwpx(tmp_path / "t.hwpx", with_table=True)
    md = extract_text(p, fmt="markdown")
    assert "| 셀00 | 셀01 |" in md
    assert "| --- | --- |" in md


def _build_section_xml(marker_text):
    """Create a section XML with a single paragraph containing marker_text."""
    body = f'<hp:p id="1000000002" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>{marker_text}</hp:t></hp:run></hp:p>'
    return SECTION_HEAD + body + '</hs:sec>'


def test_extract_preserves_multi_section_order(tmp_path):
    """Regression test: verify extraction preserves order with 11+ sections."""
    # Build base fixture
    base_path = tmp_path / "multi.hwpx"
    build_minimal_hwpx(base_path, body_texts=["마커0"])

    # Open ZIP and add sections 1-11
    with zipfile.ZipFile(base_path, "r") as zf_in:
        entries = {info.filename: zf_in.read(info.filename) for info in zf_in.infolist()}

    # Add sections 1 through 11 with marker text
    for i in range(1, 12):
        section_xml = _build_section_xml(f"마커{i}").encode("utf-8")
        entries[f"Contents/section{i}.xml"] = section_xml

    # Update content.hpf to reference all sections
    content_hpf = entries["Contents/content.hpf"].decode("utf-8")
    manifest_items = "".join(
        f'<opf:item id="section{i}" href="Contents/section{i}.xml" media-type="application/xml"/>'
        for i in range(12)
    )
    spine_refs = "".join(f'<opf:itemref idref="section{i}"/>' for i in range(12))
    content_hpf = re.sub(
        r'<opf:manifest>.*?</opf:manifest>',
        f'<opf:manifest>{manifest_items}</opf:manifest>',
        content_hpf,
        flags=re.DOTALL
    )
    content_hpf = re.sub(
        r'<opf:spine>.*?</opf:spine>',
        f'<opf:spine>{spine_refs}</opf:spine>',
        content_hpf,
        flags=re.DOTALL
    )
    entries["Contents/content.hpf"] = content_hpf.encode("utf-8")

    # Write updated ZIP
    with zipfile.ZipFile(base_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for name, data in entries.items():
            ctype = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            zf_out.writestr(zipfile.ZipInfo(name), data, compress_type=ctype)

    # Extract and verify order
    out = extract_text(base_path)
    markers = [f"마커{i}" for i in range(12)]
    for marker in markers:
        assert marker in out, f"{marker} not found in output"

    # Verify numeric order (마커2 before 마커10, not lexicographic)
    idx2 = out.index("마커2")
    idx10 = out.index("마커10")
    assert idx2 < idx10, "Numeric order not preserved (마커2 should come before 마커10)"
