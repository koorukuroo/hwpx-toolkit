#!/usr/bin/env python3
"""hwpx-toolkit 단일 CLI. 사용: python3 scripts/hwpx.py <command> ..."""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import analyze, guards  # noqa: E402
from core import edit as edit_mod  # noqa: E402
from core import fill as fill_mod  # noqa: E402
from core import markdown as md_mod  # noqa: E402
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
    section = md_mod.render_to_section(text, template=args.template)
    build_from_template(args.output, template=args.template,
                        section_xml=section, title=title)
    return _finish_generated(args.output)


def cmd_build(args):
    section = _read_text_utf8(args.section) if args.section else None
    build_from_template(args.output, template=args.template,
                        section_xml=section, title=args.title)
    return _finish_generated(args.output)


def _finish_edited(dst, report):
    gate = guards.validate_package(dst)   # Task 6에서 check_package로 교체
    ok = gate["ok"] and not report.get("not_found")
    payload = {"ok": ok, "output": str(dst), "report": report, "gate": gate}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 2


def cmd_replace(args):
    mapping = json.loads(_read_text_utf8(args.map))
    report = edit_mod.edit_file(args.src, args.dst,
                                lambda ed: ed.replace_text(mapping))
    return _finish_edited(args.dst, report)


def cmd_set_cell(args):
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.set_cell_text(args.table, args.row,
                                                   args.col, args.text))
    return _finish_edited(args.dst,
                          {"set_cell": [args.table, args.row, args.col]})


def cmd_add_row(args):
    cells = json.loads(_read_text_utf8(args.cells))
    edit_mod.edit_file(args.src, args.dst, lambda ed: ed.add_row(args.table, cells))
    return _finish_edited(args.dst, {"added_row": cells})


def cmd_del_row(args):
    edit_mod.edit_file(args.src, args.dst, lambda ed: ed.del_row(args.table, args.row))
    return _finish_edited(args.dst, {"deleted_row": args.row})


def cmd_add_para(args):
    edit_mod.edit_file(args.src, args.dst,
                       lambda ed: ed.add_para_after(args.after, args.text))
    return _finish_edited(args.dst, {"added_after": args.after})


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
    report = fill_mod.fill_file(args.src, args.dst, values=values, cells=cells)
    gate = guards.validate_package(args.dst)   # Task 6에서 check로 교체
    ok = gate["ok"] and not report["unmatched"]
    print(json.dumps({"ok": ok, "output": args.dst, "report": report,
                      "gate": gate}, ensure_ascii=False, indent=2))
    return 0 if ok else 2


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
    n.add_argument("--template", default="base")
    n.add_argument("--title")
    n.set_defaults(func=cmd_new)

    b = sub.add_parser("build", help="header+section 조립")
    b.add_argument("--section")
    b.add_argument("-o", "--output", required=True)
    b.add_argument("--template", default="base")
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
