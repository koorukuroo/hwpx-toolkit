"""CLI 실패 계약 — 모든 서브커맨드가 실패 시 JSON + exit 2를 반환하는지 확인."""
import importlib.util
import json
import sys
from pathlib import Path

_HWPX_PY = Path(__file__).resolve().parent.parent / "scripts" / "hwpx.py"
_spec = importlib.util.spec_from_file_location("hwpx_cli", _HWPX_PY)
hwpx_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hwpx_cli)


def test_extract_on_non_zip_file_returns_json_error(tmp_path, capsys):
    bad = tmp_path / "not-a-zip.hwpx"
    bad.write_bytes("이것은 ZIP 파일이 아닙니다".encode("utf-8"))

    code = hwpx_cli.main(["extract", str(bad)])

    assert code == 2
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is False
    assert "error" in payload and payload["error"]


def test_analyze_on_non_zip_file_returns_json_error(tmp_path, capsys):
    bad = tmp_path / "not-a-zip.hwpx"
    bad.write_bytes(b"garbage")

    code = hwpx_cli.main(["analyze", str(bad)])

    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"ok": False, "error": payload["error"]}
    assert payload["ok"] is False


def test_unpack_on_non_zip_file_returns_json_error(tmp_path, capsys):
    bad = tmp_path / "not-a-zip.hwpx"
    bad.write_bytes(b"garbage")
    out_dir = tmp_path / "out"

    code = hwpx_cli.main(["unpack", str(bad), str(out_dir)])

    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
