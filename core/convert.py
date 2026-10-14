# core/convert.py
"""HWP(5.x 바이너리) → HWPX 변환.

엔진 두 개를 쓴다.

- ``python`` (기본): vendor/pyhwpx_hwp5 — python-hwpx의 HWP5 읽기 측을 표준
  라이브러리로 포팅한 순수 Python 변환기. DocInfo(글자·문단·테두리·글머리표)와
  본문(표 안의 표·그림·각주·필드·쪽번호·줄바꿈)을 그대로 옮기고, 옮기지 못한
  내용은 ``report``에 종류별 개수로 남긴다. 외부 의존성 없음.
- ``rhwp`` (폴백): Node.js 18+ + vendored @rhwp/core WASM. python 엔진이 파일을
  읽지 못할 때(손상·미지원 버전 등)만 자동으로 쓴다. rhwp는 용지 여백을 기본값으로
  내보내므로 ``getPageDef``로 원본 용지 설정을 읽어 되돌려 쓴다.
  표 안에 중첩된 표·그림, 글머리표 정의, 쪽번호 컨트롤은 rhwp가 버린다.

암호·배포용·DRM 문서는 두 엔진 모두 읽을 수 없어 즉시 실패한다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from core.errors import PackageError
from core import guards

ROOT = Path(__file__).resolve().parent.parent
WRAPPER = ROOT / "scripts" / "rhwp_convert.mjs"
VENDOR = ROOT / "vendor"

ENGINES = ("auto", "python", "rhwp")
#: python 엔진이 이 코드로 거부하면 rhwp도 못 읽으므로 폴백하지 않는다.
_NO_FALLBACK_CODES = {"hwp5-password", "hwp5-distribution", "hwp5-drm"}


def node_available():
    return shutil.which("node")


def _load_python_engine():
    if str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    import pyhwpx_hwp5  # noqa: WPS433 (vendored, stdlib only)
    return pyhwpx_hwp5


# ---------------------------------------------------------------- python engine

def _convert_python(src, dst):
    engine = _load_python_engine()
    data = src.read_bytes()
    converted = engine.convert(data)
    dst.write_bytes(engine.to_hwpx_bytes(converted.files))
    report = {
        "unconverted": dict(converted.report.unconverted),
        "dropped": dict(converted.report.dropped),
        "notes": dict(converted.source.notes),
    }
    return {"engine": "python", "report": report}


def _python_error(exc):
    """python 엔진 예외 → (사용자 메시지, 폴백 가능 여부)."""
    code = getattr(exc, "code", None)
    msg = getattr(exc, "message", None) or str(exc)
    suggestion = getattr(exc, "suggestion", None)
    text = f"{msg} [{code}]" if code else f"{type(exc).__name__}: {msg}"
    if suggestion:
        text += f" — {suggestion}"
    return text, code not in _NO_FALLBACK_CODES


# ------------------------------------------------------------------ rhwp engine

def _run_node(args, timeout, name):
    node = node_available()
    if not node:
        raise PackageError(
            "Node.js 18+가 필요합니다 (rhwp 엔진 전용, 다른 커맨드는 영향 없음). "
            "설치 후 다시 시도하세요.")
    try:
        proc = subprocess.run(
            [node, str(WRAPPER), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout)
    except subprocess.TimeoutExpired:
        raise PackageError(f"변환 시간 초과({timeout}s): {name}")
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise PackageError("HWP 변환 실패: " + (msg[-1] if msg else f"exit {proc.returncode}"))
    return proc.stdout


def _rhwp_page_defs(src, timeout):
    """rhwp가 읽은 섹션별 원본 용지 설정(getPageDef). 실패하면 None."""
    try:
        raw = _run_node(["--layout-info", str(src)], timeout, src.name)
        defs = json.loads(raw)
    except (PackageError, ValueError):
        return None
    return defs if isinstance(defs, list) and defs else None


_PAGE_PR_RE = re.compile(rb"<hp:pagePr\b[^>]*>.*?</hp:pagePr>", re.DOTALL)
_MARGIN_RE = re.compile(rb"<hp:margin\b[^>]*/>")
_SECTION_RE = re.compile(r"^Contents/section(\d+)\.xml$")
_IMAGE_ITEM_RE = re.compile(rb"<opf:item\b(?=[^>]*\bmedia-type=\"image/)[^>]*?/>")


def _set_attr(tag, name, value):
    pattern = rb'(\b' + name.encode() + rb'=")[^"]*(")'
    patched, n = re.subn(pattern, rb"\g<1>" + str(int(value)).encode() + rb"\g<2>", tag, count=1)
    return patched if n == 1 else tag


def _patch_page_geometry(section_xml, page_def):
    """rhwp 출력의 기본 용지 설정을 원본 값으로 되돌린다."""
    def patch(m):
        block = m.group(0)
        end = block.find(b">") + 1
        opening, body = block[:end], block[end:]
        opening = _set_attr(opening, "width", page_def["width"])
        opening = _set_attr(opening, "height", page_def["height"])
        mm = _MARGIN_RE.search(body)
        if mm:
            margin = mm.group(0)
            for xml_name, key in (("left", "marginLeft"), ("right", "marginRight"),
                                  ("top", "marginTop"), ("bottom", "marginBottom"),
                                  ("header", "marginHeader"), ("footer", "marginFooter"),
                                  ("gutter", "marginGutter")):
                if key in page_def:
                    margin = _set_attr(margin, xml_name, page_def[key])
            body = body[:mm.start()] + margin + body[mm.end():]
        return opening + body
    patched, n = _PAGE_PR_RE.subn(patch, section_xml, count=1)
    return patched if n == 1 else section_xml


def _mark_embedded_images(hpf):
    def add(m):
        item = m.group(0)
        if re.search(rb"\bisEmbeded\s*=", item):
            return item
        return item[:-2].rstrip() + b' isEmbeded="1"/>'
    return _IMAGE_ITEM_RE.sub(add, hpf)


def _postprocess_rhwp(dst, page_defs):
    """rhwp 산출물 보정: 용지 설정 복원, 이미지 매니페스트 isEmbeded. 바뀐 엔트리만 다시 쓴다."""
    with zipfile.ZipFile(dst) as zf:
        infos = zf.infolist()
        entries = [(info, zf.read(info.filename)) for info in infos]
    changed = False
    out = []
    for info, data in entries:
        name = info.filename
        sec = _SECTION_RE.match(name)
        new = data
        if sec and page_defs:
            idx = int(sec.group(1))
            if idx < len(page_defs) and isinstance(page_defs[idx], dict):
                new = _patch_page_geometry(data, page_defs[idx])
        elif name == "Contents/content.hpf":
            new = _mark_embedded_images(data)
        changed = changed or new != data
        out.append((info, new))
    if not changed:
        return False
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w") as zf:
        for info, data in out:
            comp = zipfile.ZIP_STORED if info.filename == "mimetype" else info.compress_type
            zf.writestr(info, data, compress_type=comp)
    tmp.replace(dst)
    return True


def _convert_rhwp(src, dst, timeout):
    _run_node([str(src), str(dst)], timeout, src.name)
    if not dst.is_file():
        raise PackageError(f"HWP 변환 실패: 산출물 없음 ({src.name})")
    page_defs = _rhwp_page_defs(src, timeout)
    fixed = _postprocess_rhwp(dst, page_defs)
    return {"engine": "rhwp",
            "report": {"page_geometry_restored": bool(page_defs) and fixed,
                       "known_losses": ["표 안의 표·그림·각주", "글머리표 정의",
                                        "쪽번호·필드 컨트롤", "형광펜"]}}


# ----------------------------------------------------------------------- entry

def hwp_to_hwpx(src, dst, *, engine="auto", timeout=120):
    src = Path(src)
    dst = Path(dst)
    if engine not in ENGINES:
        raise PackageError(f"알 수 없는 엔진: {engine} (auto|python|rhwp)")
    if not src.is_file():
        raise PackageError(f"입력 파일 없음: {src}")
    if src.suffix.lower() != ".hwp":
        raise PackageError(f"from-hwp는 .hwp 입력만 받습니다: {src.name}")
    if src.resolve() == dst.resolve():
        raise PackageError("출력 경로는 입력 .hwp와 달라야 합니다")

    result = None
    fallback_reason = None
    if engine in ("auto", "python"):
        try:
            result = _convert_python(src, dst)
        except Exception as exc:  # noqa: BLE001 — 엔진 오류는 모두 사용자 메시지로
            text, can_fallback = _python_error(exc)
            if engine == "python" or not can_fallback or not node_available():
                raise PackageError(f"HWP 변환 실패(python 엔진): {text}") from exc
            fallback_reason = text
    if result is None:
        result = _convert_rhwp(src, dst, timeout)
        if fallback_reason:
            result["fallback_reason"] = fallback_reason

    check = guards.check_package(dst)
    result.update({"ok": check["ok"], "output": str(dst), "check": check})
    if not check["ok"]:
        # 게이트 실패 산출물은 요청한 이름으로 두지 않는다 (검토용 .rejected 로 보관)
        rejected = dst.with_name(dst.stem + ".rejected" + dst.suffix)
        os.replace(dst, rejected)
        result.update({"output": None, "rejected_output": str(rejected)})
    return result
