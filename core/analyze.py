"""문서 분석 — 텍스트 추출, 구조 리포트, 편집 슬롯."""
import re
import xml.etree.ElementTree as ET

from core.package import HwpxPackage, section_names
from core.text import t_text

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _q(tag):
    return f"{{{NS_HP}}}{tag}"


def _para_direct_text(p_el):
    """문단의 직접 런 텍스트 (표/개체 내부 제외). 셀 줄바꿈(hp:lineBreak)은
    "\\n", 탭(hp:tab)은 "\\t"로 환원한다."""
    parts = []
    for run in p_el.findall(_q("run")):
        for t in run.findall(_q("t")):
            parts.append(t_text(t))
    return "".join(parts)


def _flat(text, nl=" "):
    """표 한 줄로 그릴 때 셀 안 줄바꿈·탭을 치환."""
    return text.replace("\n", nl).replace("\t", " ")


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _table_rows(tbl_el, nl=" "):
    """표를 (rowCnt × colCnt) 격자로 펼친다. 병합 셀이 차지하는 자리는 빈 문자열로
    채워 모든 행의 열 수가 같다. 셀 텍스트는 중첩 표·글상자까지 포함한다."""
    n_rows = _int(tbl_el.get("rowCnt"))
    n_cols = _int(tbl_el.get("colCnt"))
    grid = {}
    max_r = max_c = -1
    for tr in tbl_el.findall(_q("tr")):
        for tc in tr.findall(_q("tc")):
            addr = tc.find(_q("cellAddr"))
            if addr is None:
                continue
            r, c = _int(addr.get("rowAddr")), _int(addr.get("colAddr"))
            grid[(r, c)] = _cell_text(tc, nl)
            span = tc.find(_q("cellSpan"))
            rs = _int(span.get("rowSpan"), 1) if span is not None else 1
            cs = _int(span.get("colSpan"), 1) if span is not None else 1
            max_r, max_c = max(max_r, r + rs - 1), max(max_c, c + cs - 1)
    n_rows = max(n_rows, max_r + 1)
    n_cols = max(n_cols, max_c + 1)
    return [[grid.get((r, c), "") for c in range(n_cols)] for r in range(n_rows)]


def _cell_text(tc, nl=" "):
    sub = tc.find(_q("subList"))
    if sub is None:
        return ""
    lines = []
    for p in sub.findall(_q("p")):
        lines.extend(_para_lines(p, nl))
    return nl.join(_flat(l, nl) for l in lines if l)


_SHAPE_TAGS = ("rect", "ellipse", "line", "polygon", "curve", "arc",
               "container", "pic", "ole", "textart", "connectLine")
_NOTE_LABEL = {"header": "[머리말]", "footer": "[꼬리말]",
               "footNote": "[각주]", "endNote": "[미주]"}


def _para_items(p, nl=" "):
    """문단 하나를 항목 목록으로: ("text", str) | ("table", rows) | ("note", str).
    순서는 직접 텍스트 → run 순서대로 표/글상자/머리말·각주."""
    out = []
    text = _para_direct_text(p)
    if text:
        out.append(("text", text))
    for run in p.findall(_q("run")):
        for child in run:
            local = child.tag.rsplit("}", 1)[-1]
            if local == "tbl":
                out.append(("table", _table_rows(child, nl)))
            elif local in _SHAPE_TAGS:
                for dt in child.iter(_q("drawText")):
                    sub = dt.find(_q("subList"))
                    if sub is None:
                        continue
                    for sp in sub.findall(_q("p")):
                        out.extend(_para_items(sp, nl))
            elif local == "ctrl":
                for story in child:
                    kind = story.tag.rsplit("}", 1)[-1]
                    label = _NOTE_LABEL.get(kind)
                    if label is None:
                        continue
                    sub = story.find(_q("subList"))
                    if sub is None:
                        continue
                    lines = []
                    for sp in sub.findall(_q("p")):
                        lines.extend(_para_lines(sp, " "))
                    body = " ".join(l for l in lines if l)
                    if body:
                        out.append(("note", f"{label} {body}"))
    return out


