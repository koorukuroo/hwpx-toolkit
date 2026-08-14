"""OWPML 요소 빌더 — 문자열 기반 XML 조각 생성."""
from xml.sax.saxutils import escape as xml_escape

from core.template import TEMPLATES_DIR

NS_HP_DECL = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'


class IdAllocator:
    def __init__(self, start=1000000002):
        self._next = start

    def next(self):
        value = self._next
        self._next += 1
        return str(value)


def load_skeleton(template="base"):
    xml = (TEMPLATES_DIR / template / "Contents/section0.xml").read_text("utf-8")
    open_start = xml.index("<hs:sec")
    open_end = xml.index(">", open_start) + 1
    sec_open = xml[open_start:open_end]
    p_start = xml.index("<hp:p", open_end)
    p_end = xml.index("</hp:p>", p_start) + len("</hp:p>")
    first_para = xml[p_start:p_end]
    return first_para, sec_open


def sec_document(first_para, body_parts, sec_open):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            + sec_open + first_para + "".join(body_parts) + "</hs:sec>")


def _para(pid, text, char_pr, para_pr, page_break):
    pb = "1" if page_break else "0"
    return (f'<hp:p {NS_HP_DECL} id="{pid}" paraPrIDRef="{para_pr}" styleIDRef="0" '
            f'pageBreak="{pb}" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{char_pr}">'
            + (f"<hp:t>{text}</hp:t>" if text else "<hp:t/>")
            + "</hp:run></hp:p>")


def text_para(text, alloc, *, char_pr="0", para_pr="0", page_break=False):
    return _para(alloc.next(), xml_escape(text), char_pr, para_pr, page_break)


def empty_line(alloc):
    return _para(alloc.next(), "", "0", "0", False)


_HEADING_MAP = {1: ("1", "1"), 2: ("2", "2")}


def heading_para(level, text, alloc):
    char_pr, para_pr = _HEADING_MAP.get(level, ("3", "3"))
    return _para(alloc.next(), xml_escape(text), char_pr, para_pr, False)


def bullet_para(text, alloc, marker="•"):
    return _para(alloc.next(), f"{marker} {xml_escape(text)}", "0", "4", False)


def _cell(row, col, text, width, height, alloc, *, header_cell):
    border = "4" if header_cell else "3"
    char_pr = "4" if header_cell else "0"
    return (
        '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
        f'dirty="0" borderFillIDRef="{border}">'
        '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
        'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
        'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="{alloc.next()}" paraPrIDRef="5" styleIDRef="0" '
        'pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{char_pr}">'
        + (f"<hp:t>{xml_escape(text)}</hp:t>" if text else "<hp:t/>")
        + "</hp:run></hp:p></hp:subList>"
        f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="{height}"/>'
        '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
        '</hp:tc>')


def table(rows, alloc, *, header=True, total_width=42520, row_height=2400):
    if not rows:
        raise ValueError("빈 표는 만들 수 없음")
    cols = len(rows[0])
    if cols == 0 or any(len(r) != cols for r in rows):
        raise ValueError("모든 행의 열 수가 같아야 함")
    base = total_width // cols
    widths = [base] * cols
    widths[-1] += total_width - base * cols
    tr_parts = []
    for r, row in enumerate(rows):
        is_header = header and r == 0
        cells = "".join(
            _cell(r, c, row[c], widths[c], row_height, alloc,
                  header_cell=is_header)
            for c in range(cols))
        tr_parts.append(f"<hp:tr>{cells}</hp:tr>")
    tbl_id = alloc.next()
    height = row_height * len(rows)
    return (
        f'<hp:p {NS_HP_DECL} id="{alloc.next()}" paraPrIDRef="0" styleIDRef="0" '
        'pageBreak="0" columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0">'
        f'<hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" '
        'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        'dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{len(rows)}" colCnt="{cols}" cellSpacing="0" '
        'borderFillIDRef="3" noAdjust="0">'
        f'<hp:sz width="{total_width}" widthRelTo="ABSOLUTE" '
        f'height="{height}" heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
        'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
        'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
        'vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="141" bottom="141"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        + "".join(tr_parts) +
        '</hp:tbl></hp:run></hp:p>')
