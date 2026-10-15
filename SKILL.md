---
name: hwpx-toolkit
description: "한글(HWPX) 문서 읽기·분석·생성·편집·서식·이미지·검증·HWP→HWPX 변환(명시 요청 시)·공문서 검수 스킬."
allowed-tools: Bash(python3 *), Read, Write, Glob, Grep
---

# hwpx-toolkit

HWPX는 한컴오피스 한글의 개방형 문서 포맷(OWPML, KS X 6101)이다.
ZIP 패키지 + XML 파트 구조. 모든 커맨드는 순수 Python stdlib로 동작한다 (pip 불필요).
from-hwp도 기본 엔진(python, vendor/pyhwpx_hwp5)은 stdlib이며, rhwp 폴백만 Node.js 18+가 필요하다.

## 워크플로우 선택

    사용자 요청
     ├─ "읽어줘/내용 알려줘" → extract
     ├─ "구조 분석" → analyze / "편집할 곳" → analyze --slots
     ├─ "새 문서 만들어줘" (마크다운) → new
     ├─ "문구 바꿔줘" → replace → (자동 check)
     ├─ "양식 빈칸 채워줘" → fill --analyze → values.json 작성 → fill → (자동 check)
     ├─ "표에 행 추가/삭제, 셀 수정" → add-row / del-row / set-cell
     ├─ "셀 병합/열 추가/셀 배경·테두리" → merge-cells / add-col / set-cell-style
     ├─ "글자/문단 서식 바꿔줘" → set-text-style / set-para-style
     ├─ "머리말/꼬리말/쪽번호" → set-header / set-footer / remove-header / remove-footer / set-pagenum
     ├─ "가로/용지/여백/다단/쪽나누기" → set-page / set-columns / page-break
     ├─ "이미지 넣어줘/바꿔줘" → insert-image / list-images / resize-image / replace-image / delete-image
     ├─ "문단 추가" → add-para
     ├─ "파일 정상 확인" → check (편집 후엔 guard --reference 원본 병행)
     ├─ "어떻게 보이는지/레이아웃 확인" → render --png 후 PNG를 Read로 보고 판단
     │   ├─ check가 char_border_bug 보고 → fix-borders 실행 후 재check
     ├─ "XML 직접 수정" → unpack → 편집 → pack --source
     ├─ .hwp 파일 + "HWPX로 변환해줘"(명시) → from-hwp(자동 check) → report 확인 → 통과 시 전달
     ├─ .hwp 파일 + 그 외 요청 → 변환 여부 먼저 확인 (자동 변환 금지)
     ├─ "공문서 작성법 검수/맞춤법 표기 확인" → lint [--doc-type gonmun|bogo]
     ├─ "보고서/계획서 양식으로 만들어줘" → new --theme report (Ⅰ·Ⅱ 번호 칩, 남색)
     ├─ "공문으로 만들어줘" → new --theme gonmun (휴먼명조 15pt, □ ○ - 기호)
     └─ "깔끔하게/모던하게" → new --theme modern (맑은 고딕, 파랑 포인트)

## 커맨드

    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" extract 문서.hwpx [--format markdown]
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" analyze 문서.hwpx [--slots]
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" validate 문서.hwpx
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" unpack 문서.hwpx ./작업디렉토리/
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" pack ./작업디렉토리/ 결과.hwpx --source 문서.hwpx
    # 생성: 마크다운 → HWPX (제목/표/목록(3단계)/굵게·코드/인용/코드블록/그림/--- 쪽나눔)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" new 입력.md -o 결과.hwpx [--theme base|gonmun|report|modern] [--title 제목]
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
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" set-cell-style 원본.hwpx 결과.hwpx --table 0 --row 0 --col 0 --col2 2 --bg E6E6E6 --border solid
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
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" guard 결과.hwpx --reference 원본.hwpx --max-unchanged-ratio 0.35 [--strict-structure]
    # 변환
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" from-hwp 원본.hwp -o 변환.hwpx      # 기본 python 엔진(의존성 없음)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" from-hwp 원본.hwp -o 변환.hwpx --engine rhwp   # Node.js 폴백 엔진 강제
    # 미리보기 (Node.js 18+; 한컴 없이 쪽 단위 SVG/PNG — 줄바꿈은 근사)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" render 문서.hwpx -o ./pages --png [--pages 1-2]
    # 검수
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" lint 문서.hwpx                       # 공문서 표기 검수 (JSON)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" lint 문서.hwpx --doc-type gonmun     # + 수신·발신명의·시행·공개 구분 유무
    # 테마 (글꼴·색·목록 기호·표 선을 테마가 정한다 — 마크다운에 기호를 직접 쓰지 않는다)
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" new 입력.md -o 결과.hwpx --theme report   # 보고서: Ⅰ·Ⅱ 칩, 남색
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" new 입력.md -o 결과.hwpx --theme gonmun   # 공문: 휴먼명조 15pt
    python3 "${CLAUDE_SKILL_DIR}/scripts/hwpx.py" new 입력.md -o 결과.hwpx --theme modern   # 현대: 맑은 고딕, 파랑

