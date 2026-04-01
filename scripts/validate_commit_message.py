#!/usr/bin/env python3
"""Validate commit subjects and PR titles against the project format."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ALLOWED_TYPES = (
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "test",
    "chore",
    "perf",
    "ci",
    "build",
)
SUBJECT_LIMIT = 72
RECOMMENDED_SUBJECT_LIMIT = 50
HEADER_RE = re.compile(
    rf"^(?P<type>{'|'.join(ALLOWED_TYPES)})\((?P<scope>[^()]+)\): (?P<subject>.+)$"
)


def _first_non_comment_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _read_header(args: argparse.Namespace) -> str:
    if args.title is not None:
        return args.title.strip()
    if args.commit_msg_file is None:
        raise ValueError("Either --title or --commit-msg-file must be provided")
    return _first_non_comment_line(Path(args.commit_msg_file).read_text(encoding="utf-8"))


def _validate_header(header: str, *, kind: str) -> list[str]:
    errors: list[str] = []
    if not header:
        errors.append(f"{kind} subject is empty")
        return errors

    match = HEADER_RE.fullmatch(header)
    if not match:
        allowed = ", ".join(ALLOWED_TYPES)
        errors.append(
            f"{kind} subject must match <type>(<scope>): <subject>; allowed types: {allowed}"
        )
        return errors

    subject = match.group("subject")
    if len(header) > SUBJECT_LIMIT:
        errors.append(f"{kind} subject must be {SUBJECT_LIMIT} characters or less")
    if subject.endswith("."):
        errors.append(f"{kind} subject should not end with a period")
    return errors


def _warn_header(header: str, *, kind: str) -> list[str]:
    warnings: list[str] = []
    match = HEADER_RE.fullmatch(header)
    if not match:
        return warnings
    subject = match.group("subject")
    if len(subject) > RECOMMENDED_SUBJECT_LIMIT:
        warnings.append(
            f"{kind} subject description is longer than the recommended {RECOMMENDED_SUBJECT_LIMIT} characters"
        )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-msg-file")
    parser.add_argument("--title")
    parser.add_argument("--pr", action="store_true")
    args = parser.parse_args()

    kind = "PR title" if args.pr else "Commit"
    try:
        header = _read_header(args)
    except Exception as exc:
        print(f"Failed to read {kind.lower()}: {exc}", file=sys.stderr)
        return 1

    errors = _validate_header(header, kind=kind)
    if not errors:
        for warning in _warn_header(header, kind=kind):
            print(f"Warning: {warning}", file=sys.stderr)
        return 0

    print(f"Invalid {kind.lower()}: {header or '<empty>'}", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    print("Expected example: fix(ci): align validator backends", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())