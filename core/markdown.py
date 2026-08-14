"""마크다운 → 블록 → OWPML 섹션. 지원 문법은 SKILL.md/README에 문서화된 부분집합."""
import re

from core import owpml

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
_ORDERED_RE = re.compile(r"^(\d+)\.\s+(.*)$")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")


def _clean_inline(text):
    return text.replace("**", "").replace("`", "")


def _split_table_row(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_markdown(text):
    blocks = []
    para_lines = []

    def flush_para():
        if para_lines:
            blocks.append({"type": "paragraph",
                           "text": _clean_inline(" ".join(para_lines))})
            para_lines.clear()

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush_para()
            i += 1
            continue
        m = _HEADING_RE.match(stripped)
        if m:
            flush_para()
            blocks.append({"type": "heading", "level": len(m.group(1)),
                           "text": _clean_inline(m.group(2).strip())})
            i += 1
            continue
        if _TABLE_ROW_RE.match(stripped) and i + 1 < len(lines) \
                and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            flush_para()
            header = _split_table_row(stripped)
            ncols = len(header)
            rows = [header]
            i += 2
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i].strip()):
                rows.append(_split_table_row(lines[i].strip()))
                i += 1
            # GFM-style normalization: pad/truncate data rows to header width
            # so a stray missing/extra pipe never reaches owpml.table as
            # ragged input.
            rows = [row + [""] * (ncols - len(row)) if len(row) < ncols
                    else row[:ncols]
                    for row in rows]
            rows = [[_clean_inline(c) for c in row] for row in rows]
            blocks.append({"type": "table", "rows": rows})
            continue
        m = _BULLET_RE.match(stripped)
        if m:
            flush_para()
            items = [_clean_inline(m.group(1).strip())]
            i += 1
            while i < len(lines):
                m2 = _BULLET_RE.match(lines[i].strip())
                if not m2:
                    break
                items.append(_clean_inline(m2.group(1).strip()))
                i += 1
            blocks.append({"type": "bullet", "items": items})
            continue
        m = _ORDERED_RE.match(stripped)
        if m:
            flush_para()
            items = [f"{m.group(1)}. {_clean_inline(m.group(2).strip())}"]
            i += 1
            while i < len(lines):
                m2 = _ORDERED_RE.match(lines[i].strip())
                if not m2:
                    break
                items.append(f"{m2.group(1)}. {_clean_inline(m2.group(2).strip())}")
                i += 1
            blocks.append({"type": "ordered", "items": items})
            continue
        para_lines.append(stripped)
        i += 1
    flush_para()
    return blocks


def first_heading(text):
    for block in parse_markdown(text):
        if block["type"] == "heading":
            return block["text"]
    return None


def render_to_section(md_text, template="base"):
    first, sec_open = owpml.load_skeleton(template)
    alloc = owpml.IdAllocator()
    parts = []
    for block in parse_markdown(md_text):
        if block["type"] == "heading":
            parts.append(owpml.heading_para(block["level"], block["text"], alloc))
        elif block["type"] == "paragraph":
            parts.append(owpml.text_para(block["text"], alloc))
        elif block["type"] == "bullet":
            for item in block["items"]:
                parts.append(owpml.bullet_para(item, alloc))
        elif block["type"] == "ordered":
            for item in block["items"]:
                parts.append(owpml.text_para(item, alloc, para_pr="4"))
        elif block["type"] == "table":
            parts.append(owpml.table(block["rows"], alloc))
    return owpml.sec_document(first, parts, sec_open)
