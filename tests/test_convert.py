import os
import shutil
import pytest
from pathlib import Path
from core.errors import PackageError
from core import convert

ROOT = Path(__file__).resolve().parent.parent


def test_vendor_files_and_notice_present():
    for rel in ("vendor/rhwp/rhwp.js", "vendor/rhwp/rhwp_bg.wasm",
                "vendor/rhwp/LICENSE", "scripts/rhwp_convert.mjs",
                "THIRD_PARTY_NOTICES.md"):
        assert (ROOT / rel).is_file(), rel
    assert "MIT" in (ROOT / "vendor/rhwp/LICENSE").read_text(encoding="utf-8")
    assert "@rhwp/core" in (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")


def test_rejects_non_hwp_and_missing(tmp_path):
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(tmp_path / "없음.hwp", tmp_path / "o.hwpx")
    bad = tmp_path / "x.txt"
    bad.write_text("x")
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(bad, tmp_path / "o.hwpx")


def test_missing_node_reports_package_error(tmp_path, monkeypatch):
    f = tmp_path / "a.hwp"
    f.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 64)
    monkeypatch.setattr(convert, "node_available", lambda: None)
    with pytest.raises(PackageError) as ei:
        convert.hwp_to_hwpx(f, tmp_path / "o.hwpx")
    assert "Node" in str(ei.value)


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_conversion_failure_on_garbage_input(tmp_path):
    f = tmp_path / "garbage.hwp"
    f.write_bytes(b"not a real hwp file at all" * 10)
    with pytest.raises(PackageError):
        convert.hwp_to_hwpx(f, tmp_path / "o.hwpx")


@pytest.mark.skipif(shutil.which("node") is None or not os.environ.get("HWPX_TEST_HWP"),
                    reason="node 또는 HWPX_TEST_HWP 샘플 없음")
def test_real_conversion_passes_check(tmp_path):
    from core.analyze import extract_text
    out = tmp_path / "conv.hwpx"
    r = convert.hwp_to_hwpx(os.environ["HWPX_TEST_HWP"], out)
    assert r["check"]["ok"], r["check"]["errors"]
    assert extract_text(out).strip()
