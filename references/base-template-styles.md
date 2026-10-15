# 테마 템플릿 스타일 ID 맵

`templates/base`, `gonmun`, `report`, `modern` 네 테마는 **같은 ID 배치**를 쓴다.
테마는 값(글꼴·크기·색·선·목록 기호)만 다르고, 렌더러(`core/owpml.py`,
`core/markdown.py`)는 `templates/<테마>/styles.json`의 ID만 읽는다.
값은 `scripts/dev/gen_templates.py`의 `THEMES` 표가 결정한다.

## 공통 ID 배치

| 종류 | ID | 용도 |
|------|----|------|
| font | 0 / 1 / 2 | 본문 글꼴 / 제목 글꼴 / 코드 글꼴(함초롬돋움) |
| borderFill | 1 | 테두리 없음 (페이지 보더용) |
| borderFill | 2 | 테두리 없음 (charPr/paraPr 참조용, 칩의 빈 칸) |
| borderFill | 3 | 표 본문 셀 — 4면 보통 선 |
| borderFill | 4 | 표 머리글 셀 — 4면 보통 선 + 머리글 배경 |
| borderFill | 5 | 포인트색 배경, 선 없음 — 장 제목 칩의 번호 칸 |
| borderFill | 6 | `##` 제목 아래 선 — 1칸 표의 셀 아래 테두리 (`h2_rule`; 테마에 선이 없으면 빈 정의) |
| borderFill | 7 | `#` 제목 아래 선 — 1칸 표의 셀 아래 테두리 (`title_rule`) |
| borderFill | 8 | 칩 제목 칸 — 아래쪽 굵은 선만 |
| borderFill | 9 | 머리글 셀 + 위쪽 굵은 선 (표 `outer: top-bottom`의 첫 행) |
| borderFill | 10 | 본문 셀 + 아래쪽 굵은 선 (마지막 행) |
| borderFill | 11 | 머리글 셀 + 위·아래 굵은 선 (한 행짜리 표) |
| charPr | 0 | 본문 |
| charPr | 1 | `#` 문서 제목 (제목 글꼴, 굵게, 테마 제목색) |
| charPr | 2 | `##` 장 제목 |
| charPr | 3 | `###` 이하 절 제목 |
| charPr | 4 | 표 머리글 (제목 글꼴, 굵게) |
| charPr | 5 | 본문 `**굵게**` (`bold_char`) |
| charPr | 6 | `` `코드` ``·코드 블록 (`code_char`, 본문보다 2pt 작게) |
| charPr | 7 | 표 본문 셀 (`table.cell_char`) |
| charPr | 8 | 포인트색 위 흰 글자 — 칩 번호 |
| charPr | 9 | 캡션 (회색, 본문보다 2pt 작게) |
| charPr | 10 | 부제·작성자·날짜 줄 (회색) |
| charPr | 11 | 하이퍼링크 글자 (파랑 0563C1, 밑줄) (`link_char`) |
| paraPr | 0 | 본문 (테마 정렬·줄간격·문단 뒤 간격) |
| paraPr | 1 | `#` 제목 (선 없는 테마에서 문단으로 씀) |
| paraPr | 2 | `##` 제목 (선 없는 테마에서 문단으로 씀) |
| paraPr | 3 | `###` 이하 |
| paraPr | 4 | 목록 1단계 — 내어쓰기 (left = hang, intent = −hang) |
| paraPr | 5 | 표 셀 가운데 130% |
| paraPr | 6 / 7 | 목록 2 / 3단계 (left = 2·hang / 3·hang) |
| paraPr | 8 | 인용 (좌우 여백, 150%) |
| paraPr | 9 | 코드 블록 (왼쪽, 130%) |
| paraPr | 10 | 표 셀 왼쪽 130% (긴 글이 있는 열) |
| paraPr | 11 | 캡션 (가운데) |
| paraPr | 12 | 부제 줄 |
| style | 0–22 | 한컴 표준 23종: 바탕글, 본문, 개요 1~10, 쪽 번호, 줄 번호, 머리말, 각주, 미주, 메모, 차례 제목, 차례 1~3, 캡션 (모두 paraPr 0 + charPr 0) |

