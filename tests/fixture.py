"""테스트용 최소 HWPX 패키지 빌더 (자체 작성 XML, 외부 파일 미복사)."""
import zipfile
from pathlib import Path

MIMETYPE = "application/hwp+zip"

VERSION_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
    'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="1" '
    'buildNumber="0" os="10" xmlVersion="1.4" application="hwpx-toolkit" appVersion="0.1"/>'
)

SETTINGS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"/>'
)

CONTAINER_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" '
    'media-type="application/hwpml-package+xml"/></ocf:rootfiles></ocf:container>'
)

MANIFEST_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'
)

CONTENT_HPF = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/" version="" '
    'unique-identifier="" id="">'
    '<opf:metadata><opf:title>fixture</opf:title></opf:metadata>'
    '<opf:manifest>'
    '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
    '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
    '</opf:manifest>'
    '<opf:spine><opf:itemref idref="header"/><opf:itemref idref="section0"/></opf:spine>'
    '</opf:package>'
)

HEADER_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
    'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" version="1.4" secCnt="1">'
    '<hh:refList>'
    '<hh:fontfaces itemCnt="1">'
    '<hh:fontface lang="HANGUL" fontCnt="1">'
    '<hh:font id="0" face="함초롬바탕" type="TTF" isEmbedded="0"/>'
    '</hh:fontface></hh:fontfaces>'
    '<hh:borderFills itemCnt="1">'
    '<hh:borderFill id="1" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
    '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
    '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
    '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
    '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
    '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
    '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
    '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
    '</hh:borderFill></hh:borderFills>'
    '<hh:charProperties itemCnt="1">'
    '<hh:charPr id="0" height="1000" textColor="#000000" shadeColor="none" '
    'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="1">'
    '<hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
    '</hh:charPr></hh:charProperties>'
    '<hh:paraProperties itemCnt="1">'
    '<hh:paraPr id="0" tabPrIDRef="0" condense="0" fontLineHeight="0" '
    'snapToGrid="1" suppressLineNumbers="0" checked="0">'
    '<hh:align horizontal="JUSTIFY" vertical="BASELINE"/>'
    '</hh:paraPr></hh:paraProperties>'
    '</hh:refList></hh:head>'
)

SECTION_HEAD = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
    '<hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0">'
    '<hp:run charPrIDRef="0">'
    '<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000">'
    '<hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">'
    '<hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" '
    'top="5668" bottom="4252"/>'
    '</hp:pagePr></hp:secPr>'
    '<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" '
    'sameSz="1" sameGap="0"/></hp:ctrl>'
    '</hp:run></hp:p>'
)

BODY_PARA = (
    '<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0">'
    '<hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run></hp:p>'
)

SPLIT_PARA = (
    '<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
    'columnBreak="0" merged="0">'
    '<hp:run charPrIDRef="0"><hp:t>{a}</hp:t></hp:run>'
    '<hp:run charPrIDRef="0"><hp:t>{b}</hp:t></hp:run>'
    '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1000" '
    'textheight="1000" baseline="850" spacing="600" horzpos="0" '
    'horzsize="42520" flags="393216"/></hp:linesegarray>'
    '</hp:p>'
)


def _cell(row, col, text, pid):
    return (
        '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '
        'dirty="0" borderFillIDRef="1">'
        '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
        'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
        'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run></hp:p>'
        '</hp:subList>'
        f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:cellSz width="21260" height="2400"/>'
        '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
        '</hp:tc>'
    )


def _table(rows=None):
    if rows is None:
        rows = [["셀00", "셀01"], ["셀10", "셀11"]]
    tr_parts = []
    pid = 1000000200
    for r, row in enumerate(rows):
        cells = "".join(_cell(r, c, row[c], pid + r * len(row) + c)
                        for c in range(len(row)))
        tr_parts.append(f"<hp:tr>{cells}</hp:tr>")
    n_rows, n_cols = len(rows), len(rows[0])
    return (
        '<hp:p id="1000000100" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
        'columnBreak="0" merged="0"><hp:run charPrIDRef="0">'
        '<hp:tbl id="1000000101" zOrder="0" numberingType="TABLE" '
        'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
        f'rowCnt="{n_rows}" colCnt="{n_cols}" cellSpacing="0" '
        'borderFillIDRef="1" noAdjust="0">'
        f'<hp:sz width="42520" widthRelTo="ABSOLUTE" height="{2400 * n_rows}" '
        'heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
        'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
        'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
        'vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        + "".join(tr_parts) +
        '</hp:tbl></hp:run></hp:p>'
    )


def build_minimal_hwpx(path, *, body_texts=None, with_table=False):
    path = Path(path)
    if body_texts is None:
        body_texts = ["안녕하세요", "두 번째 문단"]
    parts = [SECTION_HEAD]
    pid = 1000000002
    for t in body_texts:
        parts.append(BODY_PARA.format(pid=pid, text=t))
        pid += 1
    if with_table:
        parts.append(_table())
    parts.append("</hs:sec>")
    section0 = "".join(parts)

    entries = [
        ("mimetype", MIMETYPE),
        ("version.xml", VERSION_XML),
        ("settings.xml", SETTINGS_XML),
        ("META-INF/container.xml", CONTAINER_XML),
        ("META-INF/manifest.xml", MANIFEST_XML),
        ("Contents/content.hpf", CONTENT_HPF),
        ("Contents/header.xml", HEADER_XML),
        ("Contents/section0.xml", section0),
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in entries:
            ctype = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            zf.writestr(zipfile.ZipInfo(name), text.encode("utf-8"), compress_type=ctype)
    return path


def build_form_hwpx(path):
    """편집/채우기 테스트용 양식: 라벨-값 표, 체크박스, 괄호 빈칸, run 분할 문단."""
    path = Path(path)
    parts = [SECTION_HEAD]
    parts.append(_table(rows=[["성명", ""], ["연락처", ""]]))
    parts.append(BODY_PARA.format(pid=1000000301, text="□동의 □비동의"))
    parts.append(BODY_PARA.format(pid=1000000302, text="제출 부수: 일반(  )통"))
    parts.append(SPLIT_PARA.format(pid=1000000303, a="안녕", b="하세요"))
    parts.append(SPLIT_PARA.format(pid=1000000304, a="감사", b="합니다"))
    parts.append("</hs:sec>")
    section0 = "".join(parts)

    entries = [
        ("mimetype", MIMETYPE),
        ("version.xml", VERSION_XML),
        ("settings.xml", SETTINGS_XML),
        ("META-INF/container.xml", CONTAINER_XML),
        ("META-INF/manifest.xml", MANIFEST_XML),
        ("Contents/content.hpf", CONTENT_HPF),
        ("Contents/header.xml", HEADER_XML),
        ("Contents/section0.xml", section0),
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in entries:
            ctype = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            zf.writestr(zipfile.ZipInfo(name), text.encode("utf-8"),
                        compress_type=ctype)
    return path
