# 공문서 작성법 검수 규칙 (lint)

행정안전부 「행정업무운영 편람」의 공문서 표기 원칙을 자체 규칙으로 정리했다.
검수는 게이트가 아니라 안내이며, 결과 JSON의 findings를 보고 사용자가 판단한다.

| 규칙 | 원칙 | 예 |
|------|------|-----|
| date-format | 연월일은 숫자와 온점, 온점 뒤 한 칸, 마지막에도 온점 | `2026. 8. 16.` |
| time-format | 24시각제, 시·분은 쌍점 | `14:30` |
| amount-hangul | 아라비아 숫자 뒤 괄호에 한글 병기 | `금1,500,000원(금일백오십만원)` |
| attachment-format | 붙임 항목은 `N부.`로 끝냄 | `붙임  1. 계획서 1부.` |
| end-mark | 본문(붙임이 있으면 붙임) 끝에 한 칸 띄고 `끝.` (붙임 뒤는 두 칸) | `... 1부.  끝.` |
| item-hierarchy | 1. → 가. → 1) → 가) → (1) → (가) → ① | |
| colon-spacing | 쌍점 왼쪽 붙임, 오른쪽 한 칸 (시각 표기 예외) | `성명: 홍길동` |
| date-padding | 월·일에 0을 붙이지 않음 | `2026. 1. 5.` |
| year-2digit | 연도는 4자리 | `2026. 8. 16.` |
| amount-abbrev | 금액은 단위 약어 없이 아라비아 숫자 전액 | `1,500,000원` |
| attach-colon | `붙임` 뒤 쌍점 없이 두 칸 | `붙임  계획서 1부.` |
| range-redundant | 물결표 범위와 `까지` 중복 금지 | `8. 1.~8. 16.` |
| foreign-order | 한글 먼저, 외국어는 괄호 안 | `인공지능(AI)` |

## 사용법

```bash
python3 scripts/hwpx.py lint document.hwpx
python3 scripts/hwpx.py lint document.txt
```

JSON 결과: `{"findings": [{"rule", "line", "text", "message", "suggest"}], "count": N}`.
findings는 게이트가 아니므로 결과에 findings가 있어도(=`count > 0`이어도) exit code는 항상 0이다 —
findings 유무는 결과 JSON의 `count`로 판단한다.
단, 파일을 찾을 수 없거나 hwpx 패키지가 손상된 경우 등 파일 자체의 오류는 이 규칙과 별개로
툴킷의 표준 오류 계약(JSON + exit 2)을 그대로 따른다(다른 명령들과 동일).
