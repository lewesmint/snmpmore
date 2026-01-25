#!/usr/bin/env python3
"""
SNMP MIB Walk Analyser

Performs an SNMP walk and analyses the results to determine if all OIDs
can be resolved by installed MIBs. Correctly distinguishes between:
  - Fully resolved OIDs (we have the complete MIB)
  - OIDs with index tails (normal for table entries, we have the MIB)
  - Partially resolved OIDs (stub MIB - has OBJECT-TYPE but incomplete names)
  - Genuinely unresolved OIDs (missing MIB files)

Supports interactive mode for pasting walk output directly.

Streaming output:
  - --stream-unresolved PATH writes unresolved OIDs as they are found.
  - --stream-incomplete PATH writes incomplete (stub) OIDs as they are found.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_HOST = "192.168.1.107"
DEFAULT_COMMUNITY = "public"
DEFAULT_VERSION = "2c"
DEFAULT_BASE_OID = ".1"
DEFAULT_TIMEOUT = 2
DEFAULT_RETRIES = 1

NUMERIC_OID_RE = re.compile(r"^(\.[\d.]+)")
SYMBOLIC_OID_RE = re.compile(r"^(\.?[a-zA-Z][\w.-]*(?:\.[a-zA-Z0-9_-]+)*(?:\.\d+)*)")


@dataclass
class ObjectTypeInfo:
    """Information about a discovered OBJECT-TYPE (leaf node)."""

    numeric_oid: str
    symbolic_name: str | None
    is_complete: bool
    instance_count: int = 0
    index_lengths: Counter[int] = field(default_factory=Counter)
    example_indices: list[list[str]] = field(default_factory=list)


@dataclass(frozen=True)
class StopPoint:
    """Where MIB resolution stopped for an unresolved OID."""

    deepest_resolved_numeric: str
    deepest_resolved_symbolic: str
    next_arc: str


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def split_oid(oid: str) -> list[str]:
    """Split a numeric OID into its arc components."""
    return oid.lstrip(".").split(".")


def join_oid(parts: list[str]) -> str:
    """Join arc components back into a numeric OID."""
    return "." + ".".join(parts)


def has_numeric_arcs(symbolic_oid: str) -> tuple[bool, str]:
    """
    Check if a symbolic OID contains numeric arcs (indicating incomplete MIB).

    Returns:
        (has_numeric, reason)
    """
    parts = symbolic_oid.lstrip(".").split(".")

    numeric_parts = []
    for i, part in enumerate(parts):
        if part.isdigit():
            numeric_parts.append((i, part))

    if numeric_parts:
        positions = [f"parts[{i}]='{p}'" for i, p in numeric_parts]
        reason = f"Numeric arcs found: {', '.join(positions)}"
        return True, reason

    return False, "All arcs are symbolic"


@lru_cache(maxsize=250_000)
def check_object_type(numeric_oid: str, mibdirs: str | None) -> bool:
    """
    Check if snmptranslate -Td returns a real OBJECT-TYPE for this OID.

    A real OBJECT-TYPE must have both "OBJECT-TYPE" and "SYNTAX" in its
    definition.
    """
    cmd = ["snmptranslate", "-Td", numeric_oid]
    if mibdirs:
        cmd[1:1] = ["-M", mibdirs]
    proc = run_cmd(cmd)
    output = (proc.stdout or "") + (proc.stderr or "")
    return "OBJECT-TYPE" in output and "SYNTAX" in output


@lru_cache(maxsize=250_000)
def translate_to_numeric(oid: str, mibdirs: str | None) -> str | None:
    """Translate any OID to numeric form."""
    cmd = ["snmptranslate", "-On", oid]
    if mibdirs:
        cmd[1:1] = ["-M", mibdirs]
    proc = run_cmd(cmd)
    out = (proc.stdout or "").strip()
    if proc.returncode == 0 and out.startswith("."):
        return out
    return None


@lru_cache(maxsize=250_000)
def translate_to_symbolic(numeric_oid: str, mibdirs: str | None) -> str | None:
    """Translate a numeric OID to symbolic form."""
    cmd = ["snmptranslate", "-Of", numeric_oid]
    if mibdirs:
        cmd[1:1] = ["-M", mibdirs]
    proc = run_cmd(cmd)
    out = (proc.stdout or "").strip()
    if proc.returncode == 0 and out and not out.startswith(".1"):
        return out
    return None


def find_object_type(
    numeric_oid: str,
    mibdirs: str | None,
) -> tuple[str | None, int, bool, str]:
    """
    Find the OBJECT-TYPE leaf within a numeric OID.

    Returns the SHORTEST prefix that is an OBJECT-TYPE (the actual column).
    """
    parts = split_oid(numeric_oid)

    first_object_type_len = 0
    for i in range(len(parts), 0, -1):
        candidate = join_oid(parts[:i])
        if check_object_type(candidate, mibdirs):
            first_object_type_len = i
            break

    if first_object_type_len == 0:
        return None, 0, False, "No OBJECT-TYPE found"

    shortest_object_type_len = first_object_type_len
    for i in range(first_object_type_len - 1, 0, -1):
        candidate = join_oid(parts[:i])
        if check_object_type(candidate, mibdirs):
            shortest_object_type_len = i
        else:
            break

    leaf_oid = join_oid(parts[:shortest_object_type_len])

    symbolic = translate_to_symbolic(leaf_oid, mibdirs)
    if symbolic is None:
        return leaf_oid, shortest_object_type_len, False, "No symbolic translation"

    has_numeric, reason = has_numeric_arcs(symbolic)
    is_complete = not has_numeric
    return leaf_oid, shortest_object_type_len, is_complete, reason


def find_deepest_resolved(
    numeric_oid: str,
    mibdirs: str | None,
) -> tuple[str, str | None, str]:
    """For an unresolved OID, find where translation stops."""
    parts = split_oid(numeric_oid)
    if not parts:
        return ".", None, ""

    lo, hi = 1, len(parts)
    best_len = 0
    best_sym: str | None = None

    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = join_oid(parts[:mid])
        sym = translate_to_symbolic(candidate, mibdirs)
        if sym is not None:
            best_len = mid
            best_sym = sym
            lo = mid + 1
        else:
            hi = mid - 1

    if best_len == 0:
        return ".", None, parts[0] if parts else ""

    deepest_num = join_oid(parts[:best_len])
    next_arc = parts[best_len] if best_len < len(parts) else ""
    return deepest_num, best_sym, next_arc


def bucket_from_oid(numeric_oid: str) -> str:
    """Coarse grouping to hint what MIB family might be missing."""
    parts = split_oid(numeric_oid)

    if len(parts) >= 7 and parts[:6] == ["1", "3", "6", "1", "4", "1"]:
        return f"enterprises.{parts[6]}"

    if len(parts) >= 3 and parts[:3] == ["1", "0", "8802"]:
        return "iso.0.8802 (IEEE 802)"

    if len(parts) >= 7 and parts[:6] == ["1", "3", "6", "1", "2", "1"]:
        return f"mib-2.{parts[6]}"

    return "other"


def extract_oid_from_line(line: str) -> str | None:
    """Extract OID from a walk output line (handles both numeric and symbolic)."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if "=" in line:
        line = line.split("=")[0].strip()

    if line.startswith(".") and line[1:2].isdigit():
        match = NUMERIC_OID_RE.match(line)
        if match:
            return match.group(1)

    match = SYMBOLIC_OID_RE.match(line)
    if match:
        return match.group(1)

    return None


