#!/usr/bin/env python3
"""templates/base, templates/report 생성기 — OWPML(KS X 6101) 지식 기반 클린룸 작성.

템플릿을 고칠 때는 이 파일을 수정하고 재실행한다 (산출물 직접 편집 금지).
스타일 ID 맵은 docs/superpowers/plans/2026-08-15-hwpx-toolkit-phase2.md 및
references/base-template-styles.md 참조.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

LANGS = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]


def _seven(value):
    keys = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")
    return " ".join(f'{k}="{value}"' for k in keys)


def fontfaces():
    faces = []
    for lang in LANGS:
        faces.append(
            f'<hh:fontface lang="{lang}" fontCnt="2">'
            '<hh:font id="0" face="함초롬바탕" type="TTF" isEmbedded="0"/>'
            '<hh:font id="1" face="함초롬돋움" type="TTF" isEmbedded="0"/>'
            '</hh:fontface>')
    return '<hh:fontfaces itemCnt="7">' + "".join(faces) + '</hh:fontfaces>'


def border_fill(bid, edge_type="NONE", width="0.1 mm", fill=None):
    edges = "".join(
        f'<hh:{e}Border type="{edge_type}" width="{width}" color="#000000"/>'
        for e in ("left", "right", "top", "bottom"))
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


def char_pr(cid, height, font=0, bold=False, color="000000"):
    bold_xml = "<hh:bold/>" if bold else ""
    return (f'<hh:charPr id="{cid}" height="{height}" textColor="#{color}" '
            'shadeColor="none" useFontSpace="0" useKerning="0" symMark="NONE" '
            'borderFillIDRef="2">'
            f'<hh:fontRef {_seven(font)}/>'
            f'<hh:ratio {_seven(100)}/>'
            f'<hh:spacing {_seven(0)}/>'
            f'<hh:relSz {_seven(100)}/>'
            f'<hh:offset {_seven(0)}/>'
            f'{bold_xml}'
            '<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
            '<hh:strikeout shape="NONE" color="#000000"/>'
            '<hh:outline type="NONE"/>'
            '<hh:shadow type="NONE" color="#B2B2B2" offsetX="10" offsetY="10"/>'
            '</hh:charPr>')


def para_pr(pid, align="JUSTIFY", spacing=160, prev=0, nxt=0, left=0):
    margin = (
        '<hh:margin>'
        '<hc:intent value="0" unit="HWPUNIT"/>'
        f'<hc:left value="{left}" unit="HWPUNIT"/>'
        '<hc:right value="0" unit="HWPUNIT"/>'
        f'<hc:prev value="{prev}" unit="HWPUNIT"/>'
        f'<hc:next value="{nxt}" unit="HWPUNIT"/>'
        '</hh:margin>'
        f'<hh:lineSpacing type="PERCENT" value="{spacing}" unit="HWPUNIT"/>')
    return (f'<hh:paraPr id="{pid}" tabPrIDRef="0" condense="0" '
            'fontLineHeight="0" snapToGrid="1" suppressLineNumbers="0" checked="0">'
            f'<hh:align horizontal="{align}" vertical="BASELINE"/>'
            '<hh:heading type="NONE" idRef="0" level="0"/>'
            '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" '
            'widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" '
            'lineWrap="BREAK"/>'
            '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
            '<hp:switch>'
            f'<hp:case hp:required-namespace='
            f'"http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">{margin}</hp:case>'
            f'<hp:default>{margin}</hp:default>'
            '</hp:switch>'
            '<hh:border borderFillIDRef="2" offsetLeft="0" offsetRight="0" '
            'offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/>'
            '</hh:paraPr>')


def header_xml(extra_border_fills=(), extra_char_prs=(), extra_para_prs=()):
    border_fills = [
        border_fill(1),
        border_fill(2),
        border_fill(3, edge_type="SOLID", width="0.12 mm"),
        border_fill(4, edge_type="SOLID", width="0.12 mm", fill="E6E6E6"),
        *extra_border_fills,
    ]
    char_prs = [
        char_pr(0, 1000),
        char_pr(1, 1800, font=1, bold=True),
        char_pr(2, 1400, font=1, bold=True),
        char_pr(3, 1200, font=1, bold=True),
        char_pr(4, 1000, font=1, bold=True),
        *extra_char_prs,
    ]
    para_prs = [
        para_pr(0),
        para_pr(1, align="CENTER", prev=800, nxt=800),
        para_pr(2, align="LEFT", prev=600, nxt=200),
        para_pr(3, align="LEFT", prev=400, nxt=100),
        para_pr(4, left=600),
        para_pr(5, align="CENTER", spacing=130),
        *extra_para_prs,
    ]
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
        'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
        'version="1.4" secCnt="1">',
        '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>',
        '<hh:refList>',
        fontfaces(),
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
        '<hh:styles itemCnt="1">'
        '<hh:style id="0" type="PARA" name="바탕글" engName="Normal" '
        'paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0" langID="1042" '
        'lockForm="0"/>'
        '</hh:styles>',
        '</hh:refList>',
        '</hh:head>',
    ]
    return "".join(parts)


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


BASE_STYLES = {
    "heading": {"1": ["1", "1"], "2": ["2", "2"], "default": ["3", "3"]},
    "body": ["0", "0"], "bullet_para": "4",
    "table": {"header_char": "4", "header_border": "4", "body_border": "3",
              "cell_para": "5"},
}
REPORT_STYLES = {
    "heading": {"1": ["5", "1"], "2": ["2", "6"], "default": ["3", "3"]},
    "body": ["0", "0"], "bullet_para": "4",
    "table": {"header_char": "4", "header_border": "4", "body_border": "3",
              "cell_para": "5"},
    "section_bar": {"char": "6", "border": "5"},
}


def write_template(name, header, styles):
    tdir = ROOT / "templates" / name
    files = {
        "mimetype": "application/hwp+zip",
        "version.xml": VERSION_XML,
        "settings.xml": SETTINGS_XML,
        "META-INF/container.xml": CONTAINER_XML,
        "META-INF/manifest.xml": MANIFEST_XML,
        "Contents/content.hpf": CONTENT_HPF,
        "Contents/header.xml": header,
        "Contents/section0.xml": section0_xml(),
        "styles.json": json.dumps(styles, ensure_ascii=False, indent=2) + "\n",
    }
    for rel, text in files.items():
        path = tdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files to {tdir}")


def main():
    write_template("base", header_xml(), BASE_STYLES)
    write_template("report", header_xml(
        extra_border_fills=[border_fill(5, edge_type="SOLID", width="0.12 mm",
                                        fill="1F3864")],
        extra_char_prs=[char_pr(5, 1600, font=1, bold=True),
                        char_pr(6, 1200, font=1, bold=True, color="FFFFFF")],
        extra_para_prs=[para_pr(6, align="LEFT", prev=600, nxt=200)],
    ), REPORT_STYLES)


if __name__ == "__main__":
    main()
