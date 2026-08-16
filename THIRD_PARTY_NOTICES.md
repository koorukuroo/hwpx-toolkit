# Third-Party Notices

hwpx-toolkit 자체 코드는 MIT (LICENSE 참조). 아래 외부 컴포넌트를 동봉한다.

## @rhwp/core (vendor/rhwp/)

- 저작권: Copyright (c) 2025-2026 Edward Kim
- 라이선스: MIT — 전문은 `vendor/rhwp/LICENSE`
- 버전: @rhwp/core version 0.7.12
  (wasm sha256: c975610a4767e2e1a7da29f9c907510f85348620cdf8a69587d6e1cfb85b4de6)
- 사용 범위: `from-hwp` 커맨드의 HWP→HWPX 변환 런타임(WASM). 선택 의존성이며
  Node.js 18+ 환경에서만 로드된다. hwpx-toolkit은 이 라이브러리의 공개 API를
  `scripts/rhwp_convert.mjs`(자체 작성)에서 호출할 뿐 소스를 수정하지 않는다.