def _para_lines(p, nl=" "):
    """문단을 줄 목록으로 평탄화 (중첩 표는 행마다 'a | b')."""
    lines = []
    for kind, payload in _para_items(p, nl):
        if kind == "table":
            for row in payload:
                if any(row):
                    lines.append(" | ".join(row))
        else:
            lines.append(_flat(payload, nl))
    return lines


def _sections(pkg):
    return [(n, ET.fromstring(pkg.read(n))) for n in section_names(pkg.names())]


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
    p_idx = 0
    for name, root in _sections(pkg):
        sec_no = int(re.fullmatch(r"Contents/section(\d+)\.xml", name).group(1))
        prefix = "" if sec_no == 0 else f"sec{sec_no}:"
        table_index = 0  # 표 번호는 섹션마다 리셋 (core.edit.SectionEditor와 정렬)
        for p in root.findall(_q("p")):
            tbls = [tbl for run in p.findall(_q("run"))
                    for tbl in run.findall(_q("tbl"))]
            pics = [pic for run in p.findall(_q("run"))
                    for pic in run.findall(_q("pic"))]
            current_idx = p_idx
            p_idx += 1
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
                                "key": f"{prefix}cell:{table_index}:{row}:{col}",
                                "type": "cell", "table": table_index,
                                "row": row, "col": col,
                                "section": name,
                                "text": " ".join(t for t in texts if t),
                            })
                    table_index += 1
                continue
            text = _para_direct_text(p)
            if text:
                slots.append({"key": f"p:{current_idx}", "type": "paragraph",
                              "section": name, "text": text})
    return {"slots": slots}


_CHECKBOX_RE = re.compile(r"[□☐]\s?(\S{1,10})")
_PAREN_RE = re.compile(r"\(\s+\)")
_INLINE_RE = re.compile(r"^\s*([^:：\n]{1,15}?)\s*[:：]\s*(.*?)\s*$")
_SUPERSCRIPT_RE = re.compile(r"[¹²³⁴⁵⁶⁷⁸⁹⁰*※]+$")

#: 양식에서 라벨로 흔히 쓰는 낱말 — 길이 조건과 무관하게 라벨로 본다.
LABEL_KEYWORDS = frozenset({
    "성명", "이름", "주소", "전화", "전화번호", "휴대폰", "핸드폰", "연락처",
    "생년월일", "주민등록번호", "소속", "직위", "직급", "부서", "이메일", "팩스",
    "학교", "학년", "번호", "신청인", "대표자", "담당자", "작성자", "확인자",
    "승인자", "일시", "날짜", "기간", "장소", "목적", "사유", "비고", "금액",
    "수량", "단가", "합계", "소계", "사업명", "과제명", "제목", "기관명",
    "사업자등록번호", "법인명", "대표", "직책", "성별", "국적", "서명",
})


def _norm_label(s):
    return re.sub(r"[\s:：()（）·※*]", "", s)


def is_label(text):
    """라벨처럼 보이는 셀/문구인지. (1) 라벨 키워드 포함 (2) 공백·괄호를 뺀
    길이 1~10자 (3) 30자 이하이면서 쌍점으로 끝남."""
    trimmed = _SUPERSCRIPT_RE.sub("", (text or "").strip()).strip()
    if not trimmed or len(trimmed) > 30 or trimmed[0] in "□☐■☑✓":
        return False          # 체크박스 항목은 라벨이 아니다
    if any(kw in trimmed for kw in LABEL_KEYWORDS):
        return True
    if trimmed.endswith((":", "：")):
        return True
    compact = _norm_label(trimmed)
    if re.fullmatch(r"[\d.,\-/]+", compact):
        return False          # 순번·숫자만 있는 셀
    return 1 <= len(compact) <= 10


def _is_strict_label(text):
    """값이 아니라 라벨이라고 꽤 확신할 수 있는 경우 (키워드 그 자체·쌍점으로
    끝남·순수 한글 3자 이하). 안내문("사업명을 적으세요")은 값 자리로 본다."""
    trimmed = (text or "").strip()
    if not trimmed:
        return False
    compact = _norm_label(trimmed)
    if compact in LABEL_KEYWORDS or trimmed.endswith((":", "：")):
        return True
    return bool(re.fullmatch(r"[가-힣]{1,3}", compact))