## 필수 규칙

1. **pack은 반드시 --source와 함께** 사용해 원본 바이트를 보존한다.
   --source 없는 pack은 새 문서 조립 전용(Phase 2 이후)이다.
2. **모든 산출물은 전달 전 validate를 통과**해야 한다. exit 0이 아니면
   사용자에게 완료를 보고하지 않는다.
3. XML 편집 시 네임스페이스 접두사(hp:, hs:, hh:, hc:)를 유지하고,
   `<hp:t>` 내부 자식 태그(hp:fwSpace 등)를 삭제하지 않는다. `<hp:t>` 안에 탭
   **문자**(U+0009)를 넣지 않는다 — 한컴이 문서를 영원히 열지 못한다. 탭은
   `<hp:tab/>`, 줄바꿈은 `<hp:lineBreak/>` 요소로 쓴다(커맨드는 `\t`·`\n`을 자동 변환).
4. .hwp(구형 바이너리)는 읽기·편집 미지원, 변환은 명시 요청 시 from-hwp 사용
   (rule 13·18 참조). 사용자가 변환을 원하지 않으면 한글에서
   "다른 이름으로 저장 → HWPX"를 안내한다. **.hwp 산출은 불가**하다 — ".hwp로
   저장해줘"에는 .hwpx로 만든 뒤 한글에서 .hwp로 저장하도록 안내하고, 확장자만
   .hwp로 바꿔 전달하지 않는다.
5. new/build는 validate를 자동 실행한다. 출력 JSON의 ok가 false면 산출물을
   사용자에게 전달하지 않는다.
