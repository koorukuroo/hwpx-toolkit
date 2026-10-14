"""템플릿 디렉터리 → HWPX 조립."""
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from core.package import PackageError

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_ENTRY_ORDER = ["mimetype", "version.xml", "settings.xml"]

# 템플릿 디렉터리에는 있지만 OWPML 패키지 내용이 아닌 툴킷 메타 파일 —
# manifest.xml에 선언되지 않으므로 조립 시 zip에서 제외한다.
TEMPLATE_META_FILES = {"styles.json"}


def _ordered_names(names):
    def key(name):
        if name in _ENTRY_ORDER:
            return (0, _ENTRY_ORDER.index(name), name)
        if name.startswith("META-INF/"):
            return (1, 0, name)
        return (2, 0, name)
    return sorted(names, key=key)


def build_from_template(dst, *, template="base", section_xml=None, title=None,
                        extra_files=None, manifest_items=None):
    """템플릿 파일 + section0.xml(+ 추가 엔트리/manifest item) → HWPX. 그림(BinData)을
    넣을 때는 extra_files={"BinData/image1.png": bytes}, manifest_items=[opf:item XML]."""
    tdir = TEMPLATES_DIR / template
    if not tdir.is_dir():
        raise PackageError(f"템플릿 없음: {template}")
    files = {}
    for f in tdir.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(tdir)
        if any(part.startswith(".") for part in rel.parts):
            continue  # .DS_Store 등 숨김/메타 파일은 패키지에서 제외
        rel_str = str(rel).replace("\\", "/")
        if rel_str in TEMPLATE_META_FILES:
            continue  # styles.json 등 툴킷 전용 메타 파일은 패키지에서 제외
        files[rel_str] = f.read_bytes()
    if section_xml is not None:
        files["Contents/section0.xml"] = section_xml.encode("utf-8")
    for name, data in (extra_files or {}).items():
        files[name] = data
    if manifest_items:
        if "Contents/content.hpf" not in files:
            raise PackageError(f"템플릿에 content.hpf 없음: {template}")
        hpf = files["Contents/content.hpf"].decode("utf-8")
        files["Contents/content.hpf"] = hpf.replace(
            "</opf:manifest>", "".join(manifest_items) + "</opf:manifest>", 1).encode("utf-8")
    if title is not None:
        if "Contents/content.hpf" not in files:
            raise PackageError(f"템플릿에 content.hpf 없음: {template}")
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
