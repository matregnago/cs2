"""Extract supported package layouts without following links or escaping staging."""

import shutil
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO


def archive_path(name: str) -> Path | None:
    path = PurePosixPath(name)
    if "\\" in name or path.is_absolute() or ".." in path.parts or ":" in name:
        raise ValueError("unsafe archive path")
    # Packages must have the layout expected by CS2, not an arbitrary outer directory.
    if not path.parts or path.parts[0] not in ("addons", "cfg"):
        return None
    return Path(*path.parts)


def _write_file(source: BinaryIO, target: Path, mode: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as output:
        shutil.copyfileobj(source, output)
    target.chmod(mode)


def extract(archive: Path, destination: Path) -> None:
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                path = archive_path(member.filename)
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("archive symlinks are not supported")
                if path is None or member.is_dir():
                    continue
                mode = 0o755 if member.external_attr >> 16 & 0o111 else 0o644
                with bundle.open(member) as source:
                    _write_file(source, destination / path, mode)
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle:
                path = archive_path(member.name)
                if (
                    member.issym()
                    or member.islnk()
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("unsupported tar member")
                if path is None or member.isdir():
                    continue
                with bundle.extractfile(member) as source:
                    _write_file(source, destination / path, member.mode & 0o777)
