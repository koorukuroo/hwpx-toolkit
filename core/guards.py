"""검증 게이트 — Phase 1: 구조 검증(validate)."""
import re
import zipfile
import xml.etree.ElementTree as ET

from core.errors import PackageError
from core.package import HwpxPackage, section_names

REQUIRED_ENTRIES = ("mimetype", "version.xml", "Contents/header.xml",
                    "Contents/content.hpf")
MIMETYPE_VALUE = b"application/hwp+zip"

NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

from core.text import CONTROL_RE, t_model, _OPAQUE_RE  # noqa: E402

# header.xml의 (컬렉션 태그, 자식 태그, 섹션에서 참조하는 속성명)
_ID_GROUPS = [
    ("charProperties", "charPr", "charPrIDRef"),
    ("paraProperties", "paraPr", "paraPrIDRef"),
    ("borderFills", "borderFill", "borderFillIDRef"),
    ("styles", "style", "styleIDRef"),
    ("tabProperties", "tabPr", "tabPrIDRef"),
]
#: OWPML의 "charPr 미지정" 센티널(UINT -1) — 끊어진 참조가 아니다.
_CHARPR_UNSET = "4294967295"

# ---- 한컴 열기 안전 구조 규칙 (실물 문서 실측) ----
_TBL_ATTRS = ("rowCnt", "colCnt")
_TBL_CHILDREN = ("sz", "pos", "outMargin", "inMargin")
_TC_CHILDREN = ("subList", "cellAddr", "cellSpan", "cellSz", "cellMargin")
_CELL_PART_ATTRS = {"cellAddr": ("colAddr", "rowAddr"), "cellSpan": ("colSpan", "rowSpan")}
_SECPR_REQUIRED = ("pagePr",)                 # 없으면 "손상된 문서" 복구 대화상자
_SECPR_ADVISED = ("startNum", "visibility")   # 없으면 열기 거부 보고 (미검증 → 경고)
_RENDERING_MATRICES = ("transMatrix", "scaMatrix", "rotMatrix")
_SHAPE_TAGS = frozenset({"line", "rect", "ellipse", "arc", "polygon", "curve",
                         "connectLine", "container", "pic"})
_RECT_CORNERS = ("pt0", "pt1", "pt2", "pt3")
_HANCOM_FIELD_TYPES = frozenset({
    "CLICK_HERE", "HYPERLINK", "BOOKMARK", "FORMULA", "SUMMARY", "USER_INFO", "DATE",
    "DOC_DATE", "PATH", "CROSSREF", "MAILMERGE", "MEMO", "PROOFREADING_MARKS",
    "PROOFREADING_MARKS_SIGN", "PROOFREADING_MARKS_DELETE", "PRIVATE_INFO", "METADATA",
    "CITATION", "BIBLIOGRAPHY", "TABLEOFCONTENTS"})
_HANCOM_FIELD_IDS = frozenset({
    "627600491", "627272811", "623209829", "627207531", "627469685", "627340389",
    "628650598", "628387683", "627928423", "628121972", "628320615", "623192676"})
_LINESEG_EMPTY_FLAG = 0x40000
_SHARED_PARA_IDS = frozenset({"0", "2147483648"})
_SIMPLE_RUN_CHILDREN = frozenset({"t", "tab", "lineBreak", "hyphen", "nbSpace", "fwSpace"})


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _child(el, local):
    for c in el:
        if _local(c.tag) == local:
            return c
    return None


def _children(el, local):
    return [c for c in el if _local(c.tag) == local]


def _simple_text_length(p):
    """단순 문단(run 안에 글자·인라인 요소만)의 한컴 텍스트 위치 길이. 개체·컨트롤이
    있으면 None(판정 불가). hp:t 안 탭 요소는 8칸, run 직속 인라인 요소는 1칸."""
    total = 0
    for child in p:
        name = _local(child.tag)
        if name == "linesegarray":
            continue
        if name != "run":
            return None
        for rc in child:
            rn = _local(rc.tag)
            if rn == "t":
                model, _ = t_model(rc)
                model = _OPAQUE_RE.sub("", model)
                total += len(model) + 7 * model.count("\t")
            elif rn in _SIMPLE_RUN_CHILDREN:
                total += 1
            else:
                return None
    return total


