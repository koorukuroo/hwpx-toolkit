# vendored: python-hwpx `hwpx.hwp5` 읽기 측 (Apache-2.0)

- 출처: [python-hwpx](https://github.com/airmang/python-hwpx) 6.8.0 — Copyright 2025-2026 airmang,
  Apache License 2.0 (`LICENSE`, `NOTICE` 참조). 원본 파일은 `# SPDX-License-Identifier: Apache-2.0` 헤더를 유지한다.
- 용도: `from-hwp`의 기본 엔진. HWP 5.0 복합 파일(DocInfo·BodyText 레코드)을 OWPML 파트
  (`header.xml`, `section<N>.xml`, `masterpage<N>.xml`, `content.hpf`, `settings.xml`, BinData)로 옮긴다.
- 가져온 모듈: binary, bodytext, cfb, controls, docinfo, fileheader, header_xml, owpml, package,
  reader, records, section_common, section_xml, shape_xml, shapes, summary.
  HWPX→HWP 쓰기 측(writer, section_writer, docinfo_writer)은 가져오지 않았다.

## hwpx-toolkit 변경점

1. **lxml 제거** — `from lxml import etree`를 `from . import _etree as etree`로 바꿨다.
   `_etree.py`는 원본이 쓰는 부분집합(`Element(nsmap=)`, `SubElement`, `tostring`, `QName`, `_Element`)을
   `xml.etree.ElementTree`로 제공한다. 직렬화는 lxml과 같은 모양을 내도록 맞췄다:
   루트에 nsmap의 모든 접두사를 선언, 텍스트의 CR은 `&#13;`, 빈 요소는 `/>`.
2. **getparent() 제거** — `section_xml.py`의 두 곳만 썼다. 하나는 `_parent_of()` 탐색으로,
   하나는 `run[-1] is target`(부모가 run임을 함의)으로 바꿨다. 주석 `hwpx-toolkit:`으로 표시.
3. **errors.py** — `hwpx.errors`의 `Hwp5Error`/`Hwp5ConversionWarning`/`Hwp5ConversionReport`를
   패키지 안으로 옮겼다(패키지 밖 의존 제거).

포팅 검증: 실물 .hwp 11건에서 lxml 원본과 포팅본의 모든 XML 파트가 트리 단위로 동일했다
(`META-INF/container.rdf`의 네임스페이스 선언 위치만 다름).

## 갱신 절차

1. 상위 릴리즈의 `hwpx/hwp5/` 읽기 측 모듈을 덮어쓴다 (`LICENSE`, `NOTICE` 포함).
2. 위 변경점 1~3을 다시 적용한다 (`grep -n "lxml\|getparent" *.py`가 비어야 한다).
3. `python3 -m pytest tests/test_convert.py tests/test_vendor_etree.py`와 실물 코퍼스
   비교(변경점 검증과 같은 방식)를 돌린다.
