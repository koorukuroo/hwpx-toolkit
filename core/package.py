"""HWPX ZIP 패키지 IO — 읽기 + 바이트 보존 쓰기 (순수 stdlib)."""
import io
import struct
import zipfile
import zlib
from pathlib import Path


class PackageError(Exception):
    pass


class UnsupportedZipError(PackageError):
    pass


_EOCD_SIG = b"PK\x05\x06"
_CENTRAL_SIG = b"PK\x01\x02"


def _find_eocd(data):
    idx = data.rfind(_EOCD_SIG)
    if idx < 0:
        raise PackageError("EOCD 레코드 없음")
    return idx


def _central_records(data):
    """중앙 디렉터리를 (원시 바이트, 파일명) 리스트로 반환."""
    eocd = _find_eocd(data)
    cd_size, cd_off = struct.unpack("<II", data[eocd + 12:eocd + 20])
    if cd_off == 0xFFFFFFFF:
        raise UnsupportedZipError("ZIP64 미지원")
    records, pos, end = [], cd_off, cd_off + cd_size
    while pos < end:
        if data[pos:pos + 4] != _CENTRAL_SIG:
            raise PackageError("중앙 디렉터리 손상")
        fn_len, ex_len, cm_len = struct.unpack("<HHH", data[pos + 28:pos + 34])
        rec_len = 46 + fn_len + ex_len + cm_len
        name = data[pos + 46:pos + 46 + fn_len].decode("utf-8")
        records.append((bytearray(data[pos:pos + rec_len]), name))
        pos += rec_len
    return records, eocd


def _local_record_span(data, info):
    """엔트리의 (로컬 헤더 시작, 데이터 시작, 레코드 끝) 오프셋."""
    off = info.header_offset
    if info.flag_bits & 0x08:
        raise UnsupportedZipError(f"data descriptor 사용 엔트리 미지원: {info.filename}")
    fn_len, ex_len = struct.unpack("<HH", data[off + 26:off + 30])
    data_start = off + 30 + fn_len + ex_len
    return off, data_start, data_start + info.compress_size


class HwpxPackage:
    def __init__(self, path, data, zf):
        self.path = Path(path)
        self._data = data          # 원본 파일 전체 바이트
        self._zf = zf              # zipfile.ZipFile(BytesIO)
        self._infos = sorted(zf.infolist(), key=lambda i: i.header_offset)

    @classmethod
    def open(cls, path):
        path = Path(path)
        try:
            data = path.read_bytes()
        except OSError as e:
            raise PackageError(f"파일을 읽을 수 없음: {path}: {e}") from e
        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise PackageError(f"ZIP 형식이 아님: {path}")
        zf = zipfile.ZipFile(io.BytesIO(data))
        return cls(path, data, zf)

    def names(self):
        return [i.filename for i in self._infos]

    def read(self, name):
        try:
            return self._zf.read(name)
        except KeyError as e:
            raise PackageError(f"엔트리 없음: {name}") from e

    def read_text(self, name):
        return self.read(name).decode("utf-8")

    def write_replaced(self, dst, replacements):
        names = set(self.names())
        for name in replacements:
            if name not in names:
                raise PackageError(f"원본에 없는 엔트리 교체 불가: {name}")
        data = self._data
        centrals, eocd = _central_records(data)
        central_by_name = {n: rec for rec, n in centrals}

        out = io.BytesIO()
        new_offsets = {}
        for info in self._infos:
            name = info.filename
            start, data_start, end = _local_record_span(data, info)
            new_offsets[name] = out.tell()
            if name in replacements:
                raw = replacements[name]
                crc = zlib.crc32(raw) & 0xFFFFFFFF
                if info.compress_type == zipfile.ZIP_STORED:
                    comp = raw
                else:
                    c = zlib.compressobj(9, zlib.DEFLATED, -15)
                    comp = c.compress(raw) + c.flush()
                header = bytearray(data[start:data_start])
                struct.pack_into("<III", header, 14, crc, len(comp), len(raw))
                out.write(header)
                out.write(comp)
                central = central_by_name[name]
                struct.pack_into("<III", central, 16, crc, len(comp), len(raw))
            else:
                out.write(data[start:end])

        cd_start = out.tell()
        for rec, name in centrals:
            struct.pack_into("<I", rec, 42, new_offsets[name])
            out.write(rec)
        cd_size = out.tell() - cd_start
        eocd_rec = bytearray(data[eocd:eocd + 22] + data[eocd + 22:eocd + 22 +
                             struct.unpack("<H", data[eocd + 20:eocd + 22])[0]])
        struct.pack_into("<II", eocd_rec, 12, cd_size, cd_start)
        out.write(eocd_rec)
        Path(dst).write_bytes(out.getvalue())
