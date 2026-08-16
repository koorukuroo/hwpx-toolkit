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

## 템플릿 스타일 맵 (styles.json)

`new` 커맨드가 마크다운을 HWPX로 생성할 때 `styles.json`에서 charPr/paraPr/borderFill ID를 조회한다.
base 템플릿과 report 템플릿은 서로 다른 스타일 맵을 가지며,
`templates/<template-name>/styles.json`에 정의된다. 자세한 ID 맵은 references/base-template-styles.md 참조.

## 개체 구조 노트 (Phase 4)

- **그림**: `hp:p > hp:run > hp:pic` (offset/orgSz/curSz/flip/rotationInfo/renderingInfo/
  imgRect/imgClip/inMargin/imgDim/hc:img@binaryItemIDRef/effects/sz/pos/outMargin).
  바이너리는 `BinData/imageN.ext`, content.hpf manifest에 `opf:item id="imageN"
  isEmbeded="1"`로 등록. (2026-08-15 한컴 실물에서 확인)
- **머리말/꼬리말**: 첫 문단 첫 run, secPr·colPr ctrl 뒤 `hp:ctrl > hp:header|hp:footer
  @id="0" @applyPageType > hp:subList > hp:p`. 쪽번호는 그 문단의 run에
  `hp:run > hp:ctrl > hp:autoNum @numType="PAGE" > hp:autoNumFormat`, ctrl 뒤에
  빈 `hp:t`가 온다 (autoNum이 ctrl 없이 run 바로 밑에 오면 잘못된 구조).
  (2026-08-16 한컴 저장 문서 2건에서 확인)
- **스타일 추가**: header.xml의 charPr/paraPr를 복제·변형해 끝에 추가하고 itemCnt 갱신.
  기존 id는 절대 재사용하지 않는다.

## 페이지 방향 (hp:pagePr@landscape)

`hp:pagePr@landscape`는 "가로/세로" 자체가 아니라 **90° 회전 플래그**다. 폭>높이로
치수를 스왑하는 것도 별도의 회전이므로, 한컴이 실제로 렌더링하는 방향은
**landscape 속성과 (폭>높이) 여부의 XOR**이다. 두 회전을 동시에 적용(예: attr을
NARROWLY로 바꾸면서 치수도 스왑)하면 회전이 상쇄되어 의도와 반대 방향으로
렌더링된다 — `set_page(orientation="landscape")`가 세로로 열리던 버그의 원인.

실물 한컴에서 확인한 4가지 조합 (2026-08-17):

| landscape 속성 | 치수 | 한컴 렌더링 |
|---|---|---|
| WIDELY | 59528×84186 (세로 치수) | 세로 — 실물 문서 전부 이 조합 |
| WIDELY | 84186×59528 (스왑) | **가로** |
| NARROWLY | 59528×84186 (세로 치수) | **가로** |
| NARROWLY | 84186×59528 (스왑) | 세로 |

수정 전략: **landscape 속성은 절대 건드리지 않는다.** 위 표(XOR)로 현재 방향을
판정하고, 요청된 방향과 다를 때만 폭/높이를 스왑한다. 이렇게 하면 이미 원하는
방향이면 무조건 no-op이 되어 이중 적용(회전 상쇄) 버그가 원천적으로 발생하지 않는다.
