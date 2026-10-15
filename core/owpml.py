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


_INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[\^[^\]\s]+\]|\[[^\]]+\]\([^)\s]+\))")
_LINK_RE = re.compile(r"^\[([^\]]+)\]\(([^)\s]+)\)$")
_FOOTNOTE_REF_RE = re.compile(r"^\[\^([^\]\s]+)\]$")
HYPERLINK_FIELDID = "627600491"     # 한컴이 하이퍼링크 필드에 쓰는 fieldid (실물 관찰값)


def strip_inline(text):
    """인라인 마커 제거 (제목·표 머리글처럼 이미 서식이 있는 곳). 링크는 글자만, 각주 참조는 삭제."""
    text = _FOOTNOTE_REF_RE.sub("", re.sub(r"\[\^[^\]\s]+\]", "", text))
    text = re.sub(r"\[([^\]]+)\]\([^)\s]+\)", r"\1", text)
    return text.replace("**", "").replace("`", "")


class RenderContext:
    """렌더 한 번의 상태 — id 할당기, 각주 정의(id→본문)와 참조 순서."""

    def __init__(self, alloc=None, footnotes=None):
        self.alloc = alloc or IdAllocator()
        self.footnotes = dict(footnotes or {})
        self.order = []          # 참조된 각주 id (등장 순)

    def footnote_number(self, key):
        if key not in self.order:
            self.order.append(key)
        return self.order.index(key) + 1


def _hyperlink_command(url):
    """Command 파라미터 — 한컴은 ':' '?' ';' '\\' 를 역슬래시로 이스케이프한다."""
    esc = url.replace("\\", "\\\\").replace(":", "\\:").replace("?", "\\?").replace(";", "\\;")
    return f"{esc};1;0;0;"


def _hyperlink_begin(url, alloc):
    fid = alloc.next()
    xml = (f'<hp:ctrl><hp:fieldBegin id="{fid}" type="HYPERLINK" name="" editable="0" dirty="1" '
           f'zorder="-1" fieldid="{HYPERLINK_FIELDID}"><hp:parameters cnt="6" name="">'
           '<hp:integerParam name="Prop">0</hp:integerParam>'
           f'<hp:stringParam name="Command">{_escape(_hyperlink_command(url))}</hp:stringParam>'
           f'<hp:stringParam name="Path">{_escape(url)}</hp:stringParam>'
           '<hp:stringParam name="Category">HWPHYPERLINK_TYPE_URL</hp:stringParam>'
           '<hp:stringParam name="TargetType">HWPHYPERLINK_TARGET_BOOKMARK</hp:stringParam>'
           '<hp:stringParam name="DocOpenType">HWPHYPERLINK_JUMP_CURRENTTAB</hp:stringParam>'
           '</hp:parameters></hp:fieldBegin></hp:ctrl>')
    return fid, xml


def _hyperlink_end(fid):
    return f'<hp:ctrl><hp:fieldEnd beginIDRef="{fid}" fieldid="{HYPERLINK_FIELDID}"/></hp:ctrl>'


def footnote_ctrl(number, text, note_char, alloc):
    """각주 컨트롤 — 본문 run 안에 들어가는 hp:ctrl (한컴 저장 구조: autoNum + 본문)."""
    pid = alloc.next()
    return (f'<hp:ctrl><hp:footNote number="{number}" suffixChar="41" instId="{alloc.next()}">'
            '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" '
            'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" '
            'hasTextRef="0" hasNumRef="0">'
            f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{note_char}"><hp:ctrl><hp:autoNum num="{number}" numType="FOOTNOTE">'
            '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>'
            f'</hp:autoNum></hp:ctrl><hp:t> {xml_escape(text)}</hp:t></hp:run>'
            # 한컴 저장본처럼 줄 배치 캐시를 하나 둔다 (렌더러가 각주 줄 높이를 읽는다)
            '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="900" textheight="900" '
            'baseline="765" spacing="540" horzpos="0" horzsize="42520" flags="393216"/>'
            '</hp:linesegarray></hp:p>'
            '</hp:subList></hp:footNote></hp:ctrl>')


