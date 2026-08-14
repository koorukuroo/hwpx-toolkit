import shutil
import zipfile
import pytest
from core.guards import validate_package
from core.package import PackageError
from core import template as template_mod
from core.template import build_from_template


def test_build_base_passes_validate(tmp_path):
    out = build_from_template(tmp_path / "doc.hwpx")
    r = validate_package(out)
    assert r["ok"], r["errors"]
    with zipfile.ZipFile(out) as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED


def test_title_is_patched_and_escaped(tmp_path):
    out = build_from_template(tmp_path / "doc.hwpx", title="계획 <2026> & 보고")
    with zipfile.ZipFile(out) as zf:
        hpf = zf.read("Contents/content.hpf").decode("utf-8")
    assert "무제" not in hpf
    assert "계획 &lt;2026&gt; &amp; 보고" in hpf


def test_section_override(tmp_path):
    from core.template import TEMPLATES_DIR
    skeleton = (TEMPLATES_DIR / "base/Contents/section0.xml").read_text("utf-8")
    custom = skeleton.replace("</hs:sec>",
        '<hp:p id="1000000002" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0"><hp:t>커스텀 본문</hp:t></hp:run></hp:p>'
        '</hs:sec>')
    out = build_from_template(tmp_path / "doc.hwpx", section_xml=custom)
    assert validate_package(out)["ok"]
    from core.analyze import extract_text
    assert "커스텀 본문" in extract_text(out)


def test_unknown_template_raises(tmp_path):
    with pytest.raises(PackageError):
        build_from_template(tmp_path / "x.hwpx", template="없는템플릿")


def test_stray_dotfiles_excluded_from_package(tmp_path, monkeypatch):
    templates_root = tmp_path / "templates"
    shutil.copytree(template_mod.TEMPLATES_DIR / "base", templates_root / "base")
    # Finder가 흘리는 .DS_Store 등 숨김 파일을 템플릿 트리 곳곳에 시뮬레이션
    (templates_root / "base" / ".DS_Store").write_bytes(b"junk")
    (templates_root / "base" / "Contents" / ".DS_Store").write_bytes(b"junk")
    monkeypatch.setattr(template_mod, "TEMPLATES_DIR", templates_root)

    out = build_from_template(tmp_path / "doc.hwpx")
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert not any(".DS_Store" in n for n in names)
    r = validate_package(out)
    assert r["ok"], r["errors"]


def test_missing_content_hpf_raises_package_error(tmp_path, monkeypatch):
    templates_root = tmp_path / "templates_no_hpf"
    shutil.copytree(template_mod.TEMPLATES_DIR / "base", templates_root / "base")
    (templates_root / "base" / "Contents" / "content.hpf").unlink()
    monkeypatch.setattr(template_mod, "TEMPLATES_DIR", templates_root)

    with pytest.raises(PackageError):
        build_from_template(tmp_path / "doc.hwpx", title="x")