def analyse_single_oid(oid: str, mibdirs: str | None) -> None:
    """Analyse a single OID and print detailed results."""
    print(f"\n{'=' * 70}")
    print(f"INPUT: {oid}")
    print("=" * 70)

    numeric_oid: str
    if oid.startswith(".") and oid[1:2].isdigit():
        numeric_oid = oid
    else:
        translated = translate_to_numeric(oid, mibdirs)
        if translated is None:
            print("  Could not translate to numeric form")
            return
        numeric_oid = translated

    print(f"  Numeric: {numeric_oid}")

    full_symbolic = translate_to_symbolic(numeric_oid, mibdirs)
    if full_symbolic:
        print(f"  Full symbolic: {full_symbolic}")

    leaf_oid, leaf_len, is_complete, reason = find_object_type(numeric_oid, mibdirs)

    if leaf_oid is None:
        print()
        print("  NO OBJECT-TYPE FOUND - Missing MIB")
        deepest_num, deepest_sym, next_arc = find_deepest_resolved(numeric_oid, mibdirs)
        print(f"  Last resolved: {deepest_num}")
        if deepest_sym:
            print(f"  Last symbolic: {deepest_sym}")
        print(f"  Missing arc: {next_arc}")
        return

    leaf_symbolic = translate_to_symbolic(leaf_oid, mibdirs)
    parts = split_oid(numeric_oid)
    index_arcs = parts[leaf_len:]

    print()
    print(f"  OBJECT-TYPE: {leaf_oid}")
    if leaf_symbolic:
        leaf_name = leaf_symbolic.split(".")[-1]
        print(f"  Leaf name: {leaf_name}")
        print(f"  Leaf path: {leaf_symbolic}")

    if index_arcs:
        print()
        print(f"  Index: .{'.'.join(index_arcs)}")
        print(f"  Index length: {len(index_arcs)} arc(s)")
        if len(index_arcs) == 1 and index_arcs[0] == "0":
            print("  SCALAR instance (.0)")
        else:
            print("  TABLE ROW instance")

    print()
    if is_complete:
        print("  COMPLETE - MIB fully defines this OBJECT-TYPE")
    else:
        print("  INCOMPLETE - Stub MIB (numeric arcs in symbolic name)")
        print(f"    Reason: {reason}")


