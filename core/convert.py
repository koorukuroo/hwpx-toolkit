# core/convert.py
"""HWP(바이너리) → HWPX 변환 — Node.js + vendored rhwp WASM (선택 의존성)."""
import shutil
import subprocess
from pathlib import Path

from core.errors import PackageError
from core import guards

ROOT = Path(__file__).resolve().parent.parent
WRAPPER = ROOT / "scripts" / "rhwp_convert.mjs"


def node_available():
    return shutil.which("node")


def hwp_to_hwpx(src, dst, *, timeout=120):
    src = Path(src)
    dst = Path(dst)
    if not src.is_file():
        raise PackageError(f"입력 파일 없음: {src}")
    if src.suffix.lower() != ".hwp":
        raise PackageError(f"from-hwp는 .hwp 입력만 받습니다: {src.name}")
    node = node_available()
    if not node:
        raise PackageError(
            "Node.js 18+가 필요합니다 (from-hwp 전용, 다른 커맨드는 영향 없음). "
            "설치 후 다시 시도하세요.")
    try:
        proc = subprocess.run(
            [node, str(WRAPPER), str(src), str(dst)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout)
    except subprocess.TimeoutExpired:
        raise PackageError(f"변환 시간 초과({timeout}s): {src.name}")
    if proc.returncode != 0 or not dst.is_file():
        msg = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise PackageError("HWP 변환 실패: " + (msg[-1] if msg else f"exit {proc.returncode}"))
    check = guards.check_package(dst)
    return {"ok": check["ok"], "output": str(dst), "check": check}
