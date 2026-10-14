"""마크다운 → 블록 → OWPML 섹션. 지원 문법은 SKILL.md/README에 문서화된 부분집합.

블록: #~###### 제목, -/* 불릿(들여쓰기로 3단계), 1. 순서 목록(들여쓰기 3단계),
GitHub 표, > 인용, ``` 코드 블록, --- 쪽 나눔, ![](경로) 그림(PNG/JPEG),
빈 줄로 나뉘는 문단, 맨 앞 YAML 머리말(title:).
인라인: **굵게**, `코드` 는 별도 run으로 (템플릿 styles.json의 bold_char/code_char).
"""
import re
from pathlib import Path

from core import owpml

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
_ORDERED_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")
_HR_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
_QUOTE_RE = re.compile(r"^>\s?(.*)$")
_FENCE_RE = re.compile(r"^```")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)\s*$")
_FRONT_KV_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")


def _clean_inline(text):
    return owpml.strip_inline(text)


def _split_table_row(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _indent_level(ws):
    width = len(ws.replace("\t", "    "))
    return min(width // 2, 2)


def split_front_matter(text):
    """맨 앞 `---` … `---` YAML 머리말을 (메타 dict, 본문)으로 분리."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta = {}
    for i in range(1, min(len(lines), 40)):
        if lines[i].strip() == "---":
            return meta, "\n".join(lines[i + 1:])
        m = _FRONT_KV_RE.match(lines[i])
        if not m:
            return {}, text
        meta[m.group(1)] = m.group(2).strip().strip("\"'")
    return {}, text


def parse_markdown(text):
    _, text = split_front_matter(text)
    blocks = []
    para_lines = []

    def flush_para():
        if para_lines:
            blocks.append({"type": "paragraph", "text": " ".join(para_lines)})
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
        if _FENCE_RE.match(stripped):
            flush_para()
            code = []
            i += 1
            while i < len(lines) and not _FENCE_RE.match(lines[i].strip()):
                code.append(lines[i].rstrip())
                i += 1
            i += 1
            blocks.append({"type": "code", "lines": code})
            continue
        if _HR_RE.match(stripped) and not _TABLE_ROW_RE.match(stripped):
            flush_para()
            blocks.append({"type": "hr"})
            i += 1
            continue
        m = _IMAGE_RE.match(stripped)
        if m:
            flush_para()
            blocks.append({"type": "image", "alt": m.group(1), "path": m.group(2)})
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
            rows = [[_clean_inline(c) for c in row] for row in rows[:1]] + rows[1:]
            blocks.append({"type": "table", "rows": rows})
            continue
        m = _QUOTE_RE.match(stripped)
        if m:
            flush_para()
            quote = [m.group(1).strip()]
            i += 1
            while i < len(lines) and _QUOTE_RE.match(lines[i].strip()):
                quote.append(_QUOTE_RE.match(lines[i].strip()).group(1).strip())
                i += 1
            blocks.append({"type": "quote", "text": " ".join(q for q in quote if q)})
            continue
        m = _BULLET_RE.match(line)
        if m:
            flush_para()
            items = [(_indent_level(m.group(1)), m.group(2).strip())]
            i += 1
            while i < len(lines):
                m2 = _BULLET_RE.match(lines[i])
                if not m2:
                    break
                items.append((_indent_level(m2.group(1)), m2.group(2).strip()))
                i += 1
            blocks.append({"type": "bullet", "items": [t for _, t in items],
                           "levels": [lv for lv, _ in items]})
            continue
        m = _ORDERED_RE.match(line)
        if m:
            flush_para()
            items = [(_indent_level(m.group(1)), f"{m.group(2)}. {m.group(3).strip()}")]
            i += 1
            while i < len(lines):
                m2 = _ORDERED_RE.match(lines[i])
                if not m2:
                    break
                items.append((_indent_level(m2.group(1)), f"{m2.group(2)}. {m2.group(3).strip()}"))
                i += 1
            blocks.append({"type": "ordered", "items": [t for _, t in items],
                           "levels": [lv for lv, _ in items]})
            continue
        para_lines.append(stripped)
        i += 1
    flush_para()
    return blocks


def first_heading(text):
    meta, _ = split_front_matter(text)
    if meta.get("title"):
        return meta["title"]
    for block in parse_markdown(text):
        if block["type"] == "heading":
            return block["text"]
    return None


def render_document(md_text, template="base", base_dir=None):
    """마크다운 → (section0.xml 문자열, 추가 엔트리 {경로: bytes}, manifest item XML 목록).
    그림은 base_dir(기본: 현재 디렉터리) 기준 경로로 읽어 BinData에 담는다."""
    from core import images
    first, sec_open = owpml.load_skeleton(template)
    style = owpml.load_style_map(template)
    alloc = owpml.IdAllocator()
    parts = []
    assets, manifest = {}, []
    base_dir = Path(base_dir) if base_dir else Path.cwd()
    page_break = False
    for block in parse_markdown(md_text):
        kind = block["type"]
        if kind == "hr":
            page_break = True
            continue
        pb, page_break = page_break, False
        if kind == "heading":
            if block["level"] == 2 and "section_bar" in style:
                if pb:
                    parts.append(owpml.empty_line(alloc, page_break=True))
                parts.append(owpml.section_bar(block["text"], alloc, style))
            else:
                parts.append(owpml.heading_para(block["level"], block["text"], alloc,
                                                 style_map=style, page_break=pb))
        elif kind == "paragraph":
            parts.append(owpml.text_para(block["text"], alloc, char_pr=style["body"][0],
                                          para_pr=style["body"][1], page_break=pb,
                                          style_map=style))
        elif kind == "bullet":
            for n, (item, level) in enumerate(zip(block["items"], block["levels"])):
                parts.append(owpml.bullet_para(item, alloc, level=level, style_map=style,
                                                page_break=pb and n == 0))
        elif kind == "ordered":
            for n, (item, level) in enumerate(zip(block["items"], block["levels"])):
                parts.append(owpml.ordered_para(item, alloc, level=level, style_map=style,
                                                 page_break=pb and n == 0))
        elif kind == "quote":
            parts.append(owpml.quote_para(block["text"], alloc, style, page_break=pb))
        elif kind == "code":
            lines = block["lines"] or [""]
            for n, line in enumerate(lines):
                parts.append(owpml.code_para(line, alloc, style, page_break=pb and n == 0))
        elif kind == "table":
            parts.append(owpml.table(block["rows"], alloc, style_map=style, page_break=pb))
        elif kind == "image":
            path = (base_dir / block["path"]).resolve()
            try:
                data = path.read_bytes()
                _, _, ext = images.image_size(data)
            except (OSError, Exception) as e:      # noqa: BLE001 — 없는/깨진 그림은 대체 문단
                parts.append(owpml.text_para(f"[그림 누락: {block['path']}]", alloc,
                                              page_break=pb, style_map=style))
                continue
            n = len(assets) + 1
            bin_id, entry = f"image{n}", f"BinData/image{n}.{ext}"
            assets[entry] = data
            mime = "image/png" if ext == "png" else "image/jpeg"
            manifest.append(f'<opf:item id="{bin_id}" href="{entry}" media-type="{mime}" isEmbeded="1"/>')
            parts.append(owpml.image_para(bin_id, data, alloc, page_break=pb))
            if block["alt"]:
                parts.append(owpml.text_para(block["alt"], alloc, para_pr=style["table"]["cell_para"],
                                              style_map=style))
    return owpml.sec_document(first, parts, sec_open), assets, manifest


def render_to_section(md_text, template="base"):
    return render_document(md_text, template)[0]
