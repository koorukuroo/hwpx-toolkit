"""공문서 작성법 검수 — 행정안전부 행정업무운영 편람의 표기 원칙을 규칙화(자체 정의)."""
import re
from pathlib import Path

_DATE_BAD = [
    (re.compile(r"\b(\d{4})\.(\d{1,2})\.(\d{1,2})"), "온점 뒤 한 칸 띄움"),
    (re.compile(r"(?<![-/\w])(\d{4})-(\d{1,2})-(\d{1,2})(?![-/\w])"), "하이픈 대신 온점"),
    (re.compile(r"(?<![-/\w])(\d{4})/(\d{1,2})/(\d{1,2})(?![-/\w])"), "빗금 대신 온점"),
    (re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일"), "한글 단위 대신 온점"),
]
_TIME_BAD = re.compile(
    r"(오전|오후)?\s*(\d{1,2})시(?!간|점|기|험)(?!\s*방향)(?:\s*(\d{1,2})분)?")
_AMOUNT = re.compile(r"(?<![\d,])(\d{1,3}(?:,\d{3})+)원(?!\()")
_HANGUL_AMOUNT = re.compile(r"\(금[가-힣]+원\)")
_ATTACH_LINE = re.compile(r"^\s*붙임\s+")
_ENUM_HANGUL = "가나다라마바사아자차카타파하"
_ITEM = [
    (0, re.compile(r"^\s*\d+\.\s")),
    (1, re.compile(r"^\s*[" + _ENUM_HANGUL + r"]\.\s")),
    (2, re.compile(r"^\s*\d+\)\s")),
    (3, re.compile(r"^\s*[" + _ENUM_HANGUL + r"]\)\s")),
    (4, re.compile(r"^\s*\(\d+\)\s")),
    (5, re.compile(r"^\s*\([" + _ENUM_HANGUL + r"]\)\s")),
    (6, re.compile(r"^\s*[①-⑳]\s?")),
]
_COLON_LEFT_SPACE = re.compile(r"\S\s+:\s")
_COLON_NO_RIGHT = re.compile(r"[가-힣A-Za-z)\]]:(?=\S)(?!\d{2}\b)")
_TIME_OK = re.compile(r"\b\d{1,2}:\d{2}\b")
_URL = re.compile(r"\w+://\S+")
_DATE_PADDED = re.compile(r"\b(\d{4})\.\s*(0\d|\d{1,2})\.\s*(0\d|\d{1,2})\.")
_YEAR_2DIGIT = re.compile(r"(?<![\d:.])(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.")
_AMOUNT_ABBREV = re.compile(r"[\d,]+\s*(천원|백만원|억원|만원)")
_ATTACH_COLON = re.compile(r"붙임\s*:")
_RANGE_TILDE = re.compile(r"[~∼]")
_RANGE_STOP = re.compile(r"[,;，；]")
_RANGE_HANGUL = re.compile(r"[가-힣]")
_RANGE_WINDOW = 20
_RANGE_MAX_HANGUL = 2
_FOREIGN_ORDER = re.compile(r"(?<![\w/])([A-Z]{2,})\(([가-힣]{2,})\)")
_DATE_NO_END_DOT = re.compile(r"(?<![\d.])(\d{4})\.\s(\d{1,2})\.\s(\d{1,2})(?![.\d])")
_TIME_24H = re.compile(r"(?<![\d:])24:00(?![\d:])")
_TIME_COLON_SP = re.compile(r"(?<!\d)(\d{1,2})(?:\s+:\s*|\s*:\s+)(\d{2})(?!\d)")
_MONEY_GEUM_SP = re.compile(r"금\s+(\d{1,3}(?:,\d{3})+|\d+)원")
_ATTACH_NUMBERED_ONE = re.compile(r"^\s*붙임\s+1\.\s")
_SUSIN = re.compile(r"^\s*수신\s")
_SIHAENG = re.compile(r"^\s*시행\s")
_DISCLOSURE = re.compile(r"(부분공개|비공개|공개)")
_BALSIN = re.compile(r"^\s*[가-힣·\s]{2,25}(장|관|감|이사장|총장|원장|대표)\s*$")
_BOGO_SENTENCE = re.compile(r"(습니다|입니다|합니다|됩니다|있습니다)\.?\s*$")
#: 물결표는 앞말·뒷말에 붙여 쓴다 (4. 23. ~ 6. 15. → 4. 23.~6. 15.)
_TILDE_SPACED = re.compile(r"(\S)\s+[~∼]\s*(\S)|(\S)\s*[~∼]\s+(\S)")
#: 날짜 뒤 요일 괄호는 붙여 쓴다 (2023. 11. 11. (토) → 2023. 11. 11.(토))
_WEEKDAY_SPACED = re.compile(r"(\d{1,2}\.)\s+(\([월화수목금토일]\))")
#: 법령·규정 이름은 낫표 「 」 (큰따옴표·작은따옴표 대신)
_LAW_QUOTED = re.compile(r"[\"'“‘]([가-힣·\s]{2,40}?(?:법|법률|규정|규칙|조례|지침|시행령|시행규칙|훈령|예규))[\"'”’]")
#: 자주 틀리는 띄어쓰기 (편람 예시 기반, 보수적으로 고른 것만)
_SPACING_FIXES = [
    (re.compile(r"(\d+)여명"), r"\1여 명", "'여'는 접미사로 붙이고 단위 '명'은 띄운다"),
    (re.compile(r"(\d+)명\s+당\b"), r"\1명당", "'-당'은 접미사이므로 붙여 쓴다"),
    (re.compile(r"(일주일|한\s?달|하루|이틀|\d+일)\s+가량"), r"\1가량", "'-가량'은 접미사이므로 붙여 쓴다"),
    (re.compile(r"([가-힣]+인)\s+바\b"), r"\1바", "'-인바'는 붙여 쓴다"),
    (re.compile(r"\b그\s+동안\b"), "그동안", "'그동안'은 한 단어"),
    (re.compile(r"\b더욱\s+더\b"), "더욱더", "'더욱더'는 한 단어"),
    (re.compile(r"\b(두|세|네|다섯|여섯)가지\b"), r"\1 가지", "수관형사와 의존명사 '가지'는 띄운다"),
    (re.compile(r"\b안됩니다\b"), "안 됩니다", "'안'은 부사이므로 띄운다"),
    (re.compile(r"(\d+\s?%)(이상|이하|미만|초과|이내)"), r"\1 \2", "숫자·단위 뒤 '이상/이하/미만/초과/이내'는 띄운다"),
    (re.compile(r"(\d+(?:년|개월|일|시간|회|명|개|건|부|매|장|억|만))(이상|이하|미만|초과|이내|내|전|후|간)(?![가-힣])"),
     r"\1 \2", "숫자·단위 뒤 '이상/이내/전/후/간' 등은 띄운다"),
    (re.compile(r"\b방과후\b"), "방과 후", "'방과 후'는 띄운다"),
    (re.compile(r"\b사용중인\b"), "사용 중인", "'중'은 의존명사이므로 띄운다"),
    (re.compile(r"\b변동없음\b"), "변동 없음", "'없음'은 띄운다"),
    (re.compile(r"\b각(\d+)부\b"), r"각 \1부", "'각'은 관형사이므로 띄운다"),
    (re.compile(r"\b매학교\b"), "매 학교", "'매'는 관형사이므로 띄운다"),
    (re.compile(r"\b제\s+(\d+)(차|회|조|항|호|장|기|분과)"), r"제\1\2", "'제-'는 접두사이므로 붙여 쓴다"),
    (re.compile(r"(?<![가-힣])귀\s+(교|사|원|청|기관|부서)"), r"귀\1", "'귀교/귀사'는 한 단어"),
    (re.compile(r"(\([월화수목금토일]\))\s+(까지|부터)"), r"\1\2", "조사 '까지/부터'는 붙여 쓴다"),
]


def _range_redundant(line):
    """물결표(~/∼) 뒤 20자 이내에 '까지'가 나오는지 찾되, 단순 동시 출현과
    진짜 중복 표기를 '사이 구간의 내용 모양'으로 구분한다. 사이에 쉼표류가
    있으면(문장이 그 사이에서 갈라진 것) 애초에 후보에서 제외하고, 남은
    구간은 한글 음절 수를 센다 — 날짜/시간 표기(`2023.5.2.(화) 18:00`,
    `2026. 8. 16.`)는 한글이 0~1음절뿐이지만, 문장이 이어지는 경우
    (`C 등급으로 나뉘며 신청은 3월 말`)는 한글이 여러 음절이라 걸러진다."""
    for m in _RANGE_TILDE.finditer(line):
        window = line[m.end():m.end() + _RANGE_WINDOW]
        stop_m = _RANGE_STOP.search(window)
        if stop_m:
            window = window[:stop_m.start()]
        idx = window.find("까지")
        if idx == -1:
            continue
        span = window[:idx]
        if len(_RANGE_HANGUL.findall(span)) <= _RANGE_MAX_HANGUL:
            return True
    return False


def _add(findings, rule, lineno, text, message, suggest=None):
    findings.append({"rule": rule, "line": lineno, "text": text.strip(),
                     "message": message, "suggest": suggest})


def _time_suggest(m):
    ampm, hh, mm = m.group(1), int(m.group(2)), m.group(3)
    if ampm == "오후" and hh < 12:
        hh += 12
    if hh == 24:
        hh = 0          # 24시는 없다 — 자정은 00:00
    return f"{hh:02d}:{int(mm or 0):02d}"


def _lone_sub_items(lines, findings):
    """하위 항목이 하나뿐이면 항목 기호를 붙이지 않는다 (예: '가.'만 있고 '나.'가 없음)."""
    parents = {}            # (level, parent_line) → [child line numbers]
    last_at_level = {}
    for i, l in enumerate(lines, 1):
        for level, rx in _ITEM:
            if rx.match(l):
                if level > 0:
                    parent = last_at_level.get(level - 1)
                    parents.setdefault((level, parent), []).append(i)
                last_at_level[level] = i
                for deeper in [k for k in last_at_level if k > level]:
                    del last_at_level[deeper]
                break
    for (level, parent), children in parents.items():
        if parent is not None and len(children) == 1:
            i = children[0]
            _add(findings, "item-lone", i, lines[i - 1],
                 "하위 항목이 하나뿐이면 항목 기호를 붙이지 않는다")


def _gonmun_structure(lines, findings):
    stripped = [l for l in lines if l.strip()]
    if not any(_SUSIN.match(l) for l in stripped):
        _add(findings, "gonmun-missing-susin", 1, stripped[0] if stripped else "",
             "공문에는 '수신' 란이 있어야 한다 (예: 수신  수신자 참조)")
    if not any(_SIHAENG.match(l) for l in stripped):
        _add(findings, "gonmun-missing-sihaeng", len(lines), stripped[-1] if stripped else "",
             "공문 결문에는 '시행 문서번호 (일자)' 가 있어야 한다")
    if not any(_DISCLOSURE.search(l) for l in stripped[-8:]):
        _add(findings, "gonmun-missing-disclosure", len(lines), stripped[-1] if stripped else "",
             "공문 결문에는 공개 구분(공개/부분공개/비공개)이 있어야 한다")
    if not any(_BALSIN.match(l) for l in stripped):
        _add(findings, "gonmun-missing-balsin", len(lines), stripped[-1] if stripped else "",
             "발신명의(기관장 직명, '…장'/'…관'/'…감')가 한 줄로 있어야 한다")


def _bogo_style(lines, findings):
    for i, l in enumerate(lines, 1):
        if _BOGO_SENTENCE.search(l.strip()) and len(l.strip()) > 6:
            _add(findings, "bogo-sentence-ending", i, l,
                 "개조식 보고서는 서술형 종결어미(…합니다/…입니다) 대신 명사형으로 끝맺는다")


def lint_text(text, doc_type=None):
    findings = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for m in _DATE_NO_END_DOT.finditer(line):
            y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                _add(findings, "date-end-dot", i, line, "연월일 뒤에는 온점을 찍는다",
                     f"{y}. {mo}. {d}.")
        for m in _TIME_24H.finditer(line):
            _add(findings, "time-24h", i, line, "24:00 대신 00:00 (24시각제는 00:00~23:59)", "00:00")
        for m in _TIME_COLON_SP.finditer(line):
            _add(findings, "time-colon-space", i, line, "시:분 사이에 공백을 두지 않는다",
                 f"{int(m.group(1)):02d}:{m.group(2)}")
        for m in _MONEY_GEUM_SP.finditer(line):
            _add(findings, "money-geum-space", i, line, "'금'과 숫자는 붙여 쓴다",
                 f"금{m.group(1)}원")
        for rx, why in _DATE_BAD:
            for m in rx.finditer(line):
                y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
                if not (1 <= mo <= 12 and 1 <= d <= 31):
                    continue
                _add(findings, "date-format", i, line, f"날짜 표기: {why}",
                     f"{y}. {mo}. {d}.")
        for m in _TIME_BAD.finditer(line):
            _add(findings, "time-format", i, line, "시간은 24시각제 HH:MM",
                 _time_suggest(m))
        if _AMOUNT.search(line) and not _HANGUL_AMOUNT.search(line):
            m = _AMOUNT.search(line)
            _add(findings, "amount-hangul", i, line,
                 "금액은 아라비아 숫자 뒤 괄호에 한글 병기",
                 f"금{m.group(1)}원(금…원)")
        for m in _DATE_PADDED.finditer(line):
            y, mo, d = m.group(1), m.group(2), m.group(3)
            if mo.startswith("0") or d.startswith("0"):
                _add(findings, "date-padding", i, line,
                     "월·일은 0을 붙이지 않는다",
                     f"{y}. {int(mo)}. {int(d)}.")
        for m in _YEAR_2DIGIT.finditer(line):
            _add(findings, "year-2digit", i, line,
                 "연도는 4자리로 쓴다", f"20{m.group(1)}. {int(m.group(2))}. {int(m.group(3))}.")
        for m in _AMOUNT_ABBREV.finditer(line):
            _add(findings, "amount-abbrev", i, line,
                 f"금액 단위 약어('{m.group(1)}') 대신 아라비아 숫자로 전액 표기")
        if _ATTACH_COLON.search(line):
            _add(findings, "attach-colon", i, line,
                 "'붙임' 뒤에는 쌍점 없이 두 칸 띄운다", "붙임  ")
        if _range_redundant(line):
            _add(findings, "range-redundant", i, line,
                 "물결표 범위와 '까지'는 함께 쓰지 않는다")
        line_no_url = _URL.sub("URL", line)
        for m in _TILDE_SPACED.finditer(line_no_url):
            _add(findings, "tilde-spacing", i, line, "물결표(~)는 앞말·뒷말에 붙여 쓴다",
                 re.sub(r"\s*[~∼]\s*", "~", m.group(0)))
        for m in _WEEKDAY_SPACED.finditer(line):
            _add(findings, "weekday-paren-space", i, line, "날짜 뒤 요일 괄호는 붙여 쓴다",
                 f"{m.group(1)}{m.group(2)}")
        for m in _LAW_QUOTED.finditer(line):
            _add(findings, "law-title-quotes", i, line,
                 "법령·규정 이름은 낫표 「 」로 감싼다", f"「{m.group(1)}」")
        for rx, repl, why in _SPACING_FIXES:
            for m in rx.finditer(line):
                _add(findings, "spacing-common", i, line, why, rx.sub(repl, m.group(0)))
        for m in _FOREIGN_ORDER.finditer(line_no_url):
            _add(findings, "foreign-order", i, line,
                 "한글을 먼저 쓰고 외국어를 괄호 안에 넣는다",
                 f"{m.group(2)}({m.group(1)})")
        if _COLON_LEFT_SPACE.search(line_no_url):
            _add(findings, "colon-spacing", i, line, "쌍점 왼쪽은 붙이고 오른쪽만 한 칸")
        stripped_times = _TIME_OK.sub("", line_no_url)
        if _COLON_NO_RIGHT.search(stripped_times):
            _add(findings, "colon-spacing", i, line, "쌍점 오른쪽 한 칸 띄움")

    # 붙임 / 끝.
    nonempty = [(i, l) for i, l in enumerate(lines, 1) if l.strip()]
    if nonempty:
        in_attach = False
        attach_items = 0
        attach_first = None
        for i, l in nonempty:
            if _ATTACH_LINE.match(l):
                in_attach = True
                attach_first = (i, l)
            if in_attach and re.sub(r"\s*끝\.\s*$", "", _ATTACH_LINE.sub("", l)).strip():
                attach_items += 1
        if attach_items == 1 and attach_first and _ATTACH_NUMBERED_ONE.match(attach_first[1]):
            _add(findings, "attachment-single-numbered", attach_first[0], attach_first[1],
                 "붙임이 하나뿐이면 번호를 붙이지 않는다", "붙임  ○○○ 1부.")
        in_attach = False
        for i, l in nonempty:
            if _ATTACH_LINE.match(l):
                in_attach = True
            if in_attach:
                body = re.sub(r"\s*끝\.\s*$", "", l)
                body = _ATTACH_LINE.sub("", body).strip()
                if body and not re.search(r"\d+\s*부\.$", body):
                    _add(findings, "attachment-format", i, l, "붙임 항목은 'N부.'로 끝남")
        last_i, last = nonempty[-1]
        if not last.rstrip().endswith("끝."):
            _add(findings, "end-mark", last_i, last, "본문(또는 붙임) 마지막에 ' 끝.' 표기")
        elif not re.search(r"(\s|^)끝\.$", last.rstrip()):
            _add(findings, "end-mark", last_i, last, "'끝.' 앞은 한 칸(붙임 뒤는 두 칸) 띄움")

    # 항목 기호 체계
    seen_levels = []
    for i, l in enumerate(lines, 1):
        for level, rx in _ITEM:
            if rx.match(l):
                if level > 0 and (not seen_levels or level > max(seen_levels) + 1):
                    _add(findings, "item-hierarchy", i, l,
                         "항목 기호는 1. → 가. → 1) → 가) → (1) → (가) → ① 순서")
                seen_levels = [x for x in seen_levels if x < level] + [level]
                break
    _lone_sub_items(lines, findings)
    if doc_type == "gonmun":
        _gonmun_structure(lines, findings)
    elif doc_type == "bogo":
        _bogo_style(lines, findings)
    return {"findings": findings, "count": len(findings)}


def lint_file(path, doc_type=None):
    path = Path(path)
    if path.suffix.lower() == ".hwpx":
        from core.analyze import extract_text
        text = extract_text(path)
    else:
        text = path.read_text(encoding="utf-8")
    return lint_text(text, doc_type=doc_type)
