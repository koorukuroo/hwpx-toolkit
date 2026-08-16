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


def _add(findings, rule, lineno, text, message, suggest=None):
    findings.append({"rule": rule, "line": lineno, "text": text.strip(),
                     "message": message, "suggest": suggest})


def _time_suggest(m):
    ampm, hh, mm = m.group(1), int(m.group(2)), m.group(3)
    if ampm == "오후" and hh < 12:
        hh += 12
    return f"{hh:02d}:{int(mm or 0):02d}"


def lint_text(text):
    findings = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
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
        line_no_url = _URL.sub("URL", line)
        if _COLON_LEFT_SPACE.search(line_no_url):
            _add(findings, "colon-spacing", i, line, "쌍점 왼쪽은 붙이고 오른쪽만 한 칸")
        stripped_times = _TIME_OK.sub("", line_no_url)
        if _COLON_NO_RIGHT.search(stripped_times):
            _add(findings, "colon-spacing", i, line, "쌍점 오른쪽 한 칸 띄움")

    # 붙임 / 끝.
    nonempty = [(i, l) for i, l in enumerate(lines, 1) if l.strip()]
    if nonempty:
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
    return {"findings": findings, "count": len(findings)}


def lint_file(path):
    path = Path(path)
    if path.suffix.lower() == ".hwpx":
        from core.analyze import extract_text
        text = extract_text(path)
    else:
        text = path.read_text(encoding="utf-8")
    return lint_text(text)
