"""OWPML 요소 빌더 — 문자열 기반 XML 조각 생성."""
import json
import re
from xml.sax.saxutils import escape as _escape

from core.template import TEMPLATES_DIR
from core.text import clean_text


def xml_escape(text):
    """hp:t 안에 들어갈 문자열 — XML 이스케이프 + 탭/줄바꿈은 요소로, 제어문자 제거.
    (hp:t 안의 탭 *문자*는 한컴이 문서를 열지 못하게 만든다.)"""
    out = []
    for piece in re.split(r"([\t\n])", clean_text(text)):
        if piece == "\t":
            out.append("<hp:tab/>")
        elif piece == "\n":
            out.append("<hp:lineBreak/>")
        elif piece:
            out.append(_escape(piece))
    return "".join(out)

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


def load_style_map(template="base"):
    p = TEMPLATES_DIR / template / "styles.json"
    if not p.is_file():
        raise ValueError(f"styles.json 없음: {template}")
    return json.loads(p.read_text("utf-8"))


_INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def strip_inline(text):
    """인라인 마커 제거 (제목·표 머리글처럼 이미 서식이 있는 곳)."""
    return text.replace("**", "").replace("`", "")


def inline_runs(text, char_pr, style_map=None):
    """`**굵게**`·`` `코드` ``를 별도 run으로 — styles.json에 bold_char/code_char가
    없으면 마커만 제거한다."""
    bold = (style_map or {}).get("bold_char")
    code = (style_map or {}).get("code_char")
    if bold is None and code is None:
        text = strip_inline(text)
    runs = []
    for piece in _INLINE_RE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**") and len(piece) > 4 and bold:
            runs.append(f'<hp:run charPrIDRef="{bold}"><hp:t>{xml_escape(piece[2:-2])}</hp:t></hp:run>')
        elif piece.startswith("`") and piece.endswith("`") and len(piece) > 2 and code:
            runs.append(f'<hp:run charPrIDRef="{code}"><hp:t>{xml_escape(piece[1:-1])}</hp:t></hp:run>')
        else:
            runs.append(f'<hp:run charPrIDRef="{char_pr}"><hp:t>{xml_escape(strip_inline(piece))}</hp:t></hp:run>')
    return "".join(runs) or f'<hp:run charPrIDRef="{char_pr}"><hp:t/></hp:run>'


def _para(pid, text, char_pr, para_pr, page_break, *, runs=None):
    pb = "1" if page_break else "0"
    if runs is None:
        runs = (f'<hp:run charPrIDRef="{char_pr}">'
                + (f"<hp:t>{text}</hp:t>" if text else "<hp:t/>") + "</hp:run>")
    return (f'<hp:p {NS_HP_DECL} id="{pid}" paraPrIDRef="{para_pr}" styleIDRef="0" '
            f'pageBreak="{pb}" columnBreak="0" merged="0">' + runs + "</hp:p>")


def text_para(text, alloc, *, char_pr="0", para_pr="0", page_break=False,
              style_map=None):
    return _para(alloc.next(), None, char_pr, para_pr, page_break,
                 runs=inline_runs(text, char_pr, style_map))


def empty_line(alloc, page_break=False):
    return _para(alloc.next(), "", "0", "0", page_break)


_HEADING_MAP = {1: ("1", "1"), 2: ("2", "2")}


def heading_para(level, text, alloc, style_map=None, page_break=False):
    if style_map is None:
        char_pr, para_pr = _HEADING_MAP.get(level, ("3", "3"))
    else:
        h = style_map["heading"]
        char_pr, para_pr = h.get(str(level), h["default"])
    return _para(alloc.next(), xml_escape(strip_inline(text)), char_pr, para_pr, page_break)


_BULLET_MARKERS = ("•", "-", "·")


def bullet_para(text, alloc, marker="•", *, level=0, style_map=None, page_break=False):
    levels = (style_map or {}).get("bullet_levels", ["4"])
    para_pr = levels[min(level, len(levels) - 1)]
    if marker == "•" and level:
        marker = _BULLET_MARKERS[min(level, len(_BULLET_MARKERS) - 1)]
    runs = (f'<hp:run charPrIDRef="0"><hp:t>{xml_escape(marker)} </hp:t></hp:run>'
            + inline_runs(text, "0", style_map))
    return _para(alloc.next(), None, "0", para_pr, page_break, runs=runs)


def ordered_para(text, alloc, *, level=0, style_map=None, page_break=False):
    levels = (style_map or {}).get("bullet_levels", ["4"])
    para_pr = levels[min(level, len(levels) - 1)]
    return _para(alloc.next(), None, "0", para_pr, page_break,
                 runs=inline_runs(text, "0", style_map))


