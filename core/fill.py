"""양식 채우기 — fill_targets 결과에 값을 매핑해 적용."""
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


def fill_file(src, dst, values=None, cells=None):
    values = values or {}
    cells = cells or []
    targets = analyze.fill_targets(src)["targets"]

    plan = []          # (설명 키, 적용 함수 목록용 데이터)
    unmatched = []
    for key, val in values.items():
        nk = analyze._norm_label(key)
        tgt = _find_target(nk, targets)
        if tgt is None:
            unmatched.append(key)
        else:
            plan.append((key, tgt, val))

    def apply(ed):
        filled = []
        for key, tgt, val in plan:
            if tgt["kind"] == "label-cell":
                ed.set_cell_text(tgt["table"], tgt["row"], tgt["col"], str(val))
            elif tgt["kind"] == "checkbox":
                if val:
                    ed.replace_text(
                        {tgt["literal"]: tgt["literal"].replace("□", "☑", 1)})
            elif tgt["kind"] == "paren":
                ed.replace_text(
                    {tgt["literal"]: tgt["prefix"] + "(" + str(val) + ")"})
            filled.append(key)
        for spec in cells:
            ed.set_cell_text(spec["table"], spec["row"], spec["col"],
                             str(spec["value"]))
            filled.append(f"cell:{spec['table']}:{spec['row']}:{spec['col']}")
        return filled

    filled = edit_file(src, dst, apply)
    return {"filled": filled, "unmatched": unmatched}