def interactive_mode(mibdirs: str | None) -> None:
    """Run interactive mode - paste walk output, get analysis."""
    print("=" * 70)
    print("SNMP MIB ANALYSER - INTERACTIVE MODE")
    print("=" * 70)
    print()
    print("Paste walk output lines (OID = value format).")
    print("Press Ctrl+D (Unix) or Ctrl+Z (Windows) when done.")
    print("Or type 'quit' or 'exit' to stop.")
    print()

    complete_count = 0
    incomplete_count = 0
    unresolved_count = 0

    while True:
        try:
            print("-" * 70)
            line = input("Paste OID> ").strip()
        except EOFError:
            break

        if not line:
            continue

        if line.lower() in ("quit", "exit", "q"):
            break

        oid = extract_oid_from_line(line)
        if oid is None:
            print("  Could not extract OID from line")
            continue

        numeric_oid: str
        if oid.startswith(".") and oid[1:2].isdigit():
            numeric_oid = oid
        else:
            translated = translate_to_numeric(oid, mibdirs)
            if translated is None:
                print(f"  Could not translate '{oid}' to numeric")
                unresolved_count += 1
                continue
            numeric_oid = translated

        leaf_oid, leaf_len, is_complete, reason = find_object_type(numeric_oid, mibdirs)

        if leaf_oid is None:
            deepest_num, deepest_sym, next_arc = find_deepest_resolved(numeric_oid, mibdirs)
            print("  UNRESOLVED")
            print(f"    Last resolved: {deepest_sym or deepest_num}")
            print(f"    Missing arc: {next_arc}")
            unresolved_count += 1
            continue

        leaf_symbolic = translate_to_symbolic(leaf_oid, mibdirs)
        parts = split_oid(numeric_oid)
        index_arcs = parts[leaf_len:]

        if is_complete:
            leaf_name = leaf_symbolic.split(".")[-1] if leaf_symbolic else leaf_oid
            index_str = f".{'.'.join(index_arcs)}" if index_arcs else ""
            print(f"  COMPLETE: {leaf_name}{index_str}")
            complete_count += 1
        else:
            print(f"  INCOMPLETE: {leaf_symbolic or leaf_oid}")
            print(f"    {reason}")
            incomplete_count += 1

    print()
    print("=" * 70)
    print("SESSION SUMMARY")
    print("=" * 70)
    print(f"  Complete:   {complete_count}")
    print(f"  Incomplete: {incomplete_count}")
    print(f"  Unresolved: {unresolved_count}")


