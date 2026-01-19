# Mock Behavior Files

This directory contains **behavior definition files** for SNMP MIBs. These JSON files are automatically generated from compiled MIB files and define the structure and initial behavior of MIB objects.

## What Are These Files?

These JSON files are the output of the `mib_to_json.py` script, which extracts metadata from compiled MIB files (`.py` files in `compiled-mibs/`) and generates a structured JSON representation that can be used to:

1. **Mock SNMP agent behavior** - Provide initial values and behavior for MIB objects
2. **Configure dynamic behavior** - Define which objects should have dynamic values
3. **Simplify agent implementation** - Allow the SNMP agent to be data-driven rather than hard-coded

## File Structure

Each behavior JSON file contains entries for MIB objects with the following structure:

```json
{
  "objectName": {
    "oid": [1, 3, 6, 1, 4, 1, 99999, 1],
    "type": "DisplayString",
    "access": "read-only",
    "initial": null,
    "dynamic_function": null
  }
}
```

### Fields Explained

- **`oid`**: The Object Identifier as an array of integers
- **`type`**: The SNMP data type (e.g., `DisplayString`, `Integer32`, `Counter32`)
- **`access`**: Access level (`read-only`, `read-write`, etc.)
- **`initial`**: Initial value for the object (can be customized)
- **`dynamic_function`**: Name of a function to generate dynamic values (optional)

## How to Generate

To generate a behavior file from a compiled MIB:

```bash
python mib_to_json.py compiled-mibs/MY-AGENT-MIB.py MY-AGENT-MIB
```

This will create `mock-behavior/MY-AGENT-MIB_behavior.json`.

## How These Files Are Used

The `my-pysnmp-agent.py` script loads these behavior files to automatically register MIB objects:

```python
# Load MIB behavior from JSON
with open('mock-behavior/MY-AGENT-MIB_behavior.json') as f:
    mib_json = json.load(f)

# Use the metadata to create SNMP objects
for name, info in mib_json.items():
    oid = tuple(info['oid'])
    type_class = type_map[info['type']]
    initial_value = info.get('initial')
    # ... register the object
```

## Customization

You can manually edit these JSON files to:

1. **Set initial values**: Change `"initial": null` to `"initial": "your value"`
2. **Add dynamic behavior**: Set `"dynamic_function": "function_name"` to reference a Python function
3. **Adjust metadata**: Modify type or access information if needed

## Example: MY-AGENT-MIB_behavior.json

This file defines the behavior for the demo enterprise MIB (`.1.3.6.1.4.1.99999`):

- **Scalars**: `myString`, `myCounter`, `myGauge`, etc.
- **Table**: `myTable` with columns for index, name, value, and status

## Why "Mock Behavior"?

These files provide a **mock implementation** of MIB behavior:

- They define the **structure** extracted from the MIB definition
- They provide **default/initial values** for testing
- They allow **rapid prototyping** of SNMP agents without writing extensive code
- They serve as a **template** that can be customized for specific use cases

Think of them as a bridge between the MIB definition (what objects exist) and the agent implementation (what values those objects have).

## Relationship to Other Directories

```
snmpmore/
├── data/mibs/              # Original MIB source files (.mib, .txt)
├── compiled-mibs/          # Compiled Python MIB modules (.py)
└── mock-behavior/          # Behavior definitions (JSON) ← You are here
```

**Workflow:**
1. Write MIB definition → `data/mibs/MY-AGENT-MIB.mib`
2. Compile to Python → `compiled-mibs/MY-AGENT-MIB.py`
3. Extract behavior → `mock-behavior/MY-AGENT-MIB_behavior.json`
4. Use in agent → `my-pysnmp-agent.py` loads the JSON

## Notes

- These files are **generated artifacts** - they can be regenerated from compiled MIBs
- Customizations should be documented or version-controlled
- The JSON format is designed to be human-readable and editable