def _scan_checkbox_paren(text, targets, section, in_cell=False):
    boxes = list(_CHECKBOX_RE.finditer(text))
    for m in boxes:
        # "□ 사업목적"처럼 본문 문단 머리의 항목 기호(네모 뒤 공백, 한 줄에 하나)는
        # 체크박스가 아니다. 표 셀 안이거나 한 줄에 둘 이상이면 체크박스로 본다.
        if m.group(0)[1] == " " and not in_cell and len(boxes) < 2:
            continue
        targets.append({"key": _norm_label(m.group(1)),
                        "kind": "checkbox", "literal": m.group(0),
                        "section": section})
    for m in _PAREN_RE.finditer(text):
        prefix = text[max(0, m.start() - 10):m.start()]
        targets.append({"key": _norm_label(prefix),
                        "kind": "paren", "prefix": prefix,
                        "blank": m.group(0),
                        "literal": prefix + m.group(0),
                        "section": section})


def _field_begins(p):
    """문단 직속 run의 누름틀(fieldBegin type=CLICK_HERE)과 그 사이 텍스트."""
    out = []
    begin, inner = None, []
    for run in p.findall(_q("run")):
        ctrl = run.find(_q("ctrl"))
        fb = ctrl.find(_q("fieldBegin")) if ctrl is not None else None
        fe = ctrl.find(_q("fieldEnd")) if ctrl is not None else None
        if fb is not None and fb.get("type") == "CLICK_HERE" and begin is None:
            begin, inner = fb, []
            continue
        if begin is None:
            continue
        if fe is not None:
            out.append((begin, "".join(t_text(t) for t in inner)))
            begin, inner = None, []
        else:
            inner.extend(run.findall(_q("t")))
    return out


def _cell_has_field(tc):
    sub = tc.find(_q("subList"))
    return sub is not None and any(_field_begins(cp) for cp in sub.findall(_q("p")))


def _scan_inline(p, pindex, targets, section):
    text = _para_direct_text(p)
    m = _INLINE_RE.match(text)
    if not m or "\n" in text:
        return
    label, value = m.group(1), m.group(2)
    compact = _norm_label(label)
    if _PAREN_RE.search(label) or not compact or re.fullmatch(r"[\d.,\-/]+", compact):
        return
    if not (compact in LABEL_KEYWORDS
            or (len(compact) <= 8 and label.strip().count(" ") <= 1)):
        return
    targets.append({"key": _norm_label(label), "kind": "inline", "label": label,
                    "pindex": pindex, "literal": text, "value": value,
                    "section": section})


def _scan_fields(p, pindex, targets, section):
    for i, (fb, current) in enumerate(_field_begins(p)):
        name = fb.get("name") or ""
        key = _norm_label(name) or _norm_label(current)
        if not key:
            continue
        targets.append({"key": key, "kind": "field", "name": name,
                        "pindex": pindex, "field_index": i,
                        "value": current, "dirty": fb.get("dirty", "0"),
                        "section": section})


