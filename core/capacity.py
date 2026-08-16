"""표 셀 수용량 추정 — 폭·높이·여백·글자 크기·줄간격으로 들어갈 글자 수를 가늠한다.

한글(함초롬 계열) 글리프는 em 정사각형에 가까워 글자 폭 ≈ 글자 높이로 본다.
줄 높이는 글자 높이 × 문단 줄간격(%)이다. 추정이므로 결과는 경고에만 쓴다.
"""
import re
import xml.etree.ElementTree as ET

from core.analyze import _para_direct_text, _q, _sections
from core.package import HwpxPackage

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"

#: 추정 오차 여유 — 실제 글자 수가 추정치의 이 배수를 넘어야 경고한다.
OVER_MARGIN = 1.15

_DEFAULT_LINE_SPACING = 160


def estimate_chars(cell_w, cell_h, margins, font_hwp, line_spacing_pct):
    if not font_hwp or font_hwp <= 0:
        return 0
    usable_w = int(cell_w) - int(margins.get("left", 0)) - int(margins.get("right", 0))
    usable_h = int(cell_h) - int(margins.get("top", 0)) - int(margins.get("bottom", 0))
    glyph_w = int(font_hwp)
    line_h = max(1, int(round(font_hwp * (line_spacing_pct or 100) / 100)))
    per_line = max(1, usable_w // glyph_w)
    lines = max(1, usable_h // line_h)
    return per_line * lines


def _style_maps(pkg):
    """header.xml에서 charPr id → 글자 높이, paraPr id → 줄간격(%)."""
    root = ET.fromstring(pkg.read("Contents/header.xml"))
    chars, paras = {}, {}
    for cp in root.iter(f"{{{NS_HH}}}charPr"):
        h = cp.get("height")
        if cp.get("id") is not None and h and h.isdigit():
            chars[cp.get("id")] = int(h)
    for pp in root.iter(f"{{{NS_HH}}}paraPr"):
        ls = next(iter(pp.iter(f"{{{NS_HH}}}lineSpacing")), None)
        if pp.get("id") is not None:
            value = ls.get("value") if ls is not None else None
            paras[pp.get("id")] = (int(value) if value and value.isdigit()
                                   else _DEFAULT_LINE_SPACING)
    return chars, paras


def _int_attr(el, name, default=0):
    if el is None:
        return default
    v = el.get(name)
    return int(v) if v and v.lstrip("-").isdigit() else default


def cell_report(path):
    pkg = HwpxPackage.open(path)
    chars, paras = _style_maps(pkg)
    out = []
    for name, root in _sections(pkg):
        table_index = 0
        for p in root.findall(_q("p")):
            tbls = [t for run in p.findall(_q("run"))
                    for t in run.findall(_q("tbl"))]
            if not tbls:
                continue
            for tbl in tbls:
                for tc in tbl.iter(_q("tc")):
                    addr = tc.find(_q("cellAddr"))
                    if addr is None:
                        continue
                    sz = tc.find(_q("cellSz"))
                    margin_el = tc.find(_q("cellMargin"))
                    margins = {k: _int_attr(margin_el, k)
                               for k in ("left", "right", "top", "bottom")}
                    sub = tc.find(_q("subList"))
                    cell_paras = sub.findall(_q("p")) if sub is not None else []
                    text = " ".join(_para_direct_text(cp) for cp in cell_paras)
                    font = 0
                    spacing = _DEFAULT_LINE_SPACING
                    if cell_paras:
                        first = cell_paras[0]
                        spacing = paras.get(first.get("paraPrIDRef"),
                                            _DEFAULT_LINE_SPACING)
                        run = first.find(_q("run"))
                        if run is not None:
                            font = chars.get(run.get("charPrIDRef"), 0)
                    capacity = estimate_chars(_int_attr(sz, "width"),
                                              _int_attr(sz, "height"),
                                              margins, font, spacing)
                    used = len(re.sub(r"\s", "", text))
                    out.append({
                        "section": name, "table": table_index,
                        "row": _int_attr(addr, "rowAddr"),
                        "col": _int_attr(addr, "colAddr"),
                        "capacity": capacity, "used": used,
                        "over": bool(capacity and used > capacity * OVER_MARGIN),
                    })
                table_index += 1
    return {"cells": out}


def for_cell(path, table, row, col, section=None):
    for c in cell_report(path)["cells"]:
        if (c["table"] == table and c["row"] == row and c["col"] == col
                and (section is None or c["section"] == section)):
            return c["capacity"]
    return None
