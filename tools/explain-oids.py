#!/usr/bin/env python3
"""
Explain OID Resolution

Takes OIDs (numeric or symbolic) and explains:
- The OBJECT-TYPE (leaf node)
- The index/instance portion
- Whether it's fully resolved or has numeric gaps
"""
from __future__ import annotations

import re
import subprocess
import sys


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def translate_to_numeric(oid: str) -> str | None:
    """Translate any OID to numeric form."""
    proc = run_cmd(["snmptranslate", "-On", oid])
    out = (proc.stdout or "").strip()
    if proc.returncode == 0 and out.startswith("."):
        return out
    return None


def translate_to_symbolic(oid: str) -> str | None:
    """Translate numeric OID to full symbolic form."""
    proc = run_cmd(["snmptranslate", "-Of", oid])
    out = (proc.stdout or "").strip()
    if proc.returncode == 0 and out and not out.startswith(".1"):
        return out
    return None


def get_object_type_info(oid: str) -> str | None:
    """Get -Td output if this is an OBJECT-TYPE."""
    proc = run_cmd(["snmptranslate", "-Td", oid])
    output = (proc.stdout or "")
    if "OBJECT-TYPE" in output:
        return output.strip()
    return None


def split_oid(oid: str) -> list[str]:
    return oid.lstrip(".").split(".")


def join_oid(parts: list[str]) -> str:
    return "." + ".".join(parts)


def analyse_oid(oid: str) -> None:
    """Analyse a single OID and explain its structure."""
    print(f"\n{'='*70}")
    print(f"INPUT: {oid}")
    print("=" * 70)

    # Get numeric form
    numeric = translate_to_numeric(oid)
    if not numeric:
        print("  ✗ Could not translate to numeric form")
        return

    print(f"  Numeric: {numeric}")

    # Get full symbolic form
    symbolic = translate_to_symbolic(numeric)
    if symbolic:
        print(f"  Symbolic: {symbolic}")

        # Check for numeric gaps in symbolic
        if re.search(r"\.\d+", symbolic):
            print("  ⚠ WARNING: Symbolic name contains numeric arcs (incomplete MIB)")
    else:
        print("  ⚠ No symbolic translation available")

    # Walk backwards to find OBJECT-TYPE
    parts = split_oid(numeric)
    leaf_oid = None
    leaf_len = 0

    for i in range(len(parts), 0, -1):
        candidate = join_oid(parts[:i])
        info = get_object_type_info(candidate)
        if info:
            leaf_oid = candidate
            leaf_len = i
            break

    if leaf_oid:
        leaf_symbolic = translate_to_symbolic(leaf_oid)
        index_arcs = parts[leaf_len:]

        print()
        print(f"  OBJECT-TYPE found: {leaf_oid}")
        if leaf_symbolic:
            # Extract just the leaf name
            leaf_name = leaf_symbolic.split(".")[-1]
            print(f"  Leaf name: {leaf_name}")
            print(f"  Full path: {leaf_symbolic}")

        if index_arcs:
            print()
            print(f"  Index portion: .{'.'.join(index_arcs)}")
            print(f"  Index length: {len(index_arcs)} arc(s)")
            print(f"  Index values: {index_arcs}")

            if len(index_arcs) == 1 and index_arcs[0] == "0":
                print("  → This is a SCALAR (instance .0)")
            else:
                print("  → This is a TABLE ENTRY (row index)")
        else:
            print()
            print("  No index portion (this is the OBJECT-TYPE itself)")

        # Show OBJECT-TYPE definition snippet
        info = get_object_type_info(leaf_oid)
        if info:
            print()
            print("  MIB Definition (excerpt):")
            for line in info.split("\n")[:10]:
                print(f"    {line}")
            if info.count("\n") > 10:
                print("    ...")
    else:
        print()
        print("  ✗ No OBJECT-TYPE found in path")
        print("  → This OID cannot be resolved (missing MIB)")

        # Find where it stops
        for i in range(len(parts), 0, -1):
            candidate = join_oid(parts[:i])
            sym = translate_to_symbolic(candidate)
            if sym:
                print(f"  Last resolved: {candidate}")
                print(f"  Last symbolic: {sym}")
                print(f"  Unresolved arc: {parts[i] if i < len(parts) else '(none)'}")
                break


def main() -> None:
    # Read from stdin or command line
    if len(sys.argv) > 1:
        lines = sys.argv[1:]
    else:
        print("Reading OIDs from stdin (paste lines, then Ctrl+D)...")
        lines = sys.stdin.read().strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Extract OID from line (handle "OID = value" format)
        if "=" in line:
            oid = line.split("=")[0].strip()
        else:
            oid = line

        if oid:
            analyse_oid(oid)

    print()


if __name__ == "__main__":
    main()