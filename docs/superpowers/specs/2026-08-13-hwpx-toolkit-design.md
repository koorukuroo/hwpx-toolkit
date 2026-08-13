# hwpx-toolkit 설계 스펙

- 날짜: 2026-08-13
- 상태: 승인됨 (구현 계획 수립 전)
- 라이선스: MIT

## 1. 개요

한글(Hancom Office)의 개방형 문서 포맷 HWPX(.hwpx)를 생성·읽기·편집·검증하는
Claude 스킬. **코드는 전량 자체 구현(클린룸)**하여 MIT 단독 저작권으로 배포한다.

## 2. 클린룸 규칙 (법적 경계)

1. 외부 저장소의 **코드·XML 템플릿·픽스처 파일을 복사하지 않는다.**
2. OWPML 포맷 지식(KS X 6101 표준, 요소명, 속성, 단위계)은 표준 지식이므로 자유롭게 사용한다.
3. 외부 코드 반입은 MIT 등 허용 라이선스에 한하며, 반입 시 `THIRD_PARTY_NOTICES.md`에 고지한다.
   현재 계획된 유일한 외부 컴포넌트: HWP→HWPX 변환용 rhwp WASM 런타임(MIT, @rhwp/core).
4. 템플릿 HWPX/XML은 OWPML 스펙 기반으로 직접 작성하고 한컴오피스 열림 검증으로 확정한다.

## 3. 결정 사항 요약

| 항목 | 결정 |
|------|------|
| 코드 기반 | 완전 자체 구현 |
| 기능 범위 | 풍부한 기능 (단계적 달성) |
| 의존성 | 하이브리드 — 코어는 순수 stdlib, 선택 기능만 선택적 의존성 |
| HWP→HWPX | 자체 파서 없음. MIT 외부 도구(rhwp) 옵셔널 연동 |
| 구조 | 코어 라이브러리 + 얕은 단일 CLI |
| 라이선스 | MIT (저작권자 명의는 초기화 시 확정) |

## 4. 저장소 구조

```
hwpx-toolkit/
├─ SKILL.md               # 워크플로우 의사결정 트리 (LLM용 진입점)
├─ LICENSE                # MIT
├─ README.md
├─ THIRD_PARTY_NOTICES.md # rhwp 등 외부 MIT 컴포넌트 고지
├─ core/                  # 순수 stdlib (zipfile + xml.etree + re)
│   ├─ package.py         # HWPX ZIP 읽기/쓰기 — 원시 엔트리 복사로 바이트 보존
│   ├─ owpml.py           # OWPML 요소 빌더 (문단/런/표/secPr/이미지 XML 생성)
│   ├─ header.py          # header.xml 스타일 관리 (charPr/paraPr/borderFill 추가, itemCnt 보정)
│   ├─ edit.py            # 텍스트 치환(런 분할 대응)/셀 채우기/문단 추가 엔진
│   ├─ analyze.py         # 문서 구조 분석 (표/스타일/편집 슬롯 추출)
│   └─ guards.py          # 검증 게이트 (구조/레이아웃/내용/쪽수)
├─ scripts/
│   └─ hwpx.py            # 단일 CLI: python3 hwpx.py <subcommand>
├─ templates/             # 자체 제작 템플릿 (base → report/gonmun/minutes 오버레이)
├─ references/            # LLM용 포맷 문서 (자체 작성)
│   ├─ owpml-format.md    # OWPML 구조, HWPUNIT 단위계, 필수 규칙
│   └─ troubleshooting.md
├─ tests/                 # pytest + 자체 생성 픽스처
└─ vendor/                # (선택) rhwp WASM — MIT 라이선스 파일 동봉
```

## 5. 코어 모듈 설계

### core/package.py — 바이트 보존 패키지 IO

- HWPX ZIP을 읽고, **변경 대상 엔트리만 교체**하며 나머지 엔트리는 로컬 헤더·압축
  바이트·플래그·타임스탬프까지 원시 복사한다. `zipfile.writestr()` 전체 재작성 금지.
- mimetype은 항상 첫 엔트리 + STORED.
- unpack/pack 유틸 포함 (기본 바이트 보존; pretty-print는 검사 전용이며 재패킹 입력 금지 —
  `hp:t`는 mixed content라 pretty 공백이 본문으로 렌더링될 수 있음).

