"""템플릿 디렉터리 → HWPX 조립."""
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from core.package import PackageError

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_ENTRY_ORDER = ["mimetype", "version.xml", "settings.xml"]


def _ordered_names(names):
    def key(name):
        if name in _ENTRY_ORDER:
            return (0, _ENTRY_ORDER.index(name), name)
        if name.startswith("META-INF/"):
            return (1, 0, name)
        return (2, 0, name)
    return sorted(names, key=key)


def build_from_template(dst, *, template="base", section_xml=None, title=None):
    tdir = TEMPLATES_DIR / template
    if not tdir.is_dir():
        raise PackageError(f"템플릿 없음: {template}")
    files = {}
    for f in tdir.rglob("*"):
        if f.is_file():
            files[str(f.relative_to(tdir)).replace("\\", "/")] = f.read_bytes()
    if section_xml is not None:
        files["Contents/section0.xml"] = section_xml.encode("utf-8")
    if title is not None:
        hpf = files["Contents/content.hpf"].decode("utf-8")
        files["Contents/content.hpf"] = hpf.replace(
            "<opf:title>무제</opf:title>",
            f"<opf:title>{_xml_escape(title)}</opf:title>", 1).encode("utf-8")
    dst = Path(dst)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in _ordered_names(files):
            ctype = (zipfile.ZIP_STORED if name == "mimetype"
                     else zipfile.ZIP_DEFLATED)
            zf.writestr(zipfile.ZipInfo(name), files[name], compress_type=ctype)
    return dst
