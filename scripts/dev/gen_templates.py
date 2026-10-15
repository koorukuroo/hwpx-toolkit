#!/usr/bin/env python3
"""templates/<테마> 생성기 — OWPML(KS X 6101) 지식 기반 클린룸 작성.

템플릿을 고칠 때는 이 파일을 수정하고 재실행한다 (산출물 직접 편집 금지).
모든 테마는 같은 스타일 ID 배치를 쓴다 (references/base-template-styles.md).
테마는 THEMES 표의 값(글꼴·크기·색·선 굵기·목록 기호)만 다르다.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

LANGS = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]
CODE_FACE = "함초롬돋움"          # 코드·대체 글꼴 (한컴 기본 동봉)
GRAY = "595959"                   # 캡션·부제 글자색
BLACK = "000000"
NONE_LINE = ("NONE", "0.1 mm", BLACK)


# ---------------------------------------------------------------- 테마 정의
#: 테마별 값. 크기는 HWPUNIT(1pt = 100). 색은 RRGGBB.
THEMES = {
    "base": {
        "label": "기본 — 함초롬 글꼴, 남색 제목, 표 상하 굵은 선",
        "body_face": "함초롬바탕", "head_face": "함초롬돋움",
        "body": {"size": 1100, "spacing": 160, "next": 200, "align": "JUSTIFY"},
        "title": {"size": 2000, "color": "1F3864", "align": "CENTER", "prev": 0, "next": 600,
                  "rule": None},
        "h2": {"size": 1400, "color": "1F3864", "prev": 800, "next": 200,
               "rule": ("SOLID", "0.12 mm", "BFBFBF"), "chip": False},
        "h3": {"size": 1200, "color": BLACK, "prev": 400, "next": 100},
        "accent": "1F3864",
        "table": {"header_fill": "F2F2F2", "header_size": 1050, "cell_size": 1000,
                  "line": ("SOLID", "0.12 mm", "7F7F7F"), "thick": ("SOLID", "0.4 mm", BLACK),
                  "outer": "top-bottom"},
        "bullets": ["•", "-", "·"], "ordered": ["{n}.", "{n})", "({n})"],
    },
    "gonmun": {
        "page_number": "footer-center",
        "label": "공문 — 휴먼명조 15pt, HY헤드라인M 제목, 표 상하 굵은선",
        "body_face": "휴먼명조", "head_face": "HY헤드라인M",
        "body": {"size": 1500, "spacing": 160, "next": 0, "align": "JUSTIFY"},
        "title": {"size": 2000, "color": BLACK, "align": "CENTER", "prev": 0, "next": 1000,
                  "rule": None},
        "h2": {"size": 1500, "color": BLACK, "prev": 600, "next": 0,
               "rule": None, "chip": False, "face": "body", "bold": True},
        "h3": {"size": 1500, "color": BLACK, "prev": 300, "next": 0, "face": "body"},
        "accent": BLACK,
        "table": {"header_fill": None, "header_size": 1200, "cell_size": 1200,
                  "line": ("SOLID", "0.12 mm", BLACK), "thick": ("SOLID", "0.4 mm", BLACK),
                  "outer": "top-bottom"},
        "bullets": ["□", "○", "-", "·"], "ordered": ["{n}.", "{ga}.", "{n})", "{ga})"],
    },
    "report": {
        "page_number": "footer-center",
        "label": "보고서 — 남색 포인트, Ⅰ·Ⅱ 번호 칩 장 제목, 연남색 표 머리글",
        "body_face": "휴먼명조", "head_face": "HY헤드라인M",
        "body": {"size": 1500, "spacing": 160, "next": 200, "align": "JUSTIFY"},
        "title": {"size": 2200, "color": "1F3864", "align": "CENTER", "prev": 0, "next": 800,
                  "rule": ("SOLID", "0.4 mm", "1F3864")},
        "h2": {"size": 1600, "color": "1F3864", "prev": 1000, "next": 300,
               "rule": None, "chip": True},
        "h3": {"size": 1500, "color": BLACK, "prev": 500, "next": 100, "face": "body"},
        "accent": "1F3864",
        "table": {"header_fill": "DFE6F7", "header_size": 1200, "cell_size": 1200,
                  "line": ("SOLID", "0.12 mm", BLACK), "thick": ("SOLID", "0.4 mm", "1F3864"),
                  "outer": "top-bottom"},
        "bullets": ["□", "○", "-", "·"], "ordered": ["{n}.", "{ga}.", "{n})", "{ga})"],
    },
    "modern": {
        "label": "현대 — 맑은 고딕, 파랑 포인트, 왼쪽 정렬, 회색 선",
        "body_face": "맑은 고딕", "head_face": "맑은 고딕",
        "body": {"size": 1100, "spacing": 170, "next": 300, "align": "LEFT"},
        "title": {"size": 2400, "color": "1E2124", "align": "LEFT", "prev": 0, "next": 600,
                  "rule": ("SOLID", "0.3 mm", "256EF4")},
        "h2": {"size": 1400, "color": "256EF4", "prev": 900, "next": 200,
               "rule": None, "chip": False},
        "h3": {"size": 1200, "color": "1E2124", "prev": 500, "next": 100},
        "accent": "256EF4",
        "table": {"header_fill": "F4F5F6", "header_size": 1050, "cell_size": 1000,
                  "line": ("SOLID", "0.12 mm", "B1B8BE"), "thick": ("SOLID", "0.4 mm", "B1B8BE"),
                  "outer": "none"},
        "bullets": ["•", "–", "·"], "ordered": ["{n}.", "{n})", "({n})"],
    },
}


# ---------------------------------------------------------------- XML 조각
def _seven(value):
    keys = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")
    return " ".join(f'{k}="{value}"' for k in keys)


def fontfaces(body_face, head_face):
    faces = []
    for lang in LANGS:
        faces.append(
            f'<hh:fontface lang="{lang}" fontCnt="3">'
            f'<hh:font id="0" face="{body_face}" type="TTF" isEmbedded="0"/>'
            f'<hh:font id="1" face="{head_face}" type="TTF" isEmbedded="0"/>'
            f'<hh:font id="2" face="{CODE_FACE}" type="TTF" isEmbedded="0"/>'
            '</hh:fontface>')
    return '<hh:fontfaces itemCnt="7">' + "".join(faces) + '</hh:fontfaces>'


def border_fill(bid, *, left=NONE_LINE, right=NONE_LINE, top=NONE_LINE, bottom=NONE_LINE,
                fill=None):
    """edge = (type, width, color). fill = RRGGBB 또는 None."""
    edges = "".join(
        f'<hh:{name}Border type="{t}" width="{w}" color="#{c}"/>'
        for name, (t, w, c) in (("left", left), ("right", right), ("top", top),
                                ("bottom", bottom)))
    fill_xml = ""
    if fill:
        fill_xml = (f'<hc:fillBrush><hc:winBrush faceColor="#{fill}" '
                    'hatchColor="#999999" alpha="0"/></hc:fillBrush>')
    return (f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" '
            'breakCellSeparateLine="0">'
            '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
            '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
            f'{edges}'
            '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
            f'{fill_xml}</hh:borderFill>')


#: 한컴 표준 스타일 23종 (한컴오피스 새 문서의 스타일 목록과 같은 이름·순서).
#: 모두 paraPr 0 / charPr 0 을 가리킨다 — 목록이 비어 보이지 않게 하고, 사용자가
#: 한컴에서 스타일을 골라 쓸 수 있게 하는 것이 목적이다.
STANDARD_STYLES = [
    ("바탕글", "Normal"), ("본문", "Body"),
    *[(f"개요 {i}", f"Outline {i}") for i in range(1, 11)],
    ("쪽 번호", "Page Number"), ("줄 번호", "Line Number"), ("머리말", "Header"),
    ("각주", "Footnote"), ("미주", "Endnote"), ("메모", "Memo"),
    ("차례 제목", "TOC Heading"), ("차례 1", "TOC 1"), ("차례 2", "TOC 2"),
    ("차례 3", "TOC 3"), ("캡션", "Caption"),
]


def styles_xml():
    items = []
    for i, (name, eng) in enumerate(STANDARD_STYLES):
        items.append(f'<hh:style id="{i}" type="PARA" name="{name}" engName="{eng}" '
                     f'paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="{i}" langID="1042" '
                     'lockForm="0"/>')
    return f'<hh:styles itemCnt="{len(items)}">' + "".join(items) + "</hh:styles>"


def char_pr(cid, height, font=0, bold=False, color=BLACK, underline=False):
    bold_xml = "<hh:bold/>" if bold else ""
    ul = ("BOTTOM", color) if underline else ("NONE", "000000")
    return (f'<hh:charPr id="{cid}" height="{height}" textColor="#{color}" '
            'shadeColor="none" useFontSpace="0" useKerning="0" symMark="NONE" '
            'borderFillIDRef="2">'
            f'<hh:fontRef {_seven(font)}/>'
            f'<hh:ratio {_seven(100)}/>'
            f'<hh:spacing {_seven(0)}/>'
            f'<hh:relSz {_seven(100)}/>'
            f'<hh:offset {_seven(0)}/>'
            f'{bold_xml}'
            f'<hh:underline type="{ul[0]}" shape="SOLID" color="#{ul[1]}"/>'
            '<hh:strikeout shape="NONE" color="#000000"/>'
            '<hh:outline type="NONE"/>'
            '<hh:shadow type="NONE" color="#B2B2B2" offsetX="10" offsetY="10"/>'
            '</hh:charPr>')


def para_pr(pid, align="JUSTIFY", spacing=160, prev=0, nxt=0, left=0, right=0,
            intent=0, border=2, border_offset=0):
    """intent<0 이면 내어쓰기(둘째 줄부터 left 만큼 들여쓰고 첫 줄은 intent 만큼 당김).
    border = 문단 테두리 borderFill id (2 = 없음)."""
    margin = (
        '<hh:margin>'
        f'<hc:intent value="{intent}" unit="HWPUNIT"/>'
        f'<hc:left value="{left}" unit="HWPUNIT"/>'
        f'<hc:right value="{right}" unit="HWPUNIT"/>'
        f'<hc:prev value="{prev}" unit="HWPUNIT"/>'
        f'<hc:next value="{nxt}" unit="HWPUNIT"/>'
        '</hh:margin>'
        f'<hh:lineSpacing type="PERCENT" value="{spacing}" unit="HWPUNIT"/>')
    return (f'<hh:paraPr id="{pid}" tabPrIDRef="0" condense="0" '
            'fontLineHeight="0" snapToGrid="1" suppressLineNumbers="0" checked="0">'
            f'<hh:align horizontal="{align}" vertical="BASELINE"/>'
            '<hh:heading type="NONE" idRef="0" level="0"/>'
            # 한글은 글자 단위로 줄을 나눈다 (단어 단위로 두면 양쪽정렬에서 단어 사이가 크게 벌어진다)
            '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="BREAK_WORD" '
            'widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" '
            'lineWrap="BREAK"/>'
            '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
            '<hp:switch>'
            f'<hp:case hp:required-namespace='
            f'"http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">{margin}</hp:case>'
            f'<hp:default>{margin}</hp:default>'
            '</hp:switch>'
            f'<hh:border borderFillIDRef="{border}" offsetLeft="0" offsetRight="0" '
            f'offsetTop="0" offsetBottom="{border_offset}" connect="0" ignoreMargin="0"/>'
            '</hh:paraPr>')


# ---------------------------------------------------------------- 테마 → header
#: 스타일 ID 배치 (모든 테마 공통). 숫자는 references/base-template-styles.md와 같다.
BF_PAGE, BF_NONE, BF_CELL, BF_HEAD, BF_ACCENT, BF_H2_RULE, BF_TITLE_RULE, \
    BF_CHIP_TITLE, BF_HEAD_TOP, BF_CELL_BOTTOM, BF_HEAD_BOTH = range(1, 12)
CH_BODY, CH_TITLE, CH_H2, CH_H3, CH_THEAD, CH_BOLD, CH_CODE, CH_CELL, CH_ON_ACCENT, \
    CH_CAPTION, CH_SUBTITLE, CH_LINK = range(12)
LINK_COLOR = "0563C1"
PA_BODY, PA_TITLE, PA_H2, PA_H3, PA_LIST1, PA_CELL, PA_LIST2, PA_LIST3, PA_QUOTE, \
    PA_CODE, PA_CELL_LEFT, PA_CAPTION, PA_SUBTITLE = range(13)


def theme_header(theme):
    t = THEMES[theme]
    tb, body, title, h2, h3 = t["table"], t["body"], t["title"], t["h2"], t["h3"]
    line, thick = tb["line"], tb["thick"]
    head_fill = tb["header_fill"]
    accent = t["accent"]

    def rule_fill(bid, rule, *, top=False):
        if rule is None:
            return border_fill(bid)
        if top:
            return border_fill(bid, top=rule)
        return border_fill(bid, bottom=rule)

    border_fills = [
        border_fill(BF_PAGE),
        border_fill(BF_NONE),
        border_fill(BF_CELL, left=line, right=line, top=line, bottom=line),
        border_fill(BF_HEAD, left=line, right=line, top=line, bottom=line, fill=head_fill),
        border_fill(BF_ACCENT, fill=accent),
        rule_fill(BF_H2_RULE, h2["rule"]),
        rule_fill(BF_TITLE_RULE, title["rule"]),
        border_fill(BF_CHIP_TITLE, bottom=thick),
        border_fill(BF_HEAD_TOP, left=line, right=line, top=thick, bottom=line, fill=head_fill),
        border_fill(BF_CELL_BOTTOM, left=line, right=line, top=line, bottom=thick),
        border_fill(BF_HEAD_BOTH, left=line, right=line, top=thick, bottom=thick,
                    fill=head_fill),
    ]
    face = {"body": 0, "head": 1}
    h2_face = face[h2.get("face", "head")]
    h3_face = face[h3.get("face", "head")]
    char_prs = [
        char_pr(CH_BODY, body["size"]),
        char_pr(CH_TITLE, title["size"], font=1, bold=True, color=title["color"]),
        char_pr(CH_H2, h2["size"], font=h2_face, bold=True, color=h2["color"]),
        char_pr(CH_H3, h3["size"], font=h3_face, bold=True, color=h3["color"]),
        char_pr(CH_THEAD, tb["header_size"], font=1, bold=True),
        char_pr(CH_BOLD, body["size"], bold=True),
        char_pr(CH_CODE, max(900, body["size"] - 200), font=2),
        char_pr(CH_CELL, tb["cell_size"], font=face[tb.get("cell_face", "head")]),
        char_pr(CH_ON_ACCENT, h2["size"], font=1, bold=True, color="FFFFFF"),
        char_pr(CH_CAPTION, max(900, body["size"] - 200), color=GRAY),
        char_pr(CH_SUBTITLE, body["size"], color=GRAY),
        char_pr(CH_LINK, body["size"], color=LINK_COLOR, underline=True),
    ]
    hang = int(body["size"] * 1.3)           # 목록 내어쓰기 폭 (기호 + 공백)
    sp = body["spacing"]
    para_prs = [
        para_pr(PA_BODY, align=body["align"], spacing=sp, nxt=body["next"]),
        # 제목 아래 선은 문단 테두리로 그리지 않는다 — 한글은 문단 아래 간격까지 테두리에
        # 넣어 선이 다음 문단에 붙는다. 선이 있는 제목은 셀 아래선을 쓰는 1칸 표로 만든다
        # (styles.json title_rule / h2_rule; core.owpml.rule_heading).
        para_pr(PA_TITLE, align=title["align"], spacing=130, prev=title["prev"],
                nxt=title["next"]),
        para_pr(PA_H2, align="LEFT", spacing=140, prev=h2["prev"], nxt=h2["next"]),
        para_pr(PA_H3, align="LEFT", spacing=140, prev=h3["prev"], nxt=h3["next"]),
        para_pr(PA_LIST1, align=body["align"], spacing=sp, left=hang, intent=-hang),
        para_pr(PA_CELL, align="CENTER", spacing=130),
        para_pr(PA_LIST2, align=body["align"], spacing=sp, left=hang * 2, intent=-hang),
        para_pr(PA_LIST3, align=body["align"], spacing=sp, left=hang * 3, intent=-hang),
        para_pr(PA_QUOTE, align=body["align"], spacing=150, left=hang, right=hang,
                prev=200, nxt=200),
        para_pr(PA_CODE, align="LEFT", spacing=130, left=400),
        para_pr(PA_CELL_LEFT, align="LEFT", spacing=130),
        para_pr(PA_CAPTION, align="CENTER", spacing=130, prev=100, nxt=400),
        para_pr(PA_SUBTITLE, align=title["align"], spacing=150, nxt=800),
    ]
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
        'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
        'version="1.4" secCnt="1">',
        '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>',
        '<hh:refList>',
        fontfaces(t["body_face"], t["head_face"]),
        f'<hh:borderFills itemCnt="{len(border_fills)}">',
        *border_fills,
        '</hh:borderFills>',
        f'<hh:charProperties itemCnt="{len(char_prs)}">',
        *char_prs,
        '</hh:charProperties>',
        '<hh:tabProperties itemCnt="1">'
        '<hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/>'
        '</hh:tabProperties>',
        f'<hh:paraProperties itemCnt="{len(para_prs)}">',
        *para_prs,
        '</hh:paraProperties>',
        styles_xml(),
        '</hh:refList>',
        '</hh:head>',
    ]
    return "".join(parts)


def theme_styles(theme):
    """styles.json — 렌더러(core/owpml, core/markdown)가 읽는 스타일 ID 맵."""
    t = THEMES[theme]
    tb = t["table"]
    s = lambda v: str(v)  # noqa: E731
    styles = {
        "theme": theme,
        "heading": {"1": [s(CH_TITLE), s(PA_TITLE)], "2": [s(CH_H2), s(PA_H2)],
                    "default": [s(CH_H3), s(PA_H3)]},
        "body": [s(CH_BODY), s(PA_BODY)],
        "bullet_para": s(PA_LIST1),
        "bullet_levels": [s(PA_LIST1), s(PA_LIST2), s(PA_LIST3)],
        "bullets": t["bullets"],
        "ordered": t["ordered"],
        "table": {
            "header_char": s(CH_THEAD), "header_border": s(BF_HEAD),
            "body_border": s(BF_CELL), "cell_para": s(PA_CELL),
            "cell_char": s(CH_CELL), "cell_para_left": s(PA_CELL_LEFT),
            "header_border_top": s(BF_HEAD_TOP), "body_border_bottom": s(BF_CELL_BOTTOM),
            "header_border_both": s(BF_HEAD_BOTH),
            "outer": tb["outer"],
            "row_height": tb["cell_size"] * 2 + 282,
        },
        "bold_char": s(CH_BOLD), "code_char": s(CH_CODE),
        "quote_para": s(PA_QUOTE), "code_para": s(PA_CODE),
        "caption": [s(CH_CAPTION), s(PA_CAPTION)],
        "subtitle": [s(CH_SUBTITLE), s(PA_SUBTITLE)],
        "link_char": s(CH_LINK),
        "page_number": t.get("page_number", "none"),
    }
    if t["title"]["rule"]:
        styles["title_rule"] = {"border": s(BF_TITLE_RULE), "char": s(CH_TITLE),
                                "para": s(PA_CELL if t["title"]["align"] == "CENTER" else PA_CELL_LEFT),
                                "size": t["title"]["size"],
                                "prev": t["title"]["prev"], "next": t["title"]["next"]}
    if t["h2"].get("rule") and not t["h2"].get("chip"):
        styles["h2_rule"] = {"border": s(BF_H2_RULE), "char": s(CH_H2), "para": s(PA_CELL_LEFT),
                             "size": t["h2"]["size"],
                             "prev": t["h2"]["prev"], "next": t["h2"]["next"]}
    if t["h2"].get("chip"):
        styles["section_chip"] = {
            "num_char": s(CH_ON_ACCENT), "num_border": s(BF_ACCENT),
            "title_char": s(CH_H2), "title_border": s(BF_CHIP_TITLE),
            "size": t["h2"]["size"], "numbering": "roman",
        }
    return styles


# ---------------------------------------------------------------- 공통 파트
def _note_pr(tag, place, line_length):
    return (f'<hp:{tag}>'
            '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" '
            'suffixChar=")" supscript="0"/>'
            f'<hp:noteLine length="{line_length}" type="SOLID" width="0.12 mm" '
            'color="#000000"/>'
            '<hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/>'
            '<hp:numbering type="CONTINUOUS" newNum="1"/>'
            f'<hp:placement place="{place}" beneathText="0"/>'
            f'</hp:{tag}>')


def section0_xml():
    page_border = "".join(
        f'<hp:pageBorderFill type="{t}" borderFillIDRef="1" textBorder="PAPER" '
        'headerInside="0" footerInside="0" fillArea="PAPER">'
        '<hp:offset left="1417" right="1417" top="1417" bottom="1417"/>'
        '</hp:pageBorderFill>'
        for t in ("BOTH", "EVEN", "ODD"))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
        '<hp:p id="1000000000" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0">'
        '<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" '
        'tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" '
        'outlineShapeIDRef="0" memoShapeIDRef="0" textVerticalWidthHead="0" '
        'masterPageCnt="0">'
        '<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>'
        '<hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>'
        '<hp:visibility hideFirstHeader="0" hideFirstFooter="0" '
        'hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL" '
        'hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>'
        '<hp:lineNumberShape restartType="0" countBy="0" distance="0" '
        'startNumber="0"/>'
        '<hp:pagePr landscape="WIDELY" width="59528" height="84186" '
        'gutterType="LEFT_ONLY">'
        '<hp:margin header="4252" footer="4252" gutter="0" left="8504" '
        'right="8504" top="5668" bottom="4252"/>'
        '</hp:pagePr>'
        + _note_pr("footNotePr", "EACH_COLUMN", "-1")
        + _note_pr("endNotePr", "END_OF_DOCUMENT", "14692344")
        + page_border +
        '</hp:secPr>'
        '<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" '
        'sameSz="1" sameGap="0"/></hp:ctrl>'
        '</hp:run>'
        '<hp:run charPrIDRef="0"><hp:t/></hp:run>'
        '</hp:p>'
        '<hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="0"><hp:t/></hp:run>'
        '</hp:p>'
        '</hs:sec>')


VERSION_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
    'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="1" '
    'buildNumber="0" os="10" xmlVersion="1.4" application="hwpx-toolkit" '
    'appVersion="0.2"/>')

SETTINGS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<ha:HWPApplicationSetting '
    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app">'
    '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>'
    '</ha:HWPApplicationSetting>')

CONTAINER_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<ocf:container '
    'xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" '
    'media-type="application/hwpml-package+xml"/></ocf:rootfiles>'
    '</ocf:container>')

MANIFEST_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<odf:manifest '
    'xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">'
    '<odf:file-entry odf:full-path="mimetype" odf:media-type=""/>'
    '<odf:file-entry odf:full-path="version.xml" odf:media-type=""/>'
    '<odf:file-entry odf:full-path="Contents/header.xml" '
    'odf:media-type="application/xml"/>'
    '<odf:file-entry odf:full-path="Contents/section0.xml" '
    'odf:media-type="application/xml"/>'
    '<odf:file-entry odf:full-path="settings.xml" '
    'odf:media-type="application/xml"/>'
    '</odf:manifest>')

CONTENT_HPF = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" version="" '
    'unique-identifier="" id="">'
    '<opf:metadata><opf:title>무제</opf:title>'
    '<opf:language>ko</opf:language></opf:metadata>'
    '<opf:manifest>'
    '<opf:item id="header" href="Contents/header.xml" '
    'media-type="application/xml"/>'
    '<opf:item id="section0" href="Contents/section0.xml" '
    'media-type="application/xml"/>'
    '<opf:item id="settings" href="settings.xml" '
    'media-type="application/xml"/>'
    '</opf:manifest>'
    '<opf:spine><opf:itemref idref="header"/>'
    '<opf:itemref idref="section0"/></opf:spine>'
    '</opf:package>')


def write_template(name):
    tdir = ROOT / "templates" / name
    files = {
        "mimetype": "application/hwp+zip",
        "version.xml": VERSION_XML,
        "settings.xml": SETTINGS_XML,
        "META-INF/container.xml": CONTAINER_XML,
        "META-INF/manifest.xml": MANIFEST_XML,
        "Contents/content.hpf": CONTENT_HPF,
        "Contents/header.xml": theme_header(name),
        "Contents/section0.xml": section0_xml(),
        "styles.json": json.dumps(theme_styles(name), ensure_ascii=False, indent=2) + "\n",
    }
    for rel, text in files.items():
        path = tdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files to {tdir}")


def main():
    for name in THEMES:
        write_template(name)


if __name__ == "__main__":
    main()
