from __future__ import annotations

import argparse
import inspect
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, TypedDict, cast

import pysnmp.entity.engine as _engine
import pysnmp.proto.rfc1902 as _rfc1902
import pysnmp.smi.builder as _builder

JsonDict = Dict[str, object]

# Matches the repr format you are seeing:
# "<ValueSizeConstraint object, consts 8, 8>"
_SIZE_RE = re.compile(r"ValueSizeConstraint object, consts (\d+), (\d+)")
_RANGE_RE = re.compile(r"ValueRangeConstraint object, consts ([-\d]+), ([-\d]+)")
_SINGLE_RE = re.compile(r"SingleValueConstraint object, consts ([\d,\s-]+)")


# Common ASN.1 base types you care about.
# We use these names to infer base types from class inheritance.
ASN1_BASE_TYPE_NAMES: set[str] = {
    "ObjectIdentifier",
    "OctetString",
    "Integer",
    "Integer32",
    "Unsigned32",
    "Counter32",
    "Counter64",
    "Gauge32",
    "TimeTicks",
    "IpAddress",
    "Bits",
    "Opaque",
}


class HasGetSyntax(Protocol):
    def getSyntax(self) -> object: ...


class TypeEntry(TypedDict):
    base_type: Optional[str]
    display_hint: Optional[str]
    size: Optional[JsonDict]
    constraints: List[JsonDict]
    constraints_repr: Optional[str]
    enums: Optional[List[JsonDict]]
    used_by: List[str]


