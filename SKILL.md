---
name: hwpx-toolkit
description: "한글(HWPX) 문서 읽기·분석·생성·편집·서식·이미지·검증·HWP→HWPX 변환(명시 요청 시)·공문서 검수 스킬."
allowed-tools: Bash(python3 *), Read, Write, Glob, Grep
---

# hwpx-toolkit

HWPX는 한컴오피스 한글의 개방형 문서 포맷(OWPML, KS X 6101)이다.
ZIP 패키지 + XML 파트 구조. 모든 커맨드는 순수 Python stdlib로 동작한다 (pip 불필요, from-hwp만 Node.js 18+ 필요).

## 워크플로우 선택

    사용자 요청
     ├─ "읽어줘/내용 알려줘" → extract
     ├─ "구조 분석" → analyze / "편집할 곳" → analyze --slots
     ├─ "새 문서 만들어줘" (마크다운) → new
     ├─ "문구 바꿔줘" → replace → (자동 check)
     ├─ "양식 빈칸 채워줘" → fill --analyze → values.json 작성 → fill → (자동 check)
     ├─ "표에 행 추가/삭제, 셀 수정" → add-row / del-row / set-cell
     ├─ "셀 병합/열 추가" → merge-cells / add-col
     ├─ "글자/문단 서식 바꿔줘" → set-text-style / set-para-style
     ├─ "머리말/꼬리말/쪽번호" → set-header / set-footer / remove-header / remove-footer / set-pagenum
     ├─ "가로/용지/여백/다단/쪽나누기" → set-page / set-columns / page-break
     ├─ "이미지 넣어줘/바꿔줘" → insert-image / list-images / resize-image / replace-image / delete-image
     ├─ "문단 추가" → add-para
     ├─ "파일 정상 확인" → check (편집 후엔 guard --reference 원본 병행)
     │   ├─ check가 char_border_bug 보고 → fix-borders 실행 후 재check
     ├─ "XML 직접 수정" → unpack → 편집 → pack --source
     ├─ .hwp 파일 + "HWPX로 변환해줘"(명시) → from-hwp(자동 check) → 통과 시 전달
     ├─ .hwp 파일 + 그 외 요청 → 변환 여부 먼저 확인 (자동 변환 금지)
     ├─ "공문서 작성법 검수/맞춤법 표기 확인" → lint
     └─ "보고서 양식으로 만들어줘" → new --template report

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
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" merge-cells 원본.hwpx 결과.hwpx --table 0 --row 0 --col 0 --row2 1 --col2 1
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" add-col 원본.hwpx 결과.hwpx --table 0 --cells cells.json
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-text-style 원본.hwpx 결과.hwpx --after "제목" --bold --size 16
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-para-style 원본.hwpx 결과.hwpx --after "제목" --align center
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-header 원본.hwpx 결과.hwpx --text "대외비" --align center
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-footer 원본.hwpx 결과.hwpx --text "기밀" --align right
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" remove-header 원본.hwpx 결과.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" remove-footer 원본.hwpx 결과.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-pagenum 원본.hwpx 결과.hwpx --where footer --align center
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-page 원본.hwpx 결과.hwpx --orientation landscape --margin-mm 20
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-columns 원본.hwpx 결과.hwpx --count 2 --gap-mm 10
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" page-break 원본.hwpx 결과.hwpx --after "절 제목"
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" insert-image 원본.hwpx 결과.hwpx --image 그림.png --after "그림 위치" --width-mm 80
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" list-images 원본.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" resize-image 원본.hwpx 결과.hwpx --index 0 --width-mm 100
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" replace-image 원본.hwpx 결과.hwpx --index 0 --image 새그림.png
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" delete-image 원본.hwpx 결과.hwpx --index 0
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" add-para 원본.hwpx 결과.hwpx --after "기준 문구" --text "새 문단"
    # 게이트
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" check 결과.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" fix-borders 원본.hwpx 결과.hwpx   # 글자 테두리 버그 수리
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" guard 결과.hwpx --reference 원본.hwpx --max-unchanged-ratio 0.35
    # 변환
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" from-hwp 원본.hwp -o 변환.hwpx      # Node.js 18+ 필요
    # 검수
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" lint 문서.hwpx                       # 공문서 표기 검수 (JSON)
    # 템플릿
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" new 입력.md -o 결과.hwpx --template report

## 필수 규칙

