# SPDX-License-Identifier: Apache-2.0
"""hwpx-toolkit 포팅 계층: lxml.etree의 사용 부분집합을 xml.etree.ElementTree로 대체.

python-hwpx의 hwp5 읽기 모듈은 lxml의 ``Element``/``SubElement``/``tostring``/
``QName``/``getparent``만 쓴다. 이 모듈은 그 부분집합을 표준 라이브러리로
제공해 hwpx-toolkit의 "pip 불필요" 원칙을 지킨다.

- ``Element(tag, nsmap=...)``: 루트에 선언할 네임스페이스 맵을 기억한다.
  ``tostring``은 ElementTree가 실제 사용한 접두사 선언을 걷어내고 nsmap의
  모든 접두사를 한컴 파일처럼 루트에 선언한다.
- ``_Element``: 타입 주석용 별칭.
- ``QName(el).localname``: 로컬 이름.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

_Element = ET.Element


class _NsElement(ET.Element):
    """nsmap을 기억하는 루트 요소."""

    nsmap: dict[str, str] | None = None


def Element(tag: str, attrib: dict | None = None, nsmap: dict[str, str] | None = None, **extra) -> ET.Element:
    element = _NsElement(tag, attrib or {}, **extra)
    element.nsmap = dict(nsmap) if nsmap else None
    return element


def SubElement(parent: ET.Element, tag: str, attrib: dict | None = None, nsmap: dict[str, str] | None = None,
               **extra) -> ET.Element:
    # nsmap on a sub element is a declaration hint only; ElementTree declares
    # every namespace on the root, which Hancom accepts.
    return ET.SubElement(parent, tag, attrib or {}, **extra)


class QName:
    __slots__ = ("text",)

    def __init__(self, element_or_tag) -> None:
        tag = element_or_tag.tag if isinstance(element_or_tag, ET.Element) else element_or_tag
        self.text = tag

    @property
    def localname(self) -> str:
        return self.text.rsplit("}", 1)[-1]

    @property
    def namespace(self) -> str | None:
        return self.text[1:].split("}", 1)[0] if self.text.startswith("{") else None


_PREFIX_RE = re.compile(r"^(?:ns\d+|xml|xmlns)$")
_XMLNS_IN_TAG = re.compile(r'\s+xmlns(?::[A-Za-z_][\w.-]*)?="[^"]*"')


def register_namespaces(nsmap: dict[str, str]) -> None:
    for prefix, uri in nsmap.items():
        if _PREFIX_RE.match(prefix):
            continue
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass


def tostring(element: ET.Element, encoding: str = "UTF-8", **_ignored) -> bytes:
    nsmap = getattr(element, "nsmap", None)
    if nsmap:
        register_namespaces(nsmap)
    raw = ET.tostring(element, encoding="utf-8")
    # lxml writes a carriage return in text as ``&#13;`` (a raw one is folded
    # to a newline by any parser) and closes an empty element as ``/>``; a raw
    # ``>`` never survives in text or attribute values, so ``" />"`` only ever
    # ends an empty element.
    raw = raw.replace(b"\r", b"&#13;").replace(b" />", b"/>")
    if not nsmap:
        return raw
    # Move every declaration to the root start tag, in nsmap order, the way
    # Hancom writes each part (unused prefixes included).
    end = _start_tag_end(raw)
    start_tag = raw[:end].decode("utf-8")
    self_closing = start_tag.endswith("/>")
    body = start_tag[:-2] if self_closing else start_tag[:-1]
    # Keep declarations ElementTree made for namespaces outside nsmap (e.g. an
    # auto-numbered ``ns0``), after the nsmap ones.
    existing: dict[str, str] = {}
    for m in re.finditer(r'\s+xmlns(?::([A-Za-z_][\w.-]*))?="([^"]*)"', body):
        existing[m.group(1) or ""] = m.group(2)
    body = _XMLNS_IN_TAG.sub("", body)
    name_end = len(body)
    for i, ch in enumerate(body):
        if ch in " \t\r\n" and i > 0:
            name_end = i
            break
    ordered = dict(nsmap)
    for prefix, uri in existing.items():
        if prefix not in ordered:
            ordered[prefix] = uri
    decls = "".join(f' xmlns:{p}="{u}"' if p else f' xmlns="{u}"' for p, u in ordered.items())
    rebuilt = body[:name_end] + decls + body[name_end:] + ("/>" if self_closing else ">")
    return rebuilt.encode("utf-8") + raw[end:]


def _start_tag_end(raw: bytes) -> int:
    """Index just past the root start tag's ``>`` (attribute values never hold a raw ``>``)."""

    i = raw.find(b">")
    if i < 0:
        raise ValueError("no start tag")
    return i + 1
