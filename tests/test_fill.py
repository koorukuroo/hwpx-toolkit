import json
import pytest
from core.analyze import fill_targets, extract_text
from core.fill import fill_file
from core.guards import validate_package
from tests.fixture import build_form_hwpx


def test_fill_targets_detects_all_kinds(tmp_path):
    p = build_form_hwpx(tmp_path / "form.hwpx")
    targets = fill_targets(p)["targets"]
    kinds = {t["kind"] for t in targets}
    assert kinds == {"label-cell", "checkbox", "paren"}
    labels = {t["key"] for t in targets if t["kind"] == "label-cell"}
    assert labels == {"성명", "연락처"}
    boxes = {t["literal"] for t in targets if t["kind"] == "checkbox"}
    assert boxes == {"□동의", "□비동의"}
    paren = next(t for t in targets if t["kind"] == "paren")
    assert paren["blank"] == "(  )"
    assert paren["literal"].endswith("(  )")


def test_fill_by_labels_and_checkbox_and_paren(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "filled.hwpx"
    report = fill_file(src, dst, values={
        "성  명": "홍길동",          # 정규화 매칭 확인 (공백 삽입)
        "연락처": "010-1234-5678",
        "동의": True,
        "일반": "3",
    })
    assert report["unmatched"] == []
    text = extract_text(dst)
    assert "홍길동" in text and "010-1234-5678" in text
    assert "☑동의" in text and "□비동의" in text     # 비동의는 그대로
    assert "일반(3)통" in text
    assert validate_package(dst)["ok"]


def test_fill_unmatched_reported(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    report = fill_file(src, dst, values={"없는라벨": "x"})
    assert report["unmatched"] == ["없는라벨"]


def test_fill_by_cells_coordinates(tmp_path):
    src = build_form_hwpx(tmp_path / "form.hwpx")
    dst = tmp_path / "out.hwpx"
    report = fill_file(src, dst,
                       cells=[{"table": 0, "row": 1, "col": 1,
                               "value": "curator@x.kr"}])
    assert report["filled"] == ["cell:0:1:1"]
    assert "curator@x.kr" in extract_text(dst)


def test_cli_fill_analyze_and_apply(tmp_path, capsys):
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "scripts"))
    import importlib
    hwpx_cli = importlib.import_module("hwpx")
    src = build_form_hwpx(tmp_path / "form.hwpx")

    rc = hwpx_cli.main(["fill", str(src), "--analyze"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and len(payload["targets"]) >= 4

    values = tmp_path / "values.json"
    values.write_text(json.dumps({"성명": "김철수"}), encoding="utf-8")
    dst = tmp_path / "out.hwpx"
    rc = hwpx_cli.main(["fill", str(src), str(dst), "--values", str(values)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    assert "김철수" in extract_text(dst)