def _secpr_ctrl_order(loc, p, warnings):
    """구역 첫 문단의 컨트롤 순서: secPr → colPr → 머리말/꼬리말 (한컴 저장본 순서).
    머리말/꼬리말이 colPr 앞에 오면 한컴에서 오른쪽이 잘리는 사례가 보고됐다."""
    seq = []
    for run in _children(p, "run"):
        for c in run:
            name = _local(c.tag)
            if name == "secPr":
                seq.append("secPr")
            elif name == "ctrl":
                seq.extend(_local(cc.tag) for cc in c)
    if "secPr" not in seq or "colPr" not in seq:
        return
    hf = [i for i, x in enumerate(seq) if x in ("header", "footer")]
    if hf and hf[0] < seq.index("colPr"):
        warnings.append(f"secpr-ctrl-order: {loc} 머리말/꼬리말 ctrl이 colPr보다 앞에 있음 "
                        "(한컴 순서: secPr → colPr → header/footer)")


def _section_structure(sec_name, tree, errors, warnings):
    """섹션 하나의 한컴 필수 구조 검사."""
    loc = sec_name.rsplit("/", 1)[-1]
    seen_p_ids, seen_obj_ids = {}, {}
    field_ids, field_ends = set(), []
    for el in tree.iter():
        name = _local(el.tag)
        if name == "p":
            pid = el.get("id")
            # 한컴 실물은 셀 문단에 id="2147483648"(0x80000000)·"0"을 반복해 쓴다 — 중복 아님
            if pid and pid.isdigit() and pid not in _SHARED_PARA_IDS:
                seen_p_ids[pid] = seen_p_ids.get(pid, 0) + 1
            length = _simple_text_length(el)
            kids = list(el)
            if any(_local(k.tag) == "linesegarray" for k in kids) \
                    and _local(kids[-1].tag) != "linesegarray":
                warnings.append(f"lineseg-not-last: {loc} 문단 id={pid} — linesegarray는 "
                                "문단의 마지막 자식이어야 한다 (run이 뒤에 옴)")
            _secpr_ctrl_order(loc, el, warnings)
            nb = len(list(el.iter(f"{{{NS_HP}}}fieldBegin")))
            ne = len(list(el.iter(f"{{{NS_HP}}}fieldEnd")))
            if nb != ne:
                warnings.append(f"field-spans-paragraphs: {loc} 문단 id={pid} fieldBegin {nb}개 / "
                                f"fieldEnd {ne}개 — 문단을 넘는 누름틀·필드는 한컴이 지운다")
            for lsa in _children(el, "linesegarray"):
                for seg in _children(lsa, "lineseg"):
                    tp = seg.get("textpos")
                    if tp is None:
                        errors.append(f"lineseg-missing-textpos: {loc} 문단 id={pid}")
                        continue
                    if length is None or not tp.isdigit():
                        continue
                    pos = int(tp)
                    flags = seg.get("flags") or "0"
                    empty = flags.isdigit() and int(flags) & _LINESEG_EMPTY_FLAG
                    if pos > length and not (pos == length + 1 and empty):
                        errors.append(
                            f"lineseg-stale: {loc} 문단 id={pid} textpos={pos} > 글자 수 {length} "
                            "(수정한 문단의 linesegarray를 지우지 않음 — 글자 겹침 원인)")
                        break
        elif name == "t":
            raw = (el.text or "") + "".join(c.tail or "" for c in el)
            if "\t" in raw:
                errors.append(f"text-control-char: {loc} hp:t 안에 탭 문자(U+0009) — 한컴이 문서를 "
                              "열지 못함, <hp:tab/> 요소로 써야 함")
            if CONTROL_RE.search(raw):
                errors.append(f"text-control-char: {loc} hp:t 안에 XML 비허용 제어문자")
        elif name == "secPr":
            for c in _SECPR_REQUIRED:
                if _child(el, c) is None:
                    errors.append(f"secpr-incomplete: {loc} secPr에 {c} 없음 — 한컴 '손상된 문서' 대화상자")
            pagepr = _child(el, "pagePr")
            if pagepr is not None and _child(pagepr, "margin") is None:
                errors.append(f"secpr-incomplete: {loc} pagePr에 margin 없음 — 한컴 '손상된 문서' 대화상자")
            for c in _SECPR_ADVISED:
                if _child(el, c) is None:
                    warnings.append(f"secpr-incomplete: {loc} secPr에 {c} 없음 (열기 거부 보고 사례)")
        elif name == "tbl":
            tid = el.get("id")
            if tid and tid.isdigit():
                seen_obj_ids[tid] = seen_obj_ids.get(tid, 0) + 1
            for a in _TBL_ATTRS:
                if el.get(a) is None:
                    errors.append(f"table-structure: {loc} tbl에 {a} 없음")
            for c in _TBL_CHILDREN:
                if _child(el, c) is None:
                    errors.append(f"table-structure: {loc} tbl에 {c} 없음")
            trs = _children(el, "tr")
            if not trs:
                errors.append(f"table-structure: {loc} tbl에 tr 없음")
            rc = el.get("rowCnt")
            if rc and rc.isdigit() and trs and int(rc) != len(trs):
                errors.append(f"table-structure: {loc} tbl rowCnt={rc}, 실제 tr {len(trs)}개")
            for tr in trs:
                if not _children(tr, "tc"):
                    errors.append(f"table-structure: {loc} tr에 tc 없음")
        elif name == "tc":
            for c in _TC_CHILDREN:
                if _child(el, c) is None:
                    errors.append(f"table-structure: {loc} tc에 {c} 없음")
            sz = _child(el, "cellSz")
            if sz is not None:
                w, h = sz.get("width"), sz.get("height")
                if w is None or not w.lstrip("-").isdigit() or int(w) <= 0:
                    errors.append(f"cell-geometry-invalid: {loc} cellSz width={w!r}")
                if h is None or not h.lstrip("-").isdigit() or int(h) < 0:
                    errors.append(f"cell-geometry-invalid: {loc} cellSz height={h!r}")
        elif name in _CELL_PART_ATTRS:
            for a in _CELL_PART_ATTRS[name]:
                if el.get(a) is None:
                    errors.append(f"table-structure: {loc} {name}에 {a} 없음")
        elif name == "subList":
            if _child(el, "p") is None:
                errors.append(f"sublist-empty: {loc} subList에 문단 없음 — 한컴 크래시")
        elif name == "ctrl":
            if len(el) == 0:
                errors.append(f"ctrl-empty: {loc} 비어 있는 hp:ctrl — 한컴 크래시")
            for story in el:
                kind = _local(story.tag)
                if kind in ("header", "footer") and _child(story, "subList") is None:
                    errors.append(f"hf-structure: {loc} {kind}에 subList 없음 — 한컴 크래시")
        elif name == "fieldBegin":
            fid = el.get("id")
            if fid is None:
                errors.append(f"field-structure: {loc} fieldBegin에 id 없음")
            else:
                field_ids.add(fid)
            if (el.get("type") not in _HANCOM_FIELD_TYPES
                    and el.get("fieldid") not in _HANCOM_FIELD_IDS):
                errors.append(f"field-structure: {loc} fieldBegin type={el.get('type')!r} 는 한컴 "
                              "필드 유형이 아님 — 열기 거부")
        elif name == "fieldEnd":
            ref = el.get("beginIDRef")
            if ref is None:
                errors.append(f"field-structure: {loc} fieldEnd에 beginIDRef 없음")
            else:
                field_ends.append(ref)
        elif name in _SHAPE_TAGS:
            oid = el.get("id")
            if oid and oid.isdigit():
                seen_obj_ids[oid] = seen_obj_ids.get(oid, 0) + 1
        elif name == "rect":
            pass
    for ref in field_ends:
        if ref not in field_ids:
            errors.append(f"field-unpaired: {loc} fieldEnd beginIDRef={ref} 에 대응하는 fieldBegin 없음")
    _drawing_structure(loc, tree, errors)
    dup_p = sorted(k for k, n in seen_p_ids.items() if n > 1)
    if dup_p:
        warnings.append(f"duplicate-id: {loc} 문단 id 중복 {dup_p[:5]}"
                        + (f" 외 {len(dup_p) - 5}건" if len(dup_p) > 5 else ""))
    dup_o = sorted(k for k, n in seen_obj_ids.items() if n > 1)
    if dup_o:
        warnings.append(f"duplicate-id: {loc} 표/개체 id 중복 {dup_o[:5]}")


