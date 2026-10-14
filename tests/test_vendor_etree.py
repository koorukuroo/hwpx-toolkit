"""vendor/pyhwpx_hwp5/_etree — lxml 부분집합의 표준 라이브러리 포팅 계층."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor"))

from pyhwpx_hwp5 import _etree as etree  # noqa: E402
from pyhwpx_hwp5.owpml import NS, XML_DECLARATION, root, serialize, sub  # noqa: E402


def test_root_declares_every_prefix_in_nsmap_order():
    sec = root("hs:sec")
    p = sub(sec, "hp:p", (("id", "1"),))
    sub(p, "hp:t").text = "가"
    out = serialize(sec)
    assert out.startswith(XML_DECLARATION + b"<hs:sec ")
    head = out[len(XML_DECLARATION):].split(b">", 1)[0].decode()
    for prefix, uri in NS.items():
        assert f'xmlns:{prefix}="{uri}"' in head
    assert head.index("xmlns:ha=") < head.index("xmlns:hp=") < head.index("xmlns:config=")
    assert head.count("xmlns:hp=") == 1
    assert b'<hp:p id="1"><hp:t>\xea\xb0\x80</hp:t></hp:p></hs:sec>' in out
    ET.fromstring(out)  # 파싱 가능


def test_serialization_matches_lxml_conventions():
    sec = root("hs:sec")
    t = sub(sub(sec, "hp:p"), "hp:t")
    t.text = "a\r\nb"
    sub(sec, "hp:empty", (("x", "1"),))
    out = serialize(sec)
    assert b"<hp:t>a&#13;\nb</hp:t>" in out          # 캐리지 리턴은 문자 참조로
    assert b'<hp:empty x="1"/>' in out                # 빈 요소는 공백 없이 닫음
    assert b" />" not in out
    assert ET.fromstring(out).find(f"{{{NS['hp']}}}p/{{{NS['hp']}}}t").text == "a\r\nb"


def test_tostring_keeps_auto_prefixes_outside_nsmap():
    rdf_ns = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    pkg_ns = "http://example.com/pkg#"
    rdf = etree.Element(f"{{{rdf_ns}}}RDF", nsmap={"rdf": rdf_ns})
    etree.SubElement(rdf, f"{{{pkg_ns}}}hasPart", nsmap={"ns0": pkg_ns})
    out = etree.tostring(rdf, encoding="UTF-8")
    parsed = ET.fromstring(out)
    assert parsed.tag == f"{{{rdf_ns}}}RDF" and parsed[0].tag == f"{{{pkg_ns}}}hasPart"
    assert out.startswith(b'<rdf:RDF xmlns:rdf="')


def test_qname_localname_and_namespace():
    el = ET.Element("{urn:x}name")
    assert etree.QName(el).localname == "name"
    assert etree.QName(el).namespace == "urn:x"
    assert etree.QName("plain").localname == "plain"
    assert etree.QName("plain").namespace is None


def test_element_without_nsmap_serializes_plainly():
    holder = etree.Element("holder")
    etree.SubElement(holder, "{urn:a}c").text = "x>y"
    assert etree.tostring(holder) == b'<holder xmlns:ns0="urn:a"><ns0:c>x&gt;y</ns0:c></holder>'
