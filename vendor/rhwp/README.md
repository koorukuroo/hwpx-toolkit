# vendored: @rhwp/core (MIT)

- 출처: @rhwp/core — Copyright (c) 2025-2026 Edward Kim, MIT License (LICENSE 참조)
- 용도: `scripts/rhwp_convert.mjs`가 HWP(5.x 바이너리)→HWPX 변환에 사용하는 WASM 런타임
- 갱신: 파일 4개(rhwp.js, rhwp_bg.wasm, LICENSE, package.json)를 상위 릴리즈로 교체.
  hwpx-toolkit 코드는 `HwpDocument`/`exportHwpx`/`free` 공개 API만 사용한다.
