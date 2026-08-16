"""문서 복구 — check가 검출한 사고 패턴을 실제로 고친다."""
import copy

from core.errors import PackageError
from core.header import HeaderEditor, NS_HH
from core.package import HwpxPackage

_EDGES = ("leftBorder", "rightBorder", "topBorder", "bottomBorder")


def _h(tag):
    return f"{{{NS_HH}}}{tag}"


def _is_borderless(bf):
    for edge in _EDGES:
        e = bf.find(_h(edge))
        if e is not None and e.get("type") not in (None, "NONE"):
            return False
    return True


def fix_char_borders(src, dst):
    """글자마다 테두리가 그려지는 charPr borderFill 참조를 무테두리로 되돌린다."""
    pkg = HwpxPackage.open(src)
    he = HeaderEditor.from_package(pkg)
    coll = he.root.find(f".//{_h('borderFills')}")
    if coll is None:
        raise PackageError("header.xml에 borderFills 컬렉션이 없음")
    fills = coll.findall(_h("borderFill"))
    if not fills:
        raise PackageError("header.xml에 borderFill 정의가 없음")

    solid = {bf.get("id") for bf in fills if not _is_borderless(bf)}
    plain = next((bf.get("id") for bf in fills if _is_borderless(bf)), None)
    created = False
    if plain is None:
        new = copy.deepcopy(fills[0])
        next_id = max((int(b.get("id")) for b in fills
                       if (b.get("id") or "").isdigit()), default=0) + 1
        new.set("id", str(next_id))
        for edge in _EDGES:
            e = new.find(_h(edge))
            if e is not None:
                e.set("type", "NONE")
        coll.append(new)
        coll.set("itemCnt", str(len(coll.findall(_h("borderFill")))))
        plain = new.get("id")
        created = True

    fixed = 0
    for cp in he.root.iter(_h("charPr")):
        if cp.get("borderFillIDRef") in solid:
            cp.set("borderFillIDRef", plain)
            fixed += 1

    changed = bool(fixed or created)
    replacements = {"Contents/header.xml": he.serialize()} if changed else {}
    pkg.write_replaced(dst, replacements)
    return {"changed": changed, "fixed": fixed, "borderfill_id": plain,
            "created": created}
