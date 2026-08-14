#!/usr/bin/env python3
"""hwpx-toolkit 단일 CLI. 사용: python3 scripts/hwpx.py <command> ..."""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import analyze, guards  # noqa: E402
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


def cmd_new(args):
    src = Path(args.input)
    if not src.is_file():
        raise PackageError(f"입력 파일 없음: {src}")
    text = src.read_text(encoding="utf-8")
    title = args.title or md_mod.first_heading(text) or src.stem
    section = md_mod.render_to_section(text, template=args.template)
    build_from_template(args.output, template=args.template,
                        section_xml=section, title=title)
    return _finish_generated(args.output)


def cmd_build(args):
    section = Path(args.section).read_text(encoding="utf-8") \
        if args.section else None
    build_from_template(args.output, template=args.template,
                        section_xml=section, title=args.title)
    return _finish_generated(args.output)


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
