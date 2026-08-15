# 한컴오피스 열림 검증 체크리스트 (Phase 2 게이트)

base 템플릿은 OWPML 스펙 기반 클린룸 작성물이다. 구조 검증(validate)만으로는
한컴 호환을 보장할 수 없으므로 아래 절차를 한컴이 설치된 환경에서 수행한다.
템플릿(scripts/dev/gen_base_template.py)을 수정할 때마다 재수행한다.
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

## Phase 4 추가 검증 항목 (구조 미확인 — 우선 확인 필요)

머리말·꼬리말·쪽번호는 실물 샘플 없이 표준 구조로 작성했다. 아래를 한 번 확인한다.

    python3 scripts/hwpx.py set-header 샘플.hwpx h.hwpx --text "대외비" --align center
    python3 scripts/hwpx.py set-pagenum h.hwpx hp.hwpx --where footer

- [ ] h.hwpx: 머리말 "대외비"가 각 쪽 상단 가운데에 보이는가
- [ ] hp.hwpx: 꼬리말에 쪽번호가 보이는가
- [ ] set-page --orientation landscape 산출물이 가로로 열리는가
- [ ] set-text-style --bold --color C00000 산출물의 대상 문단만 붉은 굵은 글씨인가

실패 시: 한컴에서 머리말을 넣고 저장한 .hwpx를 unpack해 `hp:header` 구조를
비교하고 `SectionEditor.set_header_footer`를 보정한다.

## 실패 시

- 대화상자 문구/증상을 기록해 이슈로 남긴다.
- 한컴에서 빈 문서를 .hwpx로 저장한 파일을 확보하면:
  unpack으로 header.xml/section0.xml 구조를 비교하고, 차이를
  scripts/dev/gen_base_template.py에 반영하거나, 스펙 §8의 헤지대로
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
