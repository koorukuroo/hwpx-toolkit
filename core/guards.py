"""검증 게이트 — Phase 1: 구조 검증(validate)."""
import re
import zipfile
import xml.etree.ElementTree as ET

from core.package import HwpxPackage, PackageError

REQUIRED_ENTRIES = ("mimetype", "version.xml", "Contents/header.xml",
                    "Contents/content.hpf")
MIMETYPE_VALUE = b"application/hwp+zip"

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

# header.xml의 (컬렉션 태그, 자식 태그, 섹션에서 참조하는 속성명)
_ID_GROUPS = [
    ("charProperties", "charPr", "charPrIDRef"),
    ("paraProperties", "paraPr", "paraPrIDRef"),
    ("borderFills", "borderFill", "borderFillIDRef"),
]


def validate_package(path):
    errors, warnings = [], []
    try:
        pkg = HwpxPackage.open(path)
    except PackageError as e:
        return {"ok": False, "errors": [f"zip-invalid: {e}"], "warnings": []}

    names = pkg.names()
    for req in REQUIRED_ENTRIES:
        if req not in names:
            errors.append(f"required-missing: {req}")
    sections = sorted(n for n in names
                      if re.fullmatch(r"Contents/section\d+\.xml", n))
    if not sections:
        errors.append("required-missing: Contents/section*.xml")

    if "mimetype" in names:
        if names[0] != "mimetype":
            errors.append("mimetype-not-first: mimetype이 첫 엔트리가 아님")
        with zipfile.ZipFile(pkg.path) as zf:
            info = zf.getinfo("mimetype")
            if info.compress_type != zipfile.ZIP_STORED:
                errors.append("mimetype-not-stored: STORED가 아님")
        if pkg.read("mimetype") != MIMETYPE_VALUE:
            errors.append("mimetype-bad-content: application/hwp+zip 아님")

    trees = {}
    for name in names:
        if not (name.endswith(".xml") or name.endswith(".hpf")):
            continue
        try:
            trees[name] = ET.fromstring(pkg.read(name))
        except ET.ParseError as e:
            errors.append(f"xml-malformed: {name}: {e}")

    header = trees.get("Contents/header.xml")
    defined = {}
    if header is not None:
        for coll, child, _ in _ID_GROUPS:
            coll_el = header.find(f".//{{{NS_HH}}}{coll}")
            if coll_el is None:
                defined[child] = set()
                continue
            children = coll_el.findall(f"{{{NS_HH}}}{child}")
            declared = coll_el.get("itemCnt")
            if declared is not None and int(declared) != len(children):
                errors.append(
                    f"itemcnt-mismatch: {coll} itemCnt={declared}, 실제={len(children)}")
            defined[child] = {c.get("id") for c in children}

    for sec_name in sections:
        tree = trees.get(sec_name)
        if tree is None:
            continue
        for coll, child, attr in _ID_GROUPS:
            used = set(re.findall(rf'{attr}="(\d+)"', pkg.read_text(sec_name)))
            missing = used - defined.get(child, set())
            if header is not None and missing:
                errors.append(
                    f"dangling-ref: {sec_name} {attr} 미정의 id {sorted(missing)}")
        first_p = tree.find(f"{{{NS_HP}}}p")
        if first_p is not None:
            first_run = first_p.find(f"{{{NS_HP}}}run")
            has_secpr = (first_run is not None and
                         first_run.find(f"{{{NS_HP}}}secPr") is not None)
            if not has_secpr:
                errors.append(f"secpr-missing: {sec_name} 첫 문단 첫 런에 secPr 없음")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