6. 마크다운 지원 범위: #~###### 제목, -/* 불릿과 1. 순서 목록(2칸 들여쓰기마다
   한 단계, 최대 3단계), GitHub 표, `> 인용`, ``` 코드 블록, `---`(다음 블록 앞
   쪽 나눔), `![설명](경로.png)`(PNG/JPEG, 입력 .md 기준 상대 경로, 본문 폭 초과 시
   축소; 없으면 `[그림 누락: …]` 문단), 맨 앞 YAML 머리말(`title:`이 문서 제목),
   빈 줄 구분 문단. 인라인 `**굵게**`·`` `코드` ``는 별도 run으로 들어간다.
   이 밖의 문법은 일반 텍스트로 들어간다.
7. 편집 커맨드(replace/fill/set-cell/add-row/del-row/add-para 등)는 임시 파일에
   결과를 만들고 check를 통과했을 때만 결과 파일명을 준다. 실패하면 결과 파일은
   만들어지지 않고 `<이름>.rejected.hwpx`로 남으며(JSON `output: null`,
   `rejected_output`), 이 파일은 검토용일 뿐 사용자에게 전달하지 않는다. 레퍼런스가
   있는 작업(기관명 교체 등 전면 수정)은 guard --reference로 원문 잔재(forbid)·필수
   키워드(require)·글자 수 증가·구조 동일성(문단 수·표 모양·쪽나눔 수, 기본 경고,
   `--strict-structure`면 오류)까지 검사한 뒤 전달한다. 쪽수를 유지해야 하는
   양식·공문은 구조를 바꾸지 말고, 글자 수가 늘어 넘치면 공백을 지우거나 문장을
   잘라 맞추지 말고 사용자에게 알린다.
8. 병합 셀(rowSpan/colSpan)이 있는 표의 행 추가/삭제는 거부된다(EditError).
   이 경우 구조 한계를 사용자에게 알린다.
9. fill 워크플로우: ① `fill --analyze`로 타겟 키 확인 → ② 타겟 key에만 값을
   매핑한 values.json 작성 → ③ `fill --values` 실행 → `unmatched`와
   `verify_failed`가 비어야 완료(`verified`는 다시 읽어 값이 들어간 것을 확인한 키).
   타겟 종류: `label-cell`(라벨 오른쪽 빈 셀; `placement: below`면 머리글 행 아래 셀,
   `prefilled`가 있으면 안내문·기존 값이 있는 셀을 덮어씀, `field: true`면 셀 안
   누름틀에 값이 들어감), `checkbox`(□ 뒤 공백 허용), `paren`, `inline`(`라벨: 값`
   문단 — 해당 문단만 바꿈), `field`(본문 누름틀 — 이름 또는 안내문이 키).
   체크박스 값은 true/"예"/"☑" 등만 체크하고 false/"아니오"/""는 건너뛴다.
   체크박스/괄호는 리터럴 문자열 매칭이라 동일 리터럴이 여러 곳에 있으면 모두 함께
   바뀐다 — 유일한 리터럴인지 analyze --slots로 먼저 확인한다. 여러 섹션의 타겟도
   채워지며, 중첩 표 내부 셀만 타겟이 되지 않는다(`--cells`도 최상위 표 기준).
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
    references/owpml-format.md). fill을 제외한 편집 커맨드는 section0만 대상으로
    한다. `replace`는 머리말·꼬리말·각주·글상자·중첩 표 안의 문단까지 바꾸고,
    `extract`도 같은 범위를 읽는다(머리말은 `[머리말] …`, 각주는 `[각주] …` 줄로,
    중첩 표는 셀 안 `a | b`로, 병합 셀은 빈칸으로 채운 격자로).
13. .hwp는 사용자가 HWPX 변환을 명시적으로 요청한 경우에만 from-hwp로 변환한다.
    변환본은 별도 파일이며 원본 .hwp는 건드리지 않는다. 기본 python 엔진은 의존성이
    없다. 암호·배포용·DRM 문서는 `[hwp5-password|hwp5-distribution|hwp5-drm]`로 즉시
    실패하며 두 엔진 모두 읽을 수 없으니 한글에서 보호를 풀고 다시 저장하도록 안내한다.
14. lint는 게이트가 아니다. findings를 요약해 사용자에게 보여주고 수정 여부는
    사용자가 정한다(공문 표기 규칙은 references/gonmun-rules.md). 공문이면
    `--doc-type gonmun`으로 수신·발신명의·시행·공개 구분 유무까지, 개조식
    보고서면 `--doc-type bogo`로 서술형 종결어미를 함께 본다.
15. check가 `char-border-bug`를 보고하면 `fix-borders`로 수리한 뒤 다시 check한다.
    수리는 header.xml만 바꾸므로 본문은 그대로다. fix-borders는 header.xml을
    바꾸므로, 원본과 대조하는 `guard --reference`는 `entry-changed:
    Contents/header.xml`을 보고한다(서식 커맨드와 동일한 정상 동작).
16. check의 경고는 ok를 막지 않지만 사용자에게 알린다: `cell-overflow-risk`(추정),
    `table-taller-than-page`(글자처럼 취급한 표가 본문 높이를 넘어 아래 행이 잘림 —
    add-row로 표를 키웠을 때 특히 확인), `duplicate-id`, `secpr-incomplete`(startNum·
    visibility 없음). 오류로 막는 구조 규칙: secPr의 pagePr/margin 없음, 표의
    rowCnt/colCnt·sz/pos/여백·셀 주소/크기 누락, 빈 subList/ctrl, 누름틀 짝 불일치,
    그림·도형의 renderingInfo 없음, hp:t 안 탭 문자, lineseg textpos가 글자 수를
    넘는 오래된 캐시, manifest href 누락, secCnt 불일치. `cell-overflow-risk`는 추정이라 양식을 채울 때는
    `fill --analyze`가 알려주는 label-cell 타겟의 `capacity`(셀의 em 단위 수용량)를 보고,
    채울 값의 길이를 ASCII 0.5em·한글 1em으로 환산해 비교한다(경고는 환산값과 실제 문자 수를 함께 표시).
    넘칠 수밖에 없으면 사용자에게 알린다.
17. 문서 전체를 새 관점으로 재작성하는 작업(기관 교체 등)은 guard에
    `--max-unchanged-ratio 0.35`를 붙여 원문이 그대로 남지 않았는지 확인한다.
    guard는 `○○`, `{{...}}`, `<<>>`, `TODO`, `TBD`, `. . .` 같은 미완성 표시도
    기본 검사한다. 주의: 기본 placeholder 패턴의 `○○`는 한국 공문에서 흔한 익명화
    표기(`홍○○`, `○○부`)에도 걸리므로, 익명화가 포함된 문서를 검사할 때는
    `--no-default-placeholders`를 쓰거나 findings를 사람이 판단한다.
18. from-hwp 결과 JSON의 `engine`과 `report`를 읽고 전달한다.
    - `engine: python`(기본): `report.unconverted`(OWPML로 옮길 수 있으나 아직 변환하지 않는
      내용)·`report.dropped`(HWPX에 자리가 없는 데이터)가 비어 있지 않으면 종류와 개수를
      사용자에게 그대로 알린다(예: `memo-body 2` → 메모 본문 2건 누락). 비어 있으면
      글자·문단·테두리·글머리표·표 안의 표·그림·각주·쪽번호·줄바꿈이 모두 옮겨진 것이다.
    - `engine: rhwp`(python 엔진이 파일을 못 읽어 폴백, `fallback_reason` 동반):
      `report.known_losses`(표 안의 표·그림·각주, 글머리표 정의, 쪽번호·필드 컨트롤, 형광펜)를
      사용자에게 알리고, 중요한 문서면 한컴에서 원본과 육안 대조를 권한다.
    - 도형·OLE·수식·차트가 있는 문서는 어느 엔진이든 구조는 남아도 렌더링을 보장하지
      못하므로 한컴 육안 확인을 권한다.
19. 셀 값을 바꿀 때(set-cell/fill) 첫 문단의 글자가 가장 많은 run에 값이 들어가고
    같은 셀의 글자만 있는 나머지 문단은 제거된다(표·그림이 있는 문단은 유지). 셀
    안 줄바꿈은 값에 `\n`을 넣으면 된다. 셀에 누름틀이 있으면 누름틀 안에 값이
    들어가고 `dirty="1"`이 된다.
20. `new`는 요청 종류에 맞는 테마를 고른다: 보고서·계획서·제안서 → `report`, 공문·
    공고·협조문 → `gonmun`, 사내 문서·안내문·깔끔한 문서 → `modern`, 그 밖에는 `base`.
    마크다운에는 `-`와 `1.`만 쓴다 — 목록 기호(□ ○ - ·)와 번호 서식(1. 가. 1))은 테마가
    바꿔 주므로 본문에 직접 적으면 기호가 두 번 나온다. `report`에서 `##` 장 제목은
    번호 칩(Ⅰ·Ⅱ…)이 되므로 번호를 쓰려면 `## 1. 개요`처럼 제목 앞에 둔다.
    YAML 머리말 `subtitle:`·`author:`·`date:`는 제목 아래 줄로 들어간다. `header:`·`footer:`는
    머리말·꼬리말, `page_number: footer-center|header-right|none`은 쪽번호(report·gonmun 기본
    footer-center). `[글자](url)`은 하이퍼링크, `[^1]`+`[^1]: 내용` 줄은 각주가 된다.
21. 생성·편집 결과는 전달 전에 `render --png`로 한 번 보고(Read로 PNG 확인) 표가 좁거나
    제목 체계가 어긋나면 고친다. 렌더는 근사(줄바꿈·문단 테두리·각주 위치)이므로 "한컴에서
    이렇게 보인다"고 단정하지 말고, 구조 문제(표 폭, 여백, 빈 쪽, 목록 단계)만 판단한다.
    Node.js가 없으면 render는 건너뛰고 사용자에게 한컴 확인을 요청한다.

## 포맷 상세

references/owpml-format.md 참조 (단위: 1pt=100 HWPUNIT, A4 폭 59528, 본문폭 42520).
