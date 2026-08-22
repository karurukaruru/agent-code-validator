"""Project source-file discovery and safe text extraction."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".go": "Go",
}

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    ".env",
    "__pycache__",
    "dist",
    "build",
    "target",
}

DEFAULT_MAX_FILE_BYTES = 1_000_000


class ScanError(ValueError):
    """Raised when a project cannot be scanned."""


@dataclass(frozen=True)
class SourceFile:
    path: str
    file_type: str
    content: str
    size_bytes: int


@dataclass
class ScanResult:
    project_path: Path
    files: list[SourceFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _looks_binary(data: bytes) -> bool:
    """Use NUL bytes and a conservative control-character ratio as signals."""
    if not data:
        return False
    sample = data[:8192]
    if b"\x00" in sample:
        return True
    allowed_controls = {8, 9, 10, 12, 13}
    suspicious = sum(byte < 32 and byte not in allowed_controls for byte in sample)
    return suspicious / len(sample) > 0.10


def scan_project(
    project_path: str | Path,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> ScanResult:
    """Scan a directory and return supported, readable source files.

    Paths in the result are POSIX-style and relative to the project root so that
    reports remain portable across operating systems.
    """
    root = Path(project_path).expanduser()
    if not root.exists():
        raise ScanError(f"Project path does not exist: {root}")
    if not root.is_dir():
        raise ScanError(f"Project path is not a directory: {root}")
    if max_file_bytes <= 0:
        raise ScanError("max_file_bytes must be greater than zero")

    root = root.resolve()
    result = ScanResult(project_path=root)

    candidates: list[Path] = []

    def record_walk_error(exc: OSError) -> None:
        location = "."
        if exc.filename:
            try:
                location = Path(exc.filename).resolve().relative_to(root).as_posix()
            except (OSError, ValueError):
                location = str(exc.filename)
        result.warnings.append(f"Could not access {location}: {exc.strerror or exc}.")

    try:
        for current_dir, directory_names, file_names in os.walk(
            root, topdown=True, onerror=record_walk_error, followlinks=False
        ):
            # Pruning here is materially faster than discovering files below these
            # often very large directories and filtering them afterward.
            directory_names[:] = sorted(
                name for name in directory_names if name.lower() not in IGNORED_DIRECTORIES
            )
            current_path = Path(current_dir)
            candidates.extend(
                current_path / name
                for name in file_names
                if Path(name).suffix.lower() in SUPPORTED_EXTENSIONS
            )
        candidates.sort(key=lambda path: path.relative_to(root).as_posix().lower())
    except OSError as exc:
        raise ScanError(f"Unable to walk project directory {root}: {exc}") from exc

    for path in candidates:
        relative_path = path.relative_to(root).as_posix()
        try:
            if path.is_symlink():
                result.warnings.append(
                    f"Skipped {relative_path}: symbolic links are not scanned."
                )
                continue
            size = path.stat().st_size
            if size > max_file_bytes:
                result.warnings.append(
                    f"Skipped {relative_path}: file is larger than {max_file_bytes:,} bytes."
                )
                continue
            # Bound the read itself as well as the earlier stat check. The file
            # may grow between those operations, and ACV should never load it
            # unboundedly into memory.
            with path.open("rb") as source:
                data = source.read(max_file_bytes + 1)
            if len(data) > max_file_bytes:
                result.warnings.append(
                    f"Skipped {relative_path}: file grew beyond {max_file_bytes:,} bytes while reading."
                )
                continue
            if _looks_binary(data):
                result.warnings.append(f"Skipped {relative_path}: file appears to be binary.")
                continue
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError:
                content = data.decode("utf-8", errors="replace")
                result.warnings.append(
                    f"Decoded {relative_path} with replacement characters because it is not valid UTF-8."
                )
            result.files.append(
                SourceFile(
                    path=relative_path,
                    file_type=SUPPORTED_EXTENSIONS[path.suffix.lower()],
                    content=content,
                    size_bytes=len(data),
                )
            )
        except OSError as exc:
            result.warnings.append(f"Skipped {relative_path}: could not read file ({exc}).")

    return result