def _drawing_structure(loc, tree, errors):
    def visit(el, inside_container):
        name = _local(el.tag)
        if name in _SHAPE_TAGS and not inside_container:
            ri = _child(el, "renderingInfo")
            if ri is None or any(_child(ri, m) is None for m in _RENDERING_MATRICES):
                errors.append(f"shape-structure: {loc} {name}에 renderingInfo 행렬 3종 없음 — 한컴 크래시")
            if name == "pic" and _child(el, "img") is None:
                errors.append(f"shape-structure: {loc} pic에 hc:img 없음 — 열기 거부")
        if name == "rect" and any(_child(el, pt) is None for pt in _RECT_CORNERS):
            errors.append(f"shape-structure: {loc} rect에 꼭짓점(pt0..pt3) 누락 — 열기 거부")
        for c in el:
            if isinstance(c.tag, str):
                visit(c, inside_container or name == "container")
    visit(tree, False)


def _package_structure(pkg, names, trees, sections, errors, warnings):
    """패키지 수준: manifest·container·version·secCnt."""
    counts = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    for n, c in counts.items():
        if c > 1:
            errors.append(f"zip-duplicate-entry: {n} ({c}회)")
    names_set = set(names)
    hpf = trees.get("Contents/content.hpf")
    if hpf is not None:
        items = [el for el in hpf.iter() if _local(el.tag) == "item"]
        if not items:
            errors.append("manifest-empty: content.hpf manifest에 item 없음")
        sec_ids = []
        for it in items:
            for a in ("id", "href", "media-type"):
                if it.get(a) is None:
                    errors.append(f"manifest-item-incomplete: id={it.get('id')} href={it.get('href')} {a} 없음")
            href = it.get("href")
            if href and href not in names_set:
                errors.append(f"manifest-href-missing: {href} 엔트리가 ZIP에 없음")
            if href and re.fullmatch(r"Contents/section\d+\.xml", href):
                sec_ids.append(it.get("id"))
        expected = [f"section{i}" for i in range(len(sections))]
        if sec_ids and sorted(sec_ids, key=lambda x: (len(x or ""), x or "")) != expected:
            errors.append(f"manifest-section-ids: 섹션 item id는 section0..N 연속이어야 함: {sec_ids}")
    container = trees.get("META-INF/container.xml")
    if container is not None:
        for rf in (el for el in container.iter() if _local(el.tag) == "rootfile"):
            if rf.get("media-type") is None:
                errors.append("container-rootfile: rootfile에 media-type 없음")
            fp = rf.get("full-path")
            if fp and fp not in names_set:
                errors.append(f"container-rootfile: full-path {fp} 엔트리 없음")
    version = trees.get("version.xml")
    if version is not None and _local(version.tag) == "HCFVersion" \
            and version.get("tagetApplication") is None:
        errors.append("version-structure: HCFVersion에 tagetApplication(한컴 철자) 없음 — 열기 거부")
    header = trees.get("Contents/header.xml")
    if header is not None:
        sc = header.get("secCnt")
        if sc is not None and sc.isdigit() and int(sc) != len(sections):
            errors.append(f"seccnt-mismatch: header secCnt={sc}, 섹션 {len(sections)}개")
        for cp in header.iter(f"{{{NS_HH}}}charPr"):
            if cp.find(f"{{{NS_HH}}}bold") is not None and cp.find(f"{{{NS_HH}}}fontRef") is None:
                warnings.append(f"charpr-bold-without-fontref: charPr id={cp.get('id')} — macOS 한컴이 "
                                "굵게를 그리지 못할 수 있음")
                break
        seen = {}
        for h in header.iter(f"{{{NS_HH}}}heading"):
            kind, ref = h.get("type"), h.get("idRef")
            if kind == "BULLET":
                coll, child = "bullets", "bullet"
            elif kind in ("NUMBER", "OUTLINE"):
                coll, child = "numberings", "numbering"
            else:
                continue
            if coll not in seen:
                c = header.find(f".//{{{NS_HH}}}{coll}")
                seen[coll] = {x.get("id") for x in c.findall(f"{{{NS_HH}}}{child}")} if c is not None else set()
            if ref not in seen[coll] and not (kind == "OUTLINE" and ref == "0"):
                errors.append(f"dangling-ref: header paraPr heading {kind} idRef={ref} 미정의")


