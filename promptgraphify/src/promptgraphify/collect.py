"""Reading prompt files from disk safely (CLI). Input files are DATA: they are read, never executed.

Rules, all enforced here and tested in ``tests/test_collect.py``:

* A directory is walked without following symbolic links; a symlink found inside it is skipped and reported.
* A symlink named explicitly must point inside its own directory, otherwise it is refused.
* Only regular files are opened (a FIFO or device is never read: opening one could block forever).
* Limits on file count, bytes per file and total characters; exceeding one is an error, never a silent cut.
* Files must be strict UTF-8 without NUL bytes. The BOM, if any, is kept (offsets count it).
* The name of a source is a relative POSIX path, unique per run, free of control characters.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from .api.schemas import normalize_input_path

SUPPORTED_SUFFIXES = frozenset({".md", ".markdown", ".txt", ".prompt", ".xml", ".yaml", ".yml", ".json"})
SKIPPED_DIRS = frozenset(
    {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", "promptgraphify-out", ".idea", ".vscode"}
)
O_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)


class CollectError(Exception):
    """The input cannot be read safely; the message says what to change."""


@dataclass(frozen=True)
class Limits:
    max_files: int = 200
    max_file_bytes: int = 1_000_000
    max_total_chars: int = 500_000


@dataclass
class Collected:
    files: list[tuple[str, str]] = field(default_factory=list)  # (source name, text)
    real_paths: list[Path] = field(default_factory=list)  # parallel to ``files``
    notes: list[str] = field(default_factory=list)  # things skipped on purpose, shown to the user
    ignored: int = 0  # files in a directory with an unsupported suffix


def _real(p: str | os.PathLike[str]) -> Path:
    return Path(os.path.realpath(p))


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _read_text(real: Path, shown: str, limits: Limits) -> str:
    try:
        fd = os.open(real, O_FLAGS)
    except OSError as exc:
        raise CollectError(f"{shown}: cannot open ({exc.strerror or exc})") from exc
    with os.fdopen(fd, "rb") as fh:
        st = os.fstat(fh.fileno())
        if not stat.S_ISREG(st.st_mode):
            raise CollectError(f"{shown}: not a regular file")
        data = fh.read(limits.max_file_bytes + 1)
    if len(data) > limits.max_file_bytes:
        raise CollectError(f"{shown}: larger than {limits.max_file_bytes} bytes (raise --max-file-bytes to allow it)")
    if b"\x00" in data:
        raise CollectError(f"{shown}: contains NUL bytes; it looks like a binary file, not a prompt")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CollectError(f"{shown}: not valid UTF-8 (byte {exc.start}); convert it to UTF-8 first") from exc


def _walk(root: Path, skip: set[Path], out: Collected) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        keep = []
        for d in sorted(dirnames):
            full = here / d
            if full.is_symlink():
                out.notes.append(f"skipped symlink {full.relative_to(root).as_posix()} (links are not followed)")
            elif d in SKIPPED_DIRS or d.startswith(".") or _real(full) in skip:
                out.notes.append(f"skipped directory {full.relative_to(root).as_posix()}")
            else:
                keep.append(d)
        dirnames[:] = keep
        for f in sorted(filenames):
            full = here / f
            rel = full.relative_to(root).as_posix()
            if full.is_symlink():
                out.notes.append(f"skipped symlink {rel} (links are not followed)")
            elif f.startswith("."):
                out.notes.append(f"skipped hidden file {rel}")
            elif full.suffix.lower() not in SUPPORTED_SUFFIXES:
                out.ignored += 1
            elif not stat.S_ISREG(os.lstat(full).st_mode):
                out.notes.append(f"skipped {rel} (not a regular file)")
            else:
                found.append(full)
    return found


def collect(paths: list[str], limits: Limits | None = None, *, skip_dirs: list[Path] | None = None) -> Collected:
    """Read every prompt file named by ``paths`` (files and/or directories). Raises :class:`CollectError`."""
    limits = limits or Limits()
    if not paths:
        raise CollectError("no input: give at least one file or directory")
    skip = {_real(p) for p in (skip_dirs or [])}
    out = Collected()
    candidates: list[tuple[Path, Path]] = []  # (real file path, container directory it is named relative to)
    containers: list[Path] = []
    seen: set[Path] = set()
    for arg in paths:
        if not os.path.lexists(arg):
            raise CollectError(f"{arg}: no such file or directory")
        real = _real(arg)
        if not real.exists():
            raise CollectError(f"{arg}: broken symbolic link")
        if real.is_dir():
            containers.append(real)
            found = _walk(real, skip, out)
            if not found:
                raise CollectError(f"{arg}: no supported prompt files ({', '.join(sorted(SUPPORTED_SUFFIXES))})")
            for f in found:
                rf = _real(f)
                if not _inside(rf, real):  # cannot happen without symlinks; kept as a hard guard
                    raise CollectError(f"{f}: resolves outside {arg}")
                if rf not in seen:
                    seen.add(rf)
                    candidates.append((rf, real))
        else:
            parent = _real(Path(arg).parent)
            if os.path.islink(arg) and not _inside(real, parent):
                raise CollectError(f"{arg}: symbolic link to {real}, outside its own directory; pass the real path")
            containers.append(parent)
            if real not in seen:
                seen.add(real)
                candidates.append((real, parent))
    if len(candidates) > limits.max_files:
        raise CollectError(f"{len(candidates)} files found, the limit is {limits.max_files} (raise --max-files)")
    base = Path(os.path.commonpath([str(c) for c in containers])) if len(containers) > 1 else containers[0]
    names: dict[str, Path] = {}
    total = 0
    for real, _container in sorted(candidates, key=lambda c: c[0].as_posix()):
        rel = real.relative_to(base).as_posix() if _inside(real, base) else real.name
        try:
            name = normalize_input_path(rel)
        except ValueError as exc:
            raise CollectError(f"{rel!r}: unusable file name ({exc})") from exc
        if name in names:
            raise CollectError(f"two inputs would be called {name!r}: {names[name]} and {real}")
        text = _read_text(real, name, limits)
        total += len(text)
        if total > limits.max_total_chars:
            raise CollectError(f"input exceeds {limits.max_total_chars} characters (raise --max-chars)")
        names[name] = real
        out.files.append((name, text))
        out.real_paths.append(real)
    return out