def quote_para(text, alloc, style_map, page_break=False):
    return _para(alloc.next(), None, "0", style_map.get("quote_para", "0"), page_break,
                 runs=inline_runs(text, "0", style_map))


def code_para(line, alloc, style_map, page_break=False):
    char_pr = style_map.get("code_char", "0")
    para_pr = style_map.get("code_para", "0")
    return _para(alloc.next(), xml_escape(line) if line else "", char_pr, para_pr, page_break)


MAX_IMAGE_WIDTH = 42520        # A4 본문 폭(용지 59528 − 좌우 여백 8504×2)


def image_para(bin_id, data, alloc, *, page_break=False, max_width=MAX_IMAGE_WIDTH):
    """그림 한 장을 담은 문단 (글자처럼 취급, 본문 폭을 넘으면 비율 유지 축소)."""
    from core import images
    px_w, px_h, _ = images.image_size(data)
    w, h = images.px_to_hwp(px_w), images.px_to_hwp(px_h)
    if w > max_width:
        h = int(round(h * max_width / w))
        w = max_width
    pid = alloc.next()
    pic = images.pic_xml(alloc.next(), bin_id, w, h, px_w, px_h, instid=alloc.next())
    pic = pic.replace(f' {NS_HP_DECL}', "", 1)
    return _para(pid, None, "0", "0", page_break, runs=f'<hp:run charPrIDRef="0">{pic}</hp:run>')


def _cell(row, col, text, width, height, alloc, *, header_cell,
          header_char="4", header_border="4", body_border="3", cell_para="5",
          style_map=None):
    border = header_border if header_cell else body_border
    char_pr = header_char if header_cell else "0"
    if header_cell or not text:
        runs = (f'<hp:run charPrIDRef="{char_pr}">'
                + (f"<hp:t>{xml_escape(strip_inline(text))}</hp:t>" if text else "<hp:t/>")
                + "</hp:run>")
    else:
        runs = inline_runs(text, char_pr, style_map)
    return (
        '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
        f'dirty="0" borderFillIDRef="{border}">'
        '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
        'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
        'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="{alloc.next()}" paraPrIDRef="{cell_para}" styleIDRef="0" '
        'pageBreak="0" columnBreak="0" merged="0">'
        + runs + "</hp:p></hp:subList>"
        f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="{height}"/>'
        '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
        '</hp:tc>')


def section_bar(text, alloc, style_map, total_width=42520, height=1200):
    sb = style_map["section_bar"]
    cell = _cell(0, 0, text, total_width, height, alloc, header_cell=False)
    cell = cell.replace('borderFillIDRef="3"', f'borderFillIDRef="{sb["border"]}"', 1)
    cell = cell.replace('charPrIDRef="0"', f'charPrIDRef="{sb["char"]}"', 1)
    tbl_id = alloc.next()
    return (
        f'<hp:p id="{alloc.next()}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
        f'<hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" '
        f'repeatHeader="0" rowCnt="1" colCnt="1" cellSpacing="0" borderFillIDRef="{sb["border"]}" noAdjust="0">'
        f'<hp:sz width="{total_width}" widthRelTo="ABSOLUTE" height="{height}" heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
        'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="283" bottom="141"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        f'<hp:tr>{cell}</hp:tr></hp:tbl></hp:run></hp:p>')


def table(rows, alloc, *, header=True, total_width=42520, row_height=2400,
          style_map=None, page_break=False):
    if not rows:
        raise ValueError("빈 표는 만들 수 없음")
    cols = len(rows[0])
    if cols == 0 or any(len(r) != cols for r in rows):
        raise ValueError("모든 행의 열 수가 같아야 함")
    t = style_map["table"] if style_map else {}
    header_char = t.get("header_char", "4")
    header_border = t.get("header_border", "4")
    body_border = t.get("body_border", "3")
    cell_para = t.get("cell_para", "5")
    base = total_width // cols
    widths = [base] * cols
    widths[-1] += total_width - base * cols
    tr_parts = []
    for r, row in enumerate(rows):
        is_header = header and r == 0
        cells = "".join(
            _cell(r, c, row[c], widths[c], row_height, alloc,
                  header_cell=is_header, header_char=header_char,
                  header_border=header_border, body_border=body_border,
                  cell_para=cell_para, style_map=style_map)
            for c in range(cols))
        tr_parts.append(f"<hp:tr>{cells}</hp:tr>")
    tbl_id = alloc.next()
    height = row_height * len(rows)
    return (
        f'<hp:p {NS_HP_DECL} id="{alloc.next()}" paraPrIDRef="0" styleIDRef="0" '
        f'pageBreak="{"1" if page_break else "0"}" columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0">'
        f'<hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" '
        'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        'dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{len(rows)}" colCnt="{cols}" cellSpacing="0" '
        f'borderFillIDRef="{body_border}" noAdjust="0">'
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
