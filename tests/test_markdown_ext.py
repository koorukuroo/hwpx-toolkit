"""마크다운 확장 문법 — 굵게/코드 run, 들여쓰기 목록, 쪽 나눔, 인용, 코드 블록, 그림, 머리말."""
import struct
import zipfile
import zlib

from core.analyze import extract_text, analyze_document
from core.guards import check_package
from core.markdown import parse_markdown, render_document, render_to_section, first_heading, split_front_matter
from core.template import build_from_template


def _png(w=4, h=2):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_inline_bold_and_code_become_runs(tmp_path):
    xml = render_to_section("본문 **굵게** 와 `코드` 입니다.")
    assert '<hp:run charPrIDRef="5"><hp:t>굵게</hp:t></hp:run>' in xml
    assert '<hp:run charPrIDRef="6"><hp:t>코드</hp:t></hp:run>' in xml
    assert "**" not in xml and "`" not in xml
    out = build_from_template(tmp_path / "b.hwpx", section_xml=xml)
    assert check_package(out)["ok"]
    assert "본문 굵게 와 코드 입니다." in extract_text(out)


def test_report_template_uses_its_own_bold_ids():
    xml = render_to_section("**굵게**", template="report")
    assert 'charPrIDRef="7"' in xml


def test_nested_lists_by_indent(tmp_path):
    md = "- 상위\n  - 하위\n    - 세째\n- 다시 상위\n\n1. 하나\n   1. 하나의 하나\n"
    blocks = parse_markdown(md)
    assert blocks[0]["levels"] == [0, 1, 2, 0] and blocks[1]["levels"] == [0, 1]
    xml = render_to_section(md)
    assert 'paraPrIDRef="4"' in xml and 'paraPrIDRef="6"' in xml and 'paraPrIDRef="7"' in xml
    out = build_from_template(tmp_path / "l.hwpx", section_xml=xml)
    assert check_package(out)["ok"]
    text = extract_text(out)
    assert "• 상위" in text and "- 하위" in text and "· 세째" in text and "1. 하나의 하나" in text


def test_hr_becomes_page_break_on_next_block(tmp_path):
    md = "첫 쪽\n\n---\n\n둘째 쪽\n\n---\n\n| a |\n|---|\n| 1 |\n"
    xml = render_to_section(md)
    assert xml.count('pageBreak="1"') == 2
    out = build_from_template(tmp_path / "pb.hwpx", section_xml=xml)
    assert check_package(out)["ok"]
    assert "둘째 쪽" in extract_text(out)


def test_quote_and_code_block(tmp_path):
    md = "> 인용문\n> 둘째 줄\n\n```python\nprint('x')\n  indented\n```\n"
    blocks = parse_markdown(md)
    assert blocks[0] == {"type": "quote", "text": "인용문 둘째 줄"}
    assert blocks[1] == {"type": "code", "lines": ["print('x')", "  indented"]}
    xml = render_to_section(md)
    assert 'paraPrIDRef="8"' in xml and 'paraPrIDRef="9"' in xml and 'charPrIDRef="6"' in xml
    out = build_from_template(tmp_path / "q.hwpx", section_xml=xml)
    assert check_package(out)["ok"]
    text = extract_text(out)
    assert "인용문 둘째 줄" in text and "print('x')" in text and "  indented" in text


def test_image_is_embedded_and_registered(tmp_path):
    (tmp_path / "pic.png").write_bytes(_png(400, 100))
    md = "# 제목\n\n![그림 설명](pic.png)\n\n본문\n"
    section, assets, manifest = render_document(md, base_dir=tmp_path)
    assert list(assets) == ["BinData/image1.png"] and 'id="image1"' in manifest[0]
    out = build_from_template(tmp_path / "img.hwpx", section_xml=section,
                              extra_files=assets, manifest_items=manifest)
    r = check_package(out)
    assert r["ok"], r["errors"]
    with zipfile.ZipFile(out) as zf:
        assert "BinData/image1.png" in zf.namelist()
        assert 'href="BinData/image1.png"' in zf.read("Contents/content.hpf").decode()
    assert "그림 설명" in extract_text(out)
    assert 'instid="0"' not in section


def test_image_wider_than_text_width_is_scaled(tmp_path):
    (tmp_path / "wide.png").write_bytes(_png(3000, 300))
    section, _, _ = render_document("![](wide.png)", base_dir=tmp_path)
    import re
    sz = re.search(r'<hp:sz width="(\d+)" widthRelTo="ABSOLUTE" height="(\d+)"', section)
    assert int(sz.group(1)) == 42520 and int(sz.group(2)) == 4252


def test_missing_image_becomes_placeholder_paragraph(tmp_path):
    section, assets, manifest = render_document("![x](없음.png)", base_dir=tmp_path)
    assert not assets and not manifest and "[그림 누락: 없음.png]" in section


def test_front_matter_title_and_removal():
    md = "---\ntitle: 문서 제목\nauthor: 홍길동\n---\n# 본문 제목\n\n내용\n"
    assert split_front_matter(md)[0] == {"title": "문서 제목", "author": "홍길동"}
    assert first_heading(md) == "문서 제목"
    blocks = parse_markdown(md)
    assert blocks[0] == {"type": "heading", "level": 1, "text": "본문 제목"}
    assert first_heading("---\n\n본문") is None     # 구분선만 있는 경우는 머리말이 아님


def test_cli_new_with_image(tmp_path, capsys):
    import json
    from scripts import hwpx as cli
    (tmp_path / "p.png").write_bytes(_png())
    md = tmp_path / "doc.md"
    md.write_text("# 제목\n\n![](p.png)\n\n**굵게** 본문\n", encoding="utf-8")
    out = tmp_path / "doc.hwpx"
    code = cli.main(["new", str(md), "-o", str(out)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0 and payload["ok"]
    assert analyze_document(out)["sections"][0]["paragraphCount"] >= 3
    with zipfile.ZipFile(out) as zf:
        assert "BinData/image1.png" in zf.namelist()
