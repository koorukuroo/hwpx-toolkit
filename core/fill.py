"""양식 채우기 — fill_targets 결과에 값을 매핑해 적용하고, 다시 읽어 확인한다."""
import os
import re
from pathlib import Path

from core import analyze
from core.edit import edit_file


def _match(norm_key, target_key):
    if not norm_key or not target_key:
        return False
    return norm_key == target_key or norm_key in target_key \
        or target_key in norm_key


def _find_target(nk, targets):
    # 1단계: 정확히 일치하는 정규화 키 우선 (컨테인먼트로 오탐하는 걸 방지 —
    # 예: "동의"는 "비동의"의 부분 문자열이라 컨테인먼트만 쓰면 잘못 매칭됨).
    for t in targets:
        if nk == t["key"]:
            return t
    # 2단계: 정확 일치가 없을 때만 컨테인먼트로 폴백 (합성 paren 키 등 대응).
    for t in targets:
        if _match(nk, t["key"]):
            return t
    return None


_FALSY = {"", "false", "0", "no", "n", "off", "x", "□", "☐", "아니오", "아니요",
          "미체크", "none", "null"}


def truthy(val):
    """체크박스 값 판정 — JSON의 false/0/""/"false"/"아니오" 등은 체크하지 않는다.
    (파이썬 진릿값으로 보면 문자열 "false"가 참이 되는 사고를 막는다.)"""
    if isinstance(val, str):
        return val.strip().lower() not in _FALSY
    return bool(val)


def _ws(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def _apply_one(ed, key, tgt, val, filled, skipped, unmatched):
    kind = tgt["kind"]
    if kind == "label-cell":
        ed.set_cell_text(tgt["table"], tgt["row"], tgt["col"], str(val))
        filled.append(key)
    elif kind == "checkbox":
        if not truthy(val):
            # falsy 체크박스 값은 편집을 수행하지 않음 — filled로 보고하지 않는다.
            skipped.append(key)
            return
        rep = ed.replace_text({tgt["literal"]: tgt["literal"].replace("□", "☑", 1)
                               .replace("☐", "☑", 1)})
        (filled if rep["replaced"][tgt["literal"]] > 0 else unmatched).append(key)
    elif kind == "paren":
        rep = ed.replace_text({tgt["literal"]: tgt["prefix"] + "(" + str(val) + ")"})
        (filled if rep["replaced"][tgt["literal"]] > 0 else unmatched).append(key)
    elif kind == "inline":
        new_text = f"{tgt['label']}: {val}"
        n = ed.replace_in_para(tgt["pindex"], tgt["literal"], new_text)
        (filled if n > 0 else unmatched).append(key)
    elif kind == "field":
        ed.fill_field(tgt["pindex"], tgt["field_index"], str(val))
        filled.append(key)
    else:
        unmatched.append(key)


def _expected_text(tgt, val):
    if tgt["kind"] == "checkbox":
        return "☑" + tgt["literal"][1:]
    if tgt["kind"] == "paren":
        return tgt["prefix"] + "(" + str(val) + ")"
    if tgt["kind"] == "inline":
        return f"{tgt['label']}: {val}"
    return str(val)


def fill_file(src, dst, values=None, cells=None):
    values = values or {}
    cells = cells or []
    targets = analyze.fill_targets(src)["targets"]

    plan = {}          # section → [(key, target, value)]
    unmatched = []
    for key, val in values.items():
        nk = analyze._norm_label(key)
        tgt = _find_target(nk, targets)
        if tgt is None:
            unmatched.append(key)
        else:
            plan.setdefault(tgt["section"], []).append((key, tgt, val))
    for spec in cells:
        sec = spec.get("section", "Contents/section0.xml")
        plan.setdefault(sec, []).append((
            f"cell:{spec['table']}:{spec['row']}:{spec['col']}",
            {"kind": "label-cell", "table": spec["table"], "row": spec["row"],
             "col": spec["col"], "section": sec}, spec["value"]))

    filled, skipped = [], []
    dst = Path(dst)
    sections = sorted(plan) or ["Contents/section0.xml"]
    cur = Path(src)
    temps = []
    try:
        for i, sec in enumerate(sections):
            items = plan.get(sec, [])

            def apply(ed, items=items):
                for key, tgt, val in items:
                    _apply_one(ed, key, tgt, val, filled, skipped, unmatched)
                return filled
            out = dst if i == len(sections) - 1 else dst.with_name(f".{dst.name}.fill{i}")
            if out != dst:
                temps.append(out)
            edit_file(cur, out, apply, section=sec)
            cur = out
    finally:
        for t in temps:
            if t.exists():
                os.remove(t)

    # 채운 뒤 다시 읽어 값이 실제로 들어갔는지 확인한다
    text = _ws(analyze.extract_text(dst))
    verified, verify_failed = [], []
    for sec in sections:
        for key, tgt, val in plan.get(sec, []):
            if key not in filled:
                continue
            (verified if _ws(_expected_text(tgt, val)) in text else verify_failed).append(key)
    return {"filled": filled, "unmatched": unmatched, "skipped": skipped,
            "verified": verified, "verify_failed": verify_failed}
