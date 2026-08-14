# base 템플릿 스타일 ID 맵

| 종류 | ID | 내용 |
|------|----|------|
| font | 0 | 함초롬바탕 (본문) |
| font | 1 | 함초롬돋움 (제목/헤더) |
| borderFill | 1 | 테두리 없음 (페이지 보더용) |
| borderFill | 2 | 테두리 없음 (charPr/paraPr 참조용) |
| borderFill | 3 | SOLID 0.12mm 4면 (표 본문 셀) |
| borderFill | 4 | SOLID 0.12mm 4면 + #E6E6E6 배경 (표 헤더 셀) |
| charPr | 0 | 10pt(1000) 바탕 본문 |
| charPr | 1 | 18pt(1800) 돋움 볼드 — 문서 제목(H1) |
| charPr | 2 | 14pt(1400) 돋움 볼드 — H2 |
| charPr | 3 | 12pt(1200) 돋움 볼드 — H3 이하 |
| charPr | 4 | 10pt(1000) 돋움 볼드 — 표 헤더 |
| paraPr | 0 | JUSTIFY 160% 본문 |
| paraPr | 1 | CENTER 160%, prev/next 800 — 제목(H1) |
| paraPr | 2 | LEFT 160%, prev 600 next 200 — H2 |
| paraPr | 3 | LEFT 160%, prev 400 next 100 — H3 이하 |
| paraPr | 4 | JUSTIFY 160%, left 600 — 목록 |
| paraPr | 5 | CENTER 130% — 표 셀 |
| style | 0 | PARA "바탕글" (paraPr 0 + charPr 0) |

- 템플릿 수정은 `scripts/dev/gen_base_template.py`를 고쳐 재실행한다.
  산출물(templates/base/*)을 직접 편집하지 않는다.
- section0.xml을 손으로 쓸 때는 위 ID만 참조한다. 정의되지 않은
  charPrIDRef/paraPrIDRef는 validate의 dangling-ref로 잡힌다.
- secPr은 템플릿 section0.xml의 첫 문단에서 통째로 가져온다
  (`owpml.load_skeleton`). 추후 한컴 저장본으로 템플릿을 교체하면
  코드 변경 없이 호환성이 좋아진다.
