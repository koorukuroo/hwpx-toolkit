# 한컴오피스 열림 검증 체크리스트 (Phase 2 게이트)

base 템플릿은 OWPML 스펙 기반 클린룸 작성물이다. 구조 검증(validate)만으로는
한컴 호환을 보장할 수 없으므로 아래 절차를 한컴이 설치된 환경에서 수행한다.
템플릿(scripts/dev/gen_templates.py)을 수정할 때마다 재수행한다.
현재 상태는 하단 '검증 기록' 참조.

## 검증 절차

1. `python3 scripts/hwpx.py new samples/verify.md -o verify.hwpx` 로 생성
   (samples/verify.md: 제목 + 본문 + 불릿 + 순서목록 + 3x2 표를 포함할 것)
2. 한컴오피스(한글)에서 verify.hwpx를 연다.
3. 확인 항목:
   - [ ] 경고/복구 대화상자 없이 열리는가
   - [ ] 제목이 18pt 굵은 돋움으로 보이는가
   - [ ] 본문이 10pt 바탕, 양쪽 정렬로 보이는가
   - [ ] 표의 테두리와 헤더 행 회색 배경이 보이는가
   - [ ] 편집(타이핑) 후 저장이 정상 동작하는가
4. 편집 후 저장한 파일을 `python3 scripts/hwpx.py validate verify.hwpx`로 재검증한다.

## Phase 4 추가 검증 항목

머리말·꼬리말·쪽번호·charPr 순서는 2026-08-16에 한컴이 생성한 실물 hwpx 2건과
구조 대조 완료(하단 '검증 기록' 참조) — charPr 순서 반전, autoNum의 hp:ctrl
누락 등을 발견해 수정했다. 아래 항목은 여전히 한컴오피스에서 육안으로
직접 확인이 필요하다(실물 대조는 XML 구조 비교이지 렌더링 확인이 아님).

    python3 scripts/hwpx.py set-header 샘플.hwpx h.hwpx --text "대외비" --align center
    python3 scripts/hwpx.py set-pagenum h.hwpx hp.hwpx --where footer

- [x] h.hwpx: 머리말 "대외비"가 각 쪽 상단 가운데에 보이는가  (2026-08-17 확인)
- [x] hp.hwpx: 꼬리말에 쪽번호가 보이는가  (2026-08-17 확인)
- [x] set-page --orientation landscape 산출물이 가로로 열리는가  (2026-08-17 수정 후 확인)
- [x] set-text-style --bold --color C00000 산출물의 대상 문단만 붉은 굵은 글씨인가  (2026-08-17 확인)

실패 시: 한컴에서 머리말을 넣고 저장한 .hwpx를 unpack해 `hp:header` 구조를
비교하고 `SectionEditor.set_header_footer`를 보정한다.

## 실패 시

- 대화상자 문구/증상을 기록해 이슈로 남긴다.
- 한컴에서 빈 문서를 .hwpx로 저장한 파일을 확보하면:
  unpack으로 header.xml/section0.xml 구조를 비교하고, 차이를
  scripts/dev/gen_templates.py에 반영하거나, 스펙 §8의 헤지대로
  한컴 저장본을 새 base 템플릿으로 채택한다 (secPr 추출 구조라
  코드 변경 불필요).

## 검증 기록

### 2026-08-15 — 편집 경로 실물 검증 (통과)

- 입력: 중소벤처기업부 공고 제2023-221호 (.hwp 5.x, 문단 343·표 43·charPr 325) → rhwp 변환 HWPX
- 툴킷 결과: validate/check 통과, extract 275줄, `replace` 3건(run 분할 포함), 비섹션 엔트리 11/11 바이트 동일, 줄배치 캐시 수정 문단만 제거, guard 통과
- **한컴오피스 열림: 변환본·편집본 모두 경고 없이 정상** (사용자 확인)
- 결론: 편집 경로(ET 재직렬화, 미사용 xmlns 선언 축소 포함)는 한컴 호환 확인됨
- 발견: `fill --analyze`가 공문 항목 머리표 `□ 사업목적`을 체크박스로 오탐(38건) — Phase 4에서 휴리스틱 보강

### 2026-08-16 — 생성 경로 실물 검증 (통과)

