# SNMP Row Creation and SET Semantics
## Why Certain Objects Break Table Creation

This document explains **why some standard SNMP object types cause SET failures during row creation**, even when the MIB appears correct, and how to design SNMP agents that behave correctly.

It applies to agents written in any language, including pysnmp.

---

## 1. Core SNMP Principle

SNMP SET operations are **atomic and stateful**.

A SET PDU is processed in two logical phases:

1. **Validation (check phase)**
   - All varbinds are checked
   - No state is modified
   - Object instances must exist or be creatable
   - All semantic constraints must already be satisfiable

2. **Commit phase**
   - Changes are applied atomically
   - Only occurs if validation succeeds for all varbinds

If any varbind fails validation, **the entire SET fails**.

This behaviour is defined in SNMPv2 and later and is not optional.

---

## 2. Textual Conventions Do Not Define Creation Behaviour

A **Textual Convention (TC)** defines:
- syntax
- semantic meaning *if the object exists*

A TC does **not** define:
- instance creation
- default values
- row creation semantics
- transaction ordering

Therefore, any TC that assumes a "current value" implicitly assumes that the instance already exists.

---

## 3. TestAndIncr: Why It Fails During Creation

`TestAndIncr` is defined in RFC 2579 (SNMPv2-TC) as a spin lock.

Its semantics require:
- an existing instance
- a current stored value

If a manager SETs a value that does not equal the current value, the agent must return `inconsistentValue`.

During row creation:
- the instance does not yet exist
- there is no current value to compare against

Therefore, during validation, the agent **must reject the SET**.

This behaviour is required by SNMP transaction semantics, not by the TC itself.

### Rule
Never SET a `TestAndIncr` column as part of an atomic batch row creation SET.

Note: Individual (sequential) writes may succeed depending on implementation - see Section 7.1.

---

## 4. Other Standard Patterns That Break Creation

The following object types and patterns commonly cause SET failures during row creation.

### 4.1 RowStatus

`RowStatus` defines a state machine.

Common failure cases:
- Setting non-index columns before `createAndWait`
- Using `createAndGo` without mandatory columns
- Illegal state transitions during validation

RowStatus both enables creation and enforces strict ordering.

---

### 4.2 Cross Column Constraints

Examples:
- length fields matching another column
- enable flags requiring other columns to be present
- mode selectors constraining sibling columns

During creation, these constraints cannot yet be satisfied, so validation fails.

---

### 4.3 Index Dependent Semantics

Some tables derive internal state from index values.

Examples:
- MAC address indexed tables
- VLAN or interface indexed tables
- Tables where the index implies size or type

Validation may assume derived state already exists and reject the SET.

---

### 4.4 Monotonic or History Dependent Objects

Examples:
- writable gauges that must not decrease
- objects enforcing rate limits
- values constrained by previous values

During creation there is no prior value, so validation fails.

---

### 4.5 Auto Populated or Agent Owned Objects

Some agents populate values automatically during row creation.

If a manager tries to SET these values during creation:
- the agent may treat them as read-only
- validation fails

---

### 4.6 External Resource Mappings

Examples:
- rows representing OS users, files, interfaces, sockets
- rows mapping to hardware or kernel objects

Validation may check external state that does not yet exist.

---

## 5. Design Rule That Always Works

Any column that:
- depends on an existing value
- depends on another column
- enforces semantic invariants
- coordinates concurrency
- reflects external state

**must not be included in the creation SET.**

---

## 6. Correct Row Creation Pattern

### Phase 1: Create the Row
- Set index values
- Set RowStatus to `createAndWait` or `createAndGo`
- Initialise internal state in the agent
- Create instances for all columns, including lock columns

### Phase 2: Modify the Row
- GET current values as needed
- Use `TestAndIncr` or other locks
- SET remaining writable columns

This is not a workaround. It is the intended SNMP usage model.

---

## 7. Agent Side Recommendation (pysnmp or otherwise)

When creating a row:
- Explicitly initialise all column instances
- Assign valid default values
- Ensure `TestAndIncr` instances exist before they are used

This ensures subsequent SET operations behave predictably.

---

## 7.1 pysnmp Implementation Note

In pysnmp's agent-side implementation, **batch writes** and **individual writes** behave differently:

### Batch Writes (Atomic)

```python
mibInstrumentation.write_variables(*all_columns)
```

- All varbinds are validated together before any commit
- TestAndIncr validation fails because no instance exists yet
- The entire SET fails with `WrongValueError`

### Individual Writes (Sequential)

```python
for oid, value in columns:
    mibInstrumentation.write_variables((oid, value))
```

- Each varbind is validated and committed separately
- First write creates the instance with an initial value
- Subsequent writes (including TestAndIncr) succeed because the instance now exists

### Practical Implication

For tables containing `TestAndIncr` columns:

1. **Batch writes will fail** - this is expected and standards-compliant
2. **Individual writes succeed** - each column is created sequentially
3. The fallback from batch to individual writes is correct behaviour, not an error

The `(individual writes)` message in agent output indicates this fallback occurred and is informational, not a warning.

---

## 8. Mental Model

Row creation establishes **existence**.

Objects like `TestAndIncr` coordinate **modification**, not creation.

If an object needs a past, it cannot exist in the present.

---

## 9. Summary

- Textual Conventions do not define creation behaviour
- SNMP SET validation is atomic and stateful
- Some standard object semantics inherently break creation
- Two phase row creation is correct and expected
- Observed failures are standards compliant

Once these rules are followed, SNMP agents behave consistently across implementations.