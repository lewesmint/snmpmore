#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


INT32_MIN = -2_147_483_648
INT32_MAX = 2_147_483_647


@dataclass(frozen=True)
class Issue:
    type_name: str
    message: str


def _is_int32_full_range(con: dict[str, Any]) -> bool:
    return (
        con.get("type") == "ValueRangeConstraint"
        and con.get("min") == INT32_MIN
        and con.get("max") == INT32_MAX
    )


def _range_constraints(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in constraints if c.get("type") == "ValueRangeConstraint"]


def _has_single_value_constraint(constraints: list[dict[str, Any]]) -> bool:
    return any(c.get("type") == "SingleValueConstraint" for c in constraints)


def _has_enums(type_def: dict[str, Any]) -> bool:
    enums = type_def.get("enums")
    return isinstance(enums, list) and len(enums) > 0


def _ranges_overlap_or_contain(r1: tuple[int, int], r2: tuple[int, int]) -> bool:
    a1, b1 = r1
    a2, b2 = r2
    # Containment or equality implies redundancy, overlap implies confusion.
    return not (b1 < a2 or b2 < a1)


def validate_types(tc_map: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    for type_name, type_def_any in tc_map.items():
        if not isinstance(type_def_any, dict):
            issues.append(Issue(type_name, "Type definition is not an object"))
            continue

        type_def: dict[str, Any] = type_def_any
        constraints_any = type_def.get("constraints", [])
        if not isinstance(constraints_any, list):
            issues.append(Issue(type_name, "constraints is not a list"))
            continue

        constraints: list[dict[str, Any]] = []
        for c in constraints_any:
            if isinstance(c, dict):
                constraints.append(c)
            else:
                issues.append(Issue(type_name, "A constraint entry is not an object"))

        # Check 1: enum-like types should not keep inherited full Integer32 range.
        if _has_enums(type_def) or _has_single_value_constraint(constraints):
            if any(_is_int32_full_range(c) for c in constraints):
                issues.append(
                    Issue(
                        type_name,
                        "Enum-like type still contains full Integer32 range constraint",
                    )
                )

        # Check 2: no multiple range constraints that overlap or are redundant.
        ranges = _range_constraints(constraints)
        parsed_ranges: list[tuple[int, int]] = []
        for r in ranges:
            mn = r.get("min")
            mx = r.get("max")
            if not isinstance(mn, int) or not isinstance(mx, int):
                issues.append(Issue(type_name, "Range constraint min/max not ints"))
                continue
            if mn > mx:
                issues.append(Issue(type_name, f"Range constraint inverted: {mn}..{mx}"))
                continue
            parsed_ranges.append((mn, mx))

        for i in range(len(parsed_ranges)):
            for j in range(i + 1, len(parsed_ranges)):
                r1 = parsed_ranges[i]
                r2 = parsed_ranges[j]
                if _ranges_overlap_or_contain(r1, r2):
                    issues.append(
                        Issue(
                            type_name,
                            f"Multiple range constraints overlap or are redundant: {r1} and {r2}",
                        )
                    )

        # Check 3: size constraints sanity (optional but useful)
        # - "set" size should match ValueSizeConstraint entries if present
        size = type_def.get("size")
        if isinstance(size, dict) and size.get("type") == "set":
            allowed = size.get("allowed")
            if isinstance(allowed, list) and all(isinstance(x, int) for x in allowed):
                size_constraints = [
                    c for c in constraints if c.get("type") == "ValueSizeConstraint"
                ]
                if size_constraints:
                    mins = sorted({c["min"] for c in size_constraints if "min" in c})
                    maxs = sorted({c["max"] for c in size_constraints if "max" in c})
                    if mins != maxs or mins != sorted(set(allowed)):
                        issues.append(
                            Issue(
                                type_name,
                                f"Size set {sorted(set(allowed))} does not match ValueSizeConstraint entries",
                            )
                        )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Path to JSON file")
    args = parser.parse_args()

    data = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("ERROR: top-level JSON is not an object", file=sys.stderr)
        return 2

    issues = validate_types(data)
    if not issues:
        print("OK: no issues found")
        return 0

    print(f"FAIL: {len(issues)} issue(s) found")
    for issue in issues:
        print(f"- {issue.type_name}: {issue.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())