- `new`로 마크다운(제목 2단계·불릿·순서목록·3×3 표) → 툴킷생성테스트.hwpx 생성, validate 통과
- **한컴오피스 열림: 경고 없이 정상, 제목/본문/표 서식 확인** (사용자 확인)
- 결론: 자체 제작 base 템플릿(OWPML 스펙 기반 클린룸)은 한컴 호환 확인됨. Phase 1~3 전 경로 실물 검증 완료

### 2026-08-16 — Phase 4 구조 실물 대조 (한컴 저작 hwpx 2건, 최종 리뷰)

- 대조 표본: 한컴에서 직접 작성·저장한 hwpx 2건 (한컴에서 직접 작성·저장한 로컬 표본, 읽기 전용)
- 방법: unzip 후 header.xml/section0.xml을 툴킷 산출물과 XML 구조 직접 비교(렌더링 확인 아님)
- **발견 1**: `hh:charPr` 자식 순서가 실물은 `offset, italic, bold, underline, strikeout,
  outline, shadow`인데 툴킷은 `offset, bold, italic`로 반전되어 있었음 → `core/header.py`
  `_CHARPR_TAG_ORDER` 수정
- **발견 2**: 실물 쪽번호는 `hp:run > hp:ctrl > hp:autoNum > hp:autoNumFormat`이고 ctrl
  뒤에 빈 `hp:t`가 오는데, 툴킷은 `hp:autoNum`을 `hp:ctrl` 없이 run 바로 밑에 붙이고
  있었음 → `core/edit.py` `set_page_number` 수정. `hp:header`/`hp:footer`의 `id`도
  실물은 `"0"`인데 툴킷은 `""`이었음 → 수정
- **발견 3**: `set_header_footer`/`set_page_number`가 실제로 수정한 헤더/꼬리말 하위
  문단(hp) 대신 섹션 첫 문단(p0)만 마킹해 stale `hp:linesegarray`가 남는 경로 → 수정
- **발견 4**: `remove_header_footer`가 p0의 첫 run만 검사해, 다른 문단으로 옮겨진(또는
  한컴이 그렇게 저장한) header/footer ctrl은 못 찾고 지나쳤음 → 섹션 전체(root.iter)로
  탐색하도록 수정
- 결론: Phase 4 머리말·꼬리말·쪽번호·서식 구조는 한컴 실물과 구조적으로 일치 확인.
  렌더링(육안) 확인은 여전히 미완 — 위 체크리스트 항목 참조

### 2026-08-17 — Phase 4 육안 검증 (한컴오피스, 사용자 확인)

- Phase 4 체크리스트 항목 중 머리말·쪽번호·서식(굵게/색상)·이미지·report 템플릿
  섹션 바 등 9개는 한컴오피스에서 정상 렌더링 확인, 통과
- `set-page --orientation landscape`만 실패: 산출물이 한컴에서 **세로**로 열림
- 원인: `hp:pagePr@landscape`는 90° 회전 플래그이고 폭/높이 스왑도 별도의
  회전이라, 기존 코드가 landscape 속성을 NARROWLY로 바꾸면서 치수까지 스왑해
  회전을 이중 적용 → 상쇄되어 의도와 반대 방향으로 렌더링됨
- 수정: landscape 속성은 건드리지 않고, (landscape 속성) XOR (폭>높이)로 현재
  방향을 판정한 뒤 요청된 방향과 다를 때만 치수를 스왑하도록 변경
  (`core/edit.py` `set_page`). 상세 XOR 표는 `references/owpml-format.md`
  "페이지 방향" 절 참조
- 결론: Phase 4 항목은 이제 전부 실물 확인 완료

## Phase 5 추가 검증 항목

- [x] `new --template report` 산출물: 제목 16pt 굵게, `##` 절 제목이 진남색 바 위 흰 글자로 보이는가  (2026-08-17 확인)
- [x] `from-hwp` 산출물이 원본 .hwp와 동일한 내용/서식으로 열리는가 (rhwp 품질)  (2026-08-17 확인)

### 2026-08-17 — Phase 4·5 실물 검증 완료

- 검증 세트 10건(기준문서·머리말·쪽번호·가로방향·글자서식·문단서식·이미지·report 템플릿·다단+셀병합·from-hwp 변환본)을 한컴오피스에서 육안 확인.
- 결과: 9건 즉시 통과. `set-page --orientation landscape`만 세로로 열려 실패.
- 원인: `hp:pagePr@landscape`(90° 회전 플래그)와 폭·높이 교환을 **둘 다** 적용해 회전이 상쇄됨.
  네 조합을 한컴에서 대조해 실제 방향이 두 요소의 XOR임을 확인(표는 references/owpml-format.md).