def safe_call_zero_arg(obj: object, name: str) -> Optional[object]:
    fn_obj = getattr(obj, name, None)
    if not callable(fn_obj):
        return None

    fn = cast(Callable[..., object], fn_obj)

    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None

    required = [
        p
        for p in sig.parameters.values()
        if p.default is p.empty
        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    if required:
        return None

    try:
        return fn()
    except TypeError:
        return None


def infer_base_type_from_mro(syntax: object) -> Optional[str]:
    """
    If getSyntax() does not unwrap a TEXTUAL-CONVENTION, infer the underlying
    ASN.1 base type from the class MRO.

    Example compiled MIB:
      class ProductID(TextualConvention, ObjectIdentifier): ...
    """
    cls = type(syntax)
    for base in cls.__mro__[1:]:
        name = base.__name__
        if name in ASN1_BASE_TYPE_NAMES:
            return name
    return None


def unwrap_syntax(syntax: object) -> Tuple[str, str, object]:
    """
    Returns:
      (syntax_type_name, base_type_name, base_syntax_obj)

    - If syntax.getSyntax() exists and returns something, use that as base.
    - Otherwise infer base type from class inheritance (MRO).
    """
    syntax_type = syntax.__class__.__name__

    base_obj = safe_call_zero_arg(syntax, "getSyntax")
    if base_obj is not None:
        return syntax_type, base_obj.__class__.__name__, base_obj

    inferred = infer_base_type_from_mro(syntax)
    if inferred is not None:
        return syntax_type, inferred, syntax

    return syntax_type, syntax_type, syntax


def extract_display_hint(syntax: object) -> Optional[str]:
    hint = safe_call_zero_arg(syntax, "getDisplayHint")
    if hint is not None:
        text = str(hint).strip()
        return text or None

    for candidate in (
        getattr(syntax, "displayHint", None),
        getattr(type(syntax), "displayHint", None),
    ):
        if isinstance(candidate, str):
            text = candidate.strip()
            if text:
                return text

    return None


def extract_enums_list(syntax: object) -> Optional[List[JsonDict]]:
    """
    Return enums as a numerically ordered list:
      [{"value": 1, "name": "true"}, {"value": 2, "name": "false"}]
    """
    candidates = (
        getattr(syntax, "namedValues", None),
        getattr(type(syntax), "namedValues", None),
    )

    for candidate in candidates:
        if candidate is None:
            continue

        items = getattr(candidate, "items", None)
        if not callable(items):
            continue

        try:
            pairs = cast(Sequence[Tuple[object, object]], items())
        except Exception:
            continue

        rows: List[JsonDict] = []
        for name, value in pairs:
            if isinstance(name, str) and isinstance(value, int):
                rows.append({"value": value, "name": name})

        if rows:
            rows.sort(key=lambda r: cast(int, r["value"]))
            return rows

    return None


def parse_constraints_from_repr(subtype_repr: str) -> Tuple[Optional[JsonDict], List[JsonDict]]:
    """
    Parse repr(subtypeSpec) strings like:
      "<ConstraintsIntersection object, consts <ValueSizeConstraint object, consts 8, 8>, ...>"

    Returns:
      size:
        - {"type":"range","min":a,"max":b} for continuous size ranges
        - {"type":"set","allowed":[...]} for exact allowed sizes (8 or 11)
        - {"type":"union","ranges":[...]} if we cannot safely collapse

      constraints: structured constraint dicts (no raw repr here)
    """
    constraints: List[JsonDict] = []

    size_ranges: List[Tuple[int, int]] = []
    exact_sizes: List[int] = []

    for m in _SIZE_RE.finditer(subtype_repr):
        c_min = int(m.group(1))
        c_max = int(m.group(2))
        constraints.append({"type": "ValueSizeConstraint", "min": c_min, "max": c_max})
        size_ranges.append((c_min, c_max))
        if c_min == c_max:
            exact_sizes.append(c_min)

    for m in _RANGE_RE.finditer(subtype_repr):
        c_min = int(m.group(1))
        c_max = int(m.group(2))
        constraints.append({"type": "ValueRangeConstraint", "min": c_min, "max": c_max})

    for m in _SINGLE_RE.finditer(subtype_repr):
        raw = m.group(1)
        vals = [int(x.strip()) for x in raw.split(",") if x.strip()]
        constraints.append({"type": "SingleValueConstraint", "values": vals})

    # Deduplicate exact duplicates
    seen: set[Tuple[object, ...]] = set()
    deduped: List[JsonDict] = []
    for c in constraints:
        key: Tuple[object, ...] = (
            c.get("type"),
            c.get("min"),
            c.get("max"),
            tuple(cast(List[int], c.get("values", []))) if "values" in c else None,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    size: Optional[JsonDict] = None

    # Exact sizes imply a set (DateAndTime: 8 or 11)
    if exact_sizes:
        size = {"type": "set", "allowed": sorted(set(exact_sizes))}
        return size, deduped

    # Otherwise try to compute an intersection range
    if size_ranges:
        mins = [mn for mn, _ in size_ranges]
        maxs = [mx for _, mx in size_ranges]
        eff_min = max(mins) if mins else 0
        eff_max = min(maxs) if maxs else 0

        if eff_min <= eff_max:
            size = {"type": "range", "min": eff_min, "max": eff_max}
        else:
            size = {"type": "union", "ranges": [{"min": mn, "max": mx} for mn, mx in size_ranges]}

    return size, deduped


def extract_constraints(syntax: object) -> Tuple[Optional[JsonDict], List[JsonDict], Optional[str]]:
    """
    Returns:
      (size, constraints, constraints_repr)

    - constraints: structured only
    - constraints_repr: raw repr(subtypeSpec) for debugging (or None)
    """
    subtype_spec = getattr(syntax, "subtypeSpec", None)
    if subtype_spec is None:
        return None, [], None

    repr_text = repr(subtype_spec)
    size, constraints = parse_constraints_from_repr(repr_text)

    constraints_repr: Optional[str] = None
    empty_markers = {
        "<ConstraintsIntersection object>",
        "<ConstraintsIntersection object, consts >",
    }
    if constraints and repr_text not in empty_markers:
        constraints_repr = repr_text

    return size, constraints, constraints_repr


def _filter_constraints_by_size(
    size: Optional[JsonDict],
    constraints: List[JsonDict],
) -> List[JsonDict]:
    if size is None:
        return constraints

    size_type = size.get("type")
    if size_type == "range":
        s_min = size.get("min")
        s_max = size.get("max")
        if not isinstance(s_min, int) or not isinstance(s_max, int):
            return constraints

        filtered: List[JsonDict] = []
        for c in constraints:
            if c.get("type") != "ValueSizeConstraint":
                filtered.append(c)
                continue
            c_min = c.get("min")
            c_max = c.get("max")
            if c_min == s_min and c_max == s_max:
                filtered.append(c)
        return filtered

    if size_type == "set":
        allowed = size.get("allowed")
        if not isinstance(allowed, list) or not all(isinstance(x, int) for x in allowed):
            return constraints

        allowed_set = set(cast(List[int], allowed))
        filtered = []
        for c in constraints:
            if c.get("type") != "ValueSizeConstraint":
                filtered.append(c)
                continue
            c_min = c.get("min")
            c_max = c.get("max")
            if isinstance(c_min, int) and c_min == c_max and c_min in allowed_set:
                filtered.append(c)
        return filtered

    return constraints


def _compact_single_value_constraints_if_enums_present(
    constraints: List[JsonDict],
    enums: Optional[List[JsonDict]],
) -> List[JsonDict]:
    if not enums:
        return constraints

    out: List[JsonDict] = []
    for c in constraints:
        if c.get("type") != "SingleValueConstraint":
            out.append(c)
            continue

        values = c.get("values")
        if isinstance(values, list):
            out.append({"type": "SingleValueConstraint", "count": len(values)})
        else:
            out.append({"type": "SingleValueConstraint"})
    return out


def _is_textual_convention_symbol(sym_obj: object) -> bool:
    """
    Compiled MIB textual conventions appear in mibSymbols as classes
    (eg class DisplayString(TextualConvention, OctetString): ...)

    OBJECT-TYPEs appear as instances (eg MibScalar/MibTableColumn/etc).
    """
    if not inspect.isclass(sym_obj):
        return False

    try:
        # TextualConvention is not in pysnmp.proto.rfc1902, it's defined in compiled MIBs.
        # Check if 'TextualConvention' appears in the class's MRO by name.
        cls = cast(type, sym_obj)
        return any(base.__name__ == 'TextualConvention' for base in cls.__mro__)
    except (TypeError, AttributeError):
        return False


def _canonicalise_constraints(
    size: Optional[JsonDict],
    constraints: List[JsonDict],
    enums: Optional[List[JsonDict]],
    constraints_repr: Optional[str],
    *,
    drop_repr: bool,
) -> Tuple[Optional[JsonDict], List[JsonDict], Optional[str]]:
    """
    Applies your post-processing rules and drops constraints_repr if it could
    be misleading relative to the structured constraints.
    """
    raw_constraints = list(constraints)

    constraints = _compact_single_value_constraints_if_enums_present(constraints, enums)
    constraints = _filter_constraints_by_size(size, constraints)

    if drop_repr:
        constraints_repr = None
    elif constraints != raw_constraints:
        # If we changed constraints, the raw PySNMP repr can now be misleading
        constraints_repr = None

    return size, constraints, constraints_repr


def _seed_base_types() -> Dict[str, TypeEntry]:
    """
    Create canonical entries for ASN.1 base types so later OBJECT-TYPE instances
    cannot accidentally tighten them (eg sysServices constraining Integer32 to 0..127).
    """
    seeded: Dict[str, TypeEntry] = {}
    for name in sorted(ASN1_BASE_TYPE_NAMES):
        ctor = getattr(_rfc1902, name, None)
        if ctor is None or not callable(ctor):
            continue
        try:
            syntax_obj = ctor()
        except Exception:
            continue

        size, constraints, constraints_repr = extract_constraints(syntax_obj)

        size, constraints, constraints_repr = _canonicalise_constraints(
            size=size,
            constraints=constraints,
            enums=None,
            constraints_repr=constraints_repr,
            drop_repr=True,  # always drop repr for seeded base types
        )

        seeded[name] = {
            "base_type": None,
            "display_hint": None,
            "size": size,
            "constraints": constraints,
            "constraints_repr": constraints_repr,
            "enums": None,
            "used_by": [],
        }

    return seeded


def _has_single_value_constraint(constraints: List[JsonDict]) -> bool:
    for c in constraints:
        if c.get("type") == "SingleValueConstraint":
            return True
    return False


def _is_value_range_constraint(c: JsonDict) -> bool:
    return c.get("type") == "ValueRangeConstraint"


def _drop_dominated_value_ranges(constraints: List[JsonDict]) -> List[JsonDict]:
    ranges: List[Tuple[int, int]] = []
    for c in constraints:
        if _is_value_range_constraint(c):
            min_val = c["min"]
            max_val = c["max"]
            if isinstance(min_val, int) and isinstance(max_val, int):
                ranges.append((min_val, max_val))
            else:
                ranges.append((int(str(min_val)), int(str(max_val))))
    if len(ranges) < 2:
        return constraints
    dominated: set[Tuple[int, int]] = set()
    for a_min, a_max in ranges:
        for b_min, b_max in ranges:
            if (a_min, a_max) == (b_min, b_max):
                continue
            if a_min <= b_min and a_max >= b_max:
                dominated.add((a_min, a_max))
    if not dominated:
        return constraints
    out: List[JsonDict] = []
    for c in constraints:
        if _is_value_range_constraint(c):
            min_val = c["min"]
            max_val = c["max"]
            if isinstance(min_val, int) and isinstance(max_val, int):
                rng = (min_val, max_val)
            else:
                rng = (int(str(min_val)), int(str(max_val)))
            if rng in dominated:
                continue
        out.append(c)
    return out


def _drop_redundant_base_value_range(
    base_type: Optional[str],
    constraints: List[JsonDict],
    types: Mapping[str, TypeEntry],
) -> List[JsonDict]:
    """
    Drop inherited ValueRangeConstraint if a stricter range exists in constraints.
    Only applies if base_type is known and both have ValueRangeConstraint.
    """
    if base_type is None:
        return constraints
    base_entry = types.get(base_type)
    if not base_entry:
        return constraints
    base_ranges = [
        (
            c["min"] if isinstance(c["min"], int) else int(str(c["min"])),
            c["max"] if isinstance(c["max"], int) else int(str(c["max"]))
        )
        for c in base_entry.get("constraints", [])
        if c.get("type") == "ValueRangeConstraint"
    ]
    if not base_ranges:
        return constraints
    # Find all ValueRangeConstraint in constraints
    value_ranges = [
        (
            c["min"] if isinstance(c["min"], int) else int(str(c["min"])),
            c["max"] if isinstance(c["max"], int) else int(str(c["max"]))
        )
        for c in constraints
        if c.get("type") == "ValueRangeConstraint"
    ]
    # If any range in constraints is strictly tighter than a base range, drop the base range
    out = []
    for c in constraints:
        if c.get("type") == "ValueRangeConstraint":
            min_val = c["min"]
            max_val = c["max"]
            if isinstance(min_val, int) and isinstance(max_val, int):
                rng = (min_val, max_val)
            else:
                rng = (int(str(min_val)), int(str(max_val)))
            # If this is a base range and a tighter range exists, drop it
            if rng in base_ranges and any(
                (rng != other and other[0] >= rng[0] and other[1] <= rng[1])
                for other in value_ranges
            ):
                continue
        out.append(c)
    return out


def _drop_redundant_base_range_for_enums(
    base_type: Optional[str],
    constraints: List[JsonDict],
    enums: Optional[List[JsonDict]],
    types: Mapping[str, TypeEntry],
) -> List[JsonDict]:
    if base_type is None:
        return constraints
    if not enums and not _has_single_value_constraint(constraints):
        return constraints
    base_entry = types.get(base_type)
    if not base_entry:
        return constraints
    base_ranges = {
        (
            c["min"] if isinstance(c["min"], int) else int(str(c["min"])),
            c["max"] if isinstance(c["max"], int) else int(str(c["max"]))
        )
        for c in base_entry.get("constraints", [])
        if _is_value_range_constraint(c)
    }
    if not base_ranges:
        return constraints
    out = []
    for c in constraints:
        if _is_value_range_constraint(c):
            min_val = c["min"]
            max_val = c["max"]
            if isinstance(min_val, int) and isinstance(max_val, int):
                rng = (min_val, max_val)
            else:
                rng = (int(str(min_val)), int(str(max_val)))
            if rng in base_ranges:
                continue
        out.append(c)
    return out


def build_index(compiled_dir: Path) -> Dict[str, TypeEntry]:
    # Seed base types first (canonical constraints)
    types: Dict[str, TypeEntry] = _seed_base_types()

    snmp_engine = cast(Any, _engine.SnmpEngine())
    mib_builder = cast(Any, snmp_engine.get_mib_builder())
    mib_builder.add_mib_sources(_builder.DirMibSource(str(compiled_dir)))

    for path in compiled_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        try:
            mib_builder.load_modules(path.stem)
        except Exception:
            continue

    mib_symbols = cast(Mapping[str, Mapping[str, object]], mib_builder.mibSymbols)

    for mib_name, symbols in mib_symbols.items():
        for sym_name, sym_obj in symbols.items():
            if not hasattr(sym_obj, "getSyntax"):
                continue

            snmp_obj = cast(HasGetSyntax, sym_obj)
            try:
                syntax = snmp_obj.getSyntax()
            except Exception:
                continue

            if syntax is None:
                continue

            t_name, base_type_raw, base_obj = unwrap_syntax(syntax)

            base_type_out: Optional[str] = None if base_type_raw == t_name else base_type_raw

            is_tc_def = _is_textual_convention_symbol(sym_obj)
            is_base_type = t_name in ASN1_BASE_TYPE_NAMES

            # Critical rule:
            # If this is an OBJECT-TYPE (not a TC definition) and its syntax class is a base type,
            # do not apply size/constraints/display/enums to the base type entry.
            allow_metadata = is_tc_def or not is_base_type

            display: Optional[str]
            enums: Optional[List[JsonDict]]
            size: Optional[JsonDict]
            constraints: List[JsonDict]
            constraints_repr: Optional[str]

            if not allow_metadata:
                display = None
                enums = None
                size = None
                constraints = []
                constraints_repr = None
            else:
                if base_type_out is None:
                    display = None
                    enums = None
                    size, constraints, constraints_repr = extract_constraints(syntax)
                else:
                    display = extract_display_hint(syntax)

                    size, constraints, constraints_repr = extract_constraints(syntax)
                    if base_obj is not syntax:
                        size2, constraints2, repr2 = extract_constraints(base_obj)
                        if not constraints and constraints2:
                            size, constraints, constraints_repr = size2, constraints2, repr2

                    enums = extract_enums_list(syntax)
                    if enums is None and base_obj is not syntax:
                        enums = extract_enums_list(base_obj)

                # If this is a derived type (base_type_out is not None), drop constraints_repr.
                # Also drop it if our filtering/compaction changes the structured constraints.
                size, constraints, constraints_repr = _canonicalise_constraints(
                    size=size,
                    constraints=constraints,
                    enums=enums,
                    constraints_repr=constraints_repr,
                    drop_repr=(base_type_out is not None),
                )

            # Clean up duplicated / redundant range constraints on derived types
            if base_type_out is not None and constraints:
                constraints = _drop_redundant_base_value_range(
                    base_type=base_type_out,
                    constraints=constraints,
                    types=types,
                )
                constraints = _drop_dominated_value_ranges(constraints)
                if base_type_out is not None:
                    constraints = _drop_redundant_base_range_for_enums(
                        base_type=base_type_out,
                        constraints=constraints,
                        enums=enums,
                        types=types,
                    )

            entry = types.setdefault(
                t_name,
                {
                    "base_type": base_type_out,
                    "display_hint": display,
                    "size": size,
                    "constraints": constraints,
                    "constraints_repr": constraints_repr,
                    "enums": enums,
                    "used_by": [],
                },
            )

            if allow_metadata:
                if entry["display_hint"] is None and display is not None:
                    entry["display_hint"] = display
                if entry["size"] is None and size is not None:
                    entry["size"] = size
                if entry["enums"] is None and enums is not None:
                    entry["enums"] = enums

                if entry["constraints_repr"] is None and constraints_repr is not None:
                    entry["constraints_repr"] = constraints_repr
                if not entry["constraints"] and constraints:
                    entry["constraints"] = constraints

            entry["used_by"].append(f"{mib_name}::{sym_name}")

    return types


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("compiled_dir", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("types.json"))
    args = parser.parse_args()

    result = build_index(args.compiled_dir)

    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(f"Wrote {len(result)} types to {args.output}")


if __name__ == "__main__":
    main()