def _group_runs(items, default_char):
    """[(charPr, xml 조각)] → 같은 charPr가 이어지는 조각을 한 run으로. 한컴처럼 필드
    시작 ctrl은 앞 글자 run 끝에, 필드 끝 ctrl은 뒤 글자 run 앞에 붙는다."""
    runs, cur_char, cur = [], None, []
    for char, xml in items:
        if cur and char != cur_char:
            runs.append(f'<hp:run charPrIDRef="{cur_char}">{"".join(cur)}</hp:run>')
            cur = []
        cur_char = char
        cur.append(xml)
    if cur:
        if not cur[-1].startswith("<hp:t"):
            cur.append("<hp:t/>")          # ctrl로 끝나는 run은 빈 hp:t로 닫는다 (한컴 저장 형태)
        runs.append(f'<hp:run charPrIDRef="{cur_char}">{"".join(cur)}</hp:run>')
    return "".join(runs) or f'<hp:run charPrIDRef="{default_char}"><hp:t/></hp:run>'


def _t(text):
    return f"<hp:t>{xml_escape(text)}</hp:t>"


def inline_runs(text, char_pr, style_map=None, ctx=None):
    """`**굵게**`·`` `코드` ``·`[글자](url)`·`[^각주]`를 별도 run으로 — styles.json에
    해당 ID가 없거나 ctx가 없으면 마커만 제거한다."""
    sm = style_map or {}
    bold, code, link = sm.get("bold_char"), sm.get("code_char"), sm.get("link_char")
    if bold is None and code is None:
        text = strip_inline(text)
    items = []
    for piece in _INLINE_RE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**") and len(piece) > 4 and bold:
            items.append((bold, _t(piece[2:-2])))
        elif piece.startswith("`") and piece.endswith("`") and len(piece) > 2 and code:
            items.append((code, _t(piece[1:-1])))
        elif _LINK_RE.match(piece) and link and ctx is not None:
            m = _LINK_RE.match(piece)
            fid, begin = _hyperlink_begin(m.group(2), ctx.alloc)
            items.append((char_pr, begin))
            items.append((link, _t(m.group(1))))
            items.append((char_pr, _hyperlink_end(fid)))
        elif _FOOTNOTE_REF_RE.match(piece) and ctx is not None \
                and _FOOTNOTE_REF_RE.match(piece).group(1) in ctx.footnotes:
            key = _FOOTNOTE_REF_RE.match(piece).group(1)
            note_char = sm.get("caption", [char_pr])[0]
            items.append((char_pr, footnote_ctrl(ctx.footnote_number(key), ctx.footnotes[key],
                                                 note_char, ctx.alloc)))
        else:
            items.append((char_pr, _t(strip_inline(piece))))
    return _group_runs(items, char_pr)


def _para(pid, text, char_pr, para_pr, page_break, *, runs=None):
    pb = "1" if page_break else "0"
    if runs is None:
        runs = (f'<hp:run charPrIDRef="{char_pr}">'
                + (f"<hp:t>{text}</hp:t>" if text else "<hp:t/>") + "</hp:run>")
    return (f'<hp:p {NS_HP_DECL} id="{pid}" paraPrIDRef="{para_pr}" styleIDRef="0" '
            f'pageBreak="{pb}" columnBreak="0" merged="0">' + runs + "</hp:p>")


def text_para(text, alloc, *, char_pr="0", para_pr="0", page_break=False,
              style_map=None, ctx=None):
    return _para(alloc.next(), None, char_pr, para_pr, page_break,
                 runs=inline_runs(text, char_pr, style_map, ctx))


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
_GA = "가나다라마바사아자차카타파하"
_ROMAN = ("Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ", "Ⅻ")
_ORDERED_ITEM_RE = re.compile(r"^(\d+)\.\s+(.*)$", re.S)


def roman(n):
    """1..12 → Ⅰ..Ⅻ (그 밖은 아라비아 숫자)."""
    return _ROMAN[n - 1] if 1 <= n <= len(_ROMAN) else str(n)


def _ga(n):
    return _GA[(n - 1) % len(_GA)]


def format_ordinal(fmt, n):
    """테마의 번호 서식(`{n}.`, `{ga}.`, `{n})`, `({n})`)에 n을 넣는다."""
    return fmt.replace("{ga}", _ga(n)).replace("{n}", str(n))


def bullet_marker(level, style_map=None):
    glyphs = (style_map or {}).get("bullets") or _BULLET_MARKERS
    return glyphs[min(level, len(glyphs) - 1)]


