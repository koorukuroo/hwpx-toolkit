"""header.xml 스타일 관리 — charPr/paraPr 복제·변형, itemCnt 보정."""
import copy
import xml.etree.ElementTree as ET

from core.edit import EditError, NS, _XML_DECL

NS_HH = NS["hh"]
NS_HC = NS["hc"]


def _h(tag):
    return f"{{{NS_HH}}}{tag}"


# hh:charPr 스키마 상 offset 다음에 bold, italic이 이 순서로 온다. 삽입 위치는
# 러닝 인덱스가 아니라 매번 이 순서를 기준으로 "직전에 오는 태그 중 현재
# new에 실제로 존재하는 마지막 것" 바로 뒤로 계산한다 — 그래야 어떤 플래그가
# None(미지정)이라 건드리지 않았는지와 무관하게, 이미 있던 형제 요소(base에서
# 물려받은 bold 등) 뒤에 새 요소가 올바로 붙는다.
_CHARPR_TAG_ORDER = ("offset", "bold", "italic")


def _insert_index(new, tag):
    idx_in_order = _CHARPR_TAG_ORDER.index(tag)
    for prev_tag in reversed(_CHARPR_TAG_ORDER[:idx_in_order]):
        prev = new.find(_h(prev_tag))
        if prev is not None:
            return list(new).index(prev) + 1
    return len(new)


class HeaderEditor:
    def __init__(self, xml_bytes):
        self.root = ET.fromstring(xml_bytes)
        self.dirty = False

    @classmethod
    def from_package(cls, pkg):
        return cls(pkg.read("Contents/header.xml"))

    def _collection(self, coll, child):
        el = self.root.find(f".//{_h(coll)}")
        if el is None:
            raise EditError(f"header.xml에 {coll} 없음")
        return el, el.findall(_h(child))

    def _next_id(self, items):
        return str(max((int(c.get("id")) for c in items if c.get("id", "").isdigit()),
                       default=-1) + 1)

    def _find(self, items, base_id):
        for c in items:
            if c.get("id") == str(base_id):
                return c
        raise EditError(f"스타일 id 없음: {base_id}")

    def clone_char_pr(self, base_id, *, bold=None, italic=None, underline=None,
                      color=None, size_pt=None):
        coll, items = self._collection("charProperties", "charPr")
        new = copy.deepcopy(self._find(items, base_id))
        new.set("id", self._next_id(items))
        for flag, tag in ((bold, "bold"), (italic, "italic")):
            if flag is None:
                continue
            existing = new.find(_h(tag))
            if flag and existing is None:
                new.insert(_insert_index(new, tag), ET.Element(_h(tag)))
            elif not flag and existing is not None:
                new.remove(existing)
        if underline is not None:
            ul = new.find(_h("underline"))
            if ul is None:
                ul = ET.SubElement(new, _h("underline"),
                                   {"shape": "SOLID", "color": "#000000"})
            ul.set("type", "BOTTOM" if underline else "NONE")
        if color is not None:
            new.set("textColor", "#" + color.lstrip("#").upper())
        if size_pt is not None:
            new.set("height", str(int(round(float(size_pt) * 100))))
        coll.append(new)
        coll.set("itemCnt", str(len(coll.findall(_h("charPr")))))
        self.dirty = True
        return new.get("id")

    _ALIGN = {"left": "LEFT", "center": "CENTER", "right": "RIGHT",
              "justify": "JUSTIFY"}

    def clone_para_pr(self, base_id, *, align=None, line_spacing=None):
        coll, items = self._collection("paraProperties", "paraPr")
        new = copy.deepcopy(self._find(items, base_id))
        new.set("id", self._next_id(items))
        if align is not None:
            key = align.lower()
            if key not in self._ALIGN:
                raise EditError(f"정렬 값 오류: {align}")
            al = new.find(_h("align"))
            if al is None:
                al = ET.SubElement(new, _h("align"), {"vertical": "BASELINE"})
            al.set("horizontal", self._ALIGN[key])
        if line_spacing is not None:
            found = list(new.iter(_h("lineSpacing")))
            if not found:
                found = [ET.SubElement(new, _h("lineSpacing"),
                                       {"unit": "HWPUNIT"})]
            for ls in found:
                ls.set("type", "PERCENT")
                ls.set("value", str(int(line_spacing)))
        coll.append(new)
        coll.set("itemCnt", str(len(coll.findall(_h("paraPr")))))
        self.dirty = True
        return new.get("id")

    def serialize(self):
        return (_XML_DECL + ET.tostring(self.root, encoding="unicode")).encode("utf-8")