### core/owpml.py — 요소 빌더

- 문단/런/텍스트/표/셀/secPr/colPr/이미지/도형/각주/머리말 등 OWPML 조각을
  문자열로 생성하는 함수군. XML 특수문자 이스케이프, 고유 ID 발급 내장.
- 필수 규칙을 코드로 강제:
  - section 첫 문단 첫 런에 secPr + colPr 필수
  - 문단 id 고유성
  - 표: 열 너비 합 = 본문 폭(A4 기준 42520 HWPUNIT), cellAddr/cellSpan 정합성

### core/header.py — 스타일 관리

- header.xml 파싱 없이도 안전하게 charPr/paraPr/borderFill을 추가하고 itemCnt를 보정.
- 기존 스타일 복제-변형(예: 특정 문단만 굵게/색상) 패턴 지원 — 대상 외 문단 비영향.

### core/edit.py — 편집 엔진

- **replace**: 한컴이 문장을 여러 `<hp:t>`/런으로 쪼개 저장하는 경우 대응 —
  문단 단위로 텍스트를 이어붙여 매칭하고, 각 런의 charPrIDRef를 보존하며 교체.
- **fill**: 라벨-값 셀(라벨 오른쪽 셀 교체), 체크박스(□→☑), 괄호 빈칸, 좌표 지정
  (`--cells` 폴백). 라벨 매칭은 정규화 + 퍼지 매칭.
- **구조 편집**: add-para(기준 문단 복제), add-row(기존 행 XML 복제로 스타일 보존),
  add-col/del-row/merge-cells/set-cell. rowSpan/colSpan이 있는 표는 좌표 안전을 위해 거부.
- 수정된 문단의 `hp:linesegarray`(줄 배치 캐시)를 외과적으로 제거 — 미수정 문단 캐시는 보존.
- `hp:t` 내부 자식 컨트롤(`hp:fwSpace`, `hp:lineBreak` 등)은 절대 삭제하지 않는다.

### core/analyze.py — 분석

- 문서 구조 리포트: 페이지/여백, 스타일 목록(pt 환산), 표 구조(행×열/열너비/병합), 문단 텍스트.
- 편집 슬롯 추출: 컨테이너 문단(표/그림 포함)을 제외한 실제 텍스트 문단·셀을
  슬롯 키(JSON)로 노출 — LLM은 슬롯 키에 값만 매핑하면 된다.
- fill 타겟 분석: 채울 수 있는 라벨/체크박스/빈칸 목록을 JSON으로 출력.

### core/guards.py — 검증 게이트

- **validate**: ZIP/mimetype/XML well-formedness, 필수 파트 존재, ID 참조 정합성(itemCnt,
  charPrIDRef/paraPrIDRef/borderFillIDRef), secPr 무결성.
- **check (전달 전 필수 게이트)**: validate + 과거 사고 패턴 검출 —
  secPr 누락/비정상(손상 문서 대화상자), 한컴 미경유 의심(미리보기·줄배치 부재),
  charPr 다수의 SOLID 테두리 참조(글자 테두리 버그), 셀 textDirection 오변환.
- **guard (레퍼런스 대비)**: 비수정 엔트리 바이트 동일성, 문단/셀 글자 예산 기반
  쪽수 드리프트 추정, 원문 잔재/placeholder/필수 키워드 검사(require/forbid/forbid_regex).

## 6. CLI 서브커맨드

`python3 scripts/hwpx.py <command>` 단일 진입점. 출력은 JSON(기계 소비) 기본.

| 그룹 | 커맨드 | Phase |
|------|--------|-------|
| 읽기/분석 | `extract`, `analyze`, `unpack`, `pack` | 1 |
| 검증 | `validate`, `check`, `guard` | 1(validate)·3(check/guard) |
| 생성 | `new`(마크다운→HWPX), `build`(header+section 조립) | 2 |
| 편집 | `replace`, `fill`, `add-para`, `add-row`, `add-col`, `del-row`, `merge-cells`, `set-cell` | 3 |
| 서식 | `set-text-style`, `set-para-style`, `set-header`, `set-footer`, `set-pagenum`, `set-page`, `set-columns`, `page-break` | 3–4 |
| 개체 | `insert-image`, `resize-image`, `replace-image`, `insert-textbox`, `insert-shape`, `add-footnote`, `add-hyperlink`, `add-bookmark` | 4 |
| 변환 | `from-hwp` (rhwp 연동, Node 18+ 필요, 선택) | 5 |

