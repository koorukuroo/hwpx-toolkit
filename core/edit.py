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


class EditContext:
    """섹션/헤더를 넘나드는 편집 세션 상태 — 추가 교체·신규 엔트리를 모은다."""

    def __init__(self, pkg, section_editor):
        self.pkg = pkg
        self.section = section_editor
        self.header = None            # Task 3에서 HeaderEditor
        self.additions = {}
        self.replacements = {}

    def stage_replacement(self, name, data):
        self.replacements[name] = data

    def stage_addition(self, name, data):
        self.additions[name] = data


class SectionEditor:
    def __init__(self, xml_bytes, name="Contents/section0.xml"):
        self.name = name
        self.root = ET.fromstring(xml_bytes)
        self._modified = []          # 수정된 hp:p 요소들 (linesegarray 제거 대상)
        self.ctx = None              # edit_file이 EditContext를 주입

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
            if not old:
                raise EditError("빈 문자열은 교체 대상이 될 수 없음")
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

    # ---- 표 탐색 ----
    def _tables(self):
        # 최상위(문단 직속) 표만 문서 순서대로 나열한다 — core.analyze의
        # fill_targets/extract_slots와 번호 체계를 맞추기 위함. 셀 내부에
        # 중첩된 표는 인덱스로 접근할 수 없다(v1 미지원, 의도된 동작).
        return [tbl for p in self.root.findall(_q("p"))
                for run in p.findall(_q("run"))
                for tbl in run.findall(_q("tbl"))]

    def _get_table(self, table_index):
        tbls = self._tables()
        if not 0 <= table_index < len(tbls):
            raise EditError(f"표 없음: index {table_index} (표 {len(tbls)}개)")
        return tbls[table_index]

    def _reject_spans(self, tbl):
        for span in tbl.iter(_q("cellSpan")):
            if span.get("colSpan") != "1" or span.get("rowSpan") != "1":
                raise EditError("병합 셀(rowSpan/colSpan)이 있는 표는 구조 편집 불가")

    def _find_cell(self, table_index, row, col):
        tbl = self._get_table(table_index)
        for tc in tbl.iter(_q("tc")):
            addr = tc.find(_q("cellAddr"))
            if addr is not None and int(addr.get("rowAddr")) == row \
                    and int(addr.get("colAddr")) == col:
                return tbl, tc
        raise EditError(f"셀 없음: 표 {table_index} ({row},{col})")

    def _set_cell_content(self, tc, text):
        sub = tc.find(_q("subList"))
        if sub is None:
            raise EditError("셀에 subList 없음")
        paras = sub.findall(_q("p"))
        if not paras:
            raise EditError("셀에 문단 없음")
        first = paras[0]
        run = first.find(_q("run"))
        if run is None:
            raise EditError("셀 문단에 run 없음")
        t = run.find(_q("t"))
        if t is None:
            t = ET.SubElement(run, _q("t"))
        t.text = text
        for other in self._direct_ts(first):
            if other is not t:
                other.text = ""
        for extra in paras[1:]:
            for tt in self._direct_ts(extra):
                tt.text = ""
            self._mark(extra)
        self._mark(first)

    # ---- 셀/행 편집 ----
    def set_cell_text(self, table_index, row, col, text):
        _, tc = self._find_cell(table_index, row, col)
        self._set_cell_content(tc, text)

    def add_row(self, table_index, cells):
        tbl = self._get_table(table_index)
        self._reject_spans(tbl)
        trs = tbl.findall(_q("tr"))
        if not trs:
            raise EditError("행이 없는 표")
        last = trs[-1]
        n_cols = len(last.findall(_q("tc")))
        if len(cells) != n_cols:
            raise EditError(f"열 수 불일치: 값 {len(cells)}개, 표 {n_cols}열")
        new_tr = copy.deepcopy(last)
        next_id = self._max_id() + 1
        new_row = len(trs)
        row_height = 0
        for tc, value in zip(new_tr.findall(_q("tc")), cells):
            addr = tc.find(_q("cellAddr"))
            addr.set("rowAddr", str(new_row))
            sub = tc.find(_q("subList"))
            for p in sub.findall(_q("p")):
                p.set("id", str(next_id))
                next_id += 1
                for seg in p.findall(_q("linesegarray")):
                    p.remove(seg)
            self._set_cell_content(tc, value)
            sz = tc.find(_q("cellSz"))
            if sz is not None:
                row_height = max(row_height, int(sz.get("height", "0")))
        tbl.insert(list(tbl).index(last) + 1, new_tr)
        tbl.set("rowCnt", str(len(trs) + 1))
        tblsz = tbl.find(_q("sz"))
        if tblsz is not None and row_height:
            tblsz.set("height", str(int(tblsz.get("height", "0")) + row_height))

    def del_row(self, table_index, row):
        tbl = self._get_table(table_index)
        self._reject_spans(tbl)
        trs = tbl.findall(_q("tr"))
        target = None
        for tr in trs:
            tc = tr.find(_q("tc"))
            addr = tc.find(_q("cellAddr")) if tc is not None else None
            if addr is not None and int(addr.get("rowAddr")) == row:
                target = tr
                break
        if target is None:
            raise EditError(f"행 없음: {row}")
        first_tc = target.find(_q("tc"))
        cellsz = first_tc.find(_q("cellSz")) if first_tc is not None else None
        removed_h = int(cellsz.get("height", "0")) if cellsz is not None else 0
        tbl.remove(target)
        tbl.set("rowCnt", str(len(trs) - 1))
        for tr in tbl.findall(_q("tr")):
            for tc in tr.findall(_q("tc")):
                addr = tc.find(_q("cellAddr"))
                r = int(addr.get("rowAddr"))
                if r > row:
                    addr.set("rowAddr", str(r - 1))
        tblsz = tbl.find(_q("sz"))
        if tblsz is not None and removed_h:
            tblsz.set("height",
                      str(max(int(tblsz.get("height", "0")) - removed_h, 0)))

    # ---- 문단 추가 ----
    def add_para_after(self, anchor_text, text):
        parents = {c: par for par in self.root.iter() for c in par}

        def _in_table_cell(p):
            node = p
            while True:
                par = parents.get(node)
                if par is None:
                    return False
                if par.tag == _q("subList"):
                    return True
                node = par

        anchor = None
        for p in self._paras():
            if _in_table_cell(p):
                continue  # 표 셀 내부 문단은 기준으로 사용하지 않음 (본문만)
            if anchor_text in self._para_text(p):
                for run in p.findall(_q("run")):
                    if (run.find(_q("secPr")) is not None
                            or run.find(_q("tbl")) is not None
                            or run.find(_q("pic")) is not None):
                        raise EditError(
                            "기준 문단에 secPr/표/그림이 있어 불가 — "
                            "일반 텍스트 문단을 기준으로 지정")
                anchor = p
                break
        if anchor is None:
            raise EditError(f"본문에서 기준 문구를 찾지 못함: {anchor_text}")
        parent = parents.get(anchor)
        if parent is None:
            raise EditError("기준 문단의 부모를 찾을 수 없음")
        new_p = copy.deepcopy(anchor)
        new_p.set("id", str(self._max_id() + 1))
        ts = self._direct_ts(new_p)
        ts[0].text = text
        for t in ts[1:]:
            t.text = ""
        for seg in new_p.findall(_q("linesegarray")):
            new_p.remove(seg)
        parent.insert(list(parent).index(anchor) + 1, new_p)
        self._mark(new_p)

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
    ctx = EditContext(pkg, editor)
    editor.ctx = ctx
    result = fn(editor)
    replacements = {section: editor.serialize()}
    if ctx.header is not None and ctx.header.dirty:
        replacements["Contents/header.xml"] = ctx.header.serialize()
    replacements.update(ctx.replacements)
    pkg.write_replaced(dst, replacements, additions=ctx.additions)
    return result
