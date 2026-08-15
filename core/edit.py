"""원본 보존 섹션 편집 엔진 — ET 기반, 변경 섹션만 write_replaced로 교체."""
import copy
import re
import xml.etree.ElementTree as ET

from core.package import HwpxPackage, PackageError

NS = {
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
}
for _prefix, _uri in NS.items():
    ET.register_namespace(_prefix, _uri)

_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def _q(tag):
    return f"{{{NS['hp']}}}{tag}"


class EditError(PackageError):
    pass


class SectionEditor:
    def __init__(self, xml_bytes, name="Contents/section0.xml"):
        self.name = name
        self.root = ET.fromstring(xml_bytes)
        self._modified = []          # 수정된 hp:p 요소들 (linesegarray 제거 대상)

    @classmethod
    def from_package(cls, pkg, name="Contents/section0.xml"):
        return cls(pkg.read(name), name)

    # ---- 공용 헬퍼 ----
    def _paras(self):
        return list(self.root.iter(_q("p")))

    def _direct_ts(self, p):
        return [t for run in p.findall(_q("run")) for t in run.findall(_q("t"))]

    def _para_text(self, p):
        return "".join(t.text or "" for t in self._direct_ts(p))

    def _max_id(self):
        best = 0
        for el in self.root.iter():
            v = el.get("id")
            if v and v.isdigit():
                best = max(best, int(v))
        return best

    def _mark(self, p):
        if p not in self._modified:
            self._modified.append(p)

    # ---- 문구 교체 (run 분할 대응) ----
    def replace_text(self, mapping):
        report = {"replaced": {}, "not_found": []}
        for old, new in mapping.items():
            total = 0
            for p in self._paras():
                ts = self._direct_ts(p)
                if not ts:
                    continue
                concat0 = "".join(t.text or "" for t in ts)
                starts = [m.start() for m in re.finditer(re.escape(old), concat0)]
                if not starts:
                    continue
                # 오른쪽 매치부터 처리하면 왼쪽 오프셋이 보존된다.
                # 각 이터레이션마다 현재(직전 이터레이션에서 이미 반영된) 텍스트를
                # 다시 읽어 pos를 재계산한다 — 동일 run 안에 여러 매치가 있을 때
                # 먼저 처리한(오른쪽) 치환 결과가 tail로 그대로 이어져야 하므로
                # 원본 텍스트를 캐시해 두면 안 된다.
                for i in reversed(starts):
                    j = i + len(old)
                    texts = [t.text or "" for t in ts]
                    pos = 0
                    first_done = False
                    for t, txt in zip(ts, texts):
                        s, e = pos, pos + len(txt)
                        pos = e
                        if e <= i or s >= j:
                            continue
                        head = txt[:i - s] if s < i else ""
                        tail = txt[j - s:] if e > j else ""
                        if not first_done:
                            t.text = head + new + tail
                            first_done = True
                        else:
                            t.text = tail
                    total += 1
                self._mark(p)
            report["replaced"][old] = total
            if total == 0:
                report["not_found"].append(old)
        return report

    # ---- 직렬화 ----
    def serialize(self):
        for p in self._modified:
            for seg in p.findall(_q("linesegarray")):
                p.remove(seg)
        body = ET.tostring(self.root, encoding="unicode")
        return (_XML_DECL + body).encode("utf-8")


def edit_file(src, dst, fn, section="Contents/section0.xml"):
    pkg = HwpxPackage.open(src)
    editor = SectionEditor.from_package(pkg, section)
    result = fn(editor)
    pkg.write_replaced(dst, {section: editor.serialize()})
    return result