def bullet_para(text, alloc, marker=None, *, level=0, style_map=None, page_break=False,
                ctx=None):
    """목록 문단 — 기호는 테마(styles.json `bullets`)의 단계별 글자, 문단은 내어쓰기
    paraPr(`bullet_levels`)를 쓴다. marker를 주면 그 기호를 그대로 쓴다."""
    levels = (style_map or {}).get("bullet_levels", ["4"])
    para_pr = levels[min(level, len(levels) - 1)]
    if marker is None:
        marker = bullet_marker(level, style_map)
    runs = (f'<hp:run charPrIDRef="0"><hp:t>{xml_escape(marker)} </hp:t></hp:run>'
            + inline_runs(text, "0", style_map, ctx))
    return _para(alloc.next(), None, "0", para_pr, page_break, runs=runs)


def ordered_para(text, alloc, *, level=0, style_map=None, page_break=False, ctx=None):
    """번호 목록 문단. text가 `N. 내용` 꼴이면 테마의 단계별 번호 서식(`ordered`,
    예: 1. → 가. → 1))으로 바꾼다."""
    levels = (style_map or {}).get("bullet_levels", ["4"])
    para_pr = levels[min(level, len(levels) - 1)]
    fmts = (style_map or {}).get("ordered")
    m = _ORDERED_ITEM_RE.match(text)
    if fmts and m:
        fmt = fmts[min(level, len(fmts) - 1)]
        text = f"{format_ordinal(fmt, int(m.group(1)))} {m.group(2)}"
    return _para(alloc.next(), None, "0", para_pr, page_break,
                 runs=inline_runs(text, "0", style_map, ctx))


def quote_para(text, alloc, style_map, page_break=False, ctx=None):
    return _para(alloc.next(), None, "0", style_map.get("quote_para", "0"), page_break,
                 runs=inline_runs(text, "0", style_map, ctx))


def code_para(line, alloc, style_map, page_break=False):
    char_pr = style_map.get("code_char", "0")
    para_pr = style_map.get("code_para", "0")
    return _para(alloc.next(), xml_escape(line) if line else "", char_pr, para_pr, page_break)


def caption_para(text, alloc, style_map, page_break=False, ctx=None):
    """그림 설명 등 캡션 — 테마의 `caption` (작은 회색 글자, 가운데)."""
    char_pr, para_pr = style_map.get("caption", ["0", "0"])
    return _para(alloc.next(), None, char_pr, para_pr, page_break,
                 runs=inline_runs(text, char_pr, style_map, ctx))


def subtitle_para(text, alloc, style_map, page_break=False):
    """제목 아래 부제·작성자·날짜 줄 — 테마의 `subtitle`."""
    char_pr, para_pr = style_map.get("subtitle", ["0", "0"])
    return _para(alloc.next(), None, char_pr, para_pr, page_break,
                 runs=inline_runs(text, char_pr, style_map))


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


CELL_MARGIN = (510, 510, 141, 141)     # left, right, top, bottom — 한컴 기본값


def _cell(row, col, text, width, height, alloc, *, header_cell,
          header_char="4", header_border="4", body_border="3", cell_para="5",
          style_map=None, cell_char="0", para_pr=None, border=None, ctx=None,
          mark_header=True):
    border = border or (header_border if header_cell else body_border)
    char_pr = header_char if header_cell else cell_char
    para_pr = para_pr or cell_para
    if header_cell or not text:
        runs = (f'<hp:run charPrIDRef="{char_pr}">'
                + (f"<hp:t>{xml_escape(strip_inline(text))}</hp:t>" if text else "<hp:t/>")
                + "</hp:run>")
    else:
        runs = inline_runs(text, char_pr, style_map, ctx)
    ml, mr, mt, mb = CELL_MARGIN
    header_flag = "1" if (header_cell and mark_header) else "0"   # 머리글 행 반복(repeatHeader) 대상
    return (
        f'<hp:tc name="" header="{header_flag}" hasMargin="0" protect="0" editable="0" '
        f'dirty="0" borderFillIDRef="{border}">'
        '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
        'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
        'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="{alloc.next()}" paraPrIDRef="{para_pr}" styleIDRef="0" '
        'pageBreak="0" columnBreak="0" merged="0">'
        + runs + "</hp:p></hp:subList>"
        f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="{height}"/>'
        f'<hp:cellMargin left="{ml}" right="{mr}" top="{mt}" bottom="{mb}"/>'
        '</hp:tc>')


