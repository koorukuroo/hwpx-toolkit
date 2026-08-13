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
     ├─ "구조 분석/어떤 양식인지" → analyze
     ├─ "편집할 곳 찾아줘" → analyze --slots
     ├─ "파일이 정상인지 확인" → validate
     ├─ "XML 직접 보기/고치기" → unpack → (편집) → pack --source
     └─ .hwp 파일 → 미지원 안내 (한글에서 .hwpx로 저장 요청)

## 커맨드

    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" extract 문서.hwpx [--format markdown]
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" analyze 문서.hwpx [--slots]
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" validate 문서.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" unpack 문서.hwpx ./작업디렉토리/
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" pack ./작업디렉토리/ 결과.hwpx --source 문서.hwpx

## 필수 규칙

1. **pack은 반드시 --source와 함께** 사용해 원본 바이트를 보존한다.
   --source 없는 pack은 새 문서 조립 전용(Phase 2 이후)이다.
2. **모든 산출물은 전달 전 validate를 통과**해야 한다. exit 0이 아니면
   사용자에게 완료를 보고하지 않는다.
3. XML 편집 시 네임스페이스 접두사(hp:, hs:, hh:, hc:)를 유지하고,
   `<hp:t>` 내부 자식 태그(hp:fwSpace 등)를 삭제하지 않는다.
4. .hwp(구형 바이너리)는 읽기·편집·변환 모두 미지원. 한글에서
   "다른 이름으로 저장 → HWPX"를 안내한다.

## 포맷 상세

references/owpml-format.md 참조 (단위: 1pt=100 HWPUNIT, A4 폭 59528, 본문폭 42520).