1. **pack은 반드시 --source와 함께** 사용해 원본 바이트를 보존한다.
   --source 없는 pack은 새 문서 조립 전용(Phase 2 이후)이다.
2. **모든 산출물은 전달 전 validate를 통과**해야 한다. exit 0이 아니면
   사용자에게 완료를 보고하지 않는다.
3. XML 편집 시 네임스페이스 접두사(hp:, hs:, hh:, hc:)를 유지하고,
   `<hp:t>` 내부 자식 태그(hp:fwSpace 등)를 삭제하지 않는다.
4. .hwp(구형 바이너리)는 읽기·편집 미지원, 변환은 명시 요청 시 from-hwp 사용
   (rule 13 참조). 사용자가 변환을 원하지 않으면 한글에서
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
   analyze --slots로 먼저 확인한다. 중첩 표 내부 셀과 section0 외 섹션의
   타겟은 v1에서 편집 미지원(unmatched 처리).
10. 서식 커맨드(set-text-style/set-para-style)는 대상 문단(--after 문구 | --para N)
    만 바꾼다. header.xml에 새 스타일이 추가되고 다른 문단은 영향 없다.
    스타일을 안 건드린 편집은 header.xml이 바이트 동일하게 유지된다.
    report 템플릿의 `##` 제목은 1×1 표(섹션 바)로 렌더되므로 set-text-style --after
    등 본문 문단 대상 커맨드의 기준 문구로 쓸 수 없다(셀 텍스트).
11. 이미지는 PNG/JPEG만. insert-image에서 크기 미지정 시 96dpi 환산 (resize-image는
    한쪽 이상 지정 필요), 한쪽만 주면 비율 유지. replace-image는 기존 BinData를
    남기고 새 항목을 추가한다.
12. merge-cells/add-col도 병합 셀이 이미 있는 표에서는 거부된다. 머리말·꼬리말·
    쪽번호 구조는 한컴 저장 문서와 구조 대조로 검증됨(docs/hancom-verification.md,
    references/owpml-format.md). 모든 편집 커맨드는 section0만 대상으로 한다
    (다중 섹션 편집은 아직 미지원, 추후 로드맵).
13. .hwp는 사용자가 HWPX 변환을 명시적으로 요청한 경우에만 from-hwp로 변환한다.
    변환본은 별도 파일이며 원본 .hwp는 건드리지 않는다. Node.js가 없으면 설치를
    안내하고, 다른 커맨드는 그대로 쓸 수 있다.
14. lint는 게이트가 아니다. findings를 요약해 사용자에게 보여주고 수정 여부는
    사용자가 정한다(공문 표기 규칙은 references/gonmun-rules.md).
15. check가 `char-border-bug`를 보고하면 `fix-borders`로 수리한 뒤 다시 check한다.
    수리는 header.xml만 바꾸므로 본문은 그대로다. fix-borders는 header.xml을
    바꾸므로, 원본과 대조하는 `guard --reference`는 `entry-changed:
    Contents/header.xml`을 보고한다(서식 커맨드와 동일한 정상 동작).
16. check의 `cell-overflow-risk` 경고는 추정이라 ok를 막지 않는다. 양식을 채울 때는
    `fill --analyze`가 알려주는 label-cell 타겟의 `capacity`(셀의 em 단위 수용량)를 보고,
    채울 값의 길이를 ASCII 0.5em·한글 1em으로 환산해 비교한다(경고는 환산값과 실제 문자 수를 함께 표시).
    넘칠 수밖에 없으면 사용자에게 알린다.
17. 문서 전체를 새 관점으로 재작성하는 작업(기관 교체 등)은 guard에
    `--max-unchanged-ratio 0.35`를 붙여 원문이 그대로 남지 않았는지 확인한다.
    guard는 `○○`, `{{...}}`, `<<>>`, `TODO`, `TBD`, `. . .` 같은 미완성 표시도
    기본 검사한다. 주의: 기본 placeholder 패턴의 `○○`는 한국 공문에서 흔한 익명화
    표기(`홍○○`, `○○부`)에도 걸리므로, 익명화가 포함된 문서를 검사할 때는
    `--no-default-placeholders`를 쓰거나 findings를 사람이 판단한다.

## 포맷 상세

references/owpml-format.md 참조 (단위: 1pt=100 HWPUNIT, A4 폭 59528, 본문폭 42520).
