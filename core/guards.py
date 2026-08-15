"""검증 게이트 — Phase 1: 구조 검증(validate)."""
import re
import zipfile
import xml.etree.ElementTree as ET

from core.package import HwpxPackage, PackageError, section_names

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
    sections = section_names(names)
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
            if declared is not None:
                try:
                    declared_n = int(declared)
                except ValueError:
                    errors.append(
                        f"itemcnt-mismatch: {coll} itemCnt 비정수 '{declared}'")
                else:
                    if declared_n != len(children):
                        errors.append(
                            f"itemcnt-mismatch: {coll} itemCnt={declared}, 실제={len(children)}")
            defined[child] = {c.get("id") for c in children}

    for sec_name in sections:
        tree = trees.get(sec_name)
        if tree is None:
            continue
        used_by_attr = {attr: set() for _, _, attr in _ID_GROUPS}
        for el in tree.iter():
            for attr in used_by_attr:
                value = el.attrib.get(attr)
                if value is not None:
                    used_by_attr[attr].add(value)
        for coll, child, attr in _ID_GROUPS:
            used = used_by_attr[attr]
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


def check_package(path):
    base = validate_package(path)
    signals = {"char_border_bug": False, "vertical_misconvert": False}
    errors = list(base["errors"])
    warnings = list(base["warnings"])
    try:
        pkg = HwpxPackage.open(path)
        header = ET.fromstring(pkg.read("Contents/header.xml"))
        solid_ids = set()
        for bf in header.iter(f"{{{NS_HH}}}borderFill"):
            for edge in ("leftBorder", "rightBorder", "topBorder",
                         "bottomBorder"):
                e = bf.find(f"{{{NS_HH}}}{edge}")
                if e is not None and e.get("type") not in (None, "NONE"):
                    solid_ids.add(bf.get("id"))
                    break
        chars = list(header.iter(f"{{{NS_HH}}}charPr"))
        bordered = [c for c in chars
                    if c.get("borderFillIDRef") in solid_ids]
        if chars and len(bordered) / len(chars) > 0.5:
            signals["char_border_bug"] = True
            errors.append(
                "char-border-bug: charPr 과반이 실선 테두리 borderFill 참조 — "
                "fix 후 재검사 필요")
        vert = total = 0
        for name in section_names(pkg.names()):
            root = ET.fromstring(pkg.read(name))
            for sub in root.iter(f"{{{NS_HP}}}subList"):
                total += 1
                if sub.get("textDirection") == "VERTICAL":
                    vert += 1
        if total >= 4 and vert / total > 0.5:
            signals["vertical_misconvert"] = True
            errors.append(
                "vertical-misconvert: 셀 과반이 세로쓰기 — 오변환 여부 확인 필요")
    except (PackageError, ET.ParseError):
        pass  # 구조 오류는 validate가 이미 errors에 보고
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "signals": signals}


def guard_against_reference(output, reference, *, rules=None, max_growth=None):
    from core.analyze import extract_text
    errors, warnings = [], []
    out_pkg = HwpxPackage.open(output)
    ref_pkg = HwpxPackage.open(reference)
    sections = set(section_names(ref_pkg.names()))
    out_names = set(out_pkg.names())
    for name in ref_pkg.names():
        if name in sections:
            continue
        if name not in out_names:
            errors.append(f"entry-missing: {name}")
        elif out_pkg.read(name) != ref_pkg.read(name):
            errors.append(f"entry-changed: {name} (섹션 외 엔트리는 바이트 동일해야 함)")
    for name in out_pkg.names():
        if name not in set(ref_pkg.names()):
            errors.append(f"entry-added: {name}")

    text = extract_text(output)
    rules = rules or {}
    for kw in rules.get("require", []):
        if kw not in text:
            errors.append(f"require-missing: {kw}")
    for kw in rules.get("forbid", []):
        if kw in text:
            errors.append(f"forbid-found: {kw}")
    for pat in rules.get("forbid_regex", []):
        if re.search(pat, text):
            errors.append(f"forbid-regex-found: {pat}")

    ref_len = len(re.sub(r"\s", "", extract_text(reference)))
    out_len = len(re.sub(r"\s", "", text))
    growth = (out_len / ref_len) if ref_len else 1.0
    if max_growth is not None:
        if growth > max_growth:
            errors.append(f"growth-exceeded: {growth:.2f} > {max_growth}")
    elif growth > 1.05:
        warnings.append(
            f"growth-warning: 공백 제외 글자 수 {growth:.2f}배 — 쪽수 증가 위험")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "growth": round(growth, 3)}
