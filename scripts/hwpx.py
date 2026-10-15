#!/usr/bin/env python3
"""hwpx-toolkit 단일 CLI. 사용: python3 scripts/hwpx.py <command> ..."""
import argparse
import json
from datetime import datetime, timezone
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import analyze, guards  # noqa: E402
from core import convert as convert_mod  # noqa: E402
from core import edit as edit_mod  # noqa: E402
from core import fill as fill_mod  # noqa: E402
from core import lint as lint_mod  # noqa: E402
from core import markdown as md_mod  # noqa: E402
from core import repair as repair_mod  # noqa: E402
from core.package import HwpxPackage, PackageError, pack_dir  # noqa: E402
from core.template import build_from_template  # noqa: E402


def cmd_validate(args):
    result = guards.validate_package(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def cmd_extract(args):
    print(analyze.extract_text(args.file, fmt=args.format))
    return 0


def cmd_analyze(args):
    if args.slots:
        result = analyze.extract_slots(args.file)
    else:
        result = analyze.analyze_document(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_unpack(args):
    names = HwpxPackage.open(args.file).extract_to(args.dir)
    print(json.dumps({"ok": True, "entries": len(names)}, ensure_ascii=False))
    return 0


def cmd_pack(args):
    pack_dir(args.dir, args.out, source=args.source)
    print(json.dumps({"ok": True}, ensure_ascii=False))
    return 0


def _finish_generated(out_path):
    result = guards.validate_package(out_path)
    payload = {"ok": result["ok"], "output": str(out_path), "validate": result}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def _read_text_utf8(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise PackageError(
            f"UTF-8이 아닌 입력 파일 (CP949/EUC-KR 등): {path} — "
            "UTF-8로 저장 후 다시 시도") from e


def cmd_new(args):
    src = Path(args.input)
    if not src.is_file():
        raise PackageError(f"입력 파일 없음: {src}")
    text = _read_text_utf8(src)
    title = args.title or md_mod.first_heading(text) or src.stem
    section, assets, manifest = md_mod.render_document(
        text, template=args.template, base_dir=src.parent)
    meta, _ = md_mod.split_front_matter(text)
    try:
        deco = md_mod.document_decorations(text, args.template)
    except ValueError as e:
        raise PackageError(str(e)) from e
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    build_from_template(args.output, template=args.template,
                        section_xml=section, title=title,
                        extra_files=assets, manifest_items=manifest,
                        creator=meta.get("author"), created=now, modified=now)
    if deco["header"] or deco["footer"] or deco["page_number"]:
        # 머리말·꼬리말·쪽번호는 편집 경로(한컴 검증된 구조)로 덧붙인다
        tmp = _tmp_for(args.output)

        def decorate(ed):
            if deco["header"]:
                ed.set_header_footer("header", deco["header"], align="center")
            if deco["footer"]:
                ed.set_header_footer("footer", deco["footer"], align="center")
            if deco["page_number"]:
                where, align = deco["page_number"]
                ed.set_page_number(where=where, align=align)
        edit_mod.edit_file(args.output, tmp, decorate)
        os.replace(tmp, args.output)
    return _finish_generated(args.output)


def cmd_build(args):
    section = _read_text_utf8(args.section) if args.section else None
    build_from_template(args.output, template=args.template,
                        section_xml=section, title=args.title)
    return _finish_generated(args.output)


def _tmp_for(dst):
    """산출물을 먼저 임시 파일에 만들고 check 통과 후에만 dst 이름을 준다."""
    dst = Path(dst)
    return dst.with_name(f".{dst.name}.{os.getpid()}.pending")


def _edit(args, fn):
    tmp = _tmp_for(args.dst)
    args._tmp = tmp
    return edit_mod.edit_file(args.src, tmp, fn)


def _finish_edited(args, report):
    """check 게이트. 통과 → dst로 승격. 실패 → <dst 이름>.rejected.hwpx 로 남기고
    dst는 만들지 않는다(깨진 파일이 요청한 이름으로 전달되는 것을 막는다)."""
    dst = Path(args.dst)
    tmp = getattr(args, "_tmp", None)
    gate = guards.check_package(tmp if tmp is not None else dst)
    payload = {"ok": gate["ok"] and not report.get("not_found"),
               "output": str(dst), "report": report, "gate": gate}
    if tmp is not None:
        if gate["ok"]:
            os.replace(tmp, dst)
        else:
            rejected = dst.with_name(dst.stem + ".rejected" + dst.suffix)
            os.replace(tmp, rejected)
            payload["output"] = None
            payload["rejected_output"] = str(rejected)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 2


def cmd_replace(args):
    mapping = json.loads(_read_text_utf8(args.map))
    report = _edit(args,
                                lambda ed: ed.replace_text(mapping))
    return _finish_edited(args, report)


def cmd_set_cell(args):
    _edit(args,
                       lambda ed: ed.set_cell_text(args.table, args.row,
                                                   args.col, args.text))
    return _finish_edited(args,
                          {"set_cell": [args.table, args.row, args.col]})


def cmd_set_cell_style(args):
    n = _edit(args, lambda ed: ed.set_cell_style(
        args.table, args.row, args.col, bg=args.bg, border=args.border,
        width=args.width, row2=args.row2, col2=args.col2))
    return _finish_edited(args, {"styled_cells": n, "bg": args.bg, "border": args.border})


def cmd_add_row(args):
    cells = json.loads(_read_text_utf8(args.cells))
    _edit(args, lambda ed: ed.add_row(args.table, cells))
    return _finish_edited(args, {"added_row": cells})


def cmd_del_row(args):
    _edit(args, lambda ed: ed.del_row(args.table, args.row))
    return _finish_edited(args, {"deleted_row": args.row})


def cmd_merge_cells(args):
    _edit(args, lambda ed: ed.merge_cells(
        args.table, args.row, args.col, args.row2, args.col2))
    return _finish_edited(args, {"merged": [args.row, args.col, args.row2, args.col2]})


def cmd_add_col(args):
    cells = json.loads(_read_text_utf8(args.cells))
    _edit(args,
                       lambda ed: ed.add_col(args.table, cells, at=args.at))
    return _finish_edited(args, {"added_col": cells})


def cmd_add_para(args):
    _edit(args,
                       lambda ed: ed.add_para_after(args.after, args.text))
    return _finish_edited(args, {"added_after": args.after})


def cmd_insert_image(args):
    _edit(args, lambda ed: ed.insert_image(
        args.image, after=args.after, index=args.para,
        width_mm=args.width_mm, height_mm=args.height_mm))
    return _finish_edited(args, {"inserted": args.image})


def cmd_list_images(args):
    pkg = HwpxPackage.open(args.file)
    ed = edit_mod.SectionEditor.from_package(pkg)
    print(json.dumps({"images": ed.list_images()}, ensure_ascii=False, indent=2))
    return 0


def cmd_resize_image(args):
    _edit(args, lambda ed: ed.resize_image(
        args.index, width_mm=args.width_mm, height_mm=args.height_mm))
    return _finish_edited(args, {"resized": args.index})


def cmd_replace_image(args):
    _edit(args,
                       lambda ed: ed.replace_image(args.index, args.image))
    return _finish_edited(args, {"replaced": args.index})


def cmd_delete_image(args):
    _edit(args, lambda ed: ed.delete_image(args.index))
    return _finish_edited(args, {"deleted": args.index})


def cmd_fill(args):
    if args.analyze:
        result = analyze.fill_targets(args.src)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not args.dst:
        raise PackageError("채우기에는 <dst> 인자가 필요합니다")
    values = json.loads(_read_text_utf8(args.values)) if args.values else None
    cells = json.loads(_read_text_utf8(args.cells)) if args.cells else None
    if not values and not cells:
        raise PackageError("--values 또는 --cells 중 하나는 필요합니다")
    args._tmp = _tmp_for(args.dst)
    report = fill_mod.fill_file(args.src, args._tmp, values=values, cells=cells)
    if report["unmatched"]:
        report["not_found"] = report["unmatched"]
    return _finish_edited(args, report)


def _target_kwargs(args):
    return {"after": args.after, "index": args.para}


def cmd_set_text_style(args):
    kw = dict(bold=True if args.bold else None, italic=True if args.italic else None,
              underline=True if args.underline else None,
              color=args.color, size_pt=args.size)
    _edit(args,
                       lambda ed: ed.set_text_style(**_target_kwargs(args), **kw))
    return _finish_edited(args, {"set_text_style": kw})


def cmd_set_para_style(args):
    _edit(args,
                       lambda ed: ed.set_para_style(**_target_kwargs(args),
                                                    align=args.align,
                                                    line_spacing=args.line_spacing))
    return _finish_edited(args, {"set_para_style": {"align": args.align,
                                                        "line_spacing": args.line_spacing}})


def cmd_set_page(args):
    margins = None
    if args.margin_mm is not None:
        margins = {k: args.margin_mm for k in ("left", "right", "top", "bottom")}
    _edit(args, lambda ed: ed.set_page(
        orientation=args.orientation, size=args.size, margins_mm=margins))
    return _finish_edited(args, {"set_page": {
        "orientation": args.orientation, "size": args.size,
        "margin_mm": args.margin_mm}})


def cmd_set_columns(args):
    _edit(args,
                       lambda ed: ed.set_columns(args.count, gap_mm=args.gap_mm))
    return _finish_edited(args, {"columns": args.count})


def cmd_page_break(args):
    _edit(args,
                       lambda ed: ed.set_page_break(args.after, on=not args.off))
    return _finish_edited(args, {"page_break": args.after, "on": not args.off})


def _cmd_hf(kind):
    def run(args):
        _edit(args,
                           lambda ed: ed.set_header_footer(kind, args.text,
                                                           align=args.align))
        return _finish_edited(args, {kind: args.text})
    return run


def _cmd_remove_hf(kind):
    def run(args):
        _edit(args,
                           lambda ed: ed.remove_header_footer(kind))
        return _finish_edited(args, {"removed": kind})
    return run


def cmd_set_pagenum(args):
    _edit(args,
                       lambda ed: ed.set_page_number(where=args.where,
                                                     align=args.align))
    return _finish_edited(args, {"pagenum": args.where})


def cmd_fix_borders(args):
    args._tmp = _tmp_for(args.dst)
    report = repair_mod.fix_char_borders(args.src, args._tmp)
    return _finish_edited(args, report)


def cmd_check(args):
    result = guards.check_package(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def cmd_render(args):
    from core import render as render_mod
    result = render_mod.render_pages(args.file, args.out, fmt=args.format, pages=args.pages,
                                     png=args.png)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


def cmd_from_hwp(args):
    result = convert_mod.hwp_to_hwpx(args.input, args.output, engine=args.engine)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def cmd_lint(args):
    # findings는 게이트가 아니므로 findings 유무는 exit code에 영향을 주지 않는다(항상 0).
    # 파일을 못 찾거나 hwpx가 손상된 경우 등은 예외로 올라가 main()의 표준
    # JSON+exit 2 오류 계약을 그대로 따른다 (다른 명령과 동일).
    result = lint_mod.lint_file(args.file, doc_type=args.doc_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_guard(args):
    rules = json.loads(_read_text_utf8(args.rules)) if args.rules else None
    result = guards.guard_against_reference(
        args.output, args.reference, rules=rules, max_growth=args.max_growth,
        max_unchanged_ratio=args.max_unchanged_ratio,
        no_default_placeholders=args.no_default_placeholders,
        strict_structure=args.strict_structure)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def build_parser():
    p = argparse.ArgumentParser(prog="hwpx")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="HWPX 구조 검증")
    v.add_argument("file")
    v.set_defaults(func=cmd_validate)

    e = sub.add_parser("extract", help="텍스트 추출")
    e.add_argument("file")
    e.add_argument("--format", choices=["text", "markdown"], default="text")
    e.set_defaults(func=cmd_extract)

    a = sub.add_parser("analyze", help="구조/슬롯 분석")
    a.add_argument("file")
    a.add_argument("--slots", action="store_true", help="편집 슬롯만 출력")
    a.set_defaults(func=cmd_analyze)

    u = sub.add_parser("unpack", help="HWPX를 디렉터리로 해체")
    u.add_argument("file")
    u.add_argument("dir")
    u.set_defaults(func=cmd_unpack)

    k = sub.add_parser("pack", help="디렉터리를 HWPX로 패킹")
    k.add_argument("dir")
    k.add_argument("out")
    k.add_argument("--source", help="바이트 보존 기준이 될 원본 HWPX")
    k.set_defaults(func=cmd_pack)

    n = sub.add_parser("new", help="마크다운 → HWPX 생성")
    n.add_argument("input")
    n.add_argument("-o", "--output", required=True)
    n.add_argument("--template", "--theme", dest="template", default="base",
                   help="테마 템플릿: base(기본) | gonmun(공문) | report(보고서) | modern(현대)")
    n.add_argument("--title")
    n.set_defaults(func=cmd_new)

    b = sub.add_parser("build", help="header+section 조립")
    b.add_argument("--section")
    b.add_argument("-o", "--output", required=True)
    b.add_argument("--template", "--theme", dest="template", default="base")
    b.add_argument("--title")
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("replace", help="문구 교체 (run 분할 대응)")
    r.add_argument("src")
    r.add_argument("dst")
    r.add_argument("--map", required=True, help='{"옛 문구": "새 문구"} JSON 파일')
    r.set_defaults(func=cmd_replace)

    sc = sub.add_parser("set-cell", help="표 셀 텍스트 설정")
    sc.add_argument("src")
    sc.add_argument("dst")
    sc.add_argument("--table", type=int, required=True)
    sc.add_argument("--row", type=int, required=True)
    sc.add_argument("--col", type=int, required=True)
    sc.add_argument("--text", required=True)
    sc.set_defaults(func=cmd_set_cell)

    cs = sub.add_parser("set-cell-style", help="셀 배경색/테두리 (사각 범위 가능)")
    cs.add_argument("src")
    cs.add_argument("dst")
    cs.add_argument("--table", type=int, required=True)
    cs.add_argument("--row", type=int, required=True)
    cs.add_argument("--col", type=int, required=True)
    cs.add_argument("--row2", type=int)
    cs.add_argument("--col2", type=int)
    cs.add_argument("--bg", help="RRGGBB 또는 none")
    cs.add_argument("--border", choices=["solid", "none", "dash", "double", "dot"])
    cs.add_argument("--width", help='테두리 굵기, 예: "0.12 mm"')
    cs.set_defaults(func=cmd_set_cell_style)

    ar = sub.add_parser("add-row", help="표 행 추가 (마지막 행 복제)")
    ar.add_argument("src")
    ar.add_argument("dst")
    ar.add_argument("--table", type=int, required=True)
    ar.add_argument("--cells", required=True, help='["값1","값2"] JSON 파일')
    ar.set_defaults(func=cmd_add_row)

    dr = sub.add_parser("del-row", help="표 행 삭제")
    dr.add_argument("src")
    dr.add_argument("dst")
    dr.add_argument("--table", type=int, required=True)
    dr.add_argument("--row", type=int, required=True)
    dr.set_defaults(func=cmd_del_row)

    mc = sub.add_parser("merge-cells", help="사각 범위 셀 병합")
    mc.add_argument("src")
    mc.add_argument("dst")
    for k in ("table", "row", "col", "row2", "col2"):
        mc.add_argument(f"--{k}", type=int, required=True)
    mc.set_defaults(func=cmd_merge_cells)

    ac = sub.add_parser("add-col", help="표 열 추가")
    ac.add_argument("src")
    ac.add_argument("dst")
    ac.add_argument("--table", type=int, required=True)
    ac.add_argument("--cells", required=True, help='["행0값","행1값",...] JSON 파일')
    ac.add_argument("--at", type=int)
    ac.set_defaults(func=cmd_add_col)

    ap = sub.add_parser("add-para", help="기준 문구 뒤 문단 추가")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--after", required=True)
    ap.add_argument("--text", required=True)
    ap.set_defaults(func=cmd_add_para)

    f = sub.add_parser("fill", help="양식 필드 채우기")
    f.add_argument("src")
    f.add_argument("dst", nargs="?")
    f.add_argument("--analyze", action="store_true", help="채울 타겟만 출력")
    f.add_argument("--values", help='{"라벨": "값"} JSON 파일')
    f.add_argument("--cells", help='[{"table","row","col","value"}] JSON 파일')
    f.set_defaults(func=cmd_fill)

    def _add_target(parser):
        parser.add_argument("--after", help="기준 문구를 포함한 본문 문단")
        parser.add_argument("--para", type=int, help="본문 문단 인덱스 (음수=끝에서)")

    ts = sub.add_parser("set-text-style", help="글자 서식 (대상 문단 전체 run)")
    ts.add_argument("src")
    ts.add_argument("dst")
    _add_target(ts)
    ts.add_argument("--bold", action="store_true")
    ts.add_argument("--italic", action="store_true")
    ts.add_argument("--underline", action="store_true")
    ts.add_argument("--color", help="RRGGBB")
    ts.add_argument("--size", type=float, help="pt")
    ts.set_defaults(func=cmd_set_text_style)

    ps = sub.add_parser("set-para-style", help="문단 서식")
    ps.add_argument("src")
    ps.add_argument("dst")
    _add_target(ps)
    ps.add_argument("--align", choices=["left", "center", "right", "justify"])
    ps.add_argument("--line-spacing", type=int, help="%%")
    ps.set_defaults(func=cmd_set_para_style)

    ii = sub.add_parser("insert-image", help="이미지 삽입 (PNG/JPEG)")
    ii.add_argument("src")
    ii.add_argument("dst")
    ii.add_argument("--image", required=True)
    _add_target(ii)
    ii.add_argument("--width-mm", type=float)
    ii.add_argument("--height-mm", type=float)
    ii.set_defaults(func=cmd_insert_image)

    li = sub.add_parser("list-images", help="그림 목록")
    li.add_argument("file")
    li.set_defaults(func=cmd_list_images)

    ri = sub.add_parser("resize-image", help="그림 크기 변경")
    ri.add_argument("src")
    ri.add_argument("dst")
    ri.add_argument("--index", type=int, required=True)
    ri.add_argument("--width-mm", type=float)
    ri.add_argument("--height-mm", type=float)
    ri.set_defaults(func=cmd_resize_image)

    rp = sub.add_parser("replace-image", help="그림 교체")
    rp.add_argument("src")
    rp.add_argument("dst")
    rp.add_argument("--index", type=int, required=True)
    rp.add_argument("--image", required=True)
    rp.set_defaults(func=cmd_replace_image)

    di = sub.add_parser("delete-image", help="그림 삭제")
    di.add_argument("src")
    di.add_argument("dst")
    di.add_argument("--index", type=int, required=True)
    di.set_defaults(func=cmd_delete_image)

    pg = sub.add_parser("set-page", help="용지/방향/여백")
    pg.add_argument("src")
    pg.add_argument("dst")
    pg.add_argument("--orientation", choices=["portrait", "landscape"])
    pg.add_argument("--size", choices=["a4", "a3", "b5", "letter"])
    pg.add_argument("--margin-mm", type=float, help="상하좌우 일괄")
    pg.set_defaults(func=cmd_set_page)

    cl = sub.add_parser("set-columns", help="다단")
    cl.add_argument("src")
    cl.add_argument("dst")
    cl.add_argument("--count", type=int, required=True)
    cl.add_argument("--gap-mm", type=float)
    cl.set_defaults(func=cmd_set_columns)

    pb = sub.add_parser("page-break", help="쪽 나누기 토글")
    pb.add_argument("src")
    pb.add_argument("dst")
    pb.add_argument("--after", required=True)
    pb.add_argument("--off", action="store_true")
    pb.set_defaults(func=cmd_page_break)

    for kind in ("header", "footer"):
        s = sub.add_parser(f"set-{kind}", help=f"{kind} 설정/갱신")
        s.add_argument("src")
        s.add_argument("dst")
        s.add_argument("--text", required=True)
        s.add_argument("--align", choices=["left", "center", "right"])
        s.set_defaults(func=_cmd_hf(kind))
        rm = sub.add_parser(f"remove-{kind}", help=f"{kind} 제거")
        rm.add_argument("src")
        rm.add_argument("dst")
        rm.set_defaults(func=_cmd_remove_hf(kind))

    pn = sub.add_parser("set-pagenum", help="자동 쪽번호")
    pn.add_argument("src")
    pn.add_argument("dst")
    pn.add_argument("--where", choices=["header", "footer"], default="footer")
    pn.add_argument("--align", choices=["left", "center", "right"], default="center")
    pn.set_defaults(func=cmd_set_pagenum)

    fb = sub.add_parser("fix-borders", help="글자 테두리 버그 수리 (check 검출 시)")
    fb.add_argument("src")
    fb.add_argument("dst")
    fb.set_defaults(func=cmd_fix_borders)

    ck = sub.add_parser("check", help="전달 전 필수 게이트 (validate + 사고 패턴)")
    ck.add_argument("file")
    ck.set_defaults(func=cmd_check)

    rd = sub.add_parser("render", help="쪽 미리보기 (SVG/HTML, rhwp 렌더러·Node.js 필요)")
    rd.add_argument("file")
    rd.add_argument("-o", "--out", required=True, help="page-N.svg 를 쓸 디렉터리")
    rd.add_argument("--format", choices=["svg", "html"], default="svg")
    rd.add_argument("--pages", help="예: 1 또는 2-4 (기본 전체)")
    rd.add_argument("--png", action="store_true", help="macOS qlmanage로 PNG도 생성")
    rd.set_defaults(func=cmd_render)

    fh = sub.add_parser("from-hwp", help="HWP(5.x) → HWPX 변환 (기본 python 엔진, 의존성 없음)")
    fh.add_argument("input")
    fh.add_argument("-o", "--output", required=True)
    fh.add_argument("--engine", choices=list(convert_mod.ENGINES), default="auto",
                    help="auto: python 엔진, 읽기 실패 시 rhwp(Node.js) 폴백 / python / rhwp")
    fh.set_defaults(func=cmd_from_hwp)

    ln = sub.add_parser(
        "lint", help="공문서 작성법 검수 (hwpx 또는 텍스트; findings는 게이트 아님, "
                     "파일 오류만 exit 2)")
    ln.add_argument("file")
    ln.add_argument("--doc-type", choices=["gonmun", "bogo"],
                    help="gonmun: 공문 필수 요소(수신·발신명의·시행·공개) 검사 추가 / "
                         "bogo: 개조식 보고서 문체 검사 추가")
    ln.set_defaults(func=cmd_lint)

    g = sub.add_parser("guard", help="레퍼런스 대비 가드")
    g.add_argument("output")
    g.add_argument("--reference", required=True)
    g.add_argument("--rules", help='{"require":[],"forbid":[],"forbid_regex":[],'
                                    '"require_regex":[],"placeholder_regex":[]}')
    g.add_argument("--max-growth", type=float, default=None)
    g.add_argument("--max-unchanged-ratio", type=float, default=None,
                   help="원문 그대로인 긴 줄 비율 상한 (전면 재작성 검사)")
    g.add_argument("--no-default-placeholders", action="store_true",
                   help="기본 placeholder 패턴 검사 끄기")
    g.add_argument("--strict-structure", action="store_true",
                   help="문단 수·표 모양·쪽나눔 수가 레퍼런스와 다르면 경고가 아니라 오류")
    g.set_defaults(func=cmd_guard)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (PackageError, ET.ParseError, OSError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