def _tbl_open(tbl_id, rows, cols, width, height, border, *, repeat_header,
              out_top=141, out_bottom=141, in_margin=None):
    # 한컴은 셀의 hasMargin="0"이면 셀 여백(cellMargin) 대신 표의 inMargin을 쓴다 — 실물
    # 저장본도 둘 다 같은 값(510/510/141/141)을 갖는다. 0이면 글자가 선에 붙는다.
    ml, mr, mt, mb = in_margin or CELL_MARGIN
    return (
        f'<hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" '
        f'repeatHeader="{"1" if repeat_header else "0"}" rowCnt="{rows}" colCnt="{cols}" '
        f'cellSpacing="0" borderFillIDRef="{border}" noAdjust="0">'
        f'<hp:sz width="{width}" widthRelTo="ABSOLUTE" height="{height}" '
        'heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
        'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        f'<hp:outMargin left="0" right="0" top="{out_top}" bottom="{out_bottom}"/>'
        f'<hp:inMargin left="{ml}" right="{mr}" top="{mt}" bottom="{mb}"/>')


def section_chip(number, text, alloc, style_map, total_width=42520, height=None,
                 page_break=False):
    """장 제목 칩 — `[Ⅰ] [ ] [제목]` 1×3 표. 번호 칸은 포인트색 배경에 흰 글자,
    제목 칸은 아래쪽 굵은 선 (styles.json `section_chip`)."""
    sc = style_map["section_chip"]
    height = height or int(int(sc.get("size", 1600)) * 1.3) + 282     # 제목 글자 줄 높이 + 여백
    num_w = max(height, int(total_width * 0.08))
    gap_w = int(total_width * 0.015)
    title_w = total_width - num_w - gap_w
    num = _cell(0, 0, number, num_w, height, alloc, header_cell=True, mark_header=False,
                header_char=sc["num_char"], header_border=sc["num_border"])
    gap = _cell(0, 1, "", gap_w, height, alloc, header_cell=False, body_border="2")
    ttl = _cell(0, 2, text, title_w, height, alloc, header_cell=True, mark_header=False,
                header_char=sc["title_char"], header_border=sc["title_border"],
                cell_para=style_map["table"].get("cell_para_left", "0"))
    tbl_id = alloc.next()
    return (
        f'<hp:p id="{alloc.next()}" paraPrIDRef="0" styleIDRef="0" '
        f'pageBreak="{"1" if page_break else "0"}" columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0">'
        + _tbl_open(tbl_id, 1, 3, total_width, height, "2", repeat_header=False,
                    out_top=600, out_bottom=300)
        + f'<hp:tr>{num}{gap}{ttl}</hp:tr></hp:tbl></hp:run></hp:p>')


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


def _em_width(text):
    total = 0.0
    for ch in strip_inline(text or ""):
        if ch.isspace():
            total += 0.3
        else:
            total += 0.55 if ord(ch) < 128 else 1.0
    return total


def column_widths(rows, total_width, *, min_em=2.5, max_em=20.0, min_width=3400):
    """열 폭을 내용 글자 폭에 비례해 나눈다 (합계 = total_width).
    셀 여백(좌우 510씩)을 감안해 열마다 1.5em을 더하고, 모든 열의 내용 폭이 같으면
    균등 분할과 같다."""
    cols = len(rows[0])
    weights = []
    for c in range(cols):
        w = max(_em_width(r[c]) for r in rows)
        weights.append(min(max(w, min_em), max_em) + 1.5)
    total_w = sum(weights)
    widths = [max(min_width, int(total_width * w / total_w)) for w in weights]
    widths[-1] += total_width - sum(widths)
    if widths[-1] < min_width:            # 마지막 열이 눌리면 가장 넓은 열에서 덜어온다
        deficit = min_width - widths[-1]
        widest = max(range(cols - 1), key=lambda i: widths[i])
        widths[widest] -= deficit
        widths[-1] = min_width
    return widths


