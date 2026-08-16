# hwpx-toolkit

한글(한컴오피스) **HWPX 문서를 읽고, 만들고, 고치고, 검증하는** MIT 라이선스 도구 모음이자 Claude 스킬입니다.

- **의존성 없음** — 코어와 CLI는 Python 3.9+ 표준 라이브러리만 사용합니다 (`pip install` 불필요). HWP→HWPX 변환(`from-hwp`)만 Node.js 18+가 필요한 선택 기능입니다.
- **원본 보존 편집** — 문서를 고칠 때 변경된 XML 파트만 교체하고, 나머지 ZIP 엔트리는 **바이트 단위로 동일**하게 유지합니다. 이미지·글꼴·스타일이 재저장으로 손상되지 않습니다.
- **전달 전 검증 게이트** — 모든 편집 커맨드가 `check`를 자동 실행합니다. 구조 오류나 한컴에서 문제를 일으키는 알려진 패턴이 발견되면 종료 코드 2로 실패합니다.
- **실물 검증** — 실제 정부 공고문(.hwp 변환본)과 한컴이 저장한 문서로 구조를 대조하며 만들었고, 생성·편집 산출물이 한컴오피스에서 열리는 것을 확인했습니다.

```bash
# 마크다운 한 장을 한글 문서로
python3 scripts/hwpx.py new 보고서.md -o 보고서.hwpx

# 받은 양식의 빈칸 채우기
python3 scripts/hwpx.py fill 신청서.hwpx --analyze          # 채울 곳 확인
python3 scripts/hwpx.py fill 신청서.hwpx 제출.hwpx --values values.json

# .hwp를 HWPX로 변환하고 내용 검수
python3 scripts/hwpx.py from-hwp 공고문.hwp -o 공고문.hwpx
python3 scripts/hwpx.py lint 공고문.hwpx
```

---

## 설치

저장소를 받은 뒤 바로 실행할 수 있습니다.

```bash
git clone <이 저장소> hwpx-toolkit
cd hwpx-toolkit
python3 scripts/hwpx.py validate 아무문서.hwpx      # 동작 확인
```

**Claude 스킬로 등록**하려면 스킬 디렉터리에 연결합니다.

```bash
ln -s "$(pwd)" ~/.claude/skills/hwpx-toolkit
```

`SKILL.md`가 진입점이며, 어떤 요청에 어떤 커맨드를 쓸지에 대한 의사결정 트리와 필수 규칙이 담겨 있습니다.

**선택 사항** — `from-hwp`(HWP 5.x 바이너리 변환)를 쓰려면 Node.js 18+가 필요합니다. 변환 런타임(@rhwp/core WASM, MIT)은 `vendor/rhwp/`에 동봉되어 있어 추가 설치는 없습니다.

---

## 커맨드

모든 커맨드는 결과를 JSON으로 출력합니다(`extract` 제외). 실패 시 `{"ok": false, "error": ...}`와 종료 코드 2를 반환합니다.

### 읽기·분석

| 커맨드 | 설명 |
|--------|------|
| `extract <file> [--format text\|markdown]` | 본문 텍스트 추출. 표는 마크다운 표로 변환 가능 |
| `analyze <file> [--slots]` | 페이지 설정·스타일 수·표 구조 리포트. `--slots`는 편집 가능한 문단/셀 목록 |
| `validate <file>` | ZIP·XML 구조와 ID 참조 정합성 검증 |
| `check <file>` | **전달 전 필수 게이트** — validate + 한컴 사고 패턴(글자 테두리 버그, 세로쓰기 오변환, 깨진 이미지 참조) 검출 |
| `guard <out> --reference <원본> [--rules r.json] [--max-growth 1.1]` | 원본 대비 검사 — 비변경 엔트리 바이트 동일, 필수/금지 키워드, 글자 수 증가(쪽수 드리프트) |
| `unpack <file> <dir>` / `pack <dir> <out> [--source 원본]` | ZIP 해체·재조립 (XML 직접 수정용, `--source`로 바이트 보존) |

### 생성

| 커맨드 | 설명 |
|--------|------|
| `new <input.md> -o <out> [--template base\|report] [--title 제목]` | 마크다운 → HWPX. 제목·불릿·번호목록·GitHub 표 지원 |
| `build --section <sec.xml> -o <out> [--template] [--title]` | section0.xml을 직접 써서 조립 |
| `from-hwp <input.hwp> -o <out>` | HWP 5.x 바이너리 → HWPX (Node.js 18+ 필요) |

### 편집 — 텍스트·양식

| 커맨드 | 설명 |
|--------|------|
| `replace <src> <dst> --map map.json` | 문구 교체. 한컴이 한 문장을 여러 조각으로 나눠 저장해도 매칭합니다 |
| `fill <src> --analyze` | 채울 수 있는 항목(라벨-값 셀, 체크박스, 괄호 빈칸) 목록 |
| `fill <src> <dst> --values v.json [--cells c.json]` | 양식 채우기. 라벨은 공백·괄호를 무시하고 매칭 |
| `add-para <src> <dst> --after "기준 문구" --text "새 문단"` | 기준 문단 뒤에 문단 추가(스타일 상속) |