def validate_package(path):
    errors, warnings = [], []
    try:
        pkg = HwpxPackage.open(path)
    except PackageError as e:
        return {"ok": False, "errors": [f"zip-invalid: {e}"], "warnings": []}

    names = pkg.names()
    for req in REQUIRED_ENTRIES:
        if req not in names:
            errors.append(f"required-missing: {req}")
    sections = section_names(names)
    if not sections:
        errors.append("required-missing: Contents/section*.xml")

    if "mimetype" in names:
        if names[0] != "mimetype":
            errors.append("mimetype-not-first: mimetype이 첫 엔트리가 아님")
        with zipfile.ZipFile(pkg.path) as zf:
            info = zf.getinfo("mimetype")
            if info.compress_type != zipfile.ZIP_STORED:
                errors.append("mimetype-not-stored: STORED가 아님")
        if pkg.read("mimetype") != MIMETYPE_VALUE:
            errors.append("mimetype-bad-content: application/hwp+zip 아님")

    trees = {}
    for name in names:
        if not (name.endswith(".xml") or name.endswith(".hpf")):
            continue
        try:
            trees[name] = ET.fromstring(pkg.read(name))
        except ET.ParseError as e:
            errors.append(f"xml-malformed: {name}: {e}")

    header = trees.get("Contents/header.xml")
    defined = {}
    if header is not None:
        for coll, child, _ in _ID_GROUPS:
            coll_el = header.find(f".//{{{NS_HH}}}{coll}")
            if coll_el is None:
                defined[child] = None
                continue
            children = coll_el.findall(f"{{{NS_HH}}}{child}")
            declared = coll_el.get("itemCnt")
            if declared is not None:
                try:
                    declared_n = int(declared)
                except ValueError:
                    errors.append(
                        f"itemcnt-mismatch: {coll} itemCnt 비정수 '{declared}'")
                else:
                    if declared_n != len(children):
                        errors.append(
                            f"itemcnt-mismatch: {coll} itemCnt={declared}, 실제={len(children)}")
            defined[child] = {c.get("id") for c in children}

    for sec_name in sections:
        tree = trees.get(sec_name)
        if tree is None:
            continue
        used_by_attr = {attr: set() for _, _, attr in _ID_GROUPS}
        for el in tree.iter():
            for attr in used_by_attr:
                value = el.attrib.get(attr)
                if value is not None:
                    used_by_attr[attr].add(value)
        for coll, child, attr in _ID_GROUPS:
            used = used_by_attr[attr]
            if attr == "charPrIDRef":
                used = used - {_CHARPR_UNSET}
            if header is None or not used:
                continue
            if defined.get(child) is None:
                errors.append(f"dangling-ref: {sec_name} {attr} 사용하지만 header에 {coll} 컬렉션 없음")
                continue
            missing = used - defined[child]
            if missing:
                errors.append(
                    f"dangling-ref: {sec_name} {attr} 미정의 id {sorted(missing)}")
        first_p = tree.find(f"{{{NS_HP}}}p")
        if first_p is not None:
            first_run = first_p.find(f"{{{NS_HP}}}run")
            has_secpr = (first_run is not None and
                         first_run.find(f"{{{NS_HP}}}secPr") is not None)
            if not has_secpr:
                errors.append(f"secpr-missing: {sec_name} 첫 문단 첫 런에 secPr 없음")
        _section_structure(sec_name, tree, errors, warnings)
    _package_structure(pkg, names, trees, sections, errors, warnings)

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def check_package(path):
    base = validate_package(path)
    signals = {"char_border_bug": False, "vertical_misconvert": False,
               "image_ref_broken": False}
    errors = list(base["errors"])
    warnings = list(base["warnings"])
    try:
        pkg = HwpxPackage.open(path)
        header = ET.fromstring(pkg.read("Contents/header.xml"))
        solid_ids = set()
        for bf in header.iter(f"{{{NS_HH}}}borderFill"):
            for edge in ("leftBorder", "rightBorder", "topBorder",
                         "bottomBorder"):
                e = bf.find(f"{{{NS_HH}}}{edge}")
                if e is not None and e.get("type") not in (None, "NONE"):
                    solid_ids.add(bf.get("id"))
                    break
        chars = list(header.iter(f"{{{NS_HH}}}charPr"))
        bordered = [c for c in chars
                    if c.get("borderFillIDRef") in solid_ids]
        if chars and len(bordered) / len(chars) > 0.5:
            signals["char_border_bug"] = True
            errors.append(
                "char-border-bug: charPr 과반이 실선 테두리 borderFill 참조 — "
                "fix 후 재검사 필요")
        vert = total = 0
        for name in section_names(pkg.names()):
            root = ET.fromstring(pkg.read(name))
            for sub in root.iter(f"{{{NS_HP}}}subList"):
                total += 1
                if sub.get("textDirection") == "VERTICAL":
                    vert += 1
        if total >= 4 and vert / total > 0.5:
            signals["vertical_misconvert"] = True
            errors.append(
                "vertical-misconvert: 셀 과반이 세로쓰기 — 오변환 여부 확인 필요")

        # 이미지 참조 정합: hc:img@binaryItemIDRef ↔ content.hpf manifest ↔ 엔트리
        hpf = pkg.read_text("Contents/content.hpf")
        manifest = {}
        for m in re.finditer(r"<opf:item\b[^>]*>", hpf):
            tag = m.group(0)
            id_m = re.search(r'\bid="([^"]*)"', tag)
            href_m = re.search(r'\bhref="([^"]*)"', tag)
            if id_m and href_m:
                manifest[id_m.group(1)] = href_m.group(1)
        names_set = set(pkg.names())
        NS_HC = "http://www.hancom.co.kr/hwpml/2011/core"
        for name in section_names(pkg.names()):
            sec_root = ET.fromstring(pkg.read(name))
            for img in sec_root.iter(f"{{{NS_HC}}}img"):
                ref = img.get("binaryItemIDRef")
                href = manifest.get(ref)
                if ref is None or href is None or href not in names_set:
                    signals["image_ref_broken"] = True
                    errors.append(
                        f"image-ref-broken: {ref} (manifest/BinData 불일치)")

        warnings.extend(_tables_taller_than_page(pkg))

        from core.capacity import cell_report      # 순환 import 회피
        over = [c for c in cell_report(path)["cells"] if c["over"]]
        multi_section = len(section_names(pkg.names())) > 1
        for c in over[:20]:
            loc = f"표 {c['table']} ({c['row']},{c['col']})"
            if multi_section:
                sec_m = re.fullmatch(r"Contents/section(\d+)\.xml", c["section"])
                loc = f"sec{sec_m.group(1)} {loc}" if sec_m else f"{c['section']} {loc}"
            warnings.append(
                f"cell-overflow-risk: {loc} "
                f"추정 수용 {c['capacity']}em < 실제 {c['used']}em "
                f"(문자 {c['used_chars']}자)")
        if len(over) > 20:
            warnings.append(f"cell-overflow-risk: 외 {len(over) - 20}건 더")
    except (PackageError, ET.ParseError):
        pass  # 구조 오류는 validate가 이미 errors에 보고
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "signals": signals}


