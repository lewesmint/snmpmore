#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Defn:
    name: str
    kind: str
    oid_raw: Optional[str]
    oid_num: Optional[str]
    sig: str
    file: Path
    line: int


RESERVED_NAMES = {
    "ACCESS",
    "AUGMENTS",
    "BEGIN",
    "CONTACT-INFO",
    "DEFINITIONS",
    "DEFVAL",
    "DESCRIPTION",
    "DISPLAY-HINT",
    "END",
    "ENTERPRISE",
    "EXPORTS",
    "FROM",
    "IDENTIFIER",
    "IMPORTS",
    "INDEX",
    "LAST-UPDATED",
    "MAX-ACCESS",
    "MIN-ACCESS",
    "MODULE-IDENTITY",
    "NOTIFICATIONS",
    "OBJECTS",
    "ORGANIZATION",
    "REFERENCE",
    "REVISION",
    "STATUS",
    "SYNTAX",
    "TEXTUAL-CONVENTION",
    "TRAP-TYPE",
    "UNITS",
    "VARIABLES",
    "WRITE-SYNTAX",
}

KIND_RE = re.compile(
    r"""
    ^[ \t]*
    (?P<name>[A-Za-z][A-Za-z0-9-]*)
    [ \t]+
    (?P<kind>
        OBJECT\s+IDENTIFIER|
        OBJECT-TYPE|
        MODULE-IDENTITY|
        NOTIFICATION-TYPE|
        TEXTUAL-CONVENTION|
        OBJECT-GROUP|
        NOTIFICATION-GROUP|
        TRAP-TYPE
    )
    \b
    """,
    re.VERBOSE | re.MULTILINE,
)

OID_IN_BLOCK_RE = re.compile(r"::=\s*\{\s*(?P<body>[^}]+)\s*\}", re.MULTILINE)
COMMENT_RE = re.compile(r"--.*?$", re.MULTILINE)
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*|\d+")

# Replace quoted strings with spaces so offsets stay stable.
# Handles multi-line DESCRIPTION strings and doubled quotes "".
QUOTED_STRING_RE = re.compile(r'"(?:[^"]|"")*?"', re.DOTALL)

SYNTAX_RE = re.compile(
    r"(?m)^[ \t]*SYNTAX[ \t]+(?P<body>.+?)(?=\n[ \t]*[A-Z][A-Z-]*\b|\n[ \t]*::=|\Z)",
    re.DOTALL,
)
MAX_ACCESS_RE = re.compile(r"(?m)^[ \t]*MAX-ACCESS[ \t]+(?P<body>.+)$")
ACCESS_RE = re.compile(r"(?m)^[ \t]*ACCESS[ \t]+(?P<body>.+)$")
STATUS_RE = re.compile(r"(?m)^[ \t]*STATUS[ \t]+(?P<body>.+)$")
DISPLAY_HINT_RE = re.compile(r"(?m)^[ \t]*DISPLAY-HINT[ \t]+(?P<body>.+)$")
INDEX_RE = re.compile(r"(?m)^[ \t]*INDEX[ \t]+\{\s*(?P<body>[^}]+)\s*\}")
AUGMENTS_RE = re.compile(r"(?m)^[ \t]*AUGMENTS[ \t]+\{\s*(?P<body>[^}]+)\s*\}")
DEFVAL_RE = re.compile(r"(?m)^[ \t]*DEFVAL[ \t]+\{\s*(?P<body>[^}]+)\s*\}")


def _strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


