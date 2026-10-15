"""쪽 미리보기 — vendored rhwp(WASM) 렌더러로 HWPX/HWP를 쪽 단위 SVG/HTML로 그린다.

한컴 없이 레이아웃을 눈으로 확인하는 용도. 글자 폭을 근사하므로 줄바꿈 위치가 한컴과
조금 다를 수 있고, 문단 테두리·일부 개체는 단순화된다. Node.js 18+가 필요하며 macOS의
qlmanage가 있으면 PNG도 만든다(없으면 SVG만).
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from core.convert import _run_node
from core.errors import PackageError

FORMATS = ("svg", "html")


_SVG_SIZE_RE = re.compile(r'<svg[^>]*\swidth="([\d.]+)"[^>]*\sheight="([\d.]+)"')


def _svg_to_png(svg_path, png_path, width):
    """macOS qlmanage로 SVG → PNG. qlmanage는 정사각 썸네일만 만들어 세로가 긴 쪽을
    잘라내므로, 쪽을 정사각 캔버스에 얹어 그린 뒤 sips로 쪽 크기만큼 잘라낸다.
    실패하면 None."""
    ql, sips = shutil.which("qlmanage"), shutil.which("sips")
    if not ql or not sips:
        return None
    svg_path, png_path = Path(svg_path), Path(png_path)
    svg = svg_path.read_text(encoding="utf-8")
    m = _SVG_SIZE_RE.search(svg)
    if not m:
        return None
    w, h = float(m.group(1)), float(m.group(2))
    side = max(w, h)
    inner = svg[svg.index("<svg"):]
    # 쪽을 정사각 캔버스 가운데에 두고, 래스터 후 가운데 기준으로 쪽 크기만 잘라낸다
    ox, oy = (side - w) / 2, (side - h) / 2
    inner = inner.replace("<svg ", f'<svg x="{ox}" y="{oy}" ', 1)
    square = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{side}" height="{side}" '
              f'viewBox="0 0 {side} {side}"><rect width="100%" height="100%" fill="white"/>'
              f'{inner}</svg>')
    tmp_svg = png_path.with_name(f".{png_path.stem}.square.svg")
    tmp_svg.write_text(square, encoding="utf-8")
    try:
        subprocess.run([ql, "-t", "-s", str(width), "-o", str(png_path.parent), str(tmp_svg)],
                       capture_output=True, timeout=60, check=False)
        made = png_path.parent / (tmp_svg.name + ".png")
        if not made.is_file():
            return None
        ph, pw = round(width * h / side), round(width * w / side)
        subprocess.run([sips, "-c", str(ph), str(pw), str(made), "--out", str(png_path)],
                       capture_output=True, timeout=60, check=False)
        if not png_path.is_file():
            os.replace(made, png_path)
        else:
            made.unlink(missing_ok=True)
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        tmp_svg.unlink(missing_ok=True)
    return png_path


def render_pages(src, outdir, *, fmt="svg", pages=None, png=False, png_width=1400,
                 timeout=180):
    """src의 쪽들을 outdir/page-N.<fmt>로 렌더한다. pages="3" 또는 "2-5".
    반환: {"pages": 전체 쪽수, "from", "to", "files": [...], "png": [...]}"""
    if fmt not in FORMATS:
        raise PackageError(f"format은 svg|html: {fmt}")
    src, outdir = Path(src), Path(outdir)
    if not src.is_file():
        raise PackageError(f"입력 파일 없음: {src}")
    outdir.mkdir(parents=True, exist_ok=True)
    args = ["--render", str(src), str(outdir), fmt]
    if pages:
        args.append(str(pages))
    out = _run_node(args, timeout, src.name)
    try:
        result = json.loads(out)
    except json.JSONDecodeError as e:
        raise PackageError(f"렌더러 출력 해석 실패: {e}") from e
    result["png"] = []
    if png and fmt == "svg":
        for f in result["files"]:
            f = Path(f)
            made = _svg_to_png(f, f.with_suffix(".png"), png_width)
            if made:
                result["png"].append(str(made))
        if not result["png"]:
            result["png_note"] = "PNG 변환 도구(qlmanage) 없음 — SVG를 브라우저로 여세요"
    return result