def _usable_height(root):
    """섹션 secPr의 본문 세로 공간 (용지 높이 − 위·아래·머리말·꼬리말 여백)."""
    pagepr = root.find(f".//{{{NS_HP}}}secPr/{{{NS_HP}}}pagePr")
    if pagepr is None:
        return None
    margin = pagepr.find(f"{{{NS_HP}}}margin")
    try:
        h = int(pagepr.get("height"))
        w = int(pagepr.get("width"))
        if pagepr.get("landscape") == "NARROWLY":
            h, w = w, h
        m = {k: int(margin.get(k, "0")) for k in ("top", "bottom", "header", "footer")} \
            if margin is not None else {}
    except (TypeError, ValueError):
        return None
    return h - sum(m.values())


def _tables_taller_than_page(pkg):
    """쪽 나눔을 금지한 표(pageBreak="NONE")가 본문 세로 공간보다 길거나, 행 단위로만
    나뉘는 표(pageBreak="TABLE")의 한 행이 본문보다 길면 한컴은 넘친 부분을 그리지
    않는다 — 경고. (한컴 실물에서 treatAsChar=1 + pageBreak="CELL" 표는 정상적으로
    여러 쪽에 걸쳐 나뉘므로 글자처럼 취급 여부는 조건이 아니다.)"""
    out = []
    names = section_names(pkg.names())
    multi = len(names) > 1
    for name in names:
        root = ET.fromstring(pkg.read(name))
        usable = _usable_height(root)
        if not usable:
            continue
        idx = 0
        for p in root.findall(f"{{{NS_HP}}}p"):
            for run in p.findall(f"{{{NS_HP}}}run"):
                for tbl in run.findall(f"{{{NS_HP}}}tbl"):
                    mode = tbl.get("pageBreak") or "CELL"
                    height, tallest = 0, 0
                    for tr in tbl.findall(f"{{{NS_HP}}}tr"):
                        tc = tr.find(f"{{{NS_HP}}}tc")
                        sz = tc.find(f"{{{NS_HP}}}cellSz") if tc is not None else None
                        try:
                            h = int(sz.get("height")) if sz is not None else 0
                        except ValueError:
                            h = 0
                        height += h
                        tallest = max(tallest, h)
                    loc = f"표 {idx}"
                    if multi:
                        m = re.fullmatch(r"Contents/section(\d+)\.xml", name)
                        loc = f"sec{m.group(1)} {loc}" if m else f"{name} {loc}"
                    if mode == "NONE" and height > usable:
                        out.append(f"table-taller-than-page: {loc} 행 높이 합 {height} > 본문 세로 {usable} "
                                   '(pageBreak="NONE" — 한컴은 쪽을 나누지 않아 아래 행이 잘림)')
                    elif mode == "TABLE" and tallest > usable:
                        out.append(f"table-taller-than-page: {loc} 가장 큰 행 {tallest} > 본문 세로 {usable} "
                                   '(pageBreak="TABLE" — 행 안에서는 나뉘지 않아 잘림)')
                    idx += 1
    return out