hang(내어쓰기 폭) = 본문 크기 × 1.3.

## styles.json 키

`heading.{1,2,default}` = [charPr, paraPr], `body`, `bullet_levels` (paraPr 4/6/7),
`bullets` (단계별 기호), `ordered` (단계별 번호 서식: `{n}` 숫자, `{ga}` 가나다),
`table.{header_char, header_border, body_border, cell_para, cell_char, cell_para_left,
header_border_top, body_border_bottom, header_border_both, outer, row_height}`,
`bold_char`, `code_char`, `link_char`, `quote_para`, `code_para`, `caption`, `subtitle`,
`page_number` (테마 기본 쪽번호: `footer-center` 또는 `none`),
`section_chip` (report만: `num_char`, `num_border`, `title_char`, `title_border`,
`numbering: roman`), `title_rule` / `h2_rule` (선이 있는 제목: `border`, `char`, `para`,
`prev`, `next` — `core.owpml.rule_heading`이 1×1 표로 그린다).

선이 있는 제목을 문단 테두리(hh:border)로 그리지 않는 이유: 한글은 문단 아래 간격까지
테두리 안에 넣어 선이 다음 문단 바로 위에 붙는다(2026-10-15 한컴 확인). 셀 아래 테두리는
글자 바로 아래에 그어진다.

## 테마별 값

| | base | gonmun | report | modern |
|---|---|---|---|---|
| 본문 글꼴 / 제목 글꼴 | 함초롬바탕 / 함초롬돋움 | 휴먼명조 / HY헤드라인M | 휴먼명조 / HY헤드라인M | 맑은 고딕 / 맑은 고딕 |
| 본문 | 11pt 160% 양쪽, 뒤 2pt | 15pt 160% 양쪽, 뒤 0 | 15pt 160% 양쪽, 뒤 2pt | 11pt 170% 왼쪽, 뒤 3pt |
| `#` 제목 | 20pt 가운데 남색 | 20pt 가운데 검정 | 22pt 가운데 남색 + 0.4mm 남색 밑선 | 24pt 왼쪽 + 0.3mm 파란 밑선 |
| `##` 제목 | 14pt 남색 + 0.12mm 회색 밑선 | 15pt 굵게(본문 글꼴) | Ⅰ·Ⅱ 번호 칩 (남색 칸 + 0.4mm 밑선), 16pt | 14pt 파랑 |
| `###` | 12pt | 15pt(본문 글꼴) | 15pt(본문 글꼴) | 12pt |
| 포인트색 | 1F3864 | 000000 | 1F3864 | 256EF4 |
| 표 머리글 배경 / 머리글·셀 크기 | F2F2F2 / 10.5·10pt | 없음 / 12·12pt | DFE6F7 / 12·12pt | F4F5F6 / 10.5·10pt |
| 표 선 / 굵은 선 / outer | 7F7F7F 0.12 / 검정 0.4 / top-bottom | 검정 0.12 / 검정 0.4 / top-bottom | 검정 0.12 / 남색 0.4 / top-bottom | B1B8BE 0.12 / — / none |
| 표 안 글꼴 | 제목 글꼴(돋움) — 모든 테마 공통 (`cell_face`) | | | |
| 목록 기호 | • - · | □ ○ - · | □ ○ - · | • – · |
| 번호 서식 | 1. 1) (1) | 1. 가. 1) 가) | 1. 가. 1) 가) | 1. 1) (1) |

- 템플릿 수정은 `scripts/dev/gen_templates.py`의 `THEMES`를 고쳐 재실행한다.
  산출물(templates/*)을 직접 편집하지 않는다. 새 테마는 `THEMES`에 항목을 추가하면
  `new --theme 이름`으로 바로 쓸 수 있다.
- section0.xml을 손으로 쓸 때는 위 ID만 참조한다. 정의되지 않은
  charPrIDRef/paraPrIDRef는 validate의 dangling-ref로 잡힌다.
- secPr은 템플릿 section0.xml의 첫 문단에서 통째로 가져온다 (`owpml.load_skeleton`).