def do_snmpwalk(
    host: str,
    community: str,
    version: str,
    base_oid: str,
    timeout: int,
    retries: int,
) -> list[str]:
    """Perform an SNMP walk and return list of numeric OIDs."""
    cmd = [
        "snmpwalk",
        f"-v{version}",
        "-c",
        community,
        "-On",
        "-OQ",
        "-t",
        str(timeout),
        "-r",
        str(retries),
        host,
        base_oid,
    ]

    print(f"Running SNMP walk on {host}...", file=sys.stderr)

    proc = run_cmd(cmd)
    if proc.returncode != 0:
        raise RuntimeError(
            f"snmpwalk failed (exit code {proc.returncode})\n"
            f"Command: {' '.join(cmd)}\n"
            f"stderr: {proc.stderr}\n"
            f"stdout: {proc.stdout}"
        )

    oids: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        oid_part = line.split("=")[0].strip()
        if oid_part.startswith("."):
            oids.append(oid_part)

    print(f"  Collected {len(oids)} OIDs", file=sys.stderr)
    return oids


@dataclass
class AnalysisResults:
    """Results from analysing walked OIDs."""

    object_types: dict[str, ObjectTypeInfo]
    incomplete_oids: list[tuple[str, str, str | None, str]]
    unresolved: list[tuple[str, StopPoint]]


