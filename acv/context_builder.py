"""Build bounded, readable project context for an LLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .scanner import ScanResult, SourceFile


DEFAULT_MAX_CONTEXT_CHARS = 120_000
DEFAULT_MAX_FILE_CHARS = 30_000


@dataclass
class ContextResult:
    text: str
    included_files: list[str] = field(default_factory=list)
    omitted_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _priority(source_file: SourceFile) -> tuple[int, str]:
    """Prefer application source over tests, examples, and generated-looking files."""
    path = PurePosixPath(source_file.path)
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    lower_priority = bool(parts & {"test", "tests", "examples", "example", "fixtures"})
    generated = "generated" in parts or ".min." in name or name.endswith("_pb.py")
    return (2 if generated else 1 if lower_priority else 0, source_file.path.lower())


def build_context(
    scan_result: ScanResult,
    *,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    max_file_chars: int = DEFAULT_MAX_FILE_CHARS,
) -> ContextResult:
    """Create a context string while staying within explicit character limits."""
    if max_context_chars <= 0 or max_file_chars <= 0:
        raise ValueError("Context limits must be greater than zero")

    project_name = scan_result.project_path.name
    header = (
        f"Project: {project_name}\n"
        f"Discovered source files: {len(scan_result.files)}\n\n"
        "Files:\n"
    )
    result = ContextResult(text=header, warnings=list(scan_result.warnings))
    remaining = max_context_chars - len(header)

    for source_file in sorted(scan_result.files, key=_priority):
        content = source_file.content
        file_was_truncated = len(content) > max_file_chars
        if file_was_truncated:
            content = content[:max_file_chars]
            content += "\n... [file truncated by ACV]"

        section = (
            f"\n--- FILE: {source_file.path} ({source_file.file_type}) ---\n"
            f"{content}\n"
            f"--- END FILE: {source_file.path} ---\n"
        )
        if len(section) > remaining:
            result.omitted_files.append(source_file.path)
            continue

        result.text += section
        result.included_files.append(source_file.path)
        remaining -= len(section)
        if file_was_truncated:
            result.warnings.append(
                f"Truncated {source_file.path} to {max_file_chars:,} characters."
            )

    if result.omitted_files:
        result.warnings.append(
            f"Context limit reached: omitted {len(result.omitted_files)} source file(s)."
        )
    return result
