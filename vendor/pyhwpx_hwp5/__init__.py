# SPDX-License-Identifier: Apache-2.0
"""HWP 5.0 (``.hwp``) → HWPX 파트 변환기 — python-hwpx 6.8.0의 ``hwpx.hwp5`` 읽기 측을
hwpx-toolkit용으로 벤더링한 것 (Apache-2.0, 원 저작자 airmang; LICENSE·NOTICE 참조).

변경점(hwpx-toolkit):
- lxml 의존 제거: ``_etree`` 호환 계층(xml.etree.ElementTree)으로 교체.
- ``errors``를 패키지 안으로 옮김(``hwpx.errors`` 의존 제거).
- HWPX → HWP 쓰기 측(writer/section_writer/docinfo_writer)은 포함하지 않음.

공개 API: :func:`convert` (bytes → ``Converted``), :func:`to_hwpx_bytes`.
"""
from .errors import Hwp5ConversionReport, Hwp5Error  # noqa: F401
from .package import Converted, convert, to_hwpx_bytes  # noqa: F401

UPSTREAM = "python-hwpx 6.8.0 (hwpx/hwp5, read side)"