- 수정 후 재확인 통과 — **Phase 1~6의 생성·편집·서식·개체·변환 경로가 모두 한컴에서 검증됨.**

## 2026-10-14 — from-hwp 엔진 교체 (한컴 육안 확인 대기)

- 변경: 기본 엔진을 rhwp(WASM)에서 python-hwpx 6.8.0 HWP5 리더의 stdlib 포팅본
  (`vendor/pyhwpx_hwp5`)으로 교체. rhwp는 python 엔진이 읽지 못할 때만 폴백하며,
  폴백 시 `getPageDef`로 원본 용지 설정을 되돌려 쓴다.
- 근거(실물 .hwp 11건 비교, 원본 DocInfo 레코드 수 기준): rhwp는 ① 용지 여백을 기본값
  (좌우 8504·위 5668)으로 내보내고 ② 글머리표 정의(hh:bullet)를 버리며 ③ 표 안에 중첩된
  표·그림·각주·OLE·단 설정, 쪽번호·필드 컨트롤, 셀 안 줄바꿈, 형광펜을 버렸다.
  python 엔진은 11건 모두 `unconverted`/`dropped` 없이(1건 `label-item 2`) 변환했고,
  `check` 통과·`replace`/`set-cell` 편집 경로 동작을 확인했다.
- [ ] python 엔진 변환본(표 안의 그림·각주 포함 보고서, 글머리표 공문)이 한컴에서
      원본과 같은 모습으로 열리는가 — 사용자 육안 확인 필요.
- [ ] rhwp 폴백 변환본의 용지 설정 복원이 한컴에서 원본 쪽수와 일치하는가.

## 2026-10-15 — 편집 신뢰성·열기 안전 규칙·생성 기능 확장 (한컴 육안 확인 대기)

- 변경(버그): `replace`/`set-cell`/`fill`이 `<hp:t>` 안 `<hp:lineBreak/>`·`<hp:tab/>` 뒤의
  글자(tail)를 읽지 못해 교체를 놓치고 셀에 옛 글자가 남던 문제를 고쳤다(`core/text.py`
  텍스트 모델). 값의 `\t`·`\n`은 `<hp:tab/>`·`<hp:lineBreak/>` 요소로 쓴다.
- 변경(게이트): check가 한컴 열기 안전 구조 규칙(표·셀 필수 요소, secPr pagePr/margin,
  누름틀 짝, lineseg 캐시 등)을 오류로 막는다. 실물 한컴 저장본 10건과
  python 엔진 변환본 11건으로 오탐이 없음을 확인했다(실물의 `id="2147483648"` 반복 문단,
  `cellSz height="0"`, `<hp:tab/>` 요소는 정상으로 취급).
- 변경(산출): 편집 커맨드는 임시 파일 → check → 통과 시에만 결과 파일명으로 승격.
- 변경(생성): 마크다운 굵게/코드 run, 3단계 목록, 인용, 코드 블록, `---` 쪽나눔, 그림,
  한컴 표준 스타일 23종. `set-cell-style`(셀 배경·테두리) 추가.
- [ ] `set-cell`로 줄바꿈(`\n`)·탭(`\t`)이 든 값을 넣은 셀이 한컴에서 줄바꿈·탭으로 보이는가.
- [ ] 누름틀(CLICK_HERE)이 있는 양식을 `fill`로 채운 결과가 한컴에서 값으로(안내문이 아니라)
      보이고 인쇄되는가 (`dirty="1"` 계약).
- [ ] `new`로 만든 문서의 **굵게**/`코드` run, 2·3단계 목록 들여쓰기, 인용, 코드 블록,
      `---` 쪽 나눔, 그림(`BinData/image1.png`)이 한컴에서 의도대로 보이는가.
- [ ] 한컴 스타일 목록에 23종(바탕글…캡션)이 보이는가.
- [ ] `set-cell-style --bg E6E6E6 --border solid` 셀이 회색 배경·실선으로 보이는가.
- [ ] `add-row`로 그림이 든 행을 복제한 문서(그림 id/instid 재번호)가 한컴에서 열리는가.
