"""Safe file writes, volume locking, and transaction recovery."""

import contextlib
import fcntl
import json
import shutil
from pathlib import Path

from . import log

Changes = dict[Path, Path]


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".mod-updater-tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def safe_target(root: Path, relative: Path) -> Path:
    target = root / relative
    if not target.is_relative_to(root) or ".." in relative.parts:
        raise ValueError("target escapes game volume")
    for item in [target, *target.parents]:
        if item == root:
            break
        if item.is_symlink():
            raise ValueError("refusing to modify a symlink")
    if target.exists() and not target.is_file():
        raise ValueError("target is not a regular file")
    return target


class Transaction:
    """Back up every touched file before writing; recover interrupted writes next boot."""

    def __init__(self, root: Path, state: Path):
        self.root = root
        self.directory = state / "transaction"
        self.journal = self.directory / "journal.json"

    def recover(self) -> None:
        if self.journal.exists():
            log("Restoring previous installation from unfinished transaction")
            entries = json.loads(self.journal.read_text())
            for index, entry in reversed(list(enumerate(entries))):
                target = safe_target(self.root, Path(entry["path"]))
                target.with_name(target.name + ".mod-updater-tmp").unlink(
                    missing_ok=True
                )
                if entry["existed"]:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(self.directory / str(index), target)
                else:
                    target.unlink(missing_ok=True)
            self.journal.unlink()
        if self.directory.exists():
            shutil.rmtree(self.directory)

    def apply(self, changes: Changes) -> None:
        """Commit staged files and manifests together, rolling back failed writes."""
        self.directory.mkdir()
        entries = []
        for index, relative in enumerate(changes):
            target = safe_target(self.root, relative)
            existed = target.exists()
            if existed:
                shutil.copy2(target, self.directory / str(index))
            entries.append({"path": relative.as_posix(), "existed": existed})
        atomic_write(self.journal, json_bytes(entries))
        try:
            for relative, source in changes.items():
                target = safe_target(self.root, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".mod-updater-tmp")
                shutil.copy2(source, temporary)
                temporary.replace(target)
        except Exception:
            self.recover()  # Any recovery error is fatal, never eligible for fallback.
            raise
        self.journal.unlink()  # Commit point: all payloads and manifests are in place.
        shutil.rmtree(self.directory)


@contextlib.contextmanager
def volume_lock(state: Path):
    state.mkdir(parents=True, exist_ok=True)
    with (state / "updater.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
