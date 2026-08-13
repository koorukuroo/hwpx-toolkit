"""문서 분석 — 텍스트 추출, 구조 리포트, 편집 슬롯."""
import re
import xml.etree.ElementTree as ET

from core.package import HwpxPackage

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _q(tag):
    return f"{{{NS_HP}}}{tag}"


def _para_direct_text(p_el):
    """문단의 직접 런 텍스트 (표/개체 내부 제외)."""
    parts = []
    for run in p_el.findall(_q("run")):
        for t in run.findall(_q("t")):
            parts.append("".join(t.itertext()))
    return "".join(parts)


def _table_rows(tbl_el):
    rows = []
    for tr in tbl_el.findall(_q("tr")):
        row = []
        for tc in tr.findall(_q("tc")):
            texts = []
            sublist = tc.find(_q("subList"))
            if sublist is not None:
                for p in sublist.findall(_q("p")):
                    texts.append(_para_direct_text(p))
            row.append(" ".join(t for t in texts if t))
        rows.append(row)
    return rows


def _sections(pkg):
    candidates = [(n, int(m.group(1)))
                  for n in pkg.names()
                  if (m := re.fullmatch(r"Contents/section(\d+)\.xml", n))]
    names = [n for n, _ in sorted(candidates, key=lambda x: x[1])]
    return [(n, ET.fromstring(pkg.read(n))) for n in names]


NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def analyze_document(path):
    pkg = HwpxPackage.open(path)
    result = {"page": None, "styles": {}, "sections": []}

    header = ET.fromstring(pkg.read("Contents/header.xml"))
    for coll, key in (("charProperties", "charPrCount"),
                      ("paraProperties", "paraPrCount"),
                      ("borderFills", "borderFillCount")):
        el = header.find(f".//{{{NS_HH}}}{coll}")
        result["styles"][key] = len(list(el)) if el is not None else 0

    table_index = 0
    for name, root in _sections(pkg):
        sec_info = {"name": name, "paragraphCount": 0, "tables": []}
        for p in root.findall(_q("p")):
            sec_info["paragraphCount"] += 1
            for run in p.findall(_q("run")):
                secpr = run.find(_q("secPr"))
                if secpr is not None and result["page"] is None:
                    pagepr = secpr.find(_q("pagePr"))
                    if pagepr is not None:
                        margin = pagepr.find(_q("margin"))
                        result["page"] = {
                            "width": int(pagepr.get("width")),
                            "height": int(pagepr.get("height")),
                            "margins": {k: int(margin.get(k)) for k in
                                        ("left", "right", "top", "bottom",
                                         "header", "footer", "gutter")}
                            if margin is not None else {},
                        }
                for tbl in run.findall(_q("tbl")):
                    sec_info["tables"].append({
                        "index": table_index,
                        "rows": int(tbl.get("rowCnt")),
                        "cols": int(tbl.get("colCnt")),
                    })
                    table_index += 1
        result["sections"].append(sec_info)
    return result


def extract_slots(path):
    pkg = HwpxPackage.open(path)
    slots = []
    table_index = 0
    for name, root in _sections(pkg):
        for p_idx, p in enumerate(root.findall(_q("p"))):
            tbls = [tbl for run in p.findall(_q("run"))
                    for tbl in run.findall(_q("tbl"))]
            pics = [pic for run in p.findall(_q("run"))
                    for pic in run.findall(_q("pic"))]
            if tbls or pics:
                for tbl in tbls:
                    for tr in tbl.findall(_q("tr")):
                        for tc in tr.findall(_q("tc")):
                            addr = tc.find(_q("cellAddr"))
                            row = int(addr.get("rowAddr"))
                            col = int(addr.get("colAddr"))
                            texts = []
                            sublist = tc.find(_q("subList"))
                            if sublist is not None:
                                for cp in sublist.findall(_q("p")):
                                    texts.append(_para_direct_text(cp))
                            slots.append({
                                "key": f"cell:{table_index}:{row}:{col}",
                                "type": "cell", "table": table_index,
                                "row": row, "col": col,
                                "text": " ".join(t for t in texts if t),
                            })
                    table_index += 1
                continue
            text = _para_direct_text(p)
            if text:
                slots.append({"key": f"p:{p_idx}", "type": "paragraph",
                              "section": name, "text": text})
    return {"slots": slots}


def extract_text(path, fmt="text"):
    pkg = HwpxPackage.open(path)
    lines = []
    for _, root in _sections(pkg):
        for p in root.findall(_q("p")):
            tbls = [tbl for run in p.findall(_q("run"))
                    for tbl in run.findall(_q("tbl"))]
            if tbls:
                for tbl in tbls:
                    rows = _table_rows(tbl)
                    if not rows:
                        continue
                    if fmt == "markdown":
                        lines.append("| " + " | ".join(rows[0]) + " |")
                        lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
                        for row in rows[1:]:
                            lines.append("| " + " | ".join(row) + " |")
                    else:
                        for row in rows:
                            lines.append(" | ".join(row))
                continue
            text = _para_direct_text(p)
            if text:
                lines.append(text)
    return "\n".join(lines)