def fill_targets(path):
    from core.capacity import cell_report          # 순환 import 회피
    caps = {(c["section"], c["table"], c["row"], c["col"]): c["capacity"]
            for c in cell_report(path)["cells"]}
    pkg = HwpxPackage.open(path)
    targets = []
    for name, root in _sections(pkg):
        pindex_of = {p: i for i, p in enumerate(root.iter(_q("p")))}
        table_index = 0  # 표 번호는 섹션마다 리셋 (core.edit.SectionEditor와 정렬)
        for p in root.findall(_q("p")):
            tbls = [tbl for run in p.findall(_q("run"))
                    for tbl in run.findall(_q("tbl"))]
            if tbls:
                for tbl in tbls:
                    grid, cells = {}, {}
                    # 최상위 표의 직계 셀만(tr→tc) — 중첩 표의 셀은 제외한다
                    # (core.capacity._direct_cells, core.edit._tables와 동일 컨벤션).
                    direct_tcs = [tc for tr in tbl.findall(_q("tr"))
                                  for tc in tr.findall(_q("tc"))]
                    for tc in direct_tcs:
                        addr = tc.find(_q("cellAddr"))
                        r = int(addr.get("rowAddr"))
                        c = int(addr.get("colAddr"))
                        sub = tc.find(_q("subList"))
                        cell_text = ""
                        if sub is not None:
                            cell_text = " ".join(
                                _para_direct_text(cp)
                                for cp in sub.findall(_q("p"))).strip()
                        grid[(r, c)] = cell_text
                        cells[(r, c)] = tc
                    value_cells = set()
                    for (r, c), cell_text in sorted(grid.items()):
                        if cell_text and is_label(cell_text):
                            right, below = grid.get((r, c + 1)), grid.get((r + 1, c))
                            pos, placement, prefilled = None, "right", None
                            right_has_field = right is not None and _cell_has_field(cells[(r, c + 1)])
                            if right == "":
                                pos = (r, c + 1)
                            elif right_has_field:
                                pos, prefilled = (r, c + 1), right
                            elif below == "" and (right is None or is_label(right)):
                                pos, placement = (r + 1, c), "below"
                            elif right and not _is_strict_label(right):
                                pos, prefilled = (r, c + 1), right
                            if pos is not None and pos not in value_cells:
                                value_cells.add(pos)
                                tgt = {"key": _norm_label(cell_text),
                                       "kind": "label-cell", "label": cell_text,
                                       "table": table_index, "row": pos[0], "col": pos[1],
                                       "section": name,
                                       "capacity": caps.get((name, table_index) + pos, 0)}
                                if placement != "right":
                                    tgt["placement"] = placement
                                if prefilled is not None:
                                    tgt["prefilled"] = prefilled
                                vsub = cells[pos].find(_q("subList"))
                                vp = vsub.find(_q("p")) if vsub is not None else None
                                if vp is not None and _field_begins(vp):
                                    tgt["field"] = True
                                targets.append(tgt)
                        # 셀 내부 문단도 checkbox/paren/inline/누름틀 스캔 대상에 포함
                        _scan_checkbox_paren(cell_text, targets, name, in_cell=True)
                    for (r, c), tc in sorted(cells.items()):
                        sub = tc.find(_q("subList"))
                        if sub is None:
                            continue
                        for cp in sub.findall(_q("p")):
                            if (r, c) not in value_cells:
                                _scan_fields(cp, pindex_of[cp], targets, name)
                            if (r, c) not in value_cells and not (
                                    grid[(r, c)] and is_label(grid[(r, c)])
                                    and grid.get((r, c + 1)) == ""):
                                _scan_inline(cp, pindex_of[cp], targets, name)
                    table_index += 1
                continue
            text = _para_direct_text(p)
            _scan_checkbox_paren(text, targets, name)
            _scan_inline(p, pindex_of[p], targets, name)
            _scan_fields(p, pindex_of[p], targets, name)
    return {"targets": targets}


def extract_text(path, fmt="text"):
    """본문 텍스트 추출. text: 문단 한 줄, 표는 행마다 'a | b'. markdown: GFM 표.
    셀 안 줄바꿈은 text에서 공백, markdown에서 <br>. 중첩 표·글상자·머리말·
    꼬리말·각주도 포함한다."""
    pkg = HwpxPackage.open(path)
    nl = "<br>" if fmt == "markdown" else " "
    lines = []
    for _, root in _sections(pkg):
        for p in root.findall(_q("p")):
            for kind, payload in _para_items(p, nl):
                if kind == "table":
                    rows = payload
                    if not rows:
                        continue
                    if fmt == "markdown":
                        lines.append("| " + " | ".join(rows[0]) + " |")
                        lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
                        lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
                    else:
                        lines.extend(" | ".join(row) for row in rows)
                elif fmt == "markdown":
                    lines.append(payload.replace("\n", "  \n").replace("\t", " "))
                else:
                    lines.append(payload)
    return "\n".join(lines)