## 7. SKILL.md 워크플로우 (LLM 진입점)

의사결정 트리로 시작:

```
사용자 요청
 ├─ "읽어줘/추출" → extract / analyze
 ├─ "새 문서 만들어줘" (마크다운/텍스트) → new
 ├─ "양식 빈칸 채워줘" → analyze(타겟) → fill → check
 ├─ "문구 바꿔줘" → replace → check
 ├─ "표/서식/개체 편집" → 해당 편집 커맨드 → check
 ├─ ".hwp 변환" → 사용자가 명시한 경우에만 from-hwp
 └─ 모든 산출물: 전달 전 check 필수 통과 (실패 시 전달 금지)
```

원칙:
- 사용자가 레퍼런스 HWPX를 제공하면 **보존 편집(replace/fill)이 기본**, 새로 그리는 build는 최후 수단.
- `.hwp` 입력은 자동 변환하지 않는다 — 사용자가 명시적으로 요청한 경우에만 from-hwp.
- check가 exit 0이 아니면 "완성했습니다"라고 보고하지 않는다.

## 8. 템플릿 전략

- **base**: OWPML 스펙 기반 최소 패키지(mimetype, META-INF, version.xml, settings.xml,
  content.hpf, header.xml, section0.xml)를 직접 작성. **한컴오피스에서 열림 검증 후 확정**
  (사용자의 한컴 환경 협조 1회 필요).
- **파생 템플릿**(report/gonmun/minutes): base 위에 스타일(charPr/paraPr/borderFill)
  오버레이로 자체 디자인. 스타일 ID 맵을 references/에 문서화.
- 외부 저장소의 템플릿 XML·에셋 HWPX는 사용하지 않는다.

## 9. 의존성 정책 (하이브리드)

| 계층 | 의존성 |
|------|--------|
| core/*, scripts/hwpx.py 기본 커맨드 | Python 3.9+ stdlib만 (zipfile, xml.etree, re, json, argparse) |
| from-hwp | Node.js 18+ + vendored rhwp WASM (MIT) — 미설치 시 커맨드만 비활성, 나머지 정상 동작 |
| 향후 선택 기능(차트 등) | 필요 시 개별 검토, 코어에 전이 금지 |

## 10. 테스트 전략

- pytest. 픽스처는 **자체 빌더로 생성** (외부 픽스처 복사 금지).
- 라운드트립: unpack→pack 바이트 동일성, 편집 후 비대상 엔트리 바이트 동일성.
- 각 편집 커맨드: 적용 결과 XML 어서션 + validate/check 통과.
- 한컴 실제 열림 테스트는 수동 선택 게이트(Windows/맥 한컴 환경에서).

## 11. 단계별 로드맵

| Phase | 내용 | 산출물 |
|-------|------|--------|
| 1 기반 | package.py, validate, extract, analyze, 테스트 하네스 | 읽기·검증 가능한 최소 스킬 |
| 2 생성 | base 템플릿(한컴 검증), owpml.py, new/build | 마크다운→HWPX |
| 3 편집 | edit.py(replace/fill/표), check/guard 게이트 | 양식 채우기·문서 수정 |
| 4 개체·고급 | 이미지/도형/각주/머리말·꼬리말/다단/페이지 설정 | 서식·개체 편집 |
| 5 확장 | from-hwp(rhwp), 공문서 작성법 lint, 추가 템플릿 | 변환·특화 기능 |

각 Phase는 독립적으로 배포 가능하며, 종료 시 SKILL.md의 해당 워크플로우 섹션을 갱신한다.

## 12. 비목표 (v1에서 하지 않는 것)

- HWP 5.0 바이너리 파서 자체 구현
- HTML→HWPX 범용 변환기
- 한컴독스(웹) 전용 호환성 보장 (데스크톱 한컴 기준)
- PyPI 패키징 (스킬 단독 이식성 우선; 추후 검토)