def analyse_walk(
    oids: list[str],
    mibdirs: str | None,
    max_oids: int | None,
    verbose: bool,
    verify: bool,
    stream_unresolved: Path | None,
    stream_incomplete: Path | None,
    stream_flush_every: int,
    host: str,
) -> AnalysisResults:
    """Analyse walked OIDs for MIB coverage."""
    if max_oids is not None:
        oids = oids[:max_oids]

    total = len(oids)
    object_types: dict[str, ObjectTypeInfo] = {}
    incomplete_oids: list[tuple[str, str, str | None, str]] = []
    unresolved: list[tuple[str, StopPoint]] = []
    verified_incomplete: set[str] = set()

    complete_count = 0
    incomplete_count = 0

    print(f"\nAnalysing {total} OIDs for MIB coverage...", file=sys.stderr)

    progress_interval = max(1, total // 20)

    unresolved_fh = stream_unresolved.open("a", encoding="utf-8") if stream_unresolved else None
    incomplete_fh = stream_incomplete.open("a", encoding="utf-8") if stream_incomplete else None
    stream_writes = 0

    def stream_line(fh: Any, line: str) -> None:
        nonlocal stream_writes
        if fh is None:
            return
        fh.write(line + "\n")
        stream_writes += 1
        if stream_flush_every > 0 and (stream_writes % stream_flush_every) == 0:
            fh.flush()

    if unresolved_fh:
        stream_line(
            unresolved_fh,
            f"# stream start {datetime.now().isoformat()} host={host} total_oids={total}",
        )
        unresolved_fh.flush()

    if incomplete_fh:
        stream_line(
            incomplete_fh,
            f"# stream start {datetime.now().isoformat()} host={host} total_oids={total}",
        )
        incomplete_fh.flush()

    try:
        for idx, oid in enumerate(oids, 1):
            parts = split_oid(oid)
            leaf_oid, leaf_len, is_complete, reason = find_object_type(oid, mibdirs)

            if leaf_oid is not None:
                if leaf_oid not in object_types:
                    symbolic = translate_to_symbolic(leaf_oid, mibdirs)
                    object_types[leaf_oid] = ObjectTypeInfo(
                        numeric_oid=leaf_oid,
                        symbolic_name=symbolic,
                        is_complete=is_complete,
                    )

                info = object_types[leaf_oid]
                info.instance_count += 1

                index_arcs = parts[leaf_len:]
                index_len = len(index_arcs)
                info.index_lengths[index_len] += 1

                if len(info.example_indices) < 3:
                    info.example_indices.append(index_arcs)

                if is_complete:
                    complete_count += 1
                else:
                    incomplete_count += 1
                    incomplete_oids.append((oid, leaf_oid, info.symbolic_name, reason))

                    stream_line(
                        incomplete_fh,
                        " | ".join(
                            [
                                datetime.now().isoformat(timespec="seconds"),
                                f"OID={oid}",
                                f"leaf={leaf_oid}",
                                f"leaf_sym={info.symbolic_name or '(none)'}",
                                f"reason={reason}",
                                f"index_len={index_len}",
                            ]
                        ),
                    )

                    if verify and leaf_oid not in verified_incomplete:
                        verified_incomplete.add(leaf_oid)
                        print(f"\n{'=' * 60}", file=sys.stderr)
                        print(f"VERIFYING INCOMPLETE: {oid}", file=sys.stderr)
                        print(f"  Leaf OID (OBJECT-TYPE): {leaf_oid}", file=sys.stderr)
                        print(f"  Leaf Symbolic: {info.symbolic_name}", file=sys.stderr)
                        print(f"  Reason: {reason}", file=sys.stderr)
                        print(f"  Index arcs: {index_arcs}", file=sys.stderr)
                        print(f"{'=' * 60}", file=sys.stderr)

                if verbose:
                    status = "COMPLETE" if is_complete else "INCOMPLETE"
                    print(
                        f"  [{status}] {oid} -> {leaf_oid} + {index_len} index arcs",
                        file=sys.stderr,
                    )
                    if not is_complete:
                        print(f"    Reason: {reason}", file=sys.stderr)
            else:
                deepest_num, deepest_sym, next_arc = find_deepest_resolved(oid, mibdirs)
                sp = StopPoint(
                    deepest_resolved_numeric=deepest_num,
                    deepest_resolved_symbolic=deepest_sym or "(none)",
                    next_arc=next_arc or "(end)",
                )
                unresolved.append((oid, sp))

                stream_line(
                    unresolved_fh,
                    " | ".join(
                        [
                            datetime.now().isoformat(timespec="seconds"),
                            f"OID={oid}",
                            f"bucket={bucket_from_oid(oid)}",
                            f"last_num={sp.deepest_resolved_numeric}",
                            f"last_sym={sp.deepest_resolved_symbolic}",
                            f"next_arc={sp.next_arc}",
                        ]
                    ),
                )

                if verbose:
                    print(f"  [UNRESOLVED] {oid}", file=sys.stderr)

            if idx % progress_interval == 0 or idx == total:
                pct = (idx * 100) // total
                print(
                    f"Progress: {idx}/{total} ({pct}%) - "
                    f"Complete: {complete_count}, "
                    f"Incomplete: {incomplete_count}, "
                    f"Unresolved: {len(unresolved)}",
                    file=sys.stderr,
                )
    finally:
        if unresolved_fh:
            unresolved_fh.flush()
            unresolved_fh.close()
        if incomplete_fh:
            incomplete_fh.flush()
            incomplete_fh.close()

    return AnalysisResults(
        object_types=object_types,
        incomplete_oids=incomplete_oids,
        unresolved=unresolved,
    )


def write_unresolved_file(path: Path, results: AnalysisResults) -> None:
    """Write unresolved OIDs to a file, grouped by where resolution stops."""
    stop_point_groups: dict[StopPoint, list[str]] = defaultdict(list)
    for oid, sp in results.unresolved:
        stop_point_groups[sp].append(oid)

    with path.open("w", encoding="utf-8") as f:
        f.write("# Unresolved OIDs - Missing MIB Files\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n")
        f.write(f"# Total unresolved: {len(results.unresolved)}\n\n")

        for sp, oid_list in sorted(
            stop_point_groups.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        ):
            f.write("=" * 70 + "\n")
            f.write(f"MISSING MIB - {len(oid_list)} OIDs affected\n")
            f.write("=" * 70 + "\n")
            f.write(f"Last resolved numeric: {sp.deepest_resolved_numeric}\n")
            f.write(f"Last resolved symbolic: {sp.deepest_resolved_symbolic}\n")
            f.write(f"First unresolved arc:  {sp.next_arc}\n\n")
            f.write("Affected OIDs:\n")
            for oid in sorted(oid_list):
                f.write(f"  {oid}\n")
            f.write("\n")

    print(f"Unresolved OIDs written to: {path}", file=sys.stderr)


def write_log_file(log_path: Path, host: str, results: AnalysisResults) -> None:
    """Write detailed log of OBJECT-TYPEs and their indices."""
    with log_path.open("w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("SNMP MIB COVERAGE ANALYSIS LOG\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Host: {host}\n")
        f.write(f"Total OBJECT-TYPEs discovered: {len(results.object_types)}\n")

        complete_types = [i for i in results.object_types.values() if i.is_complete]
        incomplete_types = [i for i in results.object_types.values() if not i.is_complete]

        f.write(f"Complete OBJECT-TYPEs: {len(complete_types)}\n")
        f.write(f"Incomplete OBJECT-TYPEs (stub MIBs): {len(incomplete_types)}\n")
        f.write(f"Total unresolved OIDs: {len(results.unresolved)}\n\n")

    print(f"Log written to: {log_path}", file=sys.stderr)


def print_summary(results: AnalysisResults) -> None:
    """Print summary to stdout."""
    total_instances = sum(info.instance_count for info in results.object_types.values())
    complete_instances = sum(
        info.instance_count for info in results.object_types.values() if info.is_complete
    )
    incomplete_instances = sum(
        info.instance_count for info in results.object_types.values() if not info.is_complete
    )
    total_unresolved = len(results.unresolved)
    total = total_instances + total_unresolved

    print()
    print("=" * 60)
    print("MIB COVERAGE ANALYSIS RESULTS")
    print("=" * 60)
    print(f"Total OIDs analysed:         {total}")
    print(f"Fully resolved OIDs:         {complete_instances}")
    print(f"Incomplete MIB (stub) OIDs:  {incomplete_instances}")
    print(f"Unresolved OIDs:             {total_unresolved}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Perform an SNMP walk and analyse MIB coverage.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--community", default=DEFAULT_COMMUNITY)
    parser.add_argument("--version", default=DEFAULT_VERSION, choices=["1", "2c", "3"])
    parser.add_argument("--base-oid", default=DEFAULT_BASE_OID)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--mibdirs", default=None)
    parser.add_argument("--max-oids", type=int, default=None)
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--unresolved-file", type=Path, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("-i", "--interactive", action="store_true")
    parser.add_argument("--oid", default=None)

    parser.add_argument(
        "--stream-unresolved",
        type=Path,
        default=None,
        help="Append unresolved OIDs as they are found (one line per event).",
    )
    parser.add_argument(
        "--stream-incomplete",
        type=Path,
        default=None,
        help="Append incomplete (stub) OIDs as they are found (one line per event).",
    )
    parser.add_argument(
        "--stream-flush-every",
        type=int,
        default=50,
        help="Flush stream files every N writes (default: 50).",
    )

    args = parser.parse_args()

    if args.oid:
        analyse_single_oid(args.oid, args.mibdirs)
        return

    if args.interactive:
        interactive_mode(args.mibdirs)
        return

    oids = do_snmpwalk(
        host=args.host,
        community=args.community,
        version=args.version,
        base_oid=args.base_oid,
        timeout=args.timeout,
        retries=args.retries,
    )

    if not oids:
        print("No OIDs collected from walk!", file=sys.stderr)
        sys.exit(1)

    results = analyse_walk(
        oids=oids,
        mibdirs=args.mibdirs,
        max_oids=args.max_oids,
        verbose=args.verbose,
        verify=args.verify,
        stream_unresolved=args.stream_unresolved,
        stream_incomplete=args.stream_incomplete,
        stream_flush_every=args.stream_flush_every,
        host=args.host,
    )

    if args.log_file:
        write_log_file(args.log_file, args.host, results)

    if args.unresolved_file:
        write_unresolved_file(args.unresolved_file, results)

    print_summary(results)

    if results.unresolved:
        sys.exit(2)
    if results.incomplete_oids:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()