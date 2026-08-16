"""원본 보존 섹션 편집 엔진 — ET 기반, 변경 섹션만 write_replaced로 교체."""
import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from core.errors import PackageError, EditError  # noqa: F401 (재노출)
from core.package import HwpxPackage

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


_PAGE_SIZES = {"a4": (59528, 84186), "a3": (84186, 119055),
               "b5": (51023, 72283), "letter": (61199, 79370)}


def _mm(v):
    return str(int(round(float(v) * 283.5)))


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

    def _cell_grid(self, tbl):
        grid = {}
        for tr in tbl.findall(_q("tr")):
            for tc in tr.findall(_q("tc")):
                addr = tc.find(_q("cellAddr"))
                grid[(int(addr.get("rowAddr")), int(addr.get("colAddr")))] = (tr, tc)
        return grid

    def merge_cells(self, table_index, row, col, row2, col2):
        tbl = self._get_table(table_index)
        self._reject_spans(tbl)
        if row2 < row or col2 < col:
            raise EditError("범위는 (row,col) ≤ (row2,col2)")
        grid = self._cell_grid(tbl)
        cells = []
        for r in range(row, row2 + 1):
            for c in range(col, col2 + 1):
                if (r, c) not in grid:
                    raise EditError(f"셀 없음: ({r},{c})")
                cells.append(grid[(r, c)])
        _, anchor = grid[(row, col)]
        width = sum(int(grid[(row, c)][1].find(_q("cellSz")).get("width"))
                    for c in range(col, col2 + 1))
        height = sum(int(grid[(r, col)][1].find(_q("cellSz")).get("height"))
                     for r in range(row, row2 + 1))
        extra_text = []
        for tr, tc in cells:
            if tc is anchor:
                continue
            sub = tc.find(_q("subList"))
            if sub is not None:
                for p in sub.findall(_q("p")):
                    t = self._para_text(p)
                    if t:
                        extra_text.append(t)
            tr.remove(tc)
        if extra_text:
            anchor_sub = anchor.find(_q("subList"))
            anchor_texts = [self._para_text(p) for p in anchor_sub.findall(_q("p"))]
            base = " ".join(t for t in anchor_texts if t)
            self._set_cell_content(anchor, " ".join([base] + extra_text).strip())
        span = anchor.find(_q("cellSpan"))
        span.set("colSpan", str(col2 - col + 1))
        span.set("rowSpan", str(row2 - row + 1))
        sz = anchor.find(_q("cellSz"))
        sz.set("width", str(width))
        sz.set("height", str(height))
        self._mark(anchor.find(f"{_q('subList')}/{_q('p')}"))

    def add_col(self, table_index, cells, *, at=None):
        tbl = self._get_table(table_index)
        self._reject_spans(tbl)
        trs = tbl.findall(_q("tr"))
        if len(cells) != len(trs):
            raise EditError(f"행 수 불일치: 값 {len(cells)}개, 표 {len(trs)}행")
        n_cols = int(tbl.get("colCnt"))
        pos = n_cols if at is None else int(at)
        if not 0 <= pos <= n_cols:
            raise EditError(f"열 위치 범위 밖: {at}")
        next_id = self._max_id() + 1
        added_width = 0
        for tr, value in zip(trs, cells):
            tcs = tr.findall(_q("tc"))
            template = tcs[-1] if pos >= len(tcs) else tcs[pos]
            new_tc = copy.deepcopy(template)
            for p in new_tc.find(_q("subList")).findall(_q("p")):
                p.set("id", str(next_id))
                next_id += 1
                for seg in p.findall(_q("linesegarray")):
                    p.remove(seg)
            self._set_cell_content(new_tc, value)
            insert_at = list(tr).index(tcs[pos]) if pos < len(tcs) else list(tr).index(tcs[-1]) + 1
            tr.insert(insert_at, new_tc)
            for tc in tr.findall(_q("tc")):
                addr = tc.find(_q("cellAddr"))
                c = int(addr.get("colAddr"))
                if tc is new_tc:
                    addr.set("colAddr", str(pos))
                elif c >= pos:
                    addr.set("colAddr", str(c + 1))
            added_width = int(new_tc.find(_q("cellSz")).get("width"))
        tbl.set("colCnt", str(n_cols + 1))
        tblsz = tbl.find(_q("sz"))
        if tblsz is not None:
            tblsz.set("width", str(int(tblsz.get("width", "0")) + added_width))

    # ---- 대상 문단 선택 ----
    def _body_paras(self):
        parents = {c: par for par in self.root.iter() for c in par}
        out = []
        for p in self._paras():
            node, in_cell = p, False
            while node is not None:
                node = parents.get(node)
                if node is not None and node.tag == _q("subList"):
                    in_cell = True
                    break
            if not in_cell:
                out.append(p)
        return out

    def _target_para(self, after=None, index=None):
        body = self._body_paras()
        if not body:
            raise EditError("본문 문단 없음")
        if after is not None:
            for p in body:
                if after in self._para_text(p):
                    return p
            raise EditError(f"본문에서 기준 문구를 찾지 못함: {after}")
        if index is None:
            index = -1
        try:
            return body[index]
        except IndexError:
            raise EditError(f"문단 인덱스 범위 밖: {index}")

    def _require_header(self):
        if self.ctx is None or self.ctx.header is None:
            raise EditError("헤더 편집기 없음 — edit_file 경유 필요")
        return self.ctx.header

    # ---- 서식 ----
    def set_text_style(self, *, after=None, index=None, bold=None, italic=None,
                       underline=None, color=None, size_pt=None):
        if bold is None and italic is None and underline is None \
                and color is None and size_pt is None:
            raise EditError("변경할 서식 항목이 없음")
        he = self._require_header()
        p = self._target_para(after, index)
        cache = {}
        for run in p.findall(_q("run")):
            base = run.get("charPrIDRef", "0")
            if base not in cache:
                cache[base] = he.clone_char_pr(base, bold=bold, italic=italic,
                                               underline=underline, color=color,
                                               size_pt=size_pt)
            run.set("charPrIDRef", cache[base])
        self._mark(p)

    def set_para_style(self, *, after=None, index=None, align=None,
                       line_spacing=None):
        if align is None and line_spacing is None:
            raise EditError("변경할 서식 항목이 없음")
        he = self._require_header()
        p = self._target_para(after, index)
        new_id = he.clone_para_pr(p.get("paraPrIDRef", "0"), align=align,
                                  line_spacing=line_spacing)
        p.set("paraPrIDRef", new_id)
        self._mark(p)

    # ---- 페이지 설정 ----
    def _first_run(self):
        p = self.root.find(_q("p"))
        run = p.find(_q("run")) if p is not None else None
        if run is None or run.find(_q("secPr")) is None:
            raise EditError("첫 문단 첫 run에 secPr 없음")
        return p, run

    def set_page(self, *, orientation=None, size=None, margins_mm=None):
        p, run = self._first_run()
        pagepr = run.find(_q("secPr")).find(_q("pagePr"))
        if pagepr is None:
            raise EditError("pagePr 없음")
        if size is not None:
            if size.lower() not in _PAGE_SIZES:
                raise EditError(f"지원하지 않는 용지: {size}")
            w, h = _PAGE_SIZES[size.lower()]
            pagepr.set("width", str(w))
            pagepr.set("height", str(h))
        if orientation is not None:
            if orientation not in ("portrait", "landscape"):
                raise EditError(f"orientation 값 오류: {orientation}")
            w, h = int(pagepr.get("width")), int(pagepr.get("height"))
            # hp:pagePr@landscape는 90° 회전 플래그이고 폭>높이도 회전이라,
            # 실제 방향은 둘의 XOR이다 (한컴 실물 검증, 2026-08-17).
            rotated = pagepr.get("landscape") == "NARROWLY"
            is_landscape = (w > h) != rotated
            if is_landscape != (orientation == "landscape"):
                pagepr.set("width", str(h))
                pagepr.set("height", str(w))
        if margins_mm:
            m = pagepr.find(_q("margin"))
            if m is None:
                raise EditError("margin 없음")
            for k, v in margins_mm.items():
                if k not in ("left", "right", "top", "bottom", "header",
                             "footer", "gutter"):
                    raise EditError(f"여백 키 오류: {k}")
                m.set(k, _mm(v))
        self._mark(p)

    def set_columns(self, count, gap_mm=None):
        p, run = self._first_run()
        col = run.find(f"{_q('ctrl')}/{_q('colPr')}")
        if col is None:
            raise EditError("colPr 없음")
        if int(count) < 1:
            raise EditError("단 수는 1 이상")
        col.set("colCount", str(int(count)))
        if gap_mm is not None:
            run.find(_q("secPr")).set("spaceColumns", _mm(gap_mm))
        self._mark(p)

    def set_page_break(self, after, on=True):
        p = self._target_para(after=after)
        p.set("pageBreak", "1" if on else "0")
        self._mark(p)

    _HF_KINDS = ("header", "footer")

    def _find_hf(self, kind):
        return list(self.root.iter(_q(kind)))

    def _hf_para(self, hf):
        return hf.find(f"{_q('subList')}/{_q('p')}")

    def set_header_footer(self, kind, text, *, align=None):
        if kind not in self._HF_KINDS:
            raise EditError(f"kind는 header|footer: {kind}")
        existing = self._find_hf(kind)
        p0, run = self._first_run()
        if existing:
            hp = self._hf_para(existing[0])
            ts = self._direct_ts(hp)
            if not ts:
                ET.SubElement(hp.find(_q("run")), _q("t"))
                ts = self._direct_ts(hp)
            ts[0].text = text
            for t in ts[1:]:
                t.text = ""
            target_p = hp
        else:
            ctrl = ET.Element(_q("ctrl"))
            hf = ET.SubElement(ctrl, _q(kind), {"id": "0", "applyPageType": "BOTH"})
            sub = ET.SubElement(hf, _q("subList"), {
                "id": "", "textDirection": "HORIZONTAL", "lineWrap": "BREAK",
                "vertAlign": "TOP" if kind == "header" else "BOTTOM",
                "linkListIDRef": "0", "linkListNextIDRef": "0",
                "textWidth": "0", "textHeight": "0", "hasTextRef": "0",
                "hasNumRef": "0"})
            hp = ET.SubElement(sub, _q("p"), {
                "id": str(self._max_id() + 1), "paraPrIDRef": "0",
                "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0",
                "merged": "0"})
            r = ET.SubElement(hp, _q("run"), {"charPrIDRef": "0"})
            t = ET.SubElement(r, _q("t"))
            t.text = text
            # secPr, colPr ctrl 뒤에 삽입
            idx = max(i for i, c in enumerate(list(run))
                      if c.tag in (_q("secPr"), _q("ctrl"))) + 1
            run.insert(idx, ctrl)
            target_p = hp
            # run 구조가 바뀐 p0(첫 문단)도 linesegarray가 stale해지므로 유지
            self._mark(p0)
        if align is not None:
            he = self._require_header()
            target_p.set("paraPrIDRef",
                         he.clone_para_pr(target_p.get("paraPrIDRef", "0"),
                                          align=align))
        self._mark(target_p)

    def _parents_map(self):
        return {c: par for par in self.root.iter() for c in par}

    def remove_header_footer(self, kind):
        if kind not in self._HF_KINDS:
            raise EditError(f"kind는 header|footer: {kind}")
        parents = self._parents_map()
        removed = 0
        for ctrl in list(self.root.iter(_q("ctrl"))):
            if ctrl.find(_q(kind)) is None:
                continue
            owner_run = parents.get(ctrl)
            if owner_run is None:
                continue
            owner_run.remove(ctrl)
            removed += 1
            owner_p = self._owner_para(owner_run, parents)
            self._mark(owner_p)
        if not removed:
            raise EditError(f"{kind} 없음")

    def set_page_number(self, *, where="footer", align="center"):
        if where not in self._HF_KINDS:
            raise EditError(f"where는 header|footer: {where}")
        if not self._find_hf(where):
            self.set_header_footer(where, "", align=align)
        hf = self._find_hf(where)[0]
        hp = self._hf_para(hf)
        if hp.find(f".//{_q('autoNum')}") is not None:
            return
        r = ET.SubElement(hp, _q("run"), {"charPrIDRef": "0"})
        ctrl = ET.SubElement(r, _q("ctrl"))
        auto = ET.SubElement(ctrl, _q("autoNum"), {"num": "1", "numType": "PAGE"})
        ET.SubElement(auto, _q("autoNumFormat"), {
            "type": "DIGIT", "userChar": "", "prefixChar": "",
            "suffixChar": "", "supscript": "0"})
        ET.SubElement(r, _q("t"))
        self._mark(hp)

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

    # ---- 이미지 ----
    def _pics(self):
        return list(self.root.iter(_q("pic")))

    def _get_pic(self, index):
        pics = self._pics()
        if not 0 <= index < len(pics):
            raise EditError(f"그림 없음: index {index} (그림 {len(pics)}개)")
        return pics[index]

    def _fresh_bin_id(self):
        from core import images
        bin_id, prefix = images.next_bin_id(self.ctx.pkg)
        while any(n.startswith(prefix + ".") for n in self.ctx.additions):
            n = int(bin_id[len("image"):]) + 1
            bin_id, prefix = f"image{n}", f"BinData/image{n}"
        return bin_id, prefix

    def _stage_new_image(self, data, ext):
        """새 이미지 바이너리를 addition으로 등록하고 content.hpf manifest에
        추가한 뒤 새 bin_id를 반환한다. insert_image/replace_image 공용."""
        from core import images
        bin_id, prefix = self._fresh_bin_id()
        entry = f"{prefix}.{ext}"
        self.ctx.stage_addition(entry, data)
        hpf = self.ctx.replacements.get("Contents/content.hpf")
        hpf = hpf.decode("utf-8") if hpf else self.ctx.pkg.read_text("Contents/content.hpf")
        self.ctx.stage_replacement("Contents/content.hpf",
                                   images.register_in_hpf(hpf, bin_id, entry, ext).encode("utf-8"))
        return bin_id

    def _fit(self, px_w, px_h, width_mm, height_mm, keep_w=None, keep_h=None):
        from core.images import mm_to_hwp, px_to_hwp
        if width_mm is None and height_mm is None:
            if keep_w is not None:
                return keep_w, keep_h
            return px_to_hwp(px_w), px_to_hwp(px_h)
        ratio = px_h / px_w if px_w else 1
        if width_mm is not None and height_mm is not None:
            return mm_to_hwp(width_mm), mm_to_hwp(height_mm)
        if width_mm is not None:
            w = mm_to_hwp(width_mm)
            return w, int(round(w * ratio))
        h = mm_to_hwp(height_mm)
        return int(round(h / ratio)), h

    def insert_image(self, path, *, after=None, index=None, width_mm=None,
                     height_mm=None):
        from core import images
        if self.ctx is None:
            raise EditError("edit_file 경유 필요")
        data = Path(path).read_bytes()
        px_w, px_h, ext = images.image_size(data)
        bin_id = self._stage_new_image(data, ext)
        w, h = self._fit(px_w, px_h, width_mm, height_mm)
        anchor = self._target_para(after, index)
        parents = {c: par for par in self.root.iter() for c in par}
        parent = parents[anchor]
        pid = self._max_id() + 1
        pic_el = ET.fromstring(images.pic_xml(str(pid + 1), bin_id, w, h, px_w, px_h))
        p = ET.Element(_q("p"), {"id": str(pid), "paraPrIDRef": anchor.get("paraPrIDRef", "0"),
                                 "styleIDRef": "0", "pageBreak": "0",
                                 "columnBreak": "0", "merged": "0"})
        run = ET.SubElement(p, _q("run"), {"charPrIDRef": "0"})
        run.append(pic_el)
        parent.insert(list(parent).index(anchor) + 1, p)
        self._mark(p)

    def list_images(self):
        from core.images import hwp_to_mm
        out = []
        for i, pic in enumerate(self._pics()):
            img = pic.find(f"{{{NS['hc']}}}img")
            sz = pic.find(_q("sz"))
            out.append({"index": i,
                        "bin_id": img.get("binaryItemIDRef") if img is not None else None,
                        "width_mm": hwp_to_mm(sz.get("width")) if sz is not None else None,
                        "height_mm": hwp_to_mm(sz.get("height")) if sz is not None else None})
        return out

    def _apply_pic_size(self, pic, w, h):
        for tag in ("curSz", "sz"):
            el = pic.find(_q(tag))
            if el is not None:
                el.set("width", str(w))
                el.set("height", str(h))
        rect = pic.find(_q("imgRect"))
        if rect is not None:
            pts = {"pt0": (0, 0), "pt1": (w, 0), "pt2": (w, h), "pt3": (0, h)}
            for name, (x, y) in pts.items():
                pt = rect.find(f"{{{NS['hc']}}}{name}")
                if pt is not None:
                    pt.set("x", str(x))
                    pt.set("y", str(y))

    def resize_image(self, index, *, width_mm=None, height_mm=None):
        pic = self._get_pic(index)
        org = pic.find(_q("orgSz"))
        sz = pic.find(_q("sz"))
        px_w, px_h = int(org.get("width")), int(org.get("height"))
        w, h = self._fit(px_w, px_h, width_mm, height_mm,
                         keep_w=int(sz.get("width")), keep_h=int(sz.get("height")))
        self._apply_pic_size(pic, w, h)
        parents = {c: par for par in self.root.iter() for c in par}
        self._mark(self._owner_para(pic, parents))

    def _owner_para(self, el, parents):
        node = el
        while node is not None and node.tag != _q("p"):
            node = parents.get(node)
        if node is None:
            raise EditError("요소의 소속 문단을 찾을 수 없음")
        return node

    def replace_image(self, index, path):
        from core import images
        if self.ctx is None:
            raise EditError("edit_file 경유 필요")
        pic = self._get_pic(index)
        data = Path(path).read_bytes()
        px_w, px_h, ext = images.image_size(data)
        bin_id = self._stage_new_image(data, ext)
        img = pic.find(f"{{{NS['hc']}}}img")
        img.set("binaryItemIDRef", bin_id)
        ow, oh = images.px_to_hwp(px_w), images.px_to_hwp(px_h)
        for tag, attrs in (("orgSz", ("width", "height")), ("imgDim", ("dimwidth", "dimheight"))):
            el = pic.find(_q(tag))
            if el is not None:
                el.set(attrs[0], str(ow))
                el.set(attrs[1], str(oh))
        clip = pic.find(_q("imgClip"))
        if clip is not None:
            clip.set("right", str(ow))
            clip.set("bottom", str(oh))
        parents = {c: par for par in self.root.iter() for c in par}
        self._mark(self._owner_para(pic, parents))

    def delete_image(self, index):
        pic = self._get_pic(index)
        parents = {c: par for par in self.root.iter() for c in par}
        run = parents[pic]
        p = self._owner_para(pic, parents)
        run.remove(pic)
        if not list(run):
            p.remove(run)
        if not p.findall(_q("run")):
            gp = parents[p]
            if gp.tag == _q("subList"):
                # 셀 내부: 빈 subList를 만들지 않도록 빈 run을 남긴다
                run = ET.SubElement(p, _q("run"), {"charPrIDRef": "0"})
                ET.SubElement(run, _q("t"))
                self._mark(p)
            else:
                gp.remove(p)
        else:
            self._mark(p)

    # ---- 직렬화 ----
    def serialize(self):
        for p in self._modified:
            for seg in p.findall(_q("linesegarray")):
                p.remove(seg)
        body = ET.tostring(self.root, encoding="unicode")
        return (_XML_DECL + body).encode("utf-8")


def edit_file(src, dst, fn, section="Contents/section0.xml"):
    from core.header import HeaderEditor  # 순환 import 회피 (header→edit 의존)
    pkg = HwpxPackage.open(src)
    editor = SectionEditor.from_package(pkg, section)
    ctx = EditContext(pkg, editor)
    ctx.header = HeaderEditor.from_package(pkg)
    editor.ctx = ctx
    result = fn(editor)
    replacements = {section: editor.serialize()}
    if ctx.header is not None and ctx.header.dirty:
        replacements["Contents/header.xml"] = ctx.header.serialize()
    replacements.update(ctx.replacements)
    pkg.write_replaced(dst, replacements, additions=ctx.additions)
    return result
