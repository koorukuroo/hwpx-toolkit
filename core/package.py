"""HWPX ZIP 패키지 IO — 읽기 + 바이트 보존 쓰기 (순수 stdlib)."""
import io
import os
import re
import struct
import zipfile
import zlib
from pathlib import Path

from core.errors import PackageError, UnsupportedZipError  # noqa: F401 (재노출)

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


def atomic_write(dst, data):
    """같은 디렉터리의 임시 파일에 쓴 뒤 os.replace — 중간에 실패해도 반쪽 파일이
    dst 이름으로 남지 않는다."""
    dst = Path(dst)
    tmp = dst.with_name(f".{dst.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, dst)
    finally:
        if tmp.exists():
            tmp.unlink()


def section_names(names):
    """Contents/section<N>.xml 엔트리를 숫자순으로 반환."""
    cands = []
    for n in names:
        m = re.fullmatch(r"Contents/section(\d+)\.xml", n)
        if m:
            cands.append((int(m.group(1)), n))
    return [n for _, n in sorted(cands)]


#: 압축 폭탄·비정상 패키지 방어 — 실물 최대(수백 MB 그림 문서)를 넉넉히 넘는 값.
MAX_ENTRIES = 4096
MAX_ENTRY_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_RATIO = 1000            # 풀린 크기 / 압축 크기 (10MB 넘는 엔트리만 검사)


def _check_limits(path, zf):
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise PackageError(f"엔트리가 너무 많음({len(infos)} > {MAX_ENTRIES}): {path}")
    total = 0
    for i in infos:
        if i.file_size > MAX_ENTRY_BYTES:
            raise PackageError(f"엔트리가 너무 큼({i.file_size} bytes): {i.filename}")
        if i.file_size > 10 * 1024 * 1024 and i.compress_size \
                and i.file_size / i.compress_size > MAX_RATIO:
            raise PackageError(f"압축비 비정상(압축 폭탄 의심): {i.filename}")
        total += i.file_size
    if total > MAX_TOTAL_BYTES:
        raise PackageError(f"풀린 크기 합이 너무 큼({total} bytes): {path}")


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
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise PackageError(f"ZIP 손상: {path}: {e}") from e
        _check_limits(path, zf)
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

    def write_replaced(self, dst, replacements, additions=None):
        names = set(self.names())
        for name in replacements:
            if name not in names:
                raise PackageError(f"원본에 없는 엔트리 교체 불가: {name}")
        additions = additions or {}
        for name in additions:
            if name in names:
                raise PackageError(f"이미 존재하는 엔트리는 additions 불가: {name}")
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
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise UnsupportedZipError(f"지원하지 않는 압축 방식: {name}")
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

        added_centrals = []
        for name, raw in additions.items():
            c = zlib.compressobj(9, zlib.DEFLATED, -15)
            comp = c.compress(raw) + c.flush()
            crc = zlib.crc32(raw) & 0xFFFFFFFF
            fname = name.encode("utf-8")
            offset = out.tell()
            # 로컬 헤더: sig, ver 20, flags 0x800, method 8, time 0, date 0x21(1980-01-01)
            out.write(struct.pack("<4sHHHHHIIIHH", b"PK\x03\x04", 20, 0x0800, 8,
                                  0, 0x21, crc, len(comp), len(raw), len(fname), 0))
            out.write(fname)
            out.write(comp)
            central = struct.pack("<4sHHHHHHIIIHHHHHII", b"PK\x01\x02", 20, 20,
                                  0x0800, 8, 0, 0x21, crc, len(comp), len(raw),
                                  len(fname), 0, 0, 0, 0, 0, offset) + fname
            added_centrals.append(central)

        cd_start = out.tell()
        for rec, name in centrals:
            struct.pack_into("<I", rec, 42, new_offsets[name])
            out.write(rec)
        for rec in added_centrals:
            out.write(rec)
        cd_size = out.tell() - cd_start
        total_entries = len(centrals) + len(added_centrals)
        eocd_rec = bytearray(data[eocd:eocd + 22] + data[eocd + 22:eocd + 22 +
                             struct.unpack("<H", data[eocd + 20:eocd + 22])[0]])
        struct.pack_into("<HHII", eocd_rec, 8, total_entries, total_entries,
                         cd_size, cd_start)
        out.write(eocd_rec)
        atomic_write(dst, out.getvalue())

    def extract_to(self, dirpath):
        base = Path(dirpath).resolve()
        for name in self.names():
            if name.endswith("/"):
                continue
            target = (base / name).resolve()
            if not target.is_relative_to(base):
                raise PackageError(f"안전하지 않은 엔트리 경로: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.read(name))
        return self.names()


def pack_dir(dirpath, dst, source=None):
    dirpath = Path(dirpath)
    files = {}
    for f in dirpath.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(dirpath)
        if any(part.startswith(".") for part in rel.parts):
            continue
        files[str(rel).replace("\\", "/")] = f
    if source is not None:
        pkg = HwpxPackage.open(source)
        src_names = set(pkg.names())
        extra = set(files) - src_names
        if extra:
            raise PackageError(f"원본에 없는 파일 (엔트리 추가는 Phase 3+): {sorted(extra)}")
        replacements = {}
        for name, f in files.items():
            data = f.read_bytes()
            if data != pkg.read(name):
                replacements[name] = data
        pkg.write_replaced(dst, replacements)
    else:
        names = sorted(files)
        if "mimetype" in files:
            names.remove("mimetype")
            names.insert(0, "mimetype")
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in names:
                ctype = (zipfile.ZIP_STORED if name == "mimetype"
                         else zipfile.ZIP_DEFLATED)
                zf.writestr(zipfile.ZipInfo(name), files[name].read_bytes(),
                            compress_type=ctype)
