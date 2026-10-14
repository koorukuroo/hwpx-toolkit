"""이미지 바이너리 판독·hpf 등록·hp:pic XML 생성 (stdlib)."""
import re
import struct

from core.errors import EditError

MM_PER_INCH = 25.4
HWP_PER_MM = 283.5


def image_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if len(data) < 24:
            raise EditError("잘린 PNG (IHDR 없음)")
        w, h = struct.unpack(">II", data[16:24])
        return w, h, "png"
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker == 0xFF:          # 패딩 바이트
                i += 1
                continue
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h, "jpg"
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
        raise EditError("JPEG SOF 마커를 찾지 못함")
    raise EditError("지원하지 않는 이미지 형식 (PNG/JPEG만)")


def next_bin_id(pkg):
    hpf = pkg.read_text("Contents/content.hpf")
    nums = [int(n) for n in re.findall(r'id="image(\d+)"', hpf)]
    for name in pkg.names():
        m = re.fullmatch(r"BinData/image(\d+)\.\w+", name)
        if m:
            nums.append(int(m.group(1)))
    n = max(nums, default=0) + 1
    return f"image{n}", f"BinData/image{n}"


def register_in_hpf(hpf_text, item_id, href, ext):
    mime = "image/png" if ext == "png" else "image/jpeg"
    item = (f'<opf:item id="{item_id}" href="{href}" media-type="{mime}" '
            'isEmbeded="1"/>')
    if "</opf:manifest>" not in hpf_text:
        raise EditError("content.hpf에 manifest 없음")
    return hpf_text.replace("</opf:manifest>", item + "</opf:manifest>", 1)


def mm_to_hwp(mm):
    return int(round(float(mm) * HWP_PER_MM))


def hwp_to_mm(v):
    return round(int(v) / HWP_PER_MM, 1)


def px_to_hwp(px):
    return int(round(px / 96 * MM_PER_INCH * HWP_PER_MM))


def pic_xml(pic_id, bin_id, w, h, px_w, px_h, instid=None):
    org_w, org_h = px_to_hwp(px_w), px_to_hwp(px_h)
    # instid는 개체 인스턴스 식별자 — 그림마다 달라야 한다 (0 공유 금지).
    instid = str(instid) if instid is not None else str(pic_id)
    return (
        f'<hp:pic xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
        f'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
        f'id="{pic_id}" zOrder="0" numberingType="PICTURE" '
        'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
        f'dropcapstyle="None" href="" groupLevel="0" instid="{instid}" reverse="0">'
        '<hp:offset x="0" y="0"/>'
        f'<hp:orgSz width="{org_w}" height="{org_h}"/>'
        f'<hp:curSz width="{w}" height="{h}"/>'
        '<hp:flip horizontal="0" vertical="0"/>'
        '<hp:rotationInfo angle="0" centerX="0" centerY="0" rotateimage="0"/>'
        '<hp:renderingInfo>'
        '<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        '</hp:renderingInfo>'
        f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/>'
        f'<hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
        f'<hp:imgClip left="0" right="{org_w}" top="0" bottom="{org_h}"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        f'<hp:imgDim dimwidth="{org_w}" dimheight="{org_h}"/>'
        f'<hc:img binaryItemIDRef="{bin_id}" bright="0" contrast="0" '
        'effect="REAL_PIC" alpha="0"/>'
        '<hp:effects></hp:effects>'
        f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" '
        'heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
        'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" '
        'vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        '</hp:pic>')
