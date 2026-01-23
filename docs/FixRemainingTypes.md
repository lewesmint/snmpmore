GOAL
----
Clean up redundant "base type" constraints in the generated JSON so that TEXTUAL-CONVENTION (TC) types do not carry pointless inherited constraints when the base_type is already known and the TC adds stricter or more specific constraints.

There are two cleanups we want:

A) Drop redundant inherited ValueRangeConstraint ranges when a stricter range exists.
   Example (before):
     base_type=Integer32
     constraints: [-2147483648..2147483647, 0..2147483647]
   Example (after):
     constraints: [0..2147483647]

B) Drop redundant inherited "full Integer32 range" when the TC is effectively an enum (SingleValueConstraint + enums).
   Example (before):
     base_type=Integer32
     constraints: [-2147483648..2147483647, SingleValueConstraint(count=7)]
   Example (after):
     constraints: [SingleValueConstraint(count=7)]
   Rationale: the enum constraint already implies the valid values, and the base range is not useful noise.

WHERE TO CHANGE
---------------
File: the script that builds types.json (the one you pasted, with build_index()).

You already have helper(s) for (A):
  - _drop_redundant_base_value_range()

But it is not currently being applied in build_index(), and it does not cover enum cases (B).

IMPLEMENTATION PLAN
-------------------
1) Apply cleanup (A) to derived types only.
   That means: if base_type_out is not None, post-process constraints.

2) Add cleanup (B) for enum-like derived types.
   If enums exist OR you have a SingleValueConstraint (count or values),
   then remove the inherited base ValueRangeConstraint IF it exactly matches
   the base_type's ValueRangeConstraint.

3) Also do a small "range dominance" clean up:
   If multiple ValueRangeConstraint entries exist, remove any that is a superset
   of another. This will also fix things like:
     0..2147483647 AND 1..2147483647  -> keep only 1..2147483647
   This is independent of base_type and should be safe.

DETAILED STEPS
--------------
Step 1: Add a helper to detect SingleValueConstraint presence.

  def _has_single_value_constraint(constraints: List[JsonDict]) -> bool:
      for c in constraints:
          if c.get("type") == "SingleValueConstraint":
              return True
      return False

Step 2: Add a helper to drop dominated ranges (keep only the tightest ones).

  def _drop_dominated_value_ranges(constraints: List[JsonDict]) -> List[JsonDict]:
      ranges: List[Tuple[int, int]] = []
      for c in constraints:
          if _is_value_range_constraint(c):
              ranges.append((int(c["min"]), int(c["max"])))

      if len(ranges) < 2:
          return constraints

      # A range A dominates B if A is a strict superset of B.
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
              rng = (int(c["min"]), int(c["max"]))
              if rng in dominated:
                  continue
          out.append(c)
      return out

This will turn:
  [0..2147483647, 1..2147483647] -> [1..2147483647]
and also:
  [base_range, tighter_range] -> [tighter_range]
even before the base_type logic kicks in.

Step 3: Add a helper for enum clean up (B).

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
          (int(c["min"]), int(c["max"]))
          for c in base_entry.get("constraints", [])
          if _is_value_range_constraint(c)
      }
      if not base_ranges:
          return constraints

      out: List[JsonDict] = []
      for c in constraints:
          if _is_value_range_constraint(c):
              rng = (int(c["min"]), int(c["max"]))
              if rng in base_ranges:
                  # drop inherited base range when we have enums/single-value constraint
                  continue
          out.append(c)
      return out

Step 4: Wire these into the existing build_index() flow.

Right now you do:
  - extract_constraints(...)
  - _canonicalise_constraints(...)
  - create/update entry

Insert extra post-processing AFTER _canonicalise_constraints() and ONLY for derived types.

In build_index(), inside the "allow_metadata" branch, after:
  size, constraints, constraints_repr = _canonicalise_constraints(...)

Add:
  constraints = _drop_dominated_value_ranges(constraints)

  if base_type_out is not None:
      constraints = _drop_redundant_base_value_range(
          base_type=base_type_out,
          constraints=constraints,
          types=types,
      )

      constraints = _drop_redundant_base_range_for_enums(
          base_type=base_type_out,
          constraints=constraints,
          enums=enums,
          types=types,
      )

Notes:
- Call _drop_dominated_value_ranges() first so you simplify obvious supersets regardless.
- Then apply base_type specific removal.
- Then apply enum specific base-range removal.
- Keep constraints_repr as None for derived types as you already do.

EXPECTED OUTPUT CHANGES
-----------------------
You should see these improvements:

1) Stricter range wins:
   SnmpSecurityModel goes from:
     [0..2147483647, 1..2147483647]
   to:
     [1..2147483647]

2) Enum-like TCs drop inherited base range:
   RowStatus from:
     [-2147483648..2147483647, SingleValueConstraint(count=7)]
   to:
     [SingleValueConstraint(count=7)]

   TruthValue from:
     [-2147483648..2147483647, SingleValueConstraint(count=2)]
   to:
     [SingleValueConstraint(count=2)]

   IANAifType from:
     [-2147483648..2147483647, SingleValueConstraint(count=299)]
   to:
     [SingleValueConstraint(count=299)]

3) Non-enum derived types keep meaningful ranges:
   TestAndIncr stays:
     [0..2147483647]
   DisplayString keeps size constraint, no range constraints.

SAFETY / CORRECTNESS NOTES
--------------------------
- We are NOT dropping constraints if base_type is unknown.
- We are NOT dropping a TC range that differs from the base.
- For enums, we only drop the inherited base range if it exactly matches the base type range.
- Dropping dominated ranges is safe because the remaining constraints are at least as strict.

TESTING CHECKLIST
-----------------
1) Generate types.json before and after, diff only constraints sections.
2) Confirm:
   - All base ASN.1 types (Integer32, Counter32 etc) remain unchanged.
   - Derived non-enum ranges still present (TestAndIncr, KBytes, TimeInterval).
   - Enum derived types no longer include the redundant full Integer32 range.
   - SnmpSecurityModel only has 1..2147483647.
3) Spot check a few objects that use those types to ensure no consumer logic breaks.

DONE
----
Once these helper functions are added and wired into build_index(), rerun the generator and validate the JSON diff.