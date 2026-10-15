# Third-Party Notices

hwpx-toolkit 자체 코드는 MIT (LICENSE 참조). 아래 외부 컴포넌트를 동봉한다.

## python-hwpx — `hwpx.hwp5` 읽기 측 (vendor/pyhwpx_hwp5/)

- 저작권: Copyright 2025-2026 airmang
- 라이선스: Apache License 2.0 — 전문은 `vendor/pyhwpx_hwp5/LICENSE`, 고지는 `vendor/pyhwpx_hwp5/NOTICE`
- 버전: python-hwpx 6.8.0 (https://github.com/airmang/python-hwpx)
- 사용 범위: `from-hwp` 커맨드의 기본 엔진(HWP 5.0 → OWPML 파트). 순수 Python.
- 변경: lxml 의존을 표준 라이브러리 호환 계층(`_etree.py`)으로 대체했고, `getparent()` 두 곳을
  바꿨으며, 오류 클래스를 패키지 안으로 옮겼다. 변경 파일에는 `hwpx-toolkit:` 주석을 남겼다
  (Apache-2.0 §4(b)에 따른 변경 고지). 상세는 `vendor/pyhwpx_hwp5/README.md`.

## @rhwp/core (vendor/rhwp/)

- 저작권: Copyright (c) 2025-2026 Edward Kim
- 라이선스: MIT — 전문은 `vendor/rhwp/LICENSE`
- 버전: @rhwp/core version 0.7.12
  (wasm sha256: c975610a4767e2e1a7da29f9c907510f85348620cdf8a69587d6e1cfb85b4de6)
- 사용 범위: `from-hwp --engine rhwp`(및 python 엔진 실패 시 자동 폴백)의 변환 런타임과
  `render`(쪽 미리보기 SVG/HTML) 렌더러(WASM).
  선택 의존성이며 Node.js 18+ 환경에서만 로드된다. hwpx-toolkit은 이 라이브러리의 공개 API를
  `scripts/rhwp_convert.mjs`(자체 작성)에서 호출할 뿐 소스를 수정하지 않는다.

## 테스트 픽스처

- `tests/fixtures/labor_template.hwp` — DoHyun468/claw-hwp (MIT), `tests/fixtures/README.md` 참조.
