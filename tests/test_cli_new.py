import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import importlib
hwpx_cli = importlib.import_module("hwpx")


def test_new_from_markdown(tmp_path, capsys):
    md = tmp_path / "in.md"
    md.write_text("# 제목\n\n본문입니다.\n", encoding="utf-8")
    out = tmp_path / "out.hwpx"
    rc = hwpx_cli.main(["new", str(md), "-o", str(out)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    assert out.exists()
    from core.analyze import extract_text
    assert "본문입니다" in extract_text(out)


def test_new_title_defaults_to_first_heading(tmp_path, capsys):
    md = tmp_path / "in.md"
    md.write_text("# 보고서 제목\n\n내용\n", encoding="utf-8")
    out = tmp_path / "out.hwpx"
    hwpx_cli.main(["new", str(md), "-o", str(out)])
    capsys.readouterr()
    import zipfile
    with zipfile.ZipFile(out) as zf:
        assert "보고서 제목" in zf.read("Contents/content.hpf").decode("utf-8")


def test_build_with_section_file(tmp_path, capsys):
    from core import owpml
    first, sec_open = owpml.load_skeleton()
    alloc = owpml.IdAllocator()
    xml = owpml.sec_document(first, [owpml.text_para("빌드 본문", alloc)], sec_open)
    section = tmp_path / "sec.xml"
    section.write_text(xml, encoding="utf-8")
    out = tmp_path / "out.hwpx"
    rc = hwpx_cli.main(["build", "--section", str(section), "-o", str(out)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    from core.analyze import extract_text
    assert "빌드 본문" in extract_text(out)


def test_new_missing_input_returns_2(tmp_path, capsys):
    rc = hwpx_cli.main(["new", str(tmp_path / "없음.md"),
                        "-o", str(tmp_path / "o.hwpx")])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2 and payload["ok"] is False
