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
    names = sorted(n for n in pkg.names()
                   if re.fullmatch(r"Contents/section\d+\.xml", n))
    return [(n, ET.fromstring(pkg.read(n))) for n in names]


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