def _row_height_for(row, widths, char_h, line_pct=130):
    """행 높이 — 가장 긴 셀의 줄 수 × 줄 높이 + 위아래 여백 (한컴이 자동으로 늘리지만
    cellSz를 실제에 가깝게 써야 check의 넘침 추정이 맞는다)."""
    ml, mr, mt, mb = CELL_MARGIN
    lines = 1
    for text, width in zip(row, widths):
        usable_em = max(1.0, (width - ml - mr) / char_h)
        lines = max(lines, -(-int(_em_width(text) * 100) // int(usable_em * 100)))
    return lines * int(char_h * line_pct / 100) + mt + mb


def rule_heading(text, alloc, spec, total_width=42520, page_break=False, ctx=None):
    """아래쪽 선이 있는 제목 — 1×1 표. 셀 아래 테두리(spec["border"])가 선이 되고, 표
    바깥 여백(prev/next)이 제목 앞뒤 간격이 된다. 문단 테두리와 달리 선이 글자 바로 아래에
    그어진다."""
    char_h = int(spec.get("size", 1200))
    height = int(char_h * 1.3) + 260            # 글자 줄 높이 + 셀 위아래 여백
    cell = _cell(0, 0, text, total_width, height, alloc, header_cell=True, mark_header=False,
                 header_char=spec["char"], header_border=spec["border"], cell_para=spec["para"])
    rule_margin = (0, 0, 100, 160)
    cell = cell.replace('<hp:cellMargin left="510" right="510" top="141" bottom="141"/>',
                        '<hp:cellMargin left="0" right="0" top="100" bottom="160"/>', 1)
    tbl_id = alloc.next()
    return (
        f'<hp:p id="{alloc.next()}" paraPrIDRef="0" styleIDRef="0" '
        f'pageBreak="{"1" if page_break else "0"}" columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0">'
        + _tbl_open(tbl_id, 1, 1, total_width, height, "2", repeat_header=False,
                    out_top=int(spec.get("prev", 0)), out_bottom=int(spec.get("next", 0)),
                    in_margin=rule_margin)
        + f'<hp:tr>{cell}</hp:tr></hp:tbl></hp:run></hp:p>')


def table(rows, alloc, *, header=True, total_width=42520, row_height=None,
          style_map=None, page_break=False, ctx=None):
    """표. 열 폭은 내용 비례, 짧은 값만 있는 열은 가운데·긴 글은 왼쪽 정렬,
    테마의 `outer`가 top-bottom이면 첫 행 위·마지막 행 아래를 굵은 선으로 긋는다."""
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
    cell_char = t.get("cell_char", "0")
    left_para = t.get("cell_para_left", cell_para)
    outer = t.get("outer", "none")
    row_height = row_height or t.get("row_height", 2400)
    widths = column_widths(rows, total_width)
    body_rows = rows[1:] if header else rows
    col_para = []
    for c in range(cols):
        longest = max((_em_width(r[c]) for r in body_rows), default=0)
        col_para.append(cell_para if longest <= 8 else left_para)
    last = len(rows) - 1
    char_h = int(t.get("row_height", 2400) - 282) // 2 if t else 1000   # 셀 글자 크기(HWPUNIT)
    tr_parts, heights = [], []
    for r, row in enumerate(rows):
        is_header = header and r == 0
        row_h = max(row_height, _row_height_for(row, widths, char_h))
        border = None
        if outer == "top-bottom":
            if is_header:
                border = t.get("header_border_both" if r == last else "header_border_top")
            elif r == last:
                border = t.get("body_border_bottom")
        cells = "".join(
            _cell(r, c, row[c], widths[c], row_h, alloc,
                  header_cell=is_header, header_char=header_char,
                  header_border=header_border, body_border=body_border,
                  cell_para=cell_para, style_map=style_map, cell_char=cell_char,
                  para_pr=None if is_header else col_para[c], border=border, ctx=ctx)
            for c in range(cols))
        tr_parts.append(f"<hp:tr>{cells}</hp:tr>")
        heights.append(row_h)
    tbl_id = alloc.next()
    height = sum(heights)
    return (
        f'<hp:p {NS_HP_DECL} id="{alloc.next()}" paraPrIDRef="0" styleIDRef="0" '
        f'pageBreak="{"1" if page_break else "0"}" columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0">'
        + _tbl_open(tbl_id, len(rows), cols, total_width, height, body_border,
                    repeat_header=header)
        + "".join(tr_parts) +
        '</hp:tbl></hp:run></hp:p>')
