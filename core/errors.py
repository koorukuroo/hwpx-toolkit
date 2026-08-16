"""hwpx-toolkit 예외 계층 — 순환 import 없이 어디서든 참조."""


class PackageError(Exception):
    pass


class UnsupportedZipError(PackageError):
    pass


class EditError(PackageError):
    pass