### 편집 — 표

| 커맨드 | 설명 |
|--------|------|
| `set-cell <src> <dst> --table N --row R --col C --text T` | 셀 텍스트 설정 |
| `add-row <src> <dst> --table N --cells cells.json` | 행 추가(마지막 행 복제로 스타일 유지) |
| `add-col <src> <dst> --table N --cells cells.json [--at K]` | 열 추가 |
| `del-row <src> <dst> --table N --row R` | 행 삭제 |
| `merge-cells <src> <dst> --table N --row R --col C --row2 R2 --col2 C2` | 사각 범위 셀 병합 |

### 편집 — 서식·개체

| 커맨드 | 설명 |
|--------|------|
| `set-text-style <src> <dst> [--after 문구\|--para N] [--bold] [--italic] [--underline] [--color RRGGBB] [--size PT]` | 대상 문단의 글자 서식 |
| `set-para-style <src> <dst> [--after\|--para] [--align left\|center\|right\|justify] [--line-spacing N]` | 대상 문단의 정렬·줄간격 |
| `set-page <src> <dst> [--orientation portrait\|landscape] [--size a4\|a3\|b5\|letter] [--margin-mm N]` | 용지·방향·여백 |
| `set-columns <src> <dst> --count N [--gap-mm N]` / `page-break <src> <dst> --after 문구 [--off]` | 다단 / 쪽 나누기 |
| `set-header` · `set-footer <src> <dst> --text T [--align]` / `remove-header` · `remove-footer` | 머리말·꼬리말 |
| `set-pagenum <src> <dst> [--where header\|footer] [--align]` | 자동 쪽번호 |
| `insert-image <src> <dst> --image f.png [--after\|--para] [--width-mm] [--height-mm]` | 이미지 삽입 (PNG/JPEG) |
| `list-images <file>` / `resize-image` / `replace-image` / `delete-image` (`--index N`) | 이미지 목록·크기·교체·삭제 |

### 검수

| 커맨드 | 설명 |
|--------|------|
| `lint <file>` | 공문서 표기 검수 — 날짜·시간·금액 표기, 붙임·`끝.`, 항목 기호 체계, 쌍점 띄어쓰기. **안내용이며 종료 코드를 바꾸지 않습니다**(파일 오류만 exit 2) |

---

## 자주 쓰는 흐름

### 마크다운으로 보고서 만들기

```bash
python3 scripts/hwpx.py new 사업계획.md -o 사업계획.hwpx --template report
```

`report` 템플릿은 16pt 제목과 진남색 섹션 바를 씁니다(`##` 제목이 바로 렌더링됨). 일반 문서는 `--template base`(기본값)를 씁니다. 지원 문법은 `#`~`######` 제목, `-`/`*` 불릿, `1.` 번호 목록, GitHub 표, 빈 줄로 나뉘는 문단입니다. `**강조**`와 백틱은 마커만 제거되어 일반 텍스트로 들어갑니다.

### 받은 양식 채우기

```bash
# 1) 채울 항목 확인
python3 scripts/hwpx.py fill 신청서.hwpx --analyze
# → {"targets": [{"key": "성명", "kind": "label-cell", ...}, {"key": "동의", "kind": "checkbox", ...}]}

# 2) key에 값만 매핑
echo '{"성명": "홍길동", "연락처": "010-1234-5678", "동의": true}' > values.json

# 3) 채우고 검증
python3 scripts/hwpx.py fill 신청서.hwpx 제출.hwpx --values values.json
python3 scripts/hwpx.py guard 제출.hwpx --reference 신청서.hwpx
```

출력의 `unmatched`가 비어 있어야 완료입니다. 남아 있으면 `--analyze`가 알려준 key와 철자를 맞춰 다시 실행합니다.

### 기존 문서의 문구 바꾸기

```bash
echo '{"2025년도": "2026년도", "○○기관": "코어닷투데이"}' > map.json
python3 scripts/hwpx.py replace 원본.hwpx 결과.hwpx --map map.json

# 원문 잔재·필수 키워드·분량 증가까지 확인
echo '{"require": ["코어닷투데이"], "forbid": ["○○기관"]}' > rules.json
python3 scripts/hwpx.py guard 결과.hwpx --reference 원본.hwpx --rules rules.json
```

### 받은 .hwp 다루기

```bash
python3 scripts/hwpx.py from-hwp 공고문.hwp -o 공고문.hwpx   # 원본은 그대로 둡니다
python3 scripts/hwpx.py extract 공고문.hwpx                  # 내용 확인
python3 scripts/hwpx.py lint 공고문.hwpx                     # 표기 검수
```