def document_structure(path):
    """guard가 비교하는 구조 지문: 섹션별 문단 수·표 모양·그림/도형 수·쪽나눔 수."""
    pkg = HwpxPackage.open(path)
    out = []
    for name in section_names(pkg.names()):
        root = ET.fromstring(pkg.read(name))
        tables = []
        for tbl in root.iter(f"{{{NS_HP}}}tbl"):
            tables.append([tbl.get("rowCnt"), tbl.get("colCnt")])
        out.append({
            "section": name,
            "paragraphs": len(root.findall(f"{{{NS_HP}}}p")),
            "tables": tables,
            "pics": sum(1 for _ in root.iter(f"{{{NS_HP}}}pic")),
            "shapes": sum(1 for tag in ("rect", "ellipse", "line", "polygon", "curve", "container")
                          for _ in root.iter(f"{{{NS_HP}}}{tag}")),
            "page_breaks": sum(1 for p in root.iter(f"{{{NS_HP}}}p") if p.get("pageBreak") == "1"),
        })
    return out


def _compare_structure(out_s, ref_s, errors, warnings, strict):
    sink = errors if strict else warnings
    if len(out_s) != len(ref_s):
        sink.append(f"structure-sections: 섹션 수 {len(out_s)} ≠ 레퍼런스 {len(ref_s)}")
        return
    for o, r in zip(out_s, ref_s):
        sec = o["section"].rsplit("/", 1)[-1]
        if o["tables"] != r["tables"]:
            sink.append(f"structure-tables: {sec} 표 모양 {o['tables']} ≠ 레퍼런스 {r['tables']}")
        if o["paragraphs"] != r["paragraphs"]:
            sink.append(f"structure-paragraphs: {sec} 문단 {o['paragraphs']} ≠ 레퍼런스 {r['paragraphs']}")
        if o["page_breaks"] != r["page_breaks"]:
            sink.append(f"structure-page-breaks: {sec} 쪽나눔 {o['page_breaks']} ≠ 레퍼런스 {r['page_breaks']}")
        for k in ("pics", "shapes"):
            if o[k] < r[k]:
                sink.append(f"structure-{k}: {sec} {k} {o[k]} < 레퍼런스 {r[k]} (개체 유실)")


