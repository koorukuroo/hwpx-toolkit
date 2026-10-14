# SPDX-License-Identifier: Apache-2.0
"""Errors raised while reading HWP 5.0 (``.hwp``) documents.

hwpx-toolkit 포팅: python-hwpx의 ``hwpx.errors``에서 HWP5에 필요한 두 클래스만
옮겨 왔다(패키지 밖 의존 제거).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

__all__ = [
    "Hwp5ConversionReport",
    "Hwp5ConversionWarning",
    "Hwp5Error",
    "damaged",
    "limit_exceeded",
    "write_unsupported",
]


class Hwp5Error(ValueError):
    """An HWP 5.0 document cannot be read or written.

    ``code`` names the reason: ``hwp5-damaged`` (the container or its records
    are broken), ``hwp5-password``, ``hwp5-distribution`` and ``hwp5-drm`` (the
    body is encrypted), ``hwp5-not-hwp5`` (a compound file without an HWP 5.0
    file header), ``hwp5-version-unsupported`` and ``hwp5-limit-exceeded`` (the
    input exceeds a parsing limit).
    """

    default_code = "hwp5-damaged"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        context: Mapping[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code if code is not None else self.default_code
        self.context: dict[str, Any] = dict(context) if context else {}
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "context": dict(self.context),
            "suggestion": self.suggestion,
        }


class Hwp5ConversionWarning(UserWarning):
    """Opening an ``.hwp`` left content out of the document model."""


@dataclass(frozen=True)
class Hwp5ConversionReport:
    """What a conversion could not carry over, as counts by kind."""

    unconverted: Mapping[str, int]
    dropped: Mapping[str, int]

    @classmethod
    def of(cls, unconverted: Mapping[str, int], dropped: Mapping[str, int]) -> "Hwp5ConversionReport":
        return cls(MappingProxyType(dict(unconverted)), MappingProxyType(dict(dropped)))


def damaged(message: str, **context: object) -> Hwp5Error:
    """Build the error for a broken container or record stream."""

    return Hwp5Error(
        message,
        code="hwp5-damaged",
        context=context,
        suggestion="The file is truncated or corrupted; open and re-save it in Hancom Office.",
    )


def limit_exceeded(message: str, **context: object) -> Hwp5Error:
    """Build the error for an input that exceeds a parsing limit."""

    return Hwp5Error(message, code="hwp5-limit-exceeded", context=context)


def write_unsupported(message: str, **context: object) -> Hwp5Error:
    """Build the error for content the HWP 5.0 writer cannot express."""

    return Hwp5Error(message, code="hwp5-write-unsupported", context=context)
