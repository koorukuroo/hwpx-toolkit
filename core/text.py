"""hp:t 텍스트 모델 — 자식 인라인 요소를 포함해 읽고, 안전하게 다시 쓴다.

hp:t 안에는 글자 외에 `<hp:lineBreak/>`, `<hp:tab/>`, `<hp:fwSpace/>` 같은 빈 인라인
요소가 올 수 있고, 그 뒤 글자는 ElementTree에서 `.tail`로 매달린다. `.text`만 읽으면
요소 뒤 글자를 놓치고, `.text`만 쓰면 옛 글자가 찌꺼기로 남는다.

읽기 모델: 인라인 요소를 문자로 환원한다 (lineBreak→"\\n", tab→"\\t", fwSpace→U+3000,
nbSpace→U+00A0). 그 외 요소(markpenBegin 등)는 사용자에게 보이지 않는 사설 영역
문자로 자리만 잡아 두었다가 쓰기 시 원래 요소로 되돌린다.

쓰기 모델: 위 문자를 다시 요소로 만든다. 한컴은 hp:t 안의 탭 *문자*(U+0009)를 만나면
문서를 영원히 열지 못하므로 탭은 반드시 요소로 쓴다. XML에
허용되지 않는 제어문자는 제거한다.
"""
import re

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

INLINE_TO_CHAR = {
    "lineBreak": "\n",
    "tab": "\t",
    "fwSpace": "　",
    "nbSpace": " ",
}
CHAR_TO_INLINE = {v: k for k, v in INLINE_TO_CHAR.items()}

#: XML 1.0에서 허용되지 않거나 한컴이 받아들이지 않는 문자.
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")

_OPAQUE_BASE = 0xE000          # 사설 영역 — 불투명 자식 요소의 자리표시자
_OPAQUE_RE = re.compile(r"[-]")
_SPLIT_RE = re.compile(r"([\n\t　 -])")


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def t_model(t):
    """hp:t → (모델 문자열, 불투명 요소 목록). 모델 문자열은 인라인 요소를 문자로,
    그 외 자식은 사설 영역 자리표시자로 담는다."""
    parts = [t.text or ""]
    opaque = []
    for child in t:
        local = _local(child.tag)
        if local in INLINE_TO_CHAR:
            parts.append(INLINE_TO_CHAR[local])
        else:
            parts.append(chr(_OPAQUE_BASE + len(opaque)))
            opaque.append(child)
        parts.append(child.tail or "")
    return "".join(parts), opaque


def t_text(t):
    """hp:t의 보이는 텍스트 (lineBreak→\\n, tab→\\t). 불투명 요소는 제외."""
    model, _ = t_model(t)
    return _OPAQUE_RE.sub("", model)


def clean_text(text):
    """쓰기 전에 정규화: CRLF/CR→LF, XML 비허용 제어문자 제거."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return CONTROL_RE.sub("", text)


def t_write(t, model, opaque=()):
    """모델 문자열로 hp:t를 다시 구성한다. 자식 요소는 모두 교체된다."""
    ns = t.tag[:t.tag.rindex("}") + 1] if "}" in t.tag else ""
    for child in list(t):
        t.remove(child)
    t.text = None
    model = clean_text(model)
    last = None
    for piece in _SPLIT_RE.split(model):
        if not piece:
            continue
        if piece in CHAR_TO_INLINE or _OPAQUE_RE.fullmatch(piece):
            if piece in CHAR_TO_INLINE:
                el = t.makeelement(ns + CHAR_TO_INLINE[piece], {})
            else:
                idx = ord(piece) - _OPAQUE_BASE
                if idx >= len(opaque):
                    continue           # 출처 없는 자리표시자는 버린다
                el = opaque[idx]
            t.append(el)
            el.tail = None
            last = el
        elif last is None:
            t.text = (t.text or "") + piece
        else:
            last.tail = (last.tail or "") + piece


def set_t_text(t, text):
    """hp:t의 내용을 text로 교체한다 (자식 요소 제거, \\n·\\t는 요소로)."""
    t_write(t, text, ())