_DEFAULT_PLACEHOLDERS = [
    r"○{2,}",
    r"\{\{[^}]*\}\}",
    r"<<[^>]*>>",
    r"\bTODO\b",
    r"\bTBD\b",
    r"\.\s\.\s\.",
]
_LONG_LINE_MIN = 12


def _long_lines(text):
    out = set()
    for line in text.splitlines():
        norm = " ".join(line.split())
        if len(re.sub(r"\s", "", norm)) >= _LONG_LINE_MIN:
            out.add(norm)
    return out


def guard_against_reference(output, reference, *, rules=None, max_growth=None,
                            max_unchanged_ratio=None,
                            no_default_placeholders=False, strict_structure=False):
    from core.analyze import extract_text
    errors, warnings = [], []
    structure = document_structure(output)
    _compare_structure(structure, document_structure(reference), errors, warnings,
                       strict_structure)
    out_pkg = HwpxPackage.open(output)
    ref_pkg = HwpxPackage.open(reference)
    sections = set(section_names(ref_pkg.names()))
    out_names = set(out_pkg.names())
    for name in ref_pkg.names():
        if name in sections:
            continue
        if name not in out_names:
            errors.append(f"entry-missing: {name}")
        elif out_pkg.read(name) != ref_pkg.read(name):
            errors.append(f"entry-changed: {name} (섹션 외 엔트리는 바이트 동일해야 함)")
    for name in out_pkg.names():
        if name not in set(ref_pkg.names()):
            errors.append(f"entry-added: {name}")

    text = extract_text(output)
    ref_text = extract_text(reference)
    rules = rules or {}
    for kw in rules.get("require", []):
        if kw not in text:
            errors.append(f"require-missing: {kw}")
    for kw in rules.get("forbid", []):
        if kw in text:
            errors.append(f"forbid-found: {kw}")
    for pat in rules.get("forbid_regex", []):
        if re.search(pat, text):
            errors.append(f"forbid-regex-found: {pat}")
    for pat in rules.get("require_regex", []):
        if not re.search(pat, text):
            errors.append(f"require-regex-missing: {pat}")

    patterns = list(rules.get("placeholder_regex", []))
    if not no_default_placeholders:
        patterns = _DEFAULT_PLACEHOLDERS + patterns
    for pat in patterns:
        out_count = len(re.findall(pat, text))
        if out_count == 0:
            continue
        ref_count = len(re.findall(pat, ref_text))
        m = re.search(pat, text)
        match_str = m.group(0)[:30] if m else ""
        if out_count > ref_count:
            errors.append(f"placeholder-found: {pat} → {match_str}")
        else:
            warnings.append(
                f"placeholder-inherited: {pat} → {match_str} (레퍼런스에도 있음)")

    ref_len = len(re.sub(r"\s", "", ref_text))
    out_len = len(re.sub(r"\s", "", text))
    growth = (out_len / ref_len) if ref_len else 1.0
    if max_growth is not None:
        if growth > max_growth:
            errors.append(f"growth-exceeded: {growth:.2f} > {max_growth}")
    elif growth > 1.05:
        warnings.append(
            f"growth-warning: 공백 제외 글자 수 {growth:.2f}배 — 쪽수 증가 위험")

    unchanged_ratio = None
    if max_unchanged_ratio is not None:
        ref_lines = _long_lines(ref_text)
        out_lines = list(_long_lines(text))
        if out_lines:
            same = sum(1 for ln in out_lines if ln in ref_lines)
            unchanged_ratio = round(same / len(out_lines), 3)
            if unchanged_ratio > max_unchanged_ratio:
                errors.append(
                    f"unchanged-too-high: {unchanged_ratio} > {max_unchanged_ratio}")

    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "growth": round(growth, 3), "unchanged_ratio": unchanged_ratio,
            "structure": structure}
