#!/usr/bin/env python3
"""hwpx-toolkit 단일 CLI. 사용: python3 scripts/hwpx.py <command> ..."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import analyze, guards  # noqa: E402


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

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
