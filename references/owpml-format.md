# OWPML(HWPX) 포맷 노트

자체 조사·KS X 6101 표준 기반 정리. 외부 문서를 복사하지 않는다.

## 패키지 구조

| 엔트리 | 역할 |
|--------|------|
| mimetype | `application/hwp+zip`, 첫 엔트리, STORED |
| version.xml | 포맷 버전 |
| settings.xml | 앱 설정 |
| META-INF/container.xml | 루트 파일(content.hpf) 지시 |
| Contents/content.hpf | 파트 목록(manifest/spine) |
| Contents/header.xml | 스타일 정의 (fontfaces/borderFills/charProperties/paraProperties) |
| Contents/section0.xml | 본문 (섹션당 1파일) |
| BinData/* | 이미지 등 바이너리 |

## 네임스페이스

| 접두사 | URI |
|--------|-----|
| hs | http://www.hancom.co.kr/hwpml/2011/section |
| hp | http://www.hancom.co.kr/hwpml/2011/paragraph |
| hh | http://www.hancom.co.kr/hwpml/2011/head |
| hc | http://www.hancom.co.kr/hwpml/2011/core |

## 단위 (HWPUNIT)

| 값 | HWPUNIT |
|----|---------|
| 1pt | 100 |
| 1mm | 283.5 |
| A4 폭 210mm | 59528 |
| A4 높이 297mm | 84186 |
| 기본 좌우여백 30mm | 8504 |
| A4 본문폭 | 42520 |

## 필수 불변식

1. section 첫 문단의 첫 run에 `hp:secPr` + `hp:ctrl/hp:colPr` 필수.
2. header.xml 각 컬렉션의 itemCnt = 실제 자식 수.
3. section의 charPrIDRef/paraPrIDRef/borderFillIDRef는 header에 정의된 id만 참조.
4. 문단 id는 문서 내 고유 정수.
5. 표: cellAddr(rowAddr/colAddr)와 rowCnt/colCnt 정합, 열 너비 합 = 표 폭.
6. `hp:t`는 mixed content — 텍스트와 hp:fwSpace/hp:lineBreak 등이 섞일 수 있으므로
   pretty-print 금지, 자식 태그 삭제 금지.
7. `hp:linesegarray`는 한컴의 줄 배치 캐시 — 텍스트 수정 시 해당 문단 것을 제거해야
   손상 경고를 피한다 (Phase 3 edit에서 구현).