`.hwp` 원본을 직접 읽거나 고치지는 않습니다. 변환은 사용자가 명시적으로 요청할 때만 수행하며, 결과는 항상 별도 `.hwpx` 파일입니다.

---

## 설계 원칙

**바이트 보존.** 편집은 ZIP을 통째로 다시 쓰지 않습니다. 변경된 XML 파트만 교체하고 나머지 엔트리는 로컬 헤더와 압축 바이트까지 원본 그대로 복사합니다. `guard --reference`로 이를 검사할 수 있고, 아무것도 고치지 않은 재작성은 원본과 완전히 동일한 파일을 만듭니다.

**게이트 우선.** XML이 유효해도 한컴이 문서를 못 여는 경우가 있습니다. `check`는 구조 검증에 더해 실제로 겪었던 사고 패턴(줄 배치 캐시 불일치로 인한 손상 경고, 글자마다 테두리가 생기는 charPr 버그, 세로쓰기 오변환, 매니페스트와 어긋난 이미지 참조)을 잡아냅니다. 편집 커맨드는 이 게이트를 자동으로 통과해야 결과를 내놓습니다.

**클린룸.** 모든 코드는 OWPML(KS X 6101) 표준과 실제 한컴 문서 관찰을 근거로 직접 작성했습니다. 유일한 외부 컴포넌트는 HWP 변환용 @rhwp/core(MIT)이며 `vendor/rhwp/`에 라이선스와 함께 동봉하고 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 고지했습니다.

**템플릿은 생성기로만.** `templates/`의 파일은 손으로 고치지 않습니다. `scripts/dev/gen_templates.py`를 수정해 재실행하며, 테스트가 생성 결과의 재현성을 확인합니다.

---

## 알려진 한계 (v1)

- 편집은 **첫 번째 섹션**(`Contents/section0.xml`)만 대상으로 합니다. 다중 섹션 문서의 나머지 섹션은 읽기·분석만 가능합니다.
- **병합 셀이 있는 표**는 좌표 계산의 안전을 위해 행·열 추가/삭제를 거부합니다.
- 표 안에 중첩된 표의 셀은 편집 대상으로 지정할 수 없습니다.
- `replace`와 체크박스·괄호 채우기는 문자열 단위라, 같은 문구가 여러 곳에 있으면 모두 바뀝니다.
- 이미지는 PNG와 JPEG만 지원합니다.
- 각주·미주·하이퍼링크·책갈피·도형·차트는 아직 지원하지 않습니다.
- `lint`는 안내 도구입니다. 규칙은 행정업무운영 편람의 표기 원칙을 정리한 것이며(`references/gonmun-rules.md`), 판단은 사용자가 합니다.

---

## 개발

```bash
python3 -m pytest tests/ -v          # 163개 테스트
python3 scripts/dev/gen_templates.py # 템플릿 재생성 (base, report)
```

HWP 변환 통합 테스트는 Node.js가 없으면 건너뜁니다. 실제 `.hwp` 파일로 검증하려면:

```bash
HWPX_TEST_HWP=/경로/샘플.hwp python3 -m pytest tests/test_convert.py -v
```

### 문서

| 파일 | 내용 |
|------|------|
| [SKILL.md](SKILL.md) | Claude 스킬 진입점 — 워크플로우 의사결정 트리와 필수 규칙 |
| [references/owpml-format.md](references/owpml-format.md) | OWPML 패키지 구조, 네임스페이스, HWPUNIT 단위, 필수 불변식 |
| [references/base-template-styles.md](references/base-template-styles.md) | 템플릿 스타일 ID 맵 (charPr/paraPr/borderFill) |
| [references/gonmun-rules.md](references/gonmun-rules.md) | 공문서 검수 규칙 |
| [docs/hancom-verification.md](docs/hancom-verification.md) | 한컴오피스 실물 검증 절차와 기록 |
| `docs/superpowers/specs/`, `docs/superpowers/plans/` | 설계 스펙과 단계별 구현 계획 |

### 구조

```
core/           # 순수 stdlib 코어
  package.py    #   ZIP 패키지 IO (바이트 보존 교체)
  owpml.py      #   OWPML 요소 빌더
  markdown.py   #   마크다운 파서·렌더러
  edit.py       #   섹션 편집 엔진
  header.py     #   스타일(charPr/paraPr) 복제·추가
  images.py     #   이미지 판독·hp:pic 생성
  analyze.py    #   텍스트 추출·구조 분석·양식 타겟 탐지
  fill.py       #   양식 채우기
  guards.py     #   validate / check / guard
  lint.py       #   공문서 표기 검수
  convert.py    #   HWP→HWPX (Node 서브프로세스)
scripts/hwpx.py # 단일 CLI 진입점
templates/      # base, report (생성기 산출물)
vendor/rhwp/    # @rhwp/core WASM (MIT)
```

---

## 라이선스

MIT — [LICENSE](LICENSE) 참조. 외부 컴포넌트는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 참조하세요.
