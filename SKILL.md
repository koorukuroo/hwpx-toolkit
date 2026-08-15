---
name: hwpx-toolkit
description: "한글(HWPX) 문서 읽기·분석·검증 스킬 (Phase 1). .hwpx 파일, 한글 문서,
  Hancom, OWPML 관련 요청 시 사용. 생성·편집 기능은 이후 Phase에서 추가된다.
  .hwp 바이너리는 지원하지 않는다."
allowed-tools: Bash(python3 *), Read, Write, Glob, Grep
---

# hwpx-toolkit

HWPX는 한컴오피스 한글의 개방형 문서 포맷(OWPML, KS X 6101)이다.
ZIP 패키지 + XML 파트 구조. 모든 커맨드는 순수 Python stdlib로 동작한다 (pip 불필요).

## 워크플로우 선택

    사용자 요청
     ├─ "읽어줘/내용 알려줘" → extract
     ├─ "구조 분석" → analyze / "편집할 곳" → analyze --slots
     ├─ "새 문서 만들어줘" (마크다운) → new
     ├─ "문구 바꿔줘" → replace → (자동 check)
     ├─ "양식 빈칸 채워줘" → fill --analyze → values.json 작성 → fill → (자동 check)
     ├─ "표에 행 추가/삭제, 셀 수정" → add-row / del-row / set-cell
     ├─ "문단 추가" → add-para
     ├─ "파일 정상 확인" → check (편집 후엔 guard --reference 원본 병행)
     ├─ "XML 직접 수정" → unpack → 편집 → pack --source
     └─ .hwp 파일 → 미지원 안내

## 커맨드

    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" extract 문서.hwpx [--format markdown]
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" analyze 문서.hwpx [--slots]
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" validate 문서.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" unpack 문서.hwpx ./작업디렉토리/
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" pack ./작업디렉토리/ 결과.hwpx --source 문서.hwpx
    # 생성: 마크다운 → HWPX (제목/표/목록 지원; 강조 문법은 제거됨)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" new 입력.md -o 결과.hwpx [--title 제목]
    # 생성: section0.xml 직접 조립 (스타일 ID는 references/base-template-styles.md)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" build --section sec.xml -o 결과.hwpx
    # 편집 (원본 보존: 변경 섹션 외 바이트 동일, 자동 check 게이트)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" replace 원본.hwpx 결과.hwpx --map map.json
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" fill 양식.hwpx --analyze          # 1) 타겟 확인
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" fill 양식.hwpx 결과.hwpx --values values.json  # 2) 채우기
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-cell 원본.hwpx 결과.hwpx --table 0 --row 1 --col 1 --text "값"
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" add-row 원본.hwpx 결과.hwpx --table 0 --cells cells.json
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" del-row 원본.hwpx 결과.hwpx --table 0 --row 2
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" add-para 원본.hwpx 결과.hwpx --after "기준 문구" --text "새 문단"
    # 게이트
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" check 결과.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" guard 결과.hwpx --reference 원본.hwpx --rules rules.json

## 필수 규칙

1. **pack은 반드시 --source와 함께** 사용해 원본 바이트를 보존한다.
   --source 없는 pack은 새 문서 조립 전용(Phase 2 이후)이다.
2. **모든 산출물은 전달 전 validate를 통과**해야 한다. exit 0이 아니면
   사용자에게 완료를 보고하지 않는다.
3. XML 편집 시 네임스페이스 접두사(hp:, hs:, hh:, hc:)를 유지하고,
   `<hp:t>` 내부 자식 태그(hp:fwSpace 등)를 삭제하지 않는다.
4. .hwp(구형 바이너리)는 읽기·편집·변환 모두 미지원. 한글에서
   "다른 이름으로 저장 → HWPX"를 안내한다.
5. new/build는 validate를 자동 실행한다. 출력 JSON의 ok가 false면 산출물을
   사용자에게 전달하지 않는다.
6. 마크다운 지원 범위: #~###### 제목, -/* 불릿, 1. 순서 목록, GitHub 표,
   빈 줄 구분 문단. **강조**와 `코드`는 마커만 제거된다. 이 밖의 문법은
   일반 텍스트로 들어간다.
7. 편집 커맨드(replace/fill/set-cell/add-row/del-row/add-para)는 check를
   자동 실행한다. ok:false면 산출물을 전달하지 않는다. 레퍼런스가 있는
   작업(기관명 교체 등 전면 수정)은 guard --reference로 원문 잔재
   (forbid)·필수 키워드(require)·글자 수 증가까지 검사한 뒤 전달한다.
8. 병합 셀(rowSpan/colSpan)이 있는 표의 행 추가/삭제는 거부된다(EditError).
   이 경우 구조 한계를 사용자에게 알린다.
9. fill 워크플로우: ① `fill --analyze`로 타겟 키 확인 → ② 타겟 key에만 값을
   매핑한 values.json 작성 → ③ `fill --values` 실행 → unmatched가 비어야 완료.
   v1 한계: 체크박스/괄호 채우기는 리터럴 문자열 매칭이라 동일 리터럴이
   문서 내 여러 곳에 있으면 모두 함께 바뀐다 — 문서에서 유일한 리터럴인지
   analyze --slots로 먼저 확인한다.

## 포맷 상세

references/owpml-format.md 참조 (단위: 1pt=100 HWPUNIT, A4 폭 59528, 본문폭 42520).
