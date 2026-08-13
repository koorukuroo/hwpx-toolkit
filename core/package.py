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
