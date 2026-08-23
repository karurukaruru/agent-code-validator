"""Read-only, project-scoped tools used by the ACV reviewer agent."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .scanner import (
    DEFAULT_MAX_FILE_BYTES,
    IGNORED_DIRECTORIES,
    SUPPORTED_EXTENSIONS,
    ScanError,
    _is_link_like,
    _looks_binary,
)


DEFAULT_MAX_LIST_ENTRIES = 500
DEFAULT_MAX_READ_LINES = 200
DEFAULT_MAX_SEARCH_RESULTS = 40
DEFAULT_SEARCH_CONTEXT_LINES = 1


class ToolError(ValueError):
    """Raised when an agent tool request is invalid or unsafe."""


@dataclass(frozen=True)
class ToolResult:
    """A bounded textual observation returned to the reviewer agent."""

    content: str
    cached: bool = False


class ProjectTools:
    """Expose bounded source inspection without allowing project-root escape."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_list_entries: int = DEFAULT_MAX_LIST_ENTRIES,
        max_read_lines: int = DEFAULT_MAX_READ_LINES,
        max_search_results: int = DEFAULT_MAX_SEARCH_RESULTS,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> None:
        root = Path(project_root).expanduser()
        if not root.exists():
            raise ScanError(f"Project path does not exist: {root}")
        if not root.is_dir():
            raise ScanError(f"Project path is not a directory: {root}")
        if min(max_list_entries, max_read_lines, max_search_results, max_file_bytes) <= 0:
            raise ValueError("Agent tool limits must be greater than zero")

        self.root = root.resolve()
        self.max_list_entries = max_list_entries
        self.max_read_lines = max_read_lines
        self.max_search_results = max_search_results
        self.max_file_bytes = max_file_bytes
        self._cache: dict[tuple[str, str], str] = {}
        self.files_inspected: set[str] = set()
        self.files_observed: set[str] = set()
        self.tool_calls: list[tuple[str, dict[str, object], bool]] = []

    def _relative_text(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _validate_relative_path(self, value: object, *, must_be_file: bool = True) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ToolError("path must be a non-empty project-relative string")
        if "\x00" in value:
            raise ToolError("path contains an invalid NUL character")

        supplied = Path(value.strip())
        if supplied.is_absolute() or supplied.drive or supplied.anchor:
            raise ToolError("absolute paths are not allowed; use a path relative to the project root")
        if any(part == ".." for part in supplied.parts):
            raise ToolError("parent-directory traversal ('..') is not allowed")
        if any(part.lower() in IGNORED_DIRECTORIES for part in supplied.parts):
            raise ToolError("paths inside ignored directories are not available to the agent")

        candidate = self.root.joinpath(supplied)
        current = self.root
        for part in supplied.parts:
            current = current / part
            try:
                if _is_link_like(current):
                    raise ToolError("symbolic links are not available to the agent")
            except OSError as exc:
                raise ToolError(f"could not inspect path component {part!r}: {exc}") from exc

        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(self.root)
        except (OSError, ValueError) as exc:
            raise ToolError("path resolves outside the project root") from exc

        if must_be_file:
            if not resolved.exists():
                raise ToolError(f"file does not exist: {supplied.as_posix()}")
            if not resolved.is_file():
                raise ToolError(f"path is not a file: {supplied.as_posix()}")
        return resolved

    def _source_paths(self) -> list[Path]:
        paths: list[Path] = []

        def ignore_walk_error(_exc: OSError) -> None:
            return

        for current_dir, directory_names, file_names in os.walk(
            self.root, topdown=True, onerror=ignore_walk_error, followlinks=False
        ):
            current = Path(current_dir)
            kept_directories: list[str] = []
            for name in sorted(directory_names, key=str.lower):
                path = current / name
                if name.lower() in IGNORED_DIRECTORIES:
                    continue
                try:
                    if _is_link_like(path):
                        continue
                    path.resolve().relative_to(self.root)
                except (OSError, ValueError):
                    continue
                kept_directories.append(name)
            directory_names[:] = kept_directories

            for name in sorted(file_names, key=str.lower):
                if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                path = current / name
                try:
                    if _is_link_like(path):
                        continue
                    path.resolve().relative_to(self.root)
                except (OSError, ValueError):
                    continue
                paths.append(path)
        return sorted(paths, key=lambda item: self._relative_text(item).lower())

    @staticmethod
    def _cache_key(action: str, arguments: dict[str, object]) -> tuple[str, str]:
        try:
            normalized = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ToolError(f"tool arguments must be JSON values: {exc}") from exc
        return action, normalized

    def source_file_paths(self) -> list[str]:
        """Return all discoverable source paths without reading file contents."""
        return [self._relative_text(path) for path in self._source_paths()]

    def execute(self, action: str, arguments: dict[str, object] | None = None) -> ToolResult:
        arguments = dict(arguments or {})
        key = self._cache_key(action, arguments)
        if key in self._cache:
            self.tool_calls.append((action, arguments, True))
            return ToolResult(self._cache[key], cached=True)

        if action == "list_files":
            result = self.list_files(**arguments)
        elif action == "read_file":
            result = self.read_file(**arguments)
        elif action == "search_code":
            result = self.search_code(**arguments)
        else:
            raise ToolError(f"unknown tool: {action}")
        self._cache[key] = result
        self.tool_calls.append((action, arguments, False))
        return ToolResult(result)

    def list_files(self, limit: int | None = None) -> str:
        """Return a bounded source-file tree using portable relative paths."""
        if limit is None:
            limit = self.max_list_entries
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ToolError("limit must be a positive integer")
        limit = min(limit, self.max_list_entries)

        source_paths = self._source_paths()
        shown = source_paths[:limit]
        lines = [f"Project source files ({len(shown)} shown of {len(source_paths)}):"]
        lines.extend(f"- {self._relative_text(path)}" for path in shown)
        if len(source_paths) > len(shown):
            lines.append(f"... {len(source_paths) - len(shown)} additional source file(s) omitted by limit")
        if not shown:
            lines.append("(no supported source files found)")
        return "\n".join(lines)

    def _read_bytes(self, path: Path) -> bytes:
        try:
            size = path.stat().st_size
            if size > self.max_file_bytes:
                raise ToolError(
                    f"file is larger than the {self.max_file_bytes:,}-byte agent limit"
                )
            with path.open("rb") as source:
                data = source.read(self.max_file_bytes + 1)
        except OSError as exc:
            raise ToolError(f"could not read file: {exc}") from exc
        if len(data) > self.max_file_bytes:
            raise ToolError(f"file grew beyond the {self.max_file_bytes:,}-byte agent limit")
        if _looks_binary(data):
            raise ToolError("file appears to be binary")
        return data

    def read_file(
        self,
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> str:
        """Read at most ``max_read_lines`` lines and include stable line numbers."""
        resolved = self._validate_relative_path(path)
        suffix = resolved.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ToolError(f"unsupported source file type: {suffix or '(no extension)'}")
        if not isinstance(start_line, int) or isinstance(start_line, bool) or start_line < 1:
            raise ToolError("start_line must be a positive integer")
        if end_line is None:
            end_line = start_line + self.max_read_lines - 1
        if not isinstance(end_line, int) or isinstance(end_line, bool) or end_line < start_line:
            raise ToolError("end_line must be an integer greater than or equal to start_line")

        requested_end = end_line
        end_line = min(end_line, start_line + self.max_read_lines - 1)
        data = self._read_bytes(resolved)
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        relative = self._relative_text(resolved)
        self.files_inspected.add(relative)
        self.files_observed.add(relative)

        selected = lines[start_line - 1 : end_line]
        header = f"File: {relative} (lines {start_line}-{min(end_line, len(lines))} of {len(lines)})"
        output = [header]
        output.extend(f"{number:>6} | {line}" for number, line in enumerate(selected, start=start_line))
        if start_line > len(lines):
            output.append("(start_line is past the end of the file)")
        if requested_end > end_line:
            output.append(
                f"... request truncated to {self.max_read_lines} lines; request the next range to continue"
            )
        elif end_line < len(lines):
            output.append(f"... {len(lines) - end_line} line(s) remain")
        return "\n".join(output)

    def search_code(
        self,
        query: str,
        *,
        limit: int | None = None,
        context_lines: int = DEFAULT_SEARCH_CONTEXT_LINES,
    ) -> str:
        """Search source files literally and return bounded line-oriented context."""
        if not isinstance(query, str) or not query.strip():
            raise ToolError("query must be a non-empty string")
        query = query.strip()
        if len(query) > 200:
            raise ToolError("query must not exceed 200 characters")
        if limit is None:
            limit = self.max_search_results
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ToolError("limit must be a positive integer")
        limit = min(limit, self.max_search_results)
        if not isinstance(context_lines, int) or isinstance(context_lines, bool):
            raise ToolError("context_lines must be an integer")
        context_lines = max(0, min(context_lines, 2))

        matches: list[str] = []
        lowered_query = query.casefold()
        for path in self._source_paths():
            try:
                data = self._read_bytes(path)
            except ToolError:
                continue
            lines = data.decode("utf-8", errors="replace").splitlines()
            relative = self._relative_text(path)
            for index, line in enumerate(lines):
                if lowered_query not in line.casefold():
                    continue
                self.files_observed.add(relative)
                start = max(0, index - context_lines)
                end = min(len(lines), index + context_lines + 1)
                matches.append(f"{relative}:{index + 1}")
                for context_index in range(start, end):
                    marker = ">" if context_index == index else " "
                    matches.append(f" {marker} {context_index + 1:>6} | {lines[context_index]}")
                if sum(1 for item in matches if not item.startswith(" ")) >= limit:
                    break
            if sum(1 for item in matches if not item.startswith(" ")) >= limit:
                break

        match_count = sum(1 for item in matches if not item.startswith(" "))
        header = f"Search results for {query!r}: {match_count} match(es) shown"
        if not matches:
            return header + "\n(no matches found)"
        if match_count >= limit:
            matches.append(f"... results stopped at the {limit}-match limit")
        return "\n".join([header, *matches])


AGENT_TOOL_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List supported source files inside the project root.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a bounded line range from one project-relative source file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "minimum": 1},
                    "end_line": {"type": "integer", "minimum": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search supported source files for a literal name, string, import, or call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1},
                    "context_lines": {"type": "integer", "minimum": 0, "maximum": 2},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Stop exploring when enough evidence has been collected.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
                "additionalProperties": False,
            },
        },
    },
]
