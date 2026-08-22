"""Command-line interface for ACV."""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from . import __version__
from .context_builder import DEFAULT_MAX_CONTEXT_CHARS, build_context
from .llm_client import ConfigurationError, LLMClient, LLMError, load_config
from .report_generator import write_report
from .reviewer import ReviewError, ReviewIssue, review_code
from .scanner import ScanError, scan_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="acv",
        description="AI-powered code review for local software projects.",
    )
    parser.add_argument("--version", action="version", version=f"ACV {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="review a local project")
    review.add_argument("project_path", help="path to the project directory")
    review.add_argument(
        "--config",
        default=os.getenv("ACV_CONFIG", "config.json"),
        help="LLM configuration file (default: ./config.json or ACV_CONFIG)",
    )
    review.add_argument(
        "--output",
        default=None,
        help="report destination (default: outputs/<project>_review_<time>.md)",
    )
    review.add_argument(
        "--max-context-chars",
        type=int,
        default=DEFAULT_MAX_CONTEXT_CHARS,
        help=f"maximum LLM context characters (default: {DEFAULT_MAX_CONTEXT_CHARS})",
    )
    return parser


def _default_report_path(project_path: Path) -> Path:
    output_dir = Path(os.getenv("ACV_OUTPUT_DIR", "outputs")).expanduser()
    safe_project_name = re.sub(r"[^\w.-]+", "_", project_path.name).strip("._") or "project"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return output_dir / f"{safe_project_name}_review_{timestamp}.md"


def _print_review_results(issues: list[ReviewIssue]) -> None:
    print()
    print(f"AI review results: {len(issues)} issue(s)")
    if not issues:
        print("No meaningful issues were found in the analyzed files.")
        print()
        return

    for number, issue in enumerate(issues, start=1):
        print(f"\n{number}. [{issue.severity.upper()}] [{issue.category}] {issue.file}:{issue.location}")
        print(f"   Problem: {issue.problem}")
        print(f"   Why it matters: {issue.reason}")
        print(f"   Suggested change: {issue.suggestion}")
    print()


def _run_review(args: argparse.Namespace) -> int:
    # Validate configuration before doing potentially expensive project work.
    config = load_config(args.config)

    print("Scanning project...")
    scan_result = scan_project(args.project_path)
    if not scan_result.files:
        raise ScanError("No supported source files were found in the project")

    print("Building context...")
    context = build_context(scan_result, max_context_chars=args.max_context_chars)
    if not context.included_files:
        raise ReviewError("The context limit is too small to include any source files")
    for warning in context.warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    print("Calling AI reviewer...")
    client = LLMClient(config)
    issues = review_code(client, context.text)
    _print_review_results(issues)

    print("Generating report...")
    output_path = args.output or _default_report_path(scan_result.project_path)
    report_path = write_report(
        output_path,
        project_path=scan_result.project_path,
        files_analyzed=len(context.included_files),
        issues=issues,
        warnings=context.warnings,
    )
    print("Done.")
    print(f"Report saved: {report_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "review":
            return _run_review(args)
    except KeyboardInterrupt:
        print("\nCancelled by user.", file=sys.stderr)
        return 130
    except (ScanError, ConfigurationError, LLMError, ReviewError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