def _strip_quoted_strings_keep_len(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        return " " * (m.end() - m.start())

    return QUOTED_STRING_RE.sub(repl, text)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for m in re.finditer(r"\n", text):
        starts.append(m.end())
    return starts


def _line_for_offset(starts: list[int], offset: int) -> int:
    lo = 0
    hi = len(starts) - 1
    best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if starts[mid] <= offset:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best + 1


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _extract_first(regex: re.Pattern[str], text: str) -> Optional[str]:
    m = regex.search(text)
    if not m:
        return None
    return _collapse_ws(m.group("body"))


def _normalise_oid(body: str) -> Optional[str]:
    tokens = TOKEN_RE.findall(body)
    if not tokens:
        return None
    return " ".join(tokens)


def _oid_raw_to_numbers(oid_raw: str) -> Optional[str]:
    parts = oid_raw.split()
    if not parts:
        return None

    if all(p.isdigit() for p in parts):
        return ".".join(parts)

    digits: list[str] = []
    i = 0
    while i < len(parts):
        if parts[i].isdigit():
            digits.append(parts[i])
            i += 1
            continue
        if i + 1 < len(parts) and parts[i + 1].isdigit():
            digits.append(parts[i + 1])
            i += 2
            continue
        return None

    return ".".join(digits) if digits else None


def _definition_signature(kind: str, block: str, oid_raw: Optional[str]) -> str:
    kind_norm = " ".join(kind.split())
    block_nc = _strip_comments(block)

    if kind_norm == "OBJECT IDENTIFIER":
        payload = f"oid={oid_raw or '-'}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    parts: list[str] = [f"kind={kind_norm}"]

    syntax = _extract_first(SYNTAX_RE, block_nc)
    if syntax:
        parts.append(f"syntax={syntax}")

    max_access = _extract_first(MAX_ACCESS_RE, block_nc)
    if max_access:
        parts.append(f"max-access={max_access}")
    else:
        access = _extract_first(ACCESS_RE, block_nc)
        if access:
            parts.append(f"access={access}")

    status = _extract_first(STATUS_RE, block_nc)
    if status:
        parts.append(f"status={status}")

    if kind_norm == "TEXTUAL-CONVENTION":
        display_hint = _extract_first(DISPLAY_HINT_RE, block_nc)
        if display_hint:
            parts.append(f"display-hint={display_hint}")

    index = _extract_first(INDEX_RE, block_nc)
    if index:
        parts.append(f"index={index}")

    augments = _extract_first(AUGMENTS_RE, block_nc)
    if augments:
        parts.append(f"augments={augments}")

    defval = _extract_first(DEFVAL_RE, block_nc)
    if defval:
        parts.append(f"defval={defval}")

    parts.append(f"oid={oid_raw or '-'}")

    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _iter_files(roots: list[Path], exts: tuple[str, ...]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for root in roots:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in exts:
                continue
            rp = p.resolve()
            if rp in seen:
                continue
            seen.add(rp)
            out.append(rp)
    return out


def _parse_defs(path: Path) -> list[Defn]:
    text = _read_text(path)
    text = _strip_comments(text)

    scan_text = _strip_quoted_strings_keep_len(text)
    starts = _line_starts(text)

    matches_all = list(KIND_RE.finditer(scan_text))
    if not matches_all:
        return []

    matches: list[re.Match[str]] = []
    for m in matches_all:
        name = m.group("name")
        if name.upper() in RESERVED_NAMES:
            continue
        matches.append(m)

    if not matches:
        return []

    defs: list[Defn] = []
    for idx, m in enumerate(matches):
        name = m.group("name")
        kind = " ".join(m.group("kind").split())
        line = _line_for_offset(starts, m.start())

        block_start = m.start()
        block_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[block_start:block_end]

        # IMPORTANT: only accept a "definition" if it actually assigns an OID.
        # This prevents SEQUENCE members like:
        #   agentxRegStart OBJECT IDENTIFIER,
        # from being treated as top-level defs.
        oid_m = OID_IN_BLOCK_RE.search(block)
        if not oid_m:
            continue

        oid_raw = _normalise_oid(oid_m.group("body"))
        oid_num = _oid_raw_to_numbers(oid_raw) if oid_raw else None
        sig = _definition_signature(kind, block, oid_raw)

        defs.append(
            Defn(
                name=name,
                kind=kind,
                oid_raw=oid_raw,
                oid_num=oid_num,
                sig=sig,
                file=path,
                line=line,
            )
        )

    return defs


def _resolve_numeric_oids(defs: list[Defn]) -> list[Defn]:
    """
    Best-effort resolver:
    - Only resolve numeric OIDs for defs that actually have oid_raw.
    - Never "inherit" an oid_num for a different def just because it shares the same name.
    """
    # Seed with any already-known numeric OIDs.
    known_num: dict[str, str] = {}
    for d in defs:
        if d.oid_raw and d.oid_num:
            known_num[d.name] = d.oid_num

    # We will iteratively resolve parent chains of the form: "{ parent 7 9 }"
    changed = True
    for _ in range(400):
        if not changed:
            break
        changed = False

        for d in defs:
            if not d.oid_raw:
                continue
            if d.name in known_num:
                continue

            parts = d.oid_raw.split()
            if len(parts) >= 2 and (not parts[0].isdigit()) and all(p.isdigit() for p in parts[1:]):
                parent_num = known_num.get(parts[0])
                if parent_num:
                    known_num[d.name] = ".".join([*parent_num.split("."), *parts[1:]])
                    changed = True

    out: list[Defn] = []
    for d in defs:
        resolved_num = d.oid_num
        if d.oid_raw and not resolved_num:
            resolved_num = known_num.get(d.name)

        out.append(
            Defn(
                name=d.name,
                kind=d.kind,
                oid_raw=d.oid_raw,
                oid_num=resolved_num,
                sig=d.sig,
                file=d.file,
                line=d.line,
            )
        )
    return out


def _fmt_def(d: Defn) -> str:
    raw = d.oid_raw or "-"
    num = d.oid_num or "-"
    return (
        f"{d.file}:{d.line}: {d.kind:18} "
        f"oid_raw={raw:40} oid_num={num:25} sig={d.sig}"
    )


def _report(defs: list[Defn]) -> int:
    issues = 0

    by_name: dict[str, list[Defn]] = {}
    for d in defs:
        by_name.setdefault(d.name, []).append(d)

    for name, items in sorted(by_name.items()):
        if len(items) < 2:
            continue
        oid_keys = [i.oid_num or i.oid_raw or "-" for i in items]
        unique_oids = sorted(set(oid_keys))
        if len(unique_oids) > 1:
            issues += 1
            print(f"\nNAME REUSED DIFFERENT OID: {name}")
            print(f"  OIDs: {', '.join(unique_oids)}")
            for i in sorted(items, key=lambda x: (x.oid_num or x.oid_raw or "", str(x.file), x.line)):
                print(f"  {_fmt_def(i)}")

    for name, items in sorted(by_name.items()):
        if len(items) < 2:
            continue
        groups: dict[str, list[Defn]] = {}
        for i in items:
            oid_key = i.oid_num or i.oid_raw or "-"
            groups.setdefault(oid_key, []).append(i)

        for oid_key, g in sorted(groups.items(), key=lambda x: x[0]):
            if len(g) < 2:
                continue
            sigs = {i.sig for i in g}
            if len(sigs) > 1:
                issues += 1
                print(f"\nSAME NAME+OID BUT DIFFERENT DEFINITION: {name}  oid={oid_key}")
                for i in sorted(g, key=lambda x: (str(x.file), x.line)):
                    print(f"  {_fmt_def(i)}")

    by_oid: dict[str, list[Defn]] = {}
    for d in defs:
        if d.oid_num:
            by_oid.setdefault(d.oid_num, []).append(d)

    for oid, items in sorted(by_oid.items(), key=lambda x: x[0]):
        if len(items) < 2:
            continue
        names = {i.name for i in items}
        if len(names) <= 1:
            continue
        issues += 1
        print(f"\nOID COLLISION (same OID, different names): {oid}")
        for i in sorted(items, key=lambda x: (x.name, str(x.file), x.line)):
            print(f"  {_fmt_def(i)}")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan MIB files for name reuse, OID collisions, and conflicting redefinitions."
    )
    parser.add_argument("roots", nargs="*", type=Path, help="Root directories (repeatable).")
    parser.add_argument(
        "--root",
        action="append",
        dest="roots_opt",
        default=[],
        type=Path,
        help="Root directory (repeatable).",
    )
    parser.add_argument(
        "--ext",
        action="append",
        default=[".mib", ".txt"],
        help="File extension to include (repeatable). Default: .mib and .txt",
    )
    parser.add_argument(
        "--no-resolve",
        action="store_true",
        help="Do not attempt to resolve symbolic OIDs to numeric dotted form.",
    )

    args = parser.parse_args()
    roots: list[Path] = [*args.roots_opt, *args.roots]
    if not roots:
        print("No roots supplied. Pass one or more folders.", file=sys.stderr)
        return 2

    for r in roots:
        if not r.exists():
            print(f"Root not found: {r}", file=sys.stderr)
            return 2

    exts = tuple(e.lower() if e.startswith(".") else f".{e.lower()}" for e in args.ext)
    files = _iter_files(roots, exts)
    if not files:
        print(f"No files found in roots with extensions {exts}", file=sys.stderr)
        return 2

    defs: list[Defn] = []
    for f in files:
        try:
            defs.extend(_parse_defs(f))
        except Exception as exc:  # noqa: BLE001
            print(f"Failed parsing {f}: {exc}", file=sys.stderr)

    if not args.no_resolve:
        defs = _resolve_numeric_oids(defs)

    print(f"Scanned {len(files)} files, found {len(defs)} definitions.")
    issues = _report(defs)

    print("\nSummary")
    print(f"  Issues reported: {issues}